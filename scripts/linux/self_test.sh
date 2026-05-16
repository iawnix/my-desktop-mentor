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
  desktop_mentor_app/stickers.py \
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
import os
import shutil
import tempfile
from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QApplication, QFrame, QMenu, QPushButton, QScrollArea

from desktop_mentor_app import config_store
from desktop_mentor_app.assets import DEFAULT_IMAGE, ROOT
from desktop_mentor_app.config_store import AgentConfig
from desktop_mentor_app.constants import DEFAULT_CLICK_MESSAGE, STICKER_ACTION_IDLE, STICKER_ACTION_TAP
from desktop_mentor_app.drop_context import DROP_CONTEXT_PROMPT_HEADER, collect_drop_context, compose_prompt_with_drop_context
from desktop_mentor_app.stickers import discover_sticker_sets
from desktop_mentor_app.todo_store import load_todos, save_todos
from desktop_mentor_app.ui.dialogs import ChatDialog, SettingsDialog, TodoDialog, prepare_modern_menu
from desktop_mentor_app.ui.pet_widget import DesktopMentorPet

app = QApplication([])
settings = SettingsDialog(AgentConfig())
chat = ChatDialog()
context_chat = ChatDialog(context_hint="文件上下文：README.md")
todos = TodoDialog([])
menu = prepare_modern_menu(QMenu())
pet = DesktopMentorPet(DEFAULT_IMAGE, DEFAULT_CLICK_MESSAGE, 120)
pet.config.sticker_sets = {
    STICKER_ACTION_IDLE: [str(DEFAULT_IMAGE), str(DEFAULT_IMAGE)],
    STICKER_ACTION_TAP: [str(DEFAULT_IMAGE)],
}
assert pet.reload_sticker_sets() == []
assert pet.sticker_frame_counts()[STICKER_ACTION_IDLE] == 2
assert pet.sticker_frame_counts()[STICKER_ACTION_TAP] == 1
pet.play_action(STICKER_ACTION_TAP, duration=0.2)
assert pet.current_action == STICKER_ACTION_TAP
pet.config.todo_repeat_seconds = 10
drop_context = collect_drop_context([ROOT / "README.md", ROOT / ".env", ROOT / ".git"])
drop_prompt = compose_prompt_with_drop_context("请总结", drop_context)

save_todos([{"id": "self-test", "text": "self-test todo", "due_ts": int(time.time()) - 1}])
pet.check_todos()
rescheduled = load_todos()
assert len(pet.todo_bubbles) == 1, pet.todo_bubbles
assert len(rescheduled) == 1, rescheduled
assert str(rescheduled[0]["id"]) == "self-test"
assert int(rescheduled[0]["due_ts"]) > int(time.time())
save_todos([{"id": "self-test", "text": "self-test todo", "due_ts": int(time.time()) - 1}])
pet.check_todos()
assert len(pet.todo_bubbles) == 2, pet.todo_bubbles

section_count = len([w for w in settings.findChildren(QFrame) if w.objectName() == "sectionCard"])
scroll_count = len(settings.findChildren(QScrollArea))
nav_buttons = [w for w in settings.findChildren(QPushButton) if w.objectName().startswith("railNavButton")]
assert scroll_count == 1, scroll_count
assert section_count >= 6, section_count
assert len(nav_buttons) == 6, len(nav_buttons)
assert settings.windowFlags() & Qt.WindowType.FramelessWindowHint
assert menu.testAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
settings.scroll_to_section(2)
assert any(button.text() == "互动" and button.objectName() == "railNavButtonActive" for button in nav_buttons)
assert settings.sticker_editor.to_sticker_sets() == {}

with tempfile.TemporaryDirectory() as sticker_tmp:
    sticker_root = Path(sticker_tmp)
    for action in (STICKER_ACTION_IDLE, STICKER_ACTION_TAP):
        action_dir = sticker_root / action
        action_dir.mkdir()
        shutil.copyfile(DEFAULT_IMAGE, action_dir / f"{action}_000.png")
        shutil.copyfile(DEFAULT_IMAGE, action_dir / f"{action}_001.png")
    discovered = discover_sticker_sets(sticker_root)
    assert len(discovered[STICKER_ACTION_IDLE]) == 2, discovered
    assert len(discovered[STICKER_ACTION_TAP]) == 2, discovered
assert chat.text() == ""
assert context_chat.use_drop_context()
context_chat.remove_drop_context()
assert context_chat.drop_context_was_removed()
assert not context_chat.use_drop_context()
assert settings.todo_repeat_spin.value() >= 10
assert todos.due_edit.displayFormat() == "yyyy-MM-dd HH:mm:ss"
assert not todos.due_edit.calendarPopup()
pet.acknowledge_todo_reminder("self-test")
assert load_todos() == []
assert pet.todo_bubbles == []
assert pet.idle_suppressed_until > time.monotonic()
assert "README.md" in drop_context
assert "skipped sensitive filename" in drop_context
assert "skipped generated/cache folder" in drop_context
assert DROP_CONTEXT_PROMPT_HEADER in drop_prompt

saved_env = {key: os.environ.get(key) for key in ("DESKTOP_MENTOR_CONFIG_DIR", "DESKTOP_MENTOR_CONFIG", "XDG_CONFIG_HOME")}
with tempfile.TemporaryDirectory() as tmp:
    os.environ.pop("DESKTOP_MENTOR_CONFIG_DIR", None)
    os.environ.pop("DESKTOP_MENTOR_CONFIG", None)
    os.environ["XDG_CONFIG_HOME"] = tmp
    legacy_dir = Path(tmp) / "MyDesktopMentor"
    legacy_dir.mkdir(parents=True)
    (legacy_dir / "config.json").write_text("{}", encoding="utf-8")
    pointer = config_store.config_dir_pointer_path()
    pointer.parent.mkdir(parents=True, exist_ok=True)
    custom_dir = Path(tmp) / "custom-config"
    pointer.write_text(str(custom_dir), encoding="utf-8")
    assert config_store.configured_config_dir() == legacy_dir
    custom_dir.mkdir(parents=True)
    (custom_dir / "config.json").write_text("{}", encoding="utf-8")
    assert config_store.configured_config_dir() == custom_dir
for key, value in saved_env.items():
    if value is None:
        os.environ.pop(key, None)
    else:
        os.environ[key] = value
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
