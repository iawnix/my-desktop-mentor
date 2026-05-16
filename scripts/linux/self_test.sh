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
"$PYTHON_FOR_COMPILE" -m py_compile \
  desktop_mentor.py \
  desktop_mentor_app/constants.py \
  desktop_mentor_app/config_store.py \
  desktop_mentor_app/assets.py \
  desktop_mentor_app/todo_store.py \
  desktop_mentor_app/agent_client.py \
  desktop_mentor_app/idle_detector.py \
  desktop_mentor_app/drop_context.py \
  desktop_mentor_app/ui/dialogs.py \
  desktop_mentor_app/ui/pet_widget.py \
  packaging/windows/desktop_mentor.spec

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

from PySide6.QtWidgets import QApplication, QFrame, QPushButton, QScrollArea

from desktop_mentor_app.assets import DEFAULT_IMAGE, ROOT
from desktop_mentor_app.config_store import AgentConfig
from desktop_mentor_app.constants import DEFAULT_CLICK_MESSAGE
from desktop_mentor_app.drop_context import DROP_CONTEXT_PROMPT_HEADER, collect_drop_context, compose_prompt_with_drop_context
from desktop_mentor_app.todo_store import load_todos, save_todos
from desktop_mentor_app.ui.dialogs import ChatDialog, SettingsDialog, TodoDialog
from desktop_mentor_app.ui.pet_widget import DesktopMentorPet

app = QApplication([])
settings = SettingsDialog(AgentConfig())
chat = ChatDialog()
context_chat = ChatDialog(context_hint="文件上下文：README.md")
todos = TodoDialog([])
pet = DesktopMentorPet(DEFAULT_IMAGE, DEFAULT_CLICK_MESSAGE, 120)
drop_context = collect_drop_context([ROOT / "README.md", ROOT / ".env", ROOT / ".git"])
drop_prompt = compose_prompt_with_drop_context("请总结", drop_context)

save_todos([{"id": "self-test", "text": "self-test todo", "due_ts": int(time.time()) - 1}])
pet.check_todos()

section_count = len([w for w in settings.findChildren(QFrame) if w.objectName() == "sectionCard"])
scroll_count = len(settings.findChildren(QScrollArea))
nav_buttons = [w for w in settings.findChildren(QPushButton) if w.objectName().startswith("railNavButton")]
assert scroll_count == 1, scroll_count
assert section_count >= 5, section_count
assert len(nav_buttons) == 5, len(nav_buttons)
settings.scroll_to_section(2)
assert any(button.text() == "互动" and button.objectName() == "railNavButtonActive" for button in nav_buttons)
assert chat.text() == ""
assert context_chat.use_drop_context()
context_chat.remove_drop_context()
assert context_chat.drop_context_was_removed()
assert not context_chat.use_drop_context()
assert load_todos() == []
assert pet.idle_suppressed_until > time.monotonic()
assert "README.md" in drop_context
assert "skipped sensitive filename" in drop_context
assert "skipped generated/cache folder" in drop_context
assert DROP_CONTEXT_PROMPT_HEADER in drop_prompt
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
