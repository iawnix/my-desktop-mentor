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
  if [[ "${DESKTOP_MENTOR_PREFER_SYSTEM_QT:-1}" != "0" ]] && command -v fcitx5 >/dev/null 2>&1; then
    [[ -x /usr/bin/python3 ]] && CANDIDATES+=("/usr/bin/python3")
    [[ -x /usr/local/bin/python3 ]] && CANDIDATES+=("/usr/local/bin/python3")
  fi
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
  desktop_mentor_app/logging_config.py \
  desktop_mentor_app/config/__init__.py \
  desktop_mentor_app/config/migration.py \
  desktop_mentor_app/core/__init__.py \
  desktop_mentor_app/core/runtime.py \
  desktop_mentor_app/core/task_runner.py \
  desktop_mentor_app/model_client/__init__.py \
  desktop_mentor_app/model_client/base.py \
  desktop_mentor_app/model_client/openai_compatible.py \
  desktop_mentor_app/platforms/__init__.py \
  desktop_mentor_app/platforms/base.py \
  desktop_mentor_app/platforms/display.py \
  desktop_mentor_app/platforms/registry.py \
  desktop_mentor_app/platforms/whatsapp.py \
  desktop_mentor_app/state/__init__.py \
  desktop_mentor_app/state/conversations.py \
  desktop_mentor_app/state/memory.py \
  desktop_mentor_app/state/todos.py \
  desktop_mentor_app/security/__init__.py \
  desktop_mentor_app/security/audit.py \
  desktop_mentor_app/security/policy.py \
  desktop_mentor_app/tools/__init__.py \
  desktop_mentor_app/tools/base.py \
  desktop_mentor_app/tools/command_parser.py \
  desktop_mentor_app/tools/executor.py \
  desktop_mentor_app/tools/natural_language.py \
  desktop_mentor_app/tools/path_parser.py \
  desktop_mentor_app/tools/plan_helpers.py \
  desktop_mentor_app/tools/registry.py \
  desktop_mentor_app/tools/types.py \
  desktop_mentor_app/cron/__init__.py \
  desktop_mentor_app/cron/scheduler.py \
  desktop_mentor_app/pet/__init__.py \
  desktop_mentor_app/pet/animation.py \
  desktop_mentor_app/pet/chat_manager.py \
  desktop_mentor_app/pet/idle_manager.py \
  desktop_mentor_app/pet/sticker_manager.py \
  desktop_mentor_app/pet/todo_manager.py \
  desktop_mentor_app/config_store.py \
  desktop_mentor_app/input_method.py \
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
  desktop_mentor_app/ui/chat_components.py \
  desktop_mentor_app/ui/chat_dialog.py \
  desktop_mentor_app/ui/dialog_chrome.py \
  desktop_mentor_app/ui/dialogs.py \
  desktop_mentor_app/ui/idle_alert.py \
  desktop_mentor_app/ui/pet_dialog_coordinator.py \
  desktop_mentor_app/ui/pet_interaction_controller.py \
  desktop_mentor_app/ui/pet_painter.py \
  desktop_mentor_app/ui/pet_widget.py \
  desktop_mentor_app/ui/pointer_events.py \
  desktop_mentor_app/ui/settings_dialog.py \
  desktop_mentor_app/ui/sticker_set_editor.py \
  desktop_mentor_app/ui/text_view_dialog.py \
  desktop_mentor_app/ui/todo_dialog.py \
  packaging/windows/desktop_mentor.spec

step "Unit tests"
PYTHONPATH="$ROOT_DIR" "$PYTHON_FOR_COMPILE" -m unittest discover -s tests

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
SELF_TEST_OUTPUT="$(
  QT_QPA_PLATFORM=offscreen \
  DESKTOP_MENTOR_DIAG=1 \
  DESKTOP_MENTOR_CONFIG_DIR="${DESKTOP_MENTOR_CONFIG_DIR:-/tmp/my-desktop-mentor-self-test}" \
  DESKTOP_MENTOR_PYTHON="$PYTHON_FOR_QT" \
  ./scripts/linux/run_desktop_mentor.sh --self-test
)"
printf '%s\n' "$SELF_TEST_OUTPUT"
SELF_TEST_OUTPUT="$SELF_TEST_OUTPUT" "$PYTHON_FOR_COMPILE" - <<'PY'
import json
import os

