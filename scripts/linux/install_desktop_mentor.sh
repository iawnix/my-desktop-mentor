#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT_DIR="$(cd "$SCRIPT_DIR/../.." && pwd)"
cd "$ROOT_DIR"

APP_ID="${DESKTOP_MENTOR_APP_ID:-desktop_mentor}"
CONDA_EXE_PATH="${CONDA_EXE:-}"
ENV_PREFIX="${DESKTOP_MENTOR_CONDA_PREFIX:-}"
ENV_NAME="${DESKTOP_MENTOR_CONDA_ENV_NAME:-}"
PYTHON_VERSION="${DESKTOP_MENTOR_PYTHON_VERSION:-3.12}"
APPLICATIONS_DIR="${DESKTOP_MENTOR_APPLICATIONS_DIR:-${XDG_DATA_HOME:-$HOME/.local/share}/applications}"
INPUT_METHOD="${DESKTOP_MENTOR_INPUT_METHOD:-auto}"
QT_PLATFORM="${DESKTOP_MENTOR_QT_PLATFORM:-auto}"
INSTALL_DEPS=1
INSTALL_DESKTOP=1
DRY_RUN=0

usage() {
  cat <<'EOF'
Usage: scripts/linux/install_desktop_mentor.sh [options]

Install My Desktop Mentor for the current Linux user.

Options:
  --conda PATH            Conda executable to use for environment creation
  --env-prefix PATH       Conda environment path. Default: .conda under the project root
  --env-name NAME         Named Conda environment to create/use instead of --env-prefix
  --python-version VER    Python version for a new Conda env. Default: 3.12
  --app-id NAME           Desktop file id/name. Default: desktop_mentor
  --applications-dir DIR  Desktop file install dir. Default: $XDG_DATA_HOME/applications or ~/.local/share/applications
  --input-method MODE     auto, fcitx, ibus, or none. Default: auto
  --qt-platform MODE      auto, xcb, wayland, or none. Default: auto
  --no-deps               Do not create/update the Conda env
  --no-desktop            Do not write the .desktop file
  --dry-run               Print actions without changing files
  -h, --help              Show this help

Environment overrides:
  DESKTOP_MENTOR_CONDA_PREFIX
  DESKTOP_MENTOR_CONDA_ENV_NAME
  DESKTOP_MENTOR_PYTHON_VERSION
  DESKTOP_MENTOR_APPLICATIONS_DIR
  DESKTOP_MENTOR_INPUT_METHOD
  DESKTOP_MENTOR_QT_PLATFORM
  CONDA_EXE
EOF
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --conda)
      CONDA_EXE_PATH="${2:-}"
      shift 2
      ;;
    --env-prefix)
      ENV_PREFIX="${2:-}"
      ENV_NAME=""
      shift 2
      ;;
    --env-name)
      ENV_NAME="${2:-}"
      ENV_PREFIX=""
      shift 2
      ;;
    --python-version)
      PYTHON_VERSION="${2:-}"
      shift 2
      ;;
    --app-id)
      APP_ID="${2:-}"
      shift 2
      ;;
    --applications-dir)
      APPLICATIONS_DIR="${2:-}"
      shift 2
      ;;
    --input-method)
      INPUT_METHOD="${2:-}"
      shift 2
      ;;
    --qt-platform)
      QT_PLATFORM="${2:-}"
      shift 2
      ;;
    --no-deps)
      INSTALL_DEPS=0
      shift
      ;;
    --no-desktop)
      INSTALL_DESKTOP=0
      shift
      ;;
    --dry-run)
      DRY_RUN=1
      shift
      ;;
    -h|--help)
      usage
      exit 0
      ;;
    *)
      printf '[desktop-mentor-install] unknown option: %s\n' "$1" >&2
      usage >&2
      exit 2
      ;;
  esac
done

if [[ -z "$ENV_PREFIX" && -z "$ENV_NAME" ]]; then
  ENV_PREFIX="$ROOT_DIR/.conda"
fi

if [[ -z "$PYTHON_VERSION" || -z "$APP_ID" || -z "$APPLICATIONS_DIR" ]]; then
  printf '[desktop-mentor-install] empty option value is not allowed\n' >&2
  exit 2
fi

case "$INPUT_METHOD" in
  auto|fcitx|ibus|none) ;;
  *)
    printf '[desktop-mentor-install] invalid --input-method: %s\n' "$INPUT_METHOD" >&2
    exit 2
    ;;
esac

case "$QT_PLATFORM" in
  auto|xcb|wayland|none) ;;
  *)
    printf '[desktop-mentor-install] invalid --qt-platform: %s\n' "$QT_PLATFORM" >&2
    exit 2
    ;;
esac

DESKTOP_FILE="$APPLICATIONS_DIR/$APP_ID.desktop"

