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
  desktop_mentor_app/control/__init__.py \
  desktop_mentor_app/control/audit_log.py \
  desktop_mentor_app/control/executor.py \
  desktop_mentor_app/control/permissions.py \
  desktop_mentor_app/control/tool_registry.py \
  desktop_mentor_app/control/types.py \
  desktop_mentor_app/conversation_store.py \
  desktop_mentor_app/assets.py \
  desktop_mentor_app/stickers.py \
  desktop_mentor_app/todo_store.py \
  desktop_mentor_app/agent_client.py \
  desktop_mentor_app/idle_detector.py \
  desktop_mentor_app/drop_context.py \
  desktop_mentor_app/ui/tokens.py \
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
import shlex
import sys
import tempfile
from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QApplication, QFrame, QMenu, QPushButton, QScrollArea

from desktop_mentor_app import config_store
from desktop_mentor_app.assets import DEFAULT_IMAGE, DEFAULT_STICKERS_DIR, ROOT
from desktop_mentor_app.config_store import AgentConfig, new_default_config
from desktop_mentor_app.control import PermissionLevel, build_control_plan, execute_control_plan
from desktop_mentor_app.conversation_store import append_chat_turn, build_conversation_memory_context, clear_chat_history, create_conversation_session, load_chat_history, list_conversation_sessions
from desktop_mentor_app.constants import DEFAULT_CLICK_MESSAGE, MAX_IDLE_SECONDS, MAX_PET_SIZE, MIN_PET_SIZE, STICKER_ACTION_IDLE, STICKER_ACTION_TAP
from desktop_mentor_app.drop_context import DROP_CONTEXT_PROMPT_HEADER, collect_drop_context, compose_prompt_with_drop_context
from desktop_mentor_app.stickers import discover_sticker_sets
from desktop_mentor_app.todo_store import load_todos, save_todos
from desktop_mentor_app.ui.dialogs import ChatDialog, SettingsDialog, TodoDialog, prepare_modern_menu
from desktop_mentor_app.ui.pet_widget import DesktopMentorPet