data = json.loads(os.environ["SELF_TEST_OUTPUT"])
assert data["quit_on_last_window_closed"] is False
assert data["config_schema_version"] == 2
assert data["app_log_path"].endswith("/logs/app.log")
PY

step "Qt dialog smoke"
QT_QPA_PLATFORM=offscreen \
DESKTOP_MENTOR_CONFIG_DIR="${DESKTOP_MENTOR_CONFIG_DIR:-/tmp/my-desktop-mentor-self-test}" \
"$PYTHON_FOR_QT" - <<'PY'
import time
import asyncio
import builtins
import os
import shutil
import shlex
import sys
import tempfile
from pathlib import Path

from PySide6.QtCore import QEvent, Qt
from PySide6.QtGui import QKeyEvent, QTextCursor
from PySide6.QtWidgets import QApplication, QFrame, QMenu, QPushButton, QScrollArea, QWidget

from desktop_mentor_app import config_store
from desktop_mentor_app.agent_client import agent_system_prompt, call_agent_async, compact_text, limit_formatted_text
from desktop_mentor_app.assets import DEFAULT_IMAGE, DEFAULT_STICKERS_DIR, ROOT
from desktop_mentor_app.config_store import AgentConfig, new_default_config
from desktop_mentor_app.control import PermissionLevel
from desktop_mentor_app.state.conversations import append_chat_turn, build_conversation_memory_context, clear_chat_history, create_conversation_session, load_chat_history, list_conversation_sessions
from desktop_mentor_app.tools.executor import execute_control_plan
from desktop_mentor_app.tools.registry import build_control_plan, build_control_plan_from_agent_reply, desktop_path
from desktop_mentor_app.constants import DEFAULT_CLICK_MESSAGE, DEFAULT_STICKER_ANIMATION_SPEED, DEFAULT_TODO_REPEAT_SECONDS, MAX_IDLE_SECONDS, MAX_PET_SIZE, MAX_STICKER_ANIMATION_SPEED, MIN_PET_SIZE, STICKER_ACTION_IDLE, STICKER_ACTION_TAP
from desktop_mentor_app.drop_context import DROP_CONTEXT_PROMPT_HEADER, collect_drop_context, compose_prompt_with_drop_context
from desktop_mentor_app.input_method import configure_linux_input_method_environment, fcitx_qt_plugin_files, input_method_diagnostics, preferred_x11_display
from desktop_mentor_app.stickers import discover_sticker_sets
from desktop_mentor_app.state.todos import load_todos, save_todos
from desktop_mentor_app.ui.dialogs import ChatDialog, SettingsDialog, TodoDialog, prepare_modern_menu
from desktop_mentor_app.ui.markdown_rendering import normalize_model_markdown, render_markdown_fragment
from desktop_mentor_app.ui.pet_widget import DesktopMentorPet
from desktop_mentor_app.config.migration import CURRENT_CONFIG_SCHEMA_VERSION
from desktop_mentor_app.cron.scheduler import reschedule_due_items
from desktop_mentor_app.pet.animation import sticker_frame_interval_seconds
from desktop_mentor_app.pet.todo_manager import PetTodoService
from desktop_mentor_app.platforms.whatsapp import WhatsAppPlatform