log() {
  printf '[desktop-mentor-install] %s\n' "$*" >&2
}

run() {
  if [[ "$DRY_RUN" == "1" ]]; then
    printf '[desktop-mentor-install] dry-run:'
    printf ' %q' "$@"
    printf '\n'
  else
    "$@"
  fi
}

die() {
  log "$*"
  exit 1
}

find_conda_exe() {
  if [[ -n "$CONDA_EXE_PATH" && -x "$CONDA_EXE_PATH" ]]; then
    printf '%s\n' "$CONDA_EXE_PATH"
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

desktop_escape() {
  local value="$1"
  value="${value//\\/\\\\}"
  value="${value//\"/\\\"}"
  printf '%s' "$value"
}

desktop_quote() {
  printf '"%s"' "$(desktop_escape "$1")"
}

verify_runtime_imports() {
  local python_bin="$1"
  "$python_bin" - <<'PY'
from PySide6.QtCore import Qt
from PySide6.QtWebEngineWidgets import QWebEngineView
import latex2mathml
import markdown_it
import pygments
import qasync

print("desktop mentor runtime imports are ready")
PY
}

install_dependencies() {
  local conda_exe python_bin
  conda_exe="$(find_conda_exe || true)"
  [[ -n "$conda_exe" ]] || die "Conda was not found. Install Miniconda/Anaconda or set CONDA_EXE=/path/to/conda."

  if [[ -n "$ENV_NAME" ]]; then
    if "$conda_exe" run -n "$ENV_NAME" python -c 'import sys' >/dev/null 2>&1; then
      log "using existing Conda environment named $ENV_NAME"
    else
      log "creating Conda environment named $ENV_NAME"
      run "$conda_exe" create -y -n "$ENV_NAME" "python=$PYTHON_VERSION" pip
    fi
  else
    if [[ ! -x "$ENV_PREFIX/bin/python" ]]; then
      log "creating Conda environment at $ENV_PREFIX"
      run "$conda_exe" create -y -p "$ENV_PREFIX" "python=$PYTHON_VERSION" pip
    else
      log "using existing Conda environment at $ENV_PREFIX"
    fi
  fi

  if [[ "$DRY_RUN" == "1" ]]; then
    if [[ -n "$ENV_NAME" ]]; then
      log "would install requirements into Conda env $ENV_NAME"
    else
      log "would install requirements into $ENV_PREFIX"
    fi
    return 0
  fi

  log "installing Python requirements"
  if [[ -n "$ENV_NAME" ]]; then
    "$conda_exe" run -n "$ENV_NAME" python -m pip install --upgrade pip
    "$conda_exe" run -n "$ENV_NAME" python -m pip install -r "$ROOT_DIR/requirements.txt"
  else
    python_bin="$ENV_PREFIX/bin/python"
    "$python_bin" -m pip install --upgrade pip
    "$python_bin" -m pip install -r "$ROOT_DIR/requirements.txt"
  fi

  log "verifying runtime imports"
  if [[ -n "$ENV_NAME" ]]; then
    "$conda_exe" run -n "$ENV_NAME" python - <<'PY'
from PySide6.QtCore import Qt
from PySide6.QtWebEngineWidgets import QWebEngineView
import latex2mathml
import markdown_it
import pygments
import qasync

print("desktop mentor runtime imports are ready")
PY
  else
    verify_runtime_imports "$python_bin"
  fi
}

detect_input_method() {
  if [[ "$INPUT_METHOD" != "auto" ]]; then
    printf '%s\n' "$INPUT_METHOD"
    return 0
  fi
  if [[ "${DESKTOP_MENTOR_IM_MODULE:-}" == fcitx* || "${QT_IM_MODULE:-}" == fcitx* || "${XMODIFIERS:-}" == *@im=fcitx* ]]; then
    printf 'fcitx\n'
    return 0
  fi
  if command -v fcitx5-remote >/dev/null 2>&1 || command -v fcitx5 >/dev/null 2>&1 || command -v fcitx >/dev/null 2>&1; then
    printf 'fcitx\n'
    return 0
  fi
  if [[ "${DESKTOP_MENTOR_IM_MODULE:-}" == ibus || "${QT_IM_MODULE:-}" == ibus || "${XMODIFIERS:-}" == *@im=ibus* ]]; then
    printf 'ibus\n'
    return 0
  fi
  if command -v ibus >/dev/null 2>&1 || pgrep -x ibus-daemon >/dev/null 2>&1; then
    printf 'ibus\n'
    return 0
  fi
  printf 'none\n'
}

detect_qt_platform() {
  if [[ "$QT_PLATFORM" != "auto" ]]; then
    printf '%s\n' "$QT_PLATFORM"
    return 0
  fi
  if [[ -n "${QT_QPA_PLATFORM:-}" ]]; then
    printf '%s\n' "$QT_QPA_PLATFORM"
    return 0
  fi
  if [[ -n "${DISPLAY:-}" || -S /tmp/.X11-unix/X0 || -S /tmp/.X11-unix/X1 ]]; then
    printf 'xcb\n'
    return 0
  fi
  if [[ "${XDG_SESSION_TYPE:-}" == "wayland" || -n "${WAYLAND_DISPLAY:-}" ]]; then
    printf 'wayland\n'
    return 0
  fi
  printf 'none\n'
}

append_exec_env() {
  local key="$1"
  local value="$2"
  EXEC_ENV_PARTS+=("$key=$(desktop_quote "$value")")
}

build_exec_line() {
  local conda_exe input_method qt_platform exec_path part exec_line
  conda_exe="$(find_conda_exe || true)"
  input_method="$(detect_input_method)"
  qt_platform="$(detect_qt_platform)"
  exec_path="$ROOT_DIR/scripts/linux/run_desktop_mentor.sh"
  EXEC_ENV_PARTS=()

  if [[ -n "$ENV_NAME" ]]; then
    append_exec_env "DESKTOP_MENTOR_CONDA_ENV_NAME" "$ENV_NAME"
    if [[ -n "$conda_exe" ]]; then
      append_exec_env "CONDA_EXE" "$conda_exe"
    fi
  else
    append_exec_env "DESKTOP_MENTOR_CONDA_PREFIX" "$ENV_PREFIX"
  fi

  case "$input_method" in
    fcitx)
      append_exec_env "QT_IM_MODULE" "fcitx"
      append_exec_env "XMODIFIERS" "@im=fcitx"
      append_exec_env "GTK_IM_MODULE" "fcitx"
      append_exec_env "SDL_IM_MODULE" "fcitx"
      append_exec_env "DESKTOP_MENTOR_IM_MODULE" "fcitx"
      ;;
    ibus)
      append_exec_env "QT_IM_MODULE" "ibus"
      append_exec_env "XMODIFIERS" "@im=ibus"
      append_exec_env "GTK_IM_MODULE" "ibus"
      append_exec_env "SDL_IM_MODULE" "ibus"
      append_exec_env "DESKTOP_MENTOR_IM_MODULE" "ibus"
      ;;
    none)
      append_exec_env "DESKTOP_MENTOR_IM_MODULE" "none"
      ;;
  esac

  case "$qt_platform" in
    xcb)
      append_exec_env "QT_QPA_PLATFORM" "xcb"
      ;;
    wayland)
      append_exec_env "QT_QPA_PLATFORM" "wayland"
      append_exec_env "DESKTOP_MENTOR_ALLOW_WAYLAND" "1"
      ;;
  esac

  log "detected input method: $input_method"
  log "detected Qt platform: $qt_platform"

  exec_line="env"
  for part in "${EXEC_ENV_PARTS[@]}"; do
    exec_line+=" $part"
  done
  exec_line+=" $(desktop_quote "$exec_path")"
  printf '%s\n' "$exec_line"
}

