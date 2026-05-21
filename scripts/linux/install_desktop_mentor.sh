#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT_DIR="$(cd "$SCRIPT_DIR/../.." && pwd)"
cd "$ROOT_DIR"

APP_ID="${DESKTOP_MENTOR_APP_ID:-desktop_mentor}"
ENV_PREFIX="${DESKTOP_MENTOR_CONDA_PREFIX:-$ROOT_DIR/.conda}"
PYTHON_VERSION="${DESKTOP_MENTOR_PYTHON_VERSION:-3.12}"
APPLICATIONS_DIR="${DESKTOP_MENTOR_APPLICATIONS_DIR:-${XDG_DATA_HOME:-$HOME/.local/share}/applications}"
INSTALL_DEPS=1
INSTALL_DESKTOP=1
DRY_RUN=0

usage() {
  cat <<'EOF'
Usage: scripts/linux/install_desktop_mentor.sh [options]

Install My Desktop Mentor for the current Linux user.

Options:
  --env-prefix PATH       Conda environment path. Default: .conda under the project root
  --python-version VER    Python version for a new Conda env. Default: 3.12
  --app-id NAME           Desktop file id/name. Default: desktop_mentor
  --applications-dir DIR  Desktop file install dir. Default: $XDG_DATA_HOME/applications or ~/.local/share/applications
  --no-deps               Do not create/update the Conda env
  --no-desktop            Do not write the .desktop file
  --dry-run               Print actions without changing files
  -h, --help              Show this help

Environment overrides:
  DESKTOP_MENTOR_CONDA_PREFIX
  DESKTOP_MENTOR_PYTHON_VERSION
  DESKTOP_MENTOR_APPLICATIONS_DIR
  CONDA_EXE
EOF
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --env-prefix)
      ENV_PREFIX="${2:-}"
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

if [[ -z "$ENV_PREFIX" || -z "$PYTHON_VERSION" || -z "$APP_ID" || -z "$APPLICATIONS_DIR" ]]; then
  printf '[desktop-mentor-install] empty option value is not allowed\n' >&2
  exit 2
fi

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

desktop_escape() {
  local value="$1"
  value="${value//\\/\\\\}"
  value="${value//\"/\\\"}"
  printf '%s' "$value"
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

  if [[ ! -x "$ENV_PREFIX/bin/python" ]]; then
    log "creating Conda environment at $ENV_PREFIX"
    run "$conda_exe" create -y -p "$ENV_PREFIX" "python=$PYTHON_VERSION" pip
  else
    log "using existing Conda environment at $ENV_PREFIX"
  fi

  if [[ "$DRY_RUN" == "1" ]]; then
    log "would install requirements into $ENV_PREFIX"
    return 0
  fi

  python_bin="$ENV_PREFIX/bin/python"
  log "installing Python requirements"
  "$python_bin" -m pip install --upgrade pip
  "$python_bin" -m pip install -r "$ROOT_DIR/requirements.txt"

  log "verifying runtime imports"
  verify_runtime_imports "$python_bin"
}

write_desktop_file() {
  local exec_path icon_path escaped_env_prefix escaped_exec_path escaped_icon_path
  exec_path="$ROOT_DIR/scripts/linux/run_desktop_mentor.sh"
  icon_path="$ROOT_DIR/assets/cow.png"
  escaped_env_prefix="$(desktop_escape "$ENV_PREFIX")"
  escaped_exec_path="$(desktop_escape "$exec_path")"
  escaped_icon_path="$(desktop_escape "$icon_path")"

  log "installing desktop file to $DESKTOP_FILE"
  run mkdir -p "$APPLICATIONS_DIR"
  if [[ "$DRY_RUN" == "1" ]]; then
    log "would write desktop file with Exec=$exec_path"
    return 0
  fi

  cat > "$DESKTOP_FILE" <<EOF
[Desktop Entry]
Type=Application
Name=My Desktop Mentor
Name[zh_CN]=我的桌面导师
Comment=Always-on-top configurable desktop mentor
Comment[zh_CN]=可配置的置顶桌面导师
Exec=env DESKTOP_MENTOR_CONDA_PREFIX="$escaped_env_prefix" QT_IM_MODULE=fcitx XMODIFIERS=@im=fcitx GTK_IM_MODULE=fcitx SDL_IM_MODULE=fcitx DESKTOP_MENTOR_IM_MODULE=fcitx "$escaped_exec_path"
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
