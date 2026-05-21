"""User-level long-term memory storage."""
from __future__ import annotations

import json
import logging
import secrets
import time
from dataclasses import dataclass
from pathlib import Path

from ..config.store import user_memory_path

LOGGER = logging.getLogger(__name__)

USER_MEMORY_STORAGE_LIMIT = 240
USER_MEMORY_TEXT_LIMIT = 420
USER_MEMORY_CONTEXT_TEXT_LIMIT = 240


@dataclass
class UserMemory:
    memory_id: str
    text: str
    created_at: int
    updated_at: int
    source: str = "manual"
    session_id: str = ""
    enabled: bool = True


def new_memory_id() -> str:
    return time.strftime("%Y%m%d-%H%M%S") + "-" + secrets.token_hex(3)


def compact_memory_text(text: str, limit: int = USER_MEMORY_TEXT_LIMIT) -> str:
    clean = " ".join(str(text or "").split())
    if len(clean) <= limit:
        return clean
    return clean[: max(1, limit - 1)].rstrip() + "…"


def normalize_memory_text(text: str) -> str:
    return compact_memory_text(text, USER_MEMORY_TEXT_LIMIT).casefold()


def bool_from_memory_value(value: object, default: bool = True) -> bool:
    if isinstance(value, str):
        clean = value.strip().lower()
        if clean in {"0", "false", "no", "off"}:
            return False
        if clean in {"1", "true", "yes", "on"}:
            return True
        return default
    if value is None:
        return default
    return bool(value)


def memory_from_dict(item: object) -> UserMemory | None:
    if not isinstance(item, dict):
        return None
    memory_id = "".join(ch for ch in str(item.get("id", "") or item.get("memory_id", "")) if ch.isalnum() or ch in {"-", "_"})[:64]
    text = compact_memory_text(str(item.get("text", "") or ""))
    if not memory_id or not text:
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
    return UserMemory(
        memory_id=memory_id,
        text=text,
        created_at=created_at,
        updated_at=updated_at,
        source=compact_memory_text(str(item.get("source", "") or "manual"), 48),
        session_id=compact_memory_text(str(item.get("session_id", "") or ""), 80),
        enabled=bool_from_memory_value(item.get("enabled", True), True),
    )


def memory_to_dict(memory: UserMemory) -> dict[str, object]:
    return {
        "id": memory.memory_id,
        "text": compact_memory_text(memory.text),
        "created_at": int(memory.created_at),
        "updated_at": int(memory.updated_at),
        "source": compact_memory_text(memory.source, 48),
        "session_id": compact_memory_text(memory.session_id, 80),
        "enabled": bool(memory.enabled),
    }


def load_user_memories(path: Path | None = None) -> list[UserMemory]:
    target = path or user_memory_path()
    if not target.exists():
        return []
    try:
        data = json.loads(target.read_text(encoding="utf-8"))
    except Exception as exc:
        LOGGER.warning("failed to read user memory %s: %s", target, exc)
        return []
    raw_items = data.get("memories", data) if isinstance(data, dict) else data
    if not isinstance(raw_items, list):
        return []
    memories: list[UserMemory] = []
    seen: set[str] = set()
    for item in raw_items:
        memory = memory_from_dict(item)
        if memory is None or memory.memory_id in seen:
            continue
        seen.add(memory.memory_id)
        memories.append(memory)
    return sorted(memories, key=lambda item: item.updated_at, reverse=True)[:USER_MEMORY_STORAGE_LIMIT]


def save_user_memories(memories: list[UserMemory], path: Path | None = None) -> Path:
    target = path or user_memory_path()
    target.parent.mkdir(parents=True, exist_ok=True)
    ordered = sorted(memories, key=lambda item: item.updated_at, reverse=True)[:USER_MEMORY_STORAGE_LIMIT]
    data = {"version": 1, "memories": [memory_to_dict(memory) for memory in ordered]}
    target.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    return target


