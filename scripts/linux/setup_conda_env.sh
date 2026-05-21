#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT_DIR="$(cd "$SCRIPT_DIR/../.." && pwd)"
cd "$ROOT_DIR"

ENV_PREFIX="${DESKTOP_MENTOR_CONDA_PREFIX:-$ROOT_DIR/.conda}"
PYTHON_VERSION="${DESKTOP_MENTOR_PYTHON_VERSION:-3.12}"

log() {
  printf '[desktop-mentor-setup] %s\n' "$*" >&2
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

CONDA_EXE_PATH="$(find_conda_exe || true)"
if [[ -z "$CONDA_EXE_PATH" ]]; then
  die "Conda was not found. Install Miniconda/Anaconda or set CONDA_EXE=/path/to/conda."
fi

if [[ ! -x "$ENV_PREFIX/bin/python" ]]; then
  log "creating Conda environment at $ENV_PREFIX"
  "$CONDA_EXE_PATH" create -y -p "$ENV_PREFIX" "python=$PYTHON_VERSION" pip
else
  log "using existing Conda environment at $ENV_PREFIX"
fi

PYTHON_BIN="$ENV_PREFIX/bin/python"
log "installing Python requirements"
"$PYTHON_BIN" -m pip install --upgrade pip
"$PYTHON_BIN" -m pip install -r "$ROOT_DIR/requirements.txt"

log "verifying runtime imports"
"$PYTHON_BIN" - <<'PY'
from PySide6.QtCore import Qt
from PySide6.QtWebEngineWidgets import QWebEngineView
import latex2mathml
import markdown_it
import pygments
import qasync

print("desktop mentor conda environment is ready")
PY

log "done"
