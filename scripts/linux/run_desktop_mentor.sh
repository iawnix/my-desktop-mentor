#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT_DIR="$(cd "$SCRIPT_DIR/../.." && pwd)"
cd "$ROOT_DIR"

DIAG="${DESKTOP_MENTOR_DIAG:-0}"
ARGS=()
for arg in "$@"; do
  if [[ "$arg" == "--diagnose" ]]; then
    DIAG=1
  else
    ARGS+=("$arg")
  fi
done
set -- "${ARGS[@]}"

log() {
  if [[ "$DIAG" == "1" || "$DIAG" == "true" || "$DIAG" == "yes" ]]; then
    printf '[desktop-mentor] %s\n' "$*" >&2
  fi
}

die() {
  printf '[desktop-mentor] %s\n' "$*" >&2
  exit 1
}

ensure_xauthority() {
  if [[ -n "${XAUTHORITY:-}" ]]; then
    return 0
  fi
  for auth_file in /run/user/1000/.mutter-Xwaylandauth.*; do
    if [[ -f "$auth_file" ]]; then
      export XAUTHORITY="$auth_file"
      break
    fi
  done
}

ensure_session_bus() {
  if [[ -z "${XDG_RUNTIME_DIR:-}" && -d "/run/user/$(id -u)" ]]; then
    export XDG_RUNTIME_DIR="/run/user/$(id -u)"
  fi
  if [[ -z "${DBUS_SESSION_BUS_ADDRESS:-}" && -n "${XDG_RUNTIME_DIR:-}" && -S "$XDG_RUNTIME_DIR/bus" ]]; then
    export DBUS_SESSION_BUS_ADDRESS="unix:path=$XDG_RUNTIME_DIR/bus"
  fi
}

preferred_x11_display() {
  local socket uid socket_uid
  uid="$(id -u)"
  for socket in /tmp/.X11-unix/X*; do
    [[ -S "$socket" ]] || continue
    socket_uid="$(stat -c '%u' "$socket" 2>/dev/null || true)"
    if [[ "$socket_uid" == "$uid" ]]; then
      printf ':%s\n' "${socket##*/X}"
      return 0
    fi
  done
  for socket in /tmp/.X11-unix/X*; do
    [[ -S "$socket" ]] || continue
    printf ':%s\n' "${socket##*/X}"
    return 0
  done
  return 1
}

qt_platform_can_start() {
  local platform="$1"
  (
    QT_QPA_PLATFORM="$platform" "$PYTHON_BIN" - <<'PY'
from PySide6.QtWidgets import QApplication

app = QApplication([])
app.quit()
PY
  ) >/dev/null 2>&1
}

configure_input_method() {
  if [[ "${DESKTOP_MENTOR_IM_MODULE:-}" == "none" || "${DESKTOP_MENTOR_IM_MODULE:-}" == "off" ]]; then
    return 0
  fi

  ensure_session_bus

  local module="${DESKTOP_MENTOR_IM_MODULE:-}"
  module="${module,,}"
  if [[ -z "$module" ]]; then
    if [[ "${QT_IM_MODULE:-}" == fcitx* || "${XMODIFIERS:-}" == *@im=fcitx* ]]; then
      module="fcitx"
    elif [[ -z "${QT_IM_MODULE:-}" ]] && command -v fcitx5 >/dev/null 2>&1; then
      module="fcitx"
    fi
  fi

  if [[ "$module" == "fcitx" || "$module" == "fcitx5" ]]; then
    if [[ -z "${QT_IM_MODULE:-}" || "${QT_IM_MODULE:-}" == "fcitx5" ]]; then
      export QT_IM_MODULE=fcitx
    fi
    if [[ -z "${XMODIFIERS:-}" || "${XMODIFIERS:-}" == "@im=fcitx5" ]]; then
      export XMODIFIERS=@im=fcitx
    fi
    export GTK_IM_MODULE="${GTK_IM_MODULE:-fcitx}"
    export SDL_IM_MODULE="${SDL_IM_MODULE:-fcitx}"
    export GLFW_IM_MODULE="${GLFW_IM_MODULE:-ibus}"
  elif [[ -n "$module" ]]; then
    if [[ -n "${DESKTOP_MENTOR_IM_MODULE:-}" || -z "${QT_IM_MODULE:-}" ]]; then
      export QT_IM_MODULE="$module"
    fi
  fi
}