app = QApplication([])
configure_linux_input_method_environment()
settings = SettingsDialog(AgentConfig())
default_config = new_default_config()
assert default_config.schema_version == CURRENT_CONFIG_SCHEMA_VERSION
assert default_config.sticker_animation_speed == DEFAULT_STICKER_ANIMATION_SPEED, default_config.sticker_animation_speed
assert PetTodoService().repeat_seconds("bad") == DEFAULT_TODO_REPEAT_SECONDS
assert settings.sticker_animation_speed_spin.value() == DEFAULT_STICKER_ANIMATION_SPEED, settings.sticker_animation_speed_spin.value()
assert all(len(paths) == 16 for paths in default_config.sticker_sets.values()), default_config.sticker_sets
assert len(default_config.sticker_sets) == 8, default_config.sticker_sets
chat = ChatDialog()
context_chat = ChatDialog(context_hint="文件上下文：README.md")
markdown_sample = "**结论**\n\n- Markdown 列表\n\n```python\nprint('ok')\n```\n\n$$E=mc^2$$"
chat.add_assistant_message(markdown_sample)
markdown_views = chat.findChildren(QWidget, "chatMarkdownMessage")
assert markdown_views, "assistant replies should render through a Markdown message view"
assistant_cards = chat.findChildren(QFrame, "chatMessageCardAssistant")
assert assistant_cards, "assistant replies should be wrapped in a message card"
rendered_markdown = render_markdown_fragment(markdown_sample)
assert "codehilite" in rendered_markdown, rendered_markdown
assert "math-block" in rendered_markdown, rendered_markdown
assert "<math" in rendered_markdown, rendered_markdown
assert "```" not in rendered_markdown, rendered_markdown
collapsed_fence = "说明。 ```python import asyncio ```"
normalized_fence = normalize_model_markdown(collapsed_fence)
assert "```python\nimport asyncio" in normalized_fence, normalized_fence
assert "codehilite" in render_markdown_fragment(collapsed_fence)
original_import = builtins.__import__
def blocked_markdown_it_import(name, globals=None, locals=None, fromlist=(), level=0):
    if name == "markdown_it" or name.startswith("markdown_it."):
        raise ModuleNotFoundError(name)
    return original_import(name, globals, locals, fromlist, level)
builtins.__import__ = blocked_markdown_it_import
try:
    fallback_html = render_markdown_fragment("```python\nprint('ok')\n```")
finally:
    builtins.__import__ = original_import
