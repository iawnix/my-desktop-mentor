"""Todo storage and normalization."""
from __future__ import annotations

import json
import time
from collections.abc import Iterable
from pathlib import Path

from .config_store import todos_path


def load_todos(path: Path | None = None) -> list[dict[str, object]]:
    target = path or todos_path()
    if not target.exists():
        return []
    try:
        raw_items = json.loads(target.read_text(encoding="utf-8"))
    except Exception:
        return []
    if not isinstance(raw_items, list):
        return []
    todos: list[dict[str, object]] = []
    for item in raw_items:
        if not isinstance(item, dict):
            continue
        text = str(item.get("text", "")).strip()
        try:
            due_ts = int(item.get("due_ts", 0))
        except Exception:
            continue
        if not text or due_ts <= 0:
            continue
        todo_id = str(item.get("id") or f"{due_ts}-{len(todos)}")
        todos.append({"id": todo_id, "text": text, "due_ts": due_ts})
    return sorted(todos, key=lambda row: int(row["due_ts"]))


def save_todos(todos: list[dict[str, object]], path: Path | None = None) -> Path:
    target = path or todos_path()
    target.parent.mkdir(parents=True, exist_ok=True)
    clean_items = load_todos_from_items(todos)
    target.write_text(json.dumps(clean_items, ensure_ascii=False, indent=2), encoding="utf-8")
    return target


def load_todos_from_items(items: list[dict[str, object]]) -> list[dict[str, object]]:
    todos: list[dict[str, object]] = []
    for item in items:
        text = str(item.get("text", "")).strip()
        try:
            due_ts = int(item.get("due_ts", 0))
        except Exception:
            continue
        if not text or due_ts <= 0:
            continue
        todos.append({"id": str(item.get("id") or f"{due_ts}-{len(todos)}"), "text": text, "due_ts": due_ts})
    return sorted(todos, key=lambda row: int(row["due_ts"]))


def due_todos(todos: list[dict[str, object]], now_ts: int | None = None) -> list[dict[str, object]]:
    now_value = int(now_ts if now_ts is not None else time.time())
    return [todo for todo in todos if int(todo["due_ts"]) <= now_value]


def future_todos(todos: list[dict[str, object]], now_ts: int | None = None) -> list[dict[str, object]]:
    now_value = int(now_ts if now_ts is not None else time.time())
    return [todo for todo in todos if int(todo["due_ts"]) > now_value]


def rescheduled_todo(todo: dict[str, object], due_ts: int) -> dict[str, object]:
    return {
        "id": str(todo["id"]),
        "text": str(todo["text"]),
        "due_ts": int(due_ts),
    }


def remove_todos_by_ids(todos: list[dict[str, object]], todo_ids: Iterable[str]) -> list[dict[str, object]]:
    ids = {str(todo_id) for todo_id in todo_ids}
    return [todo for todo in todos if str(todo["id"]) not in ids]


def format_due_time(due_ts: int) -> str:
    return time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(due_ts))
