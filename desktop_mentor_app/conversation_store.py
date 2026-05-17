"""Local conversation sessions and lightweight memory."""
from __future__ import annotations

import json
import secrets
import time
from dataclasses import dataclass, field
from pathlib import Path

from .config_store import chat_history_path, config_path, memory_path

CHAT_HISTORY_DISPLAY_LIMIT = 80
CHAT_HISTORY_TEXT_LIMIT = 6000
CONVERSATION_MAX_MESSAGES = 800
SESSION_TITLE_LIMIT = 34
SESSION_SUMMARY_LIMIT = 260
SESSION_MEMORY_LIMIT = 20
SESSION_MEMORY_TEXT_LIMIT = 180


@dataclass(frozen=True)
class ChatHistoryMessage:
    role: str
    content: str
    ts: int


@dataclass
class ConversationSession:
    session_id: str
    title: str
    created_at: int
    updated_at: int
    message_count: int = 0
    summary: str = ""
    memory_items: list[str] = field(default_factory=list)


def compact_history_text(text: str, limit: int = CHAT_HISTORY_TEXT_LIMIT) -> str:
    clean = str(text or "").strip()
    if len(clean) <= limit:
        return clean
    return clean[: max(1, limit - 1)] + "…"


def compact_inline_text(text: str, limit: int) -> str:
    return compact_history_text(" ".join(str(text or "").split()), limit)


def conversation_root() -> Path:
    return config_path().parent / "conversations"


def session_index_path() -> Path:
    return conversation_root() / "sessions.json"


def active_session_path() -> Path:
    return conversation_root() / "active_session.txt"


def safe_session_id(session_id: str) -> str:
    return "".join(ch for ch in str(session_id or "") if ch.isalnum() or ch in {"-", "_"})[:64]


def session_messages_path(session_id: str) -> Path:
    clean_id = safe_session_id(session_id)
    if not clean_id:
        clean_id = new_session_id()
    return conversation_root() / f"{clean_id}.jsonl"


def new_session_id() -> str:
    return time.strftime("%Y%m%d-%H%M%S") + "-" + secrets.token_hex(3)


def format_session_time(timestamp: int) -> str:
    try:
        return time.strftime("%m-%d %H:%M", time.localtime(int(timestamp)))
    except Exception:
        return ""


def title_from_text(text: str) -> str:
    title = compact_inline_text(text, SESSION_TITLE_LIMIT)
    return title or "新会话"


def session_from_dict(item: object) -> ConversationSession | None:
    if not isinstance(item, dict):
        return None
    session_id = safe_session_id(str(item.get("id", "") or item.get("session_id", "")))
    if not session_id:
        return None
    now = int(time.time())
    try:
        created_at = int(item.get("created_at", now))
    except Exception:
        created_at = now
    try:
        updated_at = int(item.get("updated_at", created_at))
    except Exception:
        updated_at = created_at
    try:
        message_count = max(0, int(item.get("message_count", 0)))
    except Exception:
        message_count = 0
    memory_items = []
    if isinstance(item.get("memory_items"), list):
        memory_items = [
            compact_inline_text(value, SESSION_MEMORY_TEXT_LIMIT)
            for value in item["memory_items"]
            if str(value or "").strip()
        ][:SESSION_MEMORY_LIMIT]
    return ConversationSession(
        session_id=session_id,
        title=title_from_text(str(item.get("title", "") or "新会话")),
        created_at=created_at,
        updated_at=updated_at,
        message_count=message_count,
        summary=compact_inline_text(str(item.get("summary", "") or ""), SESSION_SUMMARY_LIMIT),
        memory_items=memory_items,
    )


def session_to_dict(session: ConversationSession) -> dict[str, object]:
    return {
        "id": safe_session_id(session.session_id),
        "title": title_from_text(session.title),
        "created_at": int(session.created_at),
        "updated_at": int(session.updated_at),
        "message_count": int(session.message_count),
        "summary": compact_inline_text(session.summary, SESSION_SUMMARY_LIMIT),
        "memory_items": [
            compact_inline_text(item, SESSION_MEMORY_TEXT_LIMIT)
            for item in session.memory_items
            if str(item or "").strip()
        ][:SESSION_MEMORY_LIMIT],
    }


def read_session_index() -> list[ConversationSession]:
    path = session_index_path()
    if not path.exists():
        return []
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return []
    raw_sessions = data.get("sessions", data) if isinstance(data, dict) else data
    if not isinstance(raw_sessions, list):
        return []
    sessions: list[ConversationSession] = []
    seen: set[str] = set()
    for item in raw_sessions:
        session = session_from_dict(item)
        if session is None or session.session_id in seen:
            continue
        seen.add(session.session_id)
        sessions.append(session)
    return sorted(sessions, key=lambda item: item.updated_at, reverse=True)


