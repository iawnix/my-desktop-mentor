"""Todo reminder service for the pet UI."""
from __future__ import annotations

import time

from ..constants import DEFAULT_TODO_REPEAT_SECONDS, MAX_TODO_REPEAT_SECONDS, MIN_TODO_REPEAT_SECONDS
from ..cron.scheduler import reschedule_due_items
from ..state.todos import due_todos, load_todos, remove_todos_by_ids, save_todos


class PetTodoService:
    def repeat_seconds(self, value: object) -> int:
        try:
            return max(
                MIN_TODO_REPEAT_SECONDS,
                min(MAX_TODO_REPEAT_SECONDS, int(value or DEFAULT_TODO_REPEAT_SECONDS)),
            )
        except Exception:
            return DEFAULT_TODO_REPEAT_SECONDS

    def has_due_items(self, *, now_ts: int | None = None) -> bool:
        now_ts = int(time.time()) if now_ts is None else now_ts
        return bool(due_todos(load_todos(), now_ts))

    def pop_due_reminders(self, *, repeat_seconds: int, now_ts: int | None = None) -> list[dict[str, object]]:
        now_ts = int(time.time()) if now_ts is None else now_ts
        todos = load_todos()
        due, remaining = reschedule_due_items(todos, now_ts=now_ts, repeat_seconds=repeat_seconds)
        if due:
            save_todos(remaining)
        return due

    def acknowledge(self, todo_id: str) -> None:
        if not todo_id:
            return
        save_todos(remove_todos_by_ids(load_todos(), [todo_id]))

    def active_ids(self) -> set[str]:
        return {str(todo["id"]) for todo in load_todos()}