prefer_xcb_platform() {
  ensure_xauthority
  if [[ -z "${DISPLAY:-}" ]]; then
    local selected_display
    selected_display="$(preferred_x11_display || true)"
    if [[ -n "$selected_display" ]]; then
      export DISPLAY="$selected_display"
    fi
  fi

  if [[ -z "${DISPLAY:-}" && ! -S /tmp/.X11-unix/X0 && ! -S /tmp/.X11-unix/X1 ]]; then
    return 1
  fi

  if qt_platform_can_start xcb; then
    export QT_QPA_PLATFORM=xcb
    return 0
  fi
  return 1
}

PYTHON_BIN=""
ATTEMPTED=()

python_can_run_app() {
  local candidate="$1"
  [[ -n "$candidate" ]] || return 1
  ATTEMPTED+=("$candidate")
  "$candidate" - <<'PY' >/dev/null 2>&1
from PySide6.QtCore import Qt
from PySide6.QtWebEngineWidgets import QWebEngineView
import latex2mathml
import markdown_it
import pygments
import qasync
PY
}

add_candidate() {
  local candidate="$1"
  [[ -n "$candidate" ]] || return 0
  [[ -x "$candidate" ]] || return 0
  CANDIDATES+=("$candidate")
}

find_conda_exe() {
  if [[ -n "${CONDA_EXE:-}" && -x "${CONDA_EXE:-}" ]]; then
    printf '%s\n' "$CONDA_EXE"
    return 0
  fi
  if command -v conda >/dev/null 2>&1; then
    command -v conda
    return 0
  fi
  for candidate in "$HOME"/soft/conda/*/bin/conda "$HOME"/miniconda*/bin/conda "$HOME"/anaconda*/bin/conda; do
    if [[ -x "$candidate" ]]; then
      printf '%s\n' "$candidate"
      return 0
    fi
  done
  return 1
}

add_conda_python_candidates() {
  local env_name env_prefix conda_exe conda_base env_root
  env_name="${DESKTOP_MENTOR_CONDA_ENV_NAME:-my-desktop-mentor}"
  env_prefix="${DESKTOP_MENTOR_CONDA_PREFIX:-}"

  if [[ -n "$env_prefix" ]]; then
    add_candidate "$env_prefix/bin/python"
  fi
  if [[ -n "${CONDA_PREFIX:-}" ]]; then
    add_candidate "$CONDA_PREFIX/bin/python"
  fi

  conda_exe="$(find_conda_exe || true)"
  if [[ -n "$conda_exe" ]]; then
    conda_base="$("$conda_exe" info --base 2>/dev/null || true)"
    if [[ -n "$conda_base" ]]; then
      add_candidate "$conda_base/envs/$env_name/bin/python"
    fi
  fi

  for env_root in "$HOME"/soft/conda/*/envs "$HOME"/miniconda*/envs "$HOME"/anaconda*/envs; do
    add_candidate "$env_root/$env_name/bin/python"
  done

  add_candidate "$ROOT_DIR/.conda/bin/python"
}

add_standard_python_candidates() {
  add_candidate "$ROOT_DIR/.venv/bin/python"
  if command -v python3 >/dev/null 2>&1; then
    add_candidate "$(command -v python3)"
  fi
  if command -v python >/dev/null 2>&1; then
    add_candidate "$(command -v python)"
  fi
  for candidate in "$HOME"/soft/conda/*/bin/python3 "$HOME"/miniconda*/bin/python "$HOME"/anaconda*/bin/python; do
    add_candidate "$candidate"
  done
}