def write_session_index(sessions: list[ConversationSession]) -> Path:
    path = session_index_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    ordered = sorted(sessions, key=lambda item: item.updated_at, reverse=True)
    data = {"version": 1, "sessions": [session_to_dict(session) for session in ordered]}
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    return path


def read_active_session_id() -> str:
    path = active_session_path()
    try:
        return safe_session_id(path.read_text(encoding="utf-8").strip())
    except OSError:
        return ""


def set_active_session(session_id: str) -> str:
    clean_id = safe_session_id(session_id)
    if not clean_id:
        return ""
    path = active_session_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(clean_id, encoding="utf-8")
    return clean_id


def parse_chat_history_line(line: str) -> ChatHistoryMessage | None:
    try:
        item = json.loads(line)
    except json.JSONDecodeError:
        return None
    role = str(item.get("role", "")).strip()
    content = str(item.get("content", "")).strip()
    if role not in {"user", "assistant"} or not content:
        return None
    try:
        ts = int(item.get("ts", 0))
    except Exception:
        ts = 0
    return ChatHistoryMessage(role=role, content=compact_history_text(content), ts=ts or int(time.time()))


def read_message_file(path: Path) -> list[ChatHistoryMessage]:
    if not path.exists():
        return []
    messages: list[ChatHistoryMessage] = []
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except OSError:
        return []
    for line in lines:
        if not line.strip():
            continue
        message = parse_chat_history_line(line)
        if message is not None:
            messages.append(message)
    return messages


def write_message_file(session_id: str, messages: list[ChatHistoryMessage]) -> Path:
    path = session_messages_path(session_id)
    path.parent.mkdir(parents=True, exist_ok=True)
    retained = messages[-CONVERSATION_MAX_MESSAGES:]
    with path.open("w", encoding="utf-8") as handle:
        for message in retained:
            handle.write(
                json.dumps(
                    {
                        "ts": int(message.ts),
                        "role": message.role,
                        "content": compact_history_text(message.content),
                    },
                    ensure_ascii=False,
                )
                + "\n"
            )
    return path


def read_legacy_messages() -> list[ChatHistoryMessage]:
    path = chat_history_path()
    if path.exists():
        return read_message_file(path)
    return read_message_file(memory_path())


def summarize_messages(messages: list[ChatHistoryMessage]) -> str:
    user_texts = [compact_inline_text(message.content, 90) for message in messages if message.role == "user"]
    if not user_texts:
        return ""
    return compact_inline_text(" / ".join(user_texts[-3:]), SESSION_SUMMARY_LIMIT)


def extract_memory_items(user_text: str, assistant_text: str) -> list[str]:
    source = compact_inline_text(user_text, SESSION_MEMORY_TEXT_LIMIT)
    if not source:
        return []
    keywords = (
        "记住",
        "以后",
        "之后",
        "偏好",
        "喜欢",
        "不喜欢",
        "不要",
        "别",
        "默认",
        "项目",
        "目标",
        "约束",
        "规范",
        "接口",
        "素材",
    )
    if any(keyword in source for keyword in keywords):
        return [source]
    return []


def update_memory_items(existing: list[str], user_text: str, assistant_text: str) -> list[str]:
    merged = [compact_inline_text(item, SESSION_MEMORY_TEXT_LIMIT) for item in existing if str(item or "").strip()]
    for item in extract_memory_items(user_text, assistant_text):
        if item and item not in merged:
            merged.append(item)
    return merged[-SESSION_MEMORY_LIMIT:]


def migrate_legacy_history() -> ConversationSession | None:
    if read_session_index():
        return None
    messages = read_legacy_messages()
    if not messages:
        return None
    now = int(time.time())
    first_user = next((message.content for message in messages if message.role == "user"), "")
    session = ConversationSession(
        session_id=new_session_id(),
        title=title_from_text(first_user or "旧会话"),
        created_at=messages[0].ts or now,
        updated_at=messages[-1].ts or now,
        message_count=len(messages),
        summary=summarize_messages(messages),
        memory_items=[],
    )
    write_message_file(session.session_id, messages)
    write_session_index([session])
    set_active_session(session.session_id)
    return session


def list_conversation_sessions() -> list[ConversationSession]:
    sessions = read_session_index()
    if not sessions:
        migrated = migrate_legacy_history()
        if migrated is not None:
            sessions = [migrated]
    return sorted(sessions, key=lambda item: item.updated_at, reverse=True)


def get_session(session_id: str) -> ConversationSession | None:
    clean_id = safe_session_id(session_id)
    for session in list_conversation_sessions():
        if session.session_id == clean_id:
            return session
    return None