write_desktop_file() {
  local icon_path escaped_icon_path exec_line
  icon_path="$ROOT_DIR/assets/cow.png"
  exec_line="$(build_exec_line)"
  escaped_icon_path="$(desktop_escape "$icon_path")"

  log "installing desktop file to $DESKTOP_FILE"
  run mkdir -p "$APPLICATIONS_DIR"
  if [[ "$DRY_RUN" == "1" ]]; then
    log "would write desktop file with Exec=$exec_line"
    return 0
  fi

  cat > "$DESKTOP_FILE" <<EOF
[Desktop Entry]
Type=Application
Name=My Desktop Mentor
Name[zh_CN]=我的桌面导师
Comment=Always-on-top configurable desktop mentor
Comment[zh_CN]=可配置的置顶桌面导师
Exec=$exec_line
Icon=$escaped_icon_path
Terminal=false
Categories=Utility;
EOF

  chmod 0644 "$DESKTOP_FILE"
  if command -v desktop-file-validate >/dev/null 2>&1; then
    desktop-file-validate "$DESKTOP_FILE"
  fi
  if command -v update-desktop-database >/dev/null 2>&1; then
    update-desktop-database "$APPLICATIONS_DIR" >/dev/null 2>&1 || true
  fi
}

if [[ "$INSTALL_DEPS" == "1" ]]; then
  install_dependencies
fi

if [[ "$INSTALL_DESKTOP" == "1" ]]; then
  write_desktop_file
fi

if [[ "$DRY_RUN" == "1" ]]; then
  log "dry-run complete"
else
  log "installed"
fi
log "desktop file: $DESKTOP_FILE"
log "launch test: gtk-launch $APP_ID"
log "diagnose: $ROOT_DIR/scripts/linux/run_desktop_mentor.sh --diagnose --self-test"
