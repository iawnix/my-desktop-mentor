#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT_DIR="$(cd "$SCRIPT_DIR/../.." && pwd)"
cd "$ROOT_DIR"

PYTHON_FOR_COMPILE="${DESKTOP_MENTOR_PYTHON:-}"
if [[ -z "$PYTHON_FOR_COMPILE" ]]; then
  if command -v python3 >/dev/null 2>&1; then
    PYTHON_FOR_COMPILE="$(command -v python3)"
  elif command -v python >/dev/null 2>&1; then
    PYTHON_FOR_COMPILE="$(command -v python)"
  else
    echo "[self-test] No python3/python found for syntax checks." >&2
    exit 1
  fi
fi

PYTHON_FOR_QT="${DESKTOP_MENTOR_PYTHON:-}"
if [[ -z "$PYTHON_FOR_QT" ]]; then
  CANDIDATES=()
  [[ -x "$ROOT_DIR/.venv/bin/python" ]] && CANDIDATES+=("$ROOT_DIR/.venv/bin/python")
  [[ -n "${CONDA_PREFIX:-}" && -x "$CONDA_PREFIX/bin/python" ]] && CANDIDATES+=("$CONDA_PREFIX/bin/python")
  command -v python3 >/dev/null 2>&1 && CANDIDATES+=("$(command -v python3)")
  command -v python >/dev/null 2>&1 && CANDIDATES+=("$(command -v python)")
  for candidate in "$HOME"/soft/conda/*/bin/python3 "$HOME"/miniconda*/bin/python "$HOME"/anaconda*/bin/python; do
    [[ -x "$candidate" ]] && CANDIDATES+=("$candidate")
  done
  for candidate in "${CANDIDATES[@]}"; do
    if "$candidate" -c "from PySide6.QtCore import Qt" >/dev/null 2>&1; then
      PYTHON_FOR_QT="$candidate"
      break
    fi
  done
fi

if [[ -z "$PYTHON_FOR_QT" ]]; then
  echo "[self-test] No Python interpreter with PySide6.QtCore was found." >&2
  echo "[self-test] Set DESKTOP_MENTOR_PYTHON=/path/to/python or install PySide6." >&2
  exit 1
fi

step() {
  printf '\n[self-test] %s\n' "$*"
}

step "Python syntax"
"$PYTHON_FOR_COMPILE" -m py_compile desktop_mentor.py desktop_mentor_app/drop_context.py packaging/windows/desktop_mentor.spec

step "Linux launcher syntax"
bash -n scripts/linux/run_desktop_mentor.sh
bash -n scripts/linux/self_test.sh

step "Linux desktop file"
if command -v desktop-file-validate >/dev/null 2>&1; then
  desktop-file-validate packaging/linux/desktop_mentor.desktop
else
  echo "[self-test] desktop-file-validate not found; skipped." >&2
fi

step "Offscreen app self-test"
QT_QPA_PLATFORM=offscreen \
DESKTOP_MENTOR_DIAG=1 \
DESKTOP_MENTOR_CONFIG_DIR="${DESKTOP_MENTOR_CONFIG_DIR:-/tmp/my-desktop-mentor-self-test}" \
DESKTOP_MENTOR_PYTHON="$PYTHON_FOR_QT" \
./scripts/linux/run_desktop_mentor.sh --self-test

step "Qt dialog smoke"
QT_QPA_PLATFORM=offscreen \
DESKTOP_MENTOR_CONFIG_DIR="${DESKTOP_MENTOR_CONFIG_DIR:-/tmp/my-desktop-mentor-self-test}" \
"$PYTHON_FOR_QT" - <<'PY'
import time

from PySide6.QtWidgets import QApplication, QFrame, QScrollArea

import desktop_mentor as dm

app = QApplication([])
settings = dm.SettingsDialog(dm.AgentConfig())
chat = dm.ChatDialog()
todos = dm.TodoDialog([])
pet = dm.DesktopMentorPet(dm.DEFAULT_IMAGE, dm.DEFAULT_CLICK_MESSAGE, 120)
drop_context = dm.collect_drop_context([dm.ROOT / "README.md", dm.ROOT / ".env", dm.ROOT / ".git"])
drop_prompt = dm.compose_prompt_with_drop_context("请总结", drop_context)

dm.save_todos([{"id": "self-test", "text": "self-test todo", "due_ts": int(time.time()) - 1}])
pet.check_todos()

section_count = len([w for w in settings.findChildren(QFrame) if w.objectName() == "sectionCard"])
scroll_count = len(settings.findChildren(QScrollArea))
assert scroll_count == 1, scroll_count
assert section_count >= 5, section_count
assert chat.text() == ""
assert dm.load_todos() == []
assert pet.idle_suppressed_until > time.monotonic()
assert "README.md" in drop_context
assert "skipped sensitive filename" in drop_context
assert "skipped generated/cache folder" in drop_context
assert dm.DROP_CONTEXT_PROMPT_HEADER in drop_prompt
print("[self-test] dialog smoke ok")
PY

step "Workspace cleanliness"
find . -maxdepth 3 -type d -name __pycache__ -prune -exec rm -rf {} +
if find . -maxdepth 3 -type f \( -name '*.pyc' -o -name '.env' \) | grep -q .; then
  echo "[self-test] unexpected cache or .env file found:" >&2
  find . -maxdepth 3 -type f \( -name '*.pyc' -o -name '.env' \) >&2
  exit 1
fi

echo
echo "[self-test] ok"