add_system_qt_python_candidates() {
  add_candidate /usr/bin/python3
  add_candidate /usr/local/bin/python3
  add_candidate /usr/bin/python
  add_candidate /usr/local/bin/python
}

prefer_system_qt_python() {
  if [[ "${DESKTOP_MENTOR_PREFER_SYSTEM_QT:-1}" == "0" ]]; then
    return 1
  fi
  if [[ "${DESKTOP_MENTOR_IM_MODULE:-}" == "none" || "${DESKTOP_MENTOR_IM_MODULE:-}" == "off" ]]; then
    return 1
  fi
  [[ "${DESKTOP_MENTOR_IM_MODULE:-}" == fcitx* || "${QT_IM_MODULE:-}" == fcitx* || "${XMODIFIERS:-}" == *@im=fcitx* || -x /usr/bin/fcitx5 || -x /usr/local/bin/fcitx5 ]]
}

if [[ -n "${DESKTOP_MENTOR_PYTHON:-}" ]]; then
  if python_can_run_app "$DESKTOP_MENTOR_PYTHON"; then
    PYTHON_BIN="$DESKTOP_MENTOR_PYTHON"
  else
    die "DESKTOP_MENTOR_PYTHON cannot import the required Qt/Markdown dependencies: $DESKTOP_MENTOR_PYTHON"
  fi
else
  CANDIDATES=()
  add_conda_python_candidates
  if prefer_system_qt_python; then
    add_system_qt_python_candidates
  fi
  add_standard_python_candidates

  for candidate in "${CANDIDATES[@]}"; do
    if python_can_run_app "$candidate"; then
      PYTHON_BIN="$candidate"
      break
    fi
  done
fi

if [[ -z "${PYTHON_BIN:-}" ]]; then
  printf '[desktop-mentor] No Python interpreter with the required Qt/Markdown rendering dependencies was found.\n' >&2
  printf '[desktop-mentor] Tried:\n' >&2
  for candidate in "${ATTEMPTED[@]}"; do
    printf '  - %s\n' "$candidate" >&2
  done
  printf '[desktop-mentor] Create the project Conda env with: scripts/linux/setup_conda_env.sh\n' >&2
  printf '[desktop-mentor] Or set DESKTOP_MENTOR_PYTHON=/path/to/python / DESKTOP_MENTOR_CONDA_ENV_NAME=<env>.\n' >&2
  exit 1
fi

configure_input_method

if [[ "${QT_QPA_PLATFORM:-}" == "wayland" && "${DESKTOP_MENTOR_ALLOW_WAYLAND:-0}" != "1" ]]; then
  if ! prefer_xcb_platform; then
    export QT_QPA_PLATFORM=wayland
  fi
fi

if [[ -z "${QT_QPA_PLATFORM:-}" ]]; then
  if prefer_xcb_platform; then
    :
  elif [[ -S /run/user/1000/wayland-0 ]]; then
    export XDG_RUNTIME_DIR="${XDG_RUNTIME_DIR:-/run/user/1000}"
    export WAYLAND_DISPLAY="${WAYLAND_DISPLAY:-wayland-0}"
    export QT_QPA_PLATFORM=wayland
  fi
fi

if [[ "$DIAG" == "1" || "$DIAG" == "true" || "$DIAG" == "yes" ]]; then
  log "root: $ROOT_DIR"
  log "python: $PYTHON_BIN"
  "$PYTHON_BIN" - <<'PY'
import os
import sys

try:
    import PySide6
    from PySide6.QtCore import qVersion
    pyside_path = getattr(PySide6, "__file__", "")
    qt_version = qVersion()
except Exception as exc:
    pyside_path = f"unavailable: {type(exc).__name__}"
    qt_version = "unavailable"

