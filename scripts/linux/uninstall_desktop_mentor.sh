#!/usr/bin/env bash
set -euo pipefail

APP_ID="${DESKTOP_MENTOR_APP_ID:-desktop_mentor}"
APPLICATIONS_DIR="${DESKTOP_MENTOR_APPLICATIONS_DIR:-${XDG_DATA_HOME:-$HOME/.local/share}/applications}"
CONFIG_DIR="${DESKTOP_MENTOR_CONFIG_DIR:-${XDG_CONFIG_HOME:-$HOME/.config}/my-desktop-mentor}"
ENV_PREFIX="${DESKTOP_MENTOR_CONDA_PREFIX:-}"
ENV_NAME="${DESKTOP_MENTOR_CONDA_ENV_NAME:-}"
CONDA_EXE_PATH="${CONDA_EXE:-}"
REMOVE_DESKTOP=1
REMOVE_CONFIG=0
REMOVE_ENV=0
DRY_RUN=0

usage() {
  cat <<'EOF'
Usage: scripts/linux/uninstall_desktop_mentor.sh [options]

Uninstall My Desktop Mentor for the current Linux user.

By default this only removes the desktop launcher. User data and Conda
environments are preserved unless explicitly requested.

Options:
  --app-id NAME           Desktop file id/name. Default: desktop_mentor
  --applications-dir DIR  Desktop file install dir. Default: $XDG_DATA_HOME/applications or ~/.local/share/applications
  --config-dir DIR        User config directory. Default: $XDG_CONFIG_HOME/my-desktop-mentor or ~/.config/my-desktop-mentor
  --env-name NAME         Named Conda environment to remove when --remove-env is used. Default: my-desktop-mentor
  --env-prefix PATH       Conda environment path to remove when --remove-env is used
  --conda PATH            Conda executable to use for --remove-env
  --keep-desktop          Do not remove the .desktop launcher
  --remove-config         Also remove config, chat history, memory, logs, and local app state
  --remove-env            Also remove the selected Conda environment
  --dry-run               Print actions without changing files
  -h, --help              Show this help

Environment overrides:
  DESKTOP_MENTOR_APP_ID
  DESKTOP_MENTOR_APPLICATIONS_DIR
  DESKTOP_MENTOR_CONFIG_DIR
  DESKTOP_MENTOR_CONDA_PREFIX
  DESKTOP_MENTOR_CONDA_ENV_NAME
  CONDA_EXE
EOF
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --app-id)
      APP_ID="${2:-}"
      shift 2
      ;;
    --applications-dir)
      APPLICATIONS_DIR="${2:-}"
      shift 2
      ;;
    --config-dir)
      CONFIG_DIR="${2:-}"
      shift 2
      ;;
    --env-name)
      ENV_NAME="${2:-}"
      ENV_PREFIX=""
      shift 2
      ;;
    --env-prefix)
      ENV_PREFIX="${2:-}"
      ENV_NAME=""
      shift 2
      ;;
    --conda)
      CONDA_EXE_PATH="${2:-}"
      shift 2
      ;;
    --keep-desktop)
      REMOVE_DESKTOP=0
      shift
      ;;
    --remove-config)
      REMOVE_CONFIG=1
      shift
      ;;
    --remove-env)
      REMOVE_ENV=1
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
      printf '[desktop-mentor-uninstall] unknown option: %s\n' "$1" >&2
      usage >&2
      exit 2
      ;;
  esac
done

if [[ -z "$ENV_PREFIX" && -z "$ENV_NAME" ]]; then
  ENV_NAME="my-desktop-mentor"
fi

if [[ -z "$APP_ID" || -z "$APPLICATIONS_DIR" || -z "$CONFIG_DIR" ]]; then
  printf '[desktop-mentor-uninstall] empty option value is not allowed\n' >&2
  exit 2
fi

DESKTOP_FILE="$APPLICATIONS_DIR/$APP_ID.desktop"

log() {
  printf '[desktop-mentor-uninstall] %s\n' "$*" >&2
}

run() {
  if [[ "$DRY_RUN" == "1" ]]; then
    printf '[desktop-mentor-uninstall] dry-run:'
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

assert_safe_removal_target() {
  local target="$1"
  case "$target" in
    ""|"/"|"$HOME"|"$HOME/"|"/home"|"/home/"|"/tmp"|"/tmp/")
      die "refusing to remove unsafe path: $target"
      ;;
  esac
}

remove_path_if_exists() {
  local target="$1"
  assert_safe_removal_target "$target"
  if [[ -e "$target" || -L "$target" ]]; then
    run rm -rf "$target"
  else
    log "not found: $target"
  fi
}

remove_desktop_file() {
  log "removing desktop file: $DESKTOP_FILE"
  remove_path_if_exists "$DESKTOP_FILE"
  if [[ "$DRY_RUN" != "1" && -d "$APPLICATIONS_DIR" ]] && command -v update-desktop-database >/dev/null 2>&1; then
    update-desktop-database "$APPLICATIONS_DIR" >/dev/null 2>&1 || true
  fi
}

remove_config_dir() {
  log "removing user config and state: $CONFIG_DIR"
  remove_path_if_exists "$CONFIG_DIR"
}

remove_conda_env() {
  local conda_exe
  conda_exe="$(find_conda_exe || true)"
  [[ -n "$conda_exe" ]] || die "Conda was not found. Set CONDA_EXE=/path/to/conda or omit --remove-env."

  if [[ -n "$ENV_NAME" ]]; then
    if "$conda_exe" run -n "$ENV_NAME" python -c 'import sys' >/dev/null 2>&1; then
      log "removing Conda environment named $ENV_NAME"
      run "$conda_exe" env remove -y -n "$ENV_NAME"
    else
      log "Conda environment not found: $ENV_NAME"
    fi
  else
    if [[ -z "$ENV_PREFIX" ]]; then
      die "--remove-env with a path environment requires --env-prefix PATH"
    fi
    if [[ -d "$ENV_PREFIX" ]]; then
      log "removing Conda environment at $ENV_PREFIX"
      run "$conda_exe" env remove -y -p "$ENV_PREFIX"
    else
      log "Conda environment path not found: $ENV_PREFIX"
    fi
  fi
}

if [[ "$REMOVE_DESKTOP" == "1" ]]; then
  remove_desktop_file
fi

if [[ "$REMOVE_CONFIG" == "1" ]]; then
  remove_config_dir
else
  log "keeping user config and state: $CONFIG_DIR"
fi

if [[ "$REMOVE_ENV" == "1" ]]; then
  remove_conda_env
else
  if [[ -n "$ENV_NAME" ]]; then
    log "keeping Conda environment: $ENV_NAME"
  else
    log "keeping Conda environment: $ENV_PREFIX"
  fi
fi

if [[ "$DRY_RUN" == "1" ]]; then
  log "dry-run complete"
else
  log "uninstalled"
fi