assert "codehilite" in fallback_html, fallback_html
assert "```" not in fallback_html, fallback_html
assert compact_text("a\nb", 10) == "a b"
assert limit_formatted_text("a\nb", 10) == "a\nb"
assert "目标" in asyncio.run(call_agent_async(AgentConfig(), "科研目标"))
submitted = []
chat.text_edit.submitted.connect(lambda: submitted.append(True))
chat.text_edit.setPlainText("send me")
chat.text_edit.keyPressEvent(QKeyEvent(QEvent.Type.KeyPress, Qt.Key.Key_Return, Qt.KeyboardModifier.NoModifier))
assert submitted, "Enter should submit chat input"
chat.set_waiting(False)
assert chat.cancel_button.isHidden()
cancelled_requests = []
chat.request_cancelled.connect(lambda session_id: cancelled_requests.append(session_id))
chat.set_waiting(True)
assert not chat.cancel_button.isHidden()
assert not chat.send_button.isEnabled()
chat.cancel_current_request()
assert cancelled_requests == [chat.active_session_id], cancelled_requests
assert not chat.waiting_for_reply
chat.text_edit.setPlainText("line 1")
cursor = chat.text_edit.textCursor()
cursor.movePosition(QTextCursor.MoveOperation.End)
chat.text_edit.setTextCursor(cursor)
chat.text_edit.keyPressEvent(QKeyEvent(QEvent.Type.KeyPress, Qt.Key.Key_Return, Qt.KeyboardModifier.ShiftModifier))
assert chat.text_edit.toPlainText() == "line 1\n", chat.text_edit.toPlainText()
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
assert abs(pet.sticker_frame_interval_seconds() - 0.12) < 0.001, pet.sticker_frame_interval_seconds()
pet.config.sticker_animation_speed = 2.0
assert abs(pet.sticker_frame_interval_seconds() - 0.06) < 0.001, pet.sticker_frame_interval_seconds()
assert abs(sticker_frame_interval_seconds(2.0) - 0.06) < 0.001
pet.config.sticker_animation_speed = DEFAULT_STICKER_ANIMATION_SPEED
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
assert chat.text_edit.testAttribute(Qt.WidgetAttribute.WA_InputMethodEnabled)
assert chat.session_search.testAttribute(Qt.WidgetAttribute.WA_InputMethodEnabled)
assert settings.prompt_edit.testAttribute(Qt.WidgetAttribute.WA_InputMethodEnabled)
assert settings.parent() is None
assert chat.parent() is None
assert todos.parent() is None
assert chat.windowType() != Qt.WindowType.Tool
assert menu.testAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
assert isinstance(preferred_x11_display(), str)
assert isinstance(fcitx_qt_plugin_files(), list)
im_diag = input_method_diagnostics()
assert isinstance(im_diag.get("qt_platforminputcontext_files", []), list)
assert isinstance(im_diag.get("qt_bundled_fcitx_plugin_files", []), list)
assert isinstance(im_diag.get("compatible_fcitx_qt_plugin_roots", []), list)
assert isinstance(im_diag.get("fcitx_plugin_compatibility", []), list)
settings.scroll_to_section(2)
assert any(button.text() == "互动" and button.objectName() == "railNavButtonActive" for button in nav_buttons)
assert settings.sticker_editor.to_sticker_sets() == {}
approvals = []
chat.control_plan_approved.connect(lambda plan_id: approvals.append(plan_id))
chat.add_control_plan("plan-1", "测试计划", "1. 读取状态", True)
chat.approve_control_plan("plan-1")
assert approvals == ["plan-1"], approvals
submissions = []
chat.conversation_context_check.setChecked(False)
chat.message_submitted.connect(
    lambda text, use_drop_context, session_id, use_conversation_context: submissions.append(
        (text, use_drop_context, session_id, use_conversation_context)
    )
)
chat.text_edit.setPlainText("新的问题")
chat.submit_message()
assert submissions == [("新的问题", False, "", False)], submissions
assert chat.waiting_for_reply
chat.add_assistant_message("新的回答")
chat.add_assistant_message("长回复\n" + ("detail " * 320))
assert any(button.text() == "完整回复" for button in chat.findChildren(QPushButton)), "long replies should expose a detail button"
chat.set_waiting(False)
assert not chat.waiting_for_reply
pet.open_chat()
assert pet.chat_dialog is not None
assert pet.chat_dialog.parent() is None
assert pet.chat_dialog.testAttribute(Qt.WidgetAttribute.WA_InputMethodEnabled)
assert pet.chat_dialog.windowType() != Qt.WindowType.Tool
pet.chat_dialog.close()
pet.chat_dialog = None
old_session = append_chat_turn("旧会话问题", "旧会话回答")
pet.chat_dialog = ChatDialog(
    sessions=list_conversation_sessions(),
    active_session=old_session,
    history=load_chat_history(old_session.session_id),
)
isolated_session = pet.session_for_context_policy("不带上下文的新问题", old_session.session_id, False)
assert isolated_session.session_id != old_session.session_id, (isolated_session, old_session)
assert isolated_session.message_count == 0, isolated_session
pet.show_user_message_for_session("不带上下文的新问题", isolated_session.session_id)
assert pet.chat_dialog.active_session_id == isolated_session.session_id
pet.chat_dialog = None
switched_session = create_conversation_session("切换后的会话")
pet.chat_dialog = ChatDialog(sessions=list_conversation_sessions(), active_session=managed_session, history=[])
pet.chat_dialog.set_waiting(True)
pet.show_agent_reply("切换前请求的异步返回", switched_session.session_id)
assert not pet.chat_dialog.waiting_for_reply
auth_session = create_conversation_session("授权接口测试")
pet.chat_dialog = ChatDialog(sessions=list_conversation_sessions(), active_session=auth_session, history=[])
for auth_text in (
    "/open https://example.com",
    "/write authorized-output.txt :: hello",
    f"/run --cwd {shlex.quote(str(ROOT))} {shlex.quote(sys.executable)} -c \"print('authorization')\"",
):
    auth_plan = build_control_plan(auth_text, str(ROOT))
    assert auth_plan is not None and auth_plan.requires_confirmation, auth_plan
    pet.request_control_authorization(auth_plan, auth_text, auth_session.session_id)
    assert auth_plan.plan_id in pet.pending_control_plans
    assert auth_plan.plan_id in pet.chat_dialog.control_plan_buttons
    assert not pet.chat_dialog.waiting_for_reply
    pet.pending_control_plans.pop(auth_plan.plan_id, None)