def add_user_memory(text: str, *, source: str = "manual", session_id: str = "", enabled: bool = True) -> UserMemory | None:
    clean = compact_memory_text(text)
    if not clean:
        return None
    memories = load_user_memories()
    normalized = normalize_memory_text(clean)
    now = int(time.time())
    retained: list[UserMemory] = []
    updated: UserMemory | None = None
    for memory in memories:
        if normalize_memory_text(memory.text) == normalized:
            updated = UserMemory(memory.memory_id, clean, memory.created_at, now, source or memory.source, session_id or memory.session_id, enabled)
            retained.append(updated)
        else:
            retained.append(memory)
    if updated is None:
        updated = UserMemory(new_memory_id(), clean, now, now, source or "manual", session_id, enabled)
        retained.insert(0, updated)
    save_user_memories(retained)
    return updated


def update_user_memory(memory_id: str, *, text: str | None = None, enabled: bool | None = None) -> UserMemory | None:
    clean_id = "".join(ch for ch in str(memory_id or "") if ch.isalnum() or ch in {"-", "_"})[:64]
    memories = load_user_memories()
    now = int(time.time())
    updated: UserMemory | None = None
    retained: list[UserMemory] = []
    for memory in memories:
        if memory.memory_id != clean_id:
            retained.append(memory)
            continue
        new_text = compact_memory_text(memory.text if text is None else text)
        if not new_text:
            continue
        updated = UserMemory(
            memory.memory_id,
            new_text,
            memory.created_at,
            now,
            memory.source,
            memory.session_id,
            memory.enabled if enabled is None else bool(enabled),
        )
        retained.append(updated)
    save_user_memories(retained)
    return updated


def delete_user_memory(memory_id: str) -> bool:
    clean_id = "".join(ch for ch in str(memory_id or "") if ch.isalnum() or ch in {"-", "_"})[:64]
    memories = load_user_memories()
    retained = [memory for memory in memories if memory.memory_id != clean_id]
    if len(retained) == len(memories):
        return False
    save_user_memories(retained)
    return True


def set_user_memory_enabled(memory_id: str, enabled: bool) -> UserMemory | None:
    return update_user_memory(memory_id, enabled=enabled)


def clear_user_memories() -> Path:
    return save_user_memories([])


def extract_user_memory_candidates(user_text: str, assistant_text: str = "") -> list[str]:
    source = compact_memory_text(user_text, USER_MEMORY_TEXT_LIMIT)
    if not source:
        return []
    triggers = (
        "记住",
        "以后",
        "之后",
        "偏好",
        "喜欢",
        "不喜欢",
        "不要",
        "别",
        "默认",
        "我希望",
        "我的",
        "项目",
        "目标",
        "约束",
        "规范",
    )
    if not any(trigger in source for trigger in triggers):
        return []
    candidates: list[str] = []
    for chunk in source.replace("；", "\n").replace("。", "\n").replace(";", "\n").splitlines():
        item = compact_memory_text(chunk)
        if len(item) >= 6 and item not in candidates:
            candidates.append(item)
        if len(candidates) >= 4:
            break
    return candidates


def record_user_memory_turn(user_text: str, assistant_text: str = "", *, session_id: str = "") -> list[UserMemory]:
    recorded: list[UserMemory] = []
    for candidate in extract_user_memory_candidates(user_text, assistant_text):
        memory = add_user_memory(candidate, source="chat", session_id=session_id, enabled=True)
        if memory is not None:
            recorded.append(memory)
    return recorded


def build_user_memory_context(prompt: str = "", limit: int = 12) -> str:
    try:
        max_items = max(1, int(limit))
    except Exception:
        max_items = 12
    enabled = [memory for memory in load_user_memories() if memory.enabled and memory.text]
    if not enabled:
        return ""
    prompt_key = normalize_memory_text(prompt)
    relevant = [memory for memory in enabled if prompt_key and any(token and token in normalize_memory_text(memory.text) for token in prompt_key.split())]
    recent = [memory for memory in enabled if memory not in relevant]
    selected = (relevant + recent)[:max_items]
    if not selected:
        return ""
    lines = [f"- {compact_memory_text(memory.text, USER_MEMORY_CONTEXT_TEXT_LIMIT)}" for memory in selected]
    return "用户长期记忆:\n" + "\n".join(lines)