print(f"[desktop-mentor] python version: {sys.version.split()[0]}", file=sys.stderr)
print(f"[desktop-mentor] PySide6 path: {pyside_path}", file=sys.stderr)
print(f"[desktop-mentor] Qt version: {qt_version}", file=sys.stderr)
for module_name in ("PySide6.QtWebEngineWidgets", "markdown_it", "latex2mathml", "pygments", "qasync"):
    try:
        module = __import__(module_name, fromlist=["*"])
        print(f"[desktop-mentor] {module_name}: {getattr(module, '__file__', 'built-in')}", file=sys.stderr)
    except Exception as exc:
        print(f"[desktop-mentor] {module_name}: unavailable: {type(exc).__name__}: {exc}", file=sys.stderr)
print(f"[desktop-mentor] QT_QPA_PLATFORM: {os.environ.get('QT_QPA_PLATFORM', '')}", file=sys.stderr)
print(f"[desktop-mentor] DISPLAY: {os.environ.get('DISPLAY', '')}", file=sys.stderr)
print(f"[desktop-mentor] WAYLAND_DISPLAY: {os.environ.get('WAYLAND_DISPLAY', '')}", file=sys.stderr)
print(f"[desktop-mentor] XDG_RUNTIME_DIR: {os.environ.get('XDG_RUNTIME_DIR', '')}", file=sys.stderr)
print(f"[desktop-mentor] XAUTHORITY: {os.environ.get('XAUTHORITY', '')}", file=sys.stderr)
print(f"[desktop-mentor] QT_IM_MODULE: {os.environ.get('QT_IM_MODULE', '')}", file=sys.stderr)
print(f"[desktop-mentor] XMODIFIERS: {os.environ.get('XMODIFIERS', '')}", file=sys.stderr)
print(f"[desktop-mentor] GTK_IM_MODULE: {os.environ.get('GTK_IM_MODULE', '')}", file=sys.stderr)
print(f"[desktop-mentor] DBUS_SESSION_BUS_ADDRESS: {os.environ.get('DBUS_SESSION_BUS_ADDRESS', '')}", file=sys.stderr)
try:
    from desktop_mentor_app.platforms.input_method import configure_qt_input_method_runtime, input_method_diagnostics

    configure_qt_input_method_runtime()
    diag = input_method_diagnostics()
    print(f"[desktop-mentor] fcitx5_remote: {diag.get('fcitx5_remote', '')}", file=sys.stderr)
    print(f"[desktop-mentor] fcitx_qt_plugin_files: {diag.get('fcitx_qt_plugin_files', [])}", file=sys.stderr)
    print(f"[desktop-mentor] qt_plugins_path: {diag.get('qt_plugins_path', '')}", file=sys.stderr)
    print(f"[desktop-mentor] qt_platforminputcontext_files: {diag.get('qt_platforminputcontext_files', [])}", file=sys.stderr)
    print(f"[desktop-mentor] qt_bundled_fcitx_plugin_files: {diag.get('qt_bundled_fcitx_plugin_files', [])}", file=sys.stderr)
    print(f"[desktop-mentor] compatible_fcitx_qt_plugin_roots: {diag.get('compatible_fcitx_qt_plugin_roots', [])}", file=sys.stderr)
    print(f"[desktop-mentor] fcitx_plugin_compatibility: {diag.get('fcitx_plugin_compatibility', [])}", file=sys.stderr)
    print(f"[desktop-mentor] fcitx_runtime_has_compatible_plugin: {diag.get('fcitx_runtime_has_compatible_plugin', False)}", file=sys.stderr)
    print(f"[desktop-mentor] qt_library_paths: {diag.get('qt_library_paths', [])}", file=sys.stderr)
except Exception as exc:
    print(f"[desktop-mentor] input method diagnostics unavailable: {type(exc).__name__}: {exc}", file=sys.stderr)
PY
fi

exec "$PYTHON_BIN" desktop_mentor.py "$@"