agent_plan, cleaned_reply = build_control_plan_from_agent_reply(
    "我需要先读取这个文件。\nCONTROL_REQUEST: 读取 D:\\DATA\\Desktop\\Nature_manuscript.txt",
    str(ROOT),
)
assert agent_plan is not None and agent_plan.requires_confirmation, agent_plan
assert agent_plan.action == "read_file", agent_plan
assert cleaned_reply == "我需要先读取这个文件。", cleaned_reply
pet.show_agent_control_request(agent_plan, cleaned_reply, "帮我看 Nature 文件", auth_session.session_id)
assert agent_plan.plan_id in pet.pending_control_plans
assert agent_plan.plan_id in pet.chat_dialog.control_plan_buttons
pet.pending_control_plans.pop(agent_plan.plan_id, None)
hint_plan, hint_cleaned_reply = build_control_plan_from_agent_reply(
    "我会通过内置电脑控制去读它：D:\\DATA\\Desktop\\Nature_manuscript.txt",
    str(ROOT),
)
assert hint_plan is not None and hint_plan.requires_confirmation, hint_plan
assert hint_plan.action == "read_file", hint_plan
assert hint_cleaned_reply.startswith("我会通过内置电脑控制"), hint_cleaned_reply
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
assert all(len(paths) == 16 for paths in bundled.values()), bundled
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
assert pet.idle_manager.suppressed_until > time.monotonic()
assert "README.md" in drop_context
assert "skipped sensitive filename" in drop_context
assert "skipped generated/cache folder" in drop_context
assert DROP_CONTEXT_PROMPT_HEADER in drop_prompt
due_items, remaining_items = reschedule_due_items(
    [{"id": "due", "text": "due", "due_ts": int(time.time()) - 1}],
    now_ts=int(time.time()),
    repeat_seconds=10,
)
assert len(due_items) == 1 and len(remaining_items) == 1
try:
    asyncio.run(WhatsAppPlatform().send_message("unused", "hello"))
except NotImplementedError:
    pass