app = QApplication([])
settings = SettingsDialog(AgentConfig())
default_config = new_default_config()
assert all(len(paths) == 8 for paths in default_config.sticker_sets.values()), default_config.sticker_sets
assert len(default_config.sticker_sets) == 8, default_config.sticker_sets
chat = ChatDialog()
context_chat = ChatDialog(context_hint="文件上下文：README.md")
clear_chat_history()
assert load_chat_history() == []
managed_session = append_chat_turn("记住我的默认项目是导师桌宠", "已记住")
history = load_chat_history()
memory_context = build_conversation_memory_context(managed_session.session_id, 3)
assert "导师桌宠" in memory_context, memory_context
assert any(session.session_id == managed_session.session_id for session in list_conversation_sessions())
history_chat = ChatDialog(history=history)
todos = TodoDialog([])
menu = prepare_modern_menu(QMenu())
pet = DesktopMentorPet(DEFAULT_IMAGE, DEFAULT_CLICK_MESSAGE, 120)
pet.set_pet_size(44)
assert pet.pet_size == MIN_PET_SIZE, pet.pet_size
pet.set_pet_size(999)
assert pet.pet_size == MAX_PET_SIZE, pet.pet_size
pet.set_pet_size(120)
pet.config.sticker_sets = discover_sticker_sets(DEFAULT_STICKERS_DIR)
assert pet.reload_sticker_sets() == []
bundled_source = pet.current_sticker_source_rect()
bundled_visual = pet.current_sticker_visual_rect()
assert bundled_source.width() < 1024 and bundled_source.height() < 1024, bundled_source
assert bundled_visual.width() < pet.sticker_rect().width(), (bundled_visual, pet.sticker_rect())
assert bundled_visual.height() <= pet.sticker_rect().height(), (bundled_visual, pet.sticker_rect())
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
assert section_count >= 7, section_count
assert len(nav_buttons) == 7, len(nav_buttons)
assert settings.windowFlags() & Qt.WindowType.FramelessWindowHint
assert settings.settings_scroll.objectName() == "transparentScrollArea"
assert settings.settings_scroll.viewport().objectName() == "transparentViewport"
assert chat.history_scroll.objectName() == "transparentScrollArea"
assert chat.history_scroll.viewport().objectName() == "transparentViewport"
assert menu.testAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
settings.scroll_to_section(2)
assert any(button.text() == "互动" and button.objectName() == "railNavButtonActive" for button in nav_buttons)
assert settings.sticker_editor.to_sticker_sets() == {}
approvals = []
chat.control_plan_approved.connect(lambda plan_id: approvals.append(plan_id))
chat.add_control_plan("plan-1", "测试计划", "1. 读取状态", True)
chat.approve_control_plan("plan-1")
assert approvals == ["plan-1"], approvals
submissions = []
chat.message_submitted.connect(lambda text, use_context, session_id: submissions.append((text, use_context, session_id)))
chat.text_edit.setPlainText("新的问题")
chat.submit_message()
assert submissions == [("新的问题", False, "")], submissions
assert chat.waiting_for_reply
chat.add_assistant_message("新的回答")
chat.set_waiting(False)
assert not chat.waiting_for_reply
switched_session = create_conversation_session("切换后的会话")
pet.chat_dialog = ChatDialog(sessions=list_conversation_sessions(), active_session=managed_session, history=[])
pet.chat_dialog.set_waiting(True)
pet.show_agent_reply("切换前请求的异步返回", switched_session.session_id)
assert not pet.chat_dialog.waiting_for_reply
pet.chat_dialog = None
assert len(history) == 2, history
assert len(history_chat.message_widgets) == 2, len(history_chat.message_widgets)

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
bundled = discover_sticker_sets(DEFAULT_STICKERS_DIR)
assert len(bundled) == 8, bundled
assert all(len(paths) == 8 for paths in bundled.values()), bundled
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
    custom_prompt = "我是长江，但这是用户手动保存的风格提示词，不应被自动重置。"
    custom_prompt_path = Path(tmp) / "custom-prompt" / "config.json"
    custom_prompt_path.parent.mkdir(parents=True)
    custom_prompt_path.write_text('{"system_prompt": ' + __import__("json").dumps(custom_prompt, ensure_ascii=False) + "}", encoding="utf-8")
    assert config_store.load_config(custom_prompt_path).system_prompt == custom_prompt
    custom_messages = {
        "click_message": "抓紧, 谢谢!",
        "idle_message": "课题如何了? 抓紧谢谢!",
        "drop_message": "这种垃圾就不要让我看, 我每天很忙的!",
        "idle_seconds": 999999,
        "memory_enabled": "false",
    }
    custom_messages_path = Path(tmp) / "custom-messages" / "config.json"
    custom_messages_path.parent.mkdir(parents=True)
    custom_messages_path.write_text(__import__("json").dumps(custom_messages, ensure_ascii=False), encoding="utf-8")
    loaded_messages = config_store.load_config(custom_messages_path)
    assert loaded_messages.click_message == custom_messages["click_message"]
    assert loaded_messages.idle_message == custom_messages["idle_message"]
    assert loaded_messages.drop_message == custom_messages["drop_message"]
    assert loaded_messages.idle_seconds == MAX_IDLE_SECONDS
    assert loaded_messages.memory_enabled is False
    assert loaded_messages.control_enabled is True
    control_root = Path(tmp) / "control-root"
    control_root.mkdir()
    (control_root / "input.txt").write_text("alpha\nbeta\n", encoding="utf-8")
    sys_plan = build_control_plan("/sys", str(control_root))
    assert sys_plan is not None and sys_plan.permission == PermissionLevel.READ_ONLY
    assert execute_control_plan(sys_plan).ok
    ls_plan = build_control_plan("/ls .", str(control_root))
    assert ls_plan is not None and execute_control_plan(ls_plan).ok
    read_plan = build_control_plan("/read input.txt", str(control_root))
    assert read_plan is not None
    read_result = execute_control_plan(read_plan)
    assert read_result.ok and "alpha" in read_result.output
    search_plan = build_control_plan("/search beta .", str(control_root))
    assert search_plan is not None
    search_result = execute_control_plan(search_plan)
    assert search_result.ok and "input.txt" in search_result.output
    write_plan = build_control_plan("/write output.txt :: hello", str(control_root))
    assert write_plan is not None and write_plan.requires_confirmation
    write_result = execute_control_plan(write_plan)
    assert write_result.ok and (control_root / "output.txt").read_text(encoding="utf-8").strip() == "hello"
    run_plan = build_control_plan(
        f"/run --cwd {shlex.quote(str(control_root))} {shlex.quote(sys.executable)} -c \"print('mentor-control')\"",
        str(control_root),
    )
    assert run_plan is not None and run_plan.requires_confirmation
    run_result = execute_control_plan(run_plan)
    assert run_result.ok and "mentor-control" in run_result.output
    blocked_plan = build_control_plan("/run rm -rf /", str(control_root))
    assert blocked_plan is not None and blocked_plan.is_blocked
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
