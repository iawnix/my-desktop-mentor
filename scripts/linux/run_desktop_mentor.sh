#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")/../.."

if [[ -n "${DESKTOP_MENTOR_PYTHON:-}" ]]; then
  PYTHON_BIN="$DESKTOP_MENTOR_PYTHON"
else
  PYTHON_BIN=""
  for candidate in python3 python; do
    if command -v "$candidate" >/dev/null 2>&1 && "$candidate" -c "from PySide6.QtCore import Qt" >/dev/null 2>&1; then
      PYTHON_BIN="$(command -v "$candidate")"
      break
    fi
  done
fi

if [[ -z "${PYTHON_BIN:-}" ]]; then
  echo "No Python interpreter with PySide6.QtCore was found." >&2
  echo "Set DESKTOP_MENTOR_PYTHON=/path/to/python or install PySide6." >&2
  exit 1
fi

if [[ -z "${QT_QPA_PLATFORM:-}" ]]; then
  if [[ -z "${XAUTHORITY:-}" ]]; then
    for auth_file in /run/user/1000/.mutter-Xwaylandauth.*; do
      if [[ -f "$auth_file" ]]; then
        export XAUTHORITY="$auth_file"
        break
      fi
    done
  fi

  if [[ -n "${DISPLAY:-}" ]]; then
    export QT_QPA_PLATFORM=xcb
  elif [[ -S /tmp/.X11-unix/X0 ]]; then
    export DISPLAY=:0
    export QT_QPA_PLATFORM=xcb
  elif [[ -S /tmp/.X11-unix/X1 ]]; then
    export DISPLAY=:1
    export QT_QPA_PLATFORM=xcb
  elif [[ -S /run/user/1000/wayland-0 ]]; then
    export XDG_RUNTIME_DIR="${XDG_RUNTIME_DIR:-/run/user/1000}"
    export WAYLAND_DISPLAY="${WAYLAND_DISPLAY:-wayland-0}"
    export QT_QPA_PLATFORM=wayland
  fi
fi

exec "$PYTHON_BIN" desktop_mentor.py "$@"
