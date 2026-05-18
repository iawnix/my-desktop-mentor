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

qt_platform_can_start() {
  local platform="$1"
  QT_QPA_PLATFORM="$platform" "$PYTHON_BIN" - <<'PY' >/dev/null 2>&1
from PySide6.QtWidgets import QApplication

app = QApplication([])
app.quit()
PY
}

prefer_xcb_platform() {
  ensure_xauthority
  if [[ -z "${DISPLAY:-}" && -S /tmp/.X11-unix/X0 ]]; then
    export DISPLAY=:0
  elif [[ -z "${DISPLAY:-}" && -S /tmp/.X11-unix/X1 ]]; then
    export DISPLAY=:1
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
  "$candidate" -c "from PySide6.QtCore import Qt" >/dev/null 2>&1
}

add_candidate() {
  local candidate="$1"
  [[ -n "$candidate" ]] || return 0
  [[ -x "$candidate" ]] || return 0
  CANDIDATES+=("$candidate")
}

if [[ -n "${DESKTOP_MENTOR_PYTHON:-}" ]]; then
  if python_can_run_app "$DESKTOP_MENTOR_PYTHON"; then
    PYTHON_BIN="$DESKTOP_MENTOR_PYTHON"
  else
    die "DESKTOP_MENTOR_PYTHON cannot import PySide6.QtCore: $DESKTOP_MENTOR_PYTHON"
  fi
else
  CANDIDATES=()
  add_candidate "$ROOT_DIR/.venv/bin/python"
  if [[ -n "${CONDA_PREFIX:-}" ]]; then
    add_candidate "$CONDA_PREFIX/bin/python"
  fi
  if command -v python3 >/dev/null 2>&1; then
    add_candidate "$(command -v python3)"
  fi
  if command -v python >/dev/null 2>&1; then
    add_candidate "$(command -v python)"
  fi
  for candidate in "$HOME"/soft/conda/*/bin/python3 "$HOME"/miniconda*/bin/python "$HOME"/anaconda*/bin/python; do
    add_candidate "$candidate"
  done

  for candidate in "${CANDIDATES[@]}"; do
    if python_can_run_app "$candidate"; then
      PYTHON_BIN="$candidate"
      break
    fi
  done
fi

if [[ -z "${PYTHON_BIN:-}" ]]; then
  printf '[desktop-mentor] No Python interpreter with PySide6.QtCore was found.\n' >&2
  printf '[desktop-mentor] Tried:\n' >&2
  for candidate in "${ATTEMPTED[@]}"; do
    printf '  - %s\n' "$candidate" >&2
  done
  printf '[desktop-mentor] Set DESKTOP_MENTOR_PYTHON=/path/to/python or install PySide6.\n' >&2
  exit 1
fi

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
print(f"[desktop-mentor] QT_QPA_PLATFORM: {os.environ.get('QT_QPA_PLATFORM', '')}", file=sys.stderr)
print(f"[desktop-mentor] DISPLAY: {os.environ.get('DISPLAY', '')}", file=sys.stderr)
print(f"[desktop-mentor] WAYLAND_DISPLAY: {os.environ.get('WAYLAND_DISPLAY', '')}", file=sys.stderr)
print(f"[desktop-mentor] XDG_RUNTIME_DIR: {os.environ.get('XDG_RUNTIME_DIR', '')}", file=sys.stderr)
print(f"[desktop-mentor] XAUTHORITY: {os.environ.get('XAUTHORITY', '')}", file=sys.stderr)
PY
fi

exec "$PYTHON_BIN" desktop_mentor.py "$@"