def create_conversation_session(title: str = "") -> ConversationSession:
    now = int(time.time())
    session = ConversationSession(
        session_id=new_session_id(),
        title=title_from_text(title or "新会话"),
        created_at=now,
        updated_at=now,
        message_count=0,
    )
    sessions = [session] + [item for item in read_session_index() if item.session_id != session.session_id]
    write_session_index(sessions)
    write_message_file(session.session_id, [])
    set_active_session(session.session_id)
    return session


def ensure_active_session() -> ConversationSession:
    sessions = list_conversation_sessions()
    active_id = read_active_session_id()
    for session in sessions:
        if session.session_id == active_id:
            return session
    if sessions:
        set_active_session(sessions[0].session_id)
        return sessions[0]
    return create_conversation_session()


def load_chat_history(session_id: str | None = None, limit: int = CHAT_HISTORY_DISPLAY_LIMIT) -> list[ChatHistoryMessage]:
    active_id = session_id or read_active_session_id()
    session = get_session(active_id) if active_id else ensure_active_session()
    if session is None:
        session = ensure_active_session()
    messages = read_message_file(session_messages_path(session.session_id))
    if limit <= 0:
        return messages
    return messages[-limit:]


def refresh_session_metadata(session_id: str, messages: list[ChatHistoryMessage], user_text: str = "", assistant_text: str = "") -> ConversationSession:
    clean_id = safe_session_id(session_id)
    sessions = read_session_index()
    now = int(time.time())
    target: ConversationSession | None = None
    retained: list[ConversationSession] = []
    for session in sessions:
        if session.session_id == clean_id:
            target = session
        else:
            retained.append(session)
    if target is None:
        target = ConversationSession(clean_id or new_session_id(), title_from_text(user_text or "新会话"), now, now)
    if user_text and target.message_count == 0:
        target.title = title_from_text(user_text)
    target.updated_at = messages[-1].ts if messages else now
    target.message_count = len(messages)
    target.summary = summarize_messages(messages)
    target.memory_items = update_memory_items(target.memory_items, user_text, assistant_text)
    write_session_index([target] + retained)
    set_active_session(target.session_id)
    return target


def append_chat_turn(user_text: str, assistant_text: str, session_id: str | None = None) -> ConversationSession:
    session = get_session(session_id or read_active_session_id()) if session_id or read_active_session_id() else ensure_active_session()
    if session is None:
        session = create_conversation_session(user_text)
    timestamp = int(time.time())
    messages = read_message_file(session_messages_path(session.session_id))
    messages.extend(
        [
            ChatHistoryMessage("user", compact_history_text(user_text), timestamp),
            ChatHistoryMessage("assistant", compact_history_text(assistant_text), timestamp),
        ]
    )
    messages = messages[-CONVERSATION_MAX_MESSAGES:]
    write_message_file(session.session_id, messages)
    return refresh_session_metadata(session.session_id, messages, user_text, assistant_text)


def clear_chat_history(session_id: str | None = None) -> ConversationSession:
    session = get_session(session_id or read_active_session_id()) if session_id or read_active_session_id() else ensure_active_session()
    if session is None:
        session = create_conversation_session()
    write_message_file(session.session_id, [])
    session.message_count = 0
    session.summary = ""
    session.memory_items = []
    session.updated_at = int(time.time())
    sessions = [session] + [item for item in read_session_index() if item.session_id != session.session_id]
    write_session_index(sessions)
    set_active_session(session.session_id)
    return session


def delete_conversation_session(session_id: str) -> ConversationSession:
    clean_id = safe_session_id(session_id)
    sessions = [session for session in read_session_index() if session.session_id != clean_id]
    try:
        session_messages_path(clean_id).unlink()
    except OSError:
        pass
    write_session_index(sessions)
    if sessions:
        set_active_session(sessions[0].session_id)
        return sessions[0]
    return create_conversation_session()


def build_conversation_memory_context(session_id: str, limit_turns: int) -> str:
    session = get_session(session_id)
    if session is None:
        return ""
    messages = load_chat_history(session.session_id, max(2, int(limit_turns) * 2))
    parts: list[str] = []
    if session.summary:
        parts.append("会话摘要:\n" + session.summary)
    if session.memory_items:
        parts.append("会话记忆:\n" + "\n".join(f"- {item}" for item in session.memory_items))
    if messages:
        recent = []
        for message in messages:
            role = "用户" if message.role == "user" else "导师"
            recent.append(f"{role}: {compact_inline_text(message.content, 500)}")
        parts.append("最近会话:\n" + "\n".join(recent))
    if not parts:
        return ""
    return "以下是本地会话管理器提供的上下文，只用于延续当前会话，不要逐字复述:\n\n" + "\n\n".join(parts)