else:
    raise AssertionError("WhatsAppPlatform should be a placeholder")

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
    loaded_custom_prompt = config_store.load_config(custom_prompt_path)
    assert loaded_custom_prompt.system_prompt == custom_prompt
    assert loaded_custom_prompt.schema_version == CURRENT_CONFIG_SCHEMA_VERSION
    assert (custom_prompt_path.parent / "config.v1.bak.json").exists()
    custom_messages = {
        "click_message": "抓紧, 谢谢!",
        "idle_message": "课题如何了? 抓紧谢谢!",
        "drop_message": "这种垃圾就不要让我看, 我每天很忙的!",
        "idle_seconds": 999999,
        "sticker_animation_speed": 99,
        "memory_enabled": "false",
    }
    custom_messages_path = Path(tmp) / "custom-messages" / "config.json"
    custom_messages_path.parent.mkdir(parents=True)
    custom_messages_path.write_text(__import__("json").dumps(custom_messages, ensure_ascii=False), encoding="utf-8")
    loaded_messages = config_store.load_config(custom_messages_path)
    assert loaded_messages.schema_version == CURRENT_CONFIG_SCHEMA_VERSION
    assert loaded_messages.click_message == custom_messages["click_message"]
    assert loaded_messages.idle_message == custom_messages["idle_message"]
    assert loaded_messages.drop_message == custom_messages["drop_message"]
    assert loaded_messages.idle_seconds == MAX_IDLE_SECONDS
    assert loaded_messages.sticker_animation_speed == MAX_STICKER_ANIMATION_SPEED
    assert loaded_messages.memory_enabled is False
    assert loaded_messages.control_enabled is True
    configured_desktop = Path(tmp) / "configured-desktop"
    configured_desktop.mkdir()
    (Path(tmp) / "user-dirs.dirs").write_text(f'XDG_DESKTOP_DIR="{configured_desktop}"\n', encoding="utf-8")
    assert desktop_path() == configured_desktop.resolve(strict=False)
    control_root = Path(tmp) / "control-root"
    control_root.mkdir()
    (control_root / "input.txt").write_text("alpha\nbeta\n", encoding="utf-8")
    (configured_desktop / "Nature_manuscript.txt").write_text("draft abstract", encoding="utf-8")
    sys_plan = build_control_plan("/sys", str(control_root))
    assert sys_plan is not None and sys_plan.permission == PermissionLevel.READ_ONLY
    assert execute_control_plan(sys_plan).ok
    ls_plan = build_control_plan("/ls .", str(control_root))
    assert ls_plan is not None and execute_control_plan(ls_plan).ok
    read_plan = build_control_plan("/read input.txt", str(control_root))
    assert read_plan is not None
    read_result = execute_control_plan(read_plan)
    assert read_result.ok and "alpha" in read_result.output
    nl_read_plan = build_control_plan("帮我看一下桌面的 Nature_manuscript.txt", str(control_root))
    assert nl_read_plan is not None and nl_read_plan.requires_confirmation
    assert nl_read_plan.action == "read_file", nl_read_plan
    assert Path(str(nl_read_plan.args["path"])) == configured_desktop.resolve(strict=False) / "Nature_manuscript.txt"
    nl_read_result = execute_control_plan(nl_read_plan)
    assert nl_read_result.ok and "draft abstract" in nl_read_result.output
    nl_list_plan = build_control_plan("请列出桌面文件", str(control_root))
    assert nl_list_plan is not None and nl_list_plan.requires_confirmation
    assert nl_list_plan.action == "list_dir", nl_list_plan
    assert Path(str(nl_list_plan.args["path"])) == configured_desktop.resolve(strict=False)
    nl_list_result = execute_control_plan(nl_list_plan)
    assert nl_list_result.ok and "Nature_manuscript.txt" in nl_list_result.output
    copied_no_card_text = "可以，但我这边没弹出 Computer control 的文件读取确认卡，先检查一下设置里是否开启了电脑控制权限。 开启后我就能帮你列桌面文件；大家抓紧交任务！服务器很空了！"
    copied_no_card_plan = build_control_plan(copied_no_card_text, str(control_root))
    assert copied_no_card_plan is not None and copied_no_card_plan.requires_confirmation
    assert copied_no_card_plan.action == "list_dir", copied_no_card_plan
    explicit_path_plan = build_control_plan(r"这个路径明确了：`D:\DATA\Desktop\Nature_manuscript.txt`", str(control_root))
    assert explicit_path_plan is not None and explicit_path_plan.requires_confirmation
    assert explicit_path_plan.action == "read_file", explicit_path_plan
    assert str(explicit_path_plan.args["path"]).endswith(r"D:\DATA\Desktop\Nature_manuscript.txt")
    system_prompt = agent_system_prompt(AgentConfig(system_prompt="自定义风格"))
    assert "读取用户本机文件前应通过内置电脑控制确认卡让用户选择" in system_prompt
    search_plan = build_control_plan("/search beta .", str(control_root))
    assert search_plan is not None
    search_result = execute_control_plan(search_plan)
    assert search_result.ok and "input.txt" in search_result.output
    write_plan = build_control_plan("/write output.txt :: hello", str(control_root))
    assert write_plan is not None and write_plan.requires_confirmation
    write_result = execute_control_plan(write_plan)
    assert write_result.ok and (control_root / "output.txt").read_text(encoding="utf-8").strip() == "hello"
    nl_plan = build_control_plan("请在桌面创建一个文件 `mentor-note.txt`，内容是「hello mentor」", str(control_root))
    assert nl_plan is not None and nl_plan.requires_confirmation
    assert nl_plan.action == "write_file", nl_plan
    assert Path(str(nl_plan.args["path"])) == configured_desktop.resolve(strict=False) / "mentor-note.txt"
    assert nl_plan.args["content"] == "hello mentor"
    assert "需要你的授权" in nl_plan.summary()
    assert "允许本次" in nl_plan.summary()
    nl_result = execute_control_plan(nl_plan)
    assert nl_result.ok and (configured_desktop / "mentor-note.txt").read_text(encoding="utf-8").strip() == "hello mentor"
    safe_name_plan = build_control_plan("请在桌面创建 `../bad.txt`，内容是「safe」", str(control_root))
    assert safe_name_plan is not None
    safe_name_path = Path(str(safe_name_plan.args["path"]))
    assert safe_name_path.parent == configured_desktop.resolve(strict=False)
    assert ".." not in safe_name_path.name
    assert build_control_plan("我们聊一下怎么设计桌面应用和文件结构", str(control_root)) is None
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
