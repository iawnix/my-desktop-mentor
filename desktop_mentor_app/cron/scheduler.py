"""Reminder scheduling helpers."""
from __future__ import annotations

from ..todo_store import due_todos, future_todos, remove_todos_by_ids, rescheduled_todo


def reschedule_due_items(
    todos: list[dict[str, object]],
    *,
    now_ts: int,
    repeat_seconds: int,
) -> tuple[list[dict[str, object]], list[dict[str, object]]]:
    due = due_todos(todos, now_ts)
    if not due:
        return [], todos
    next_due_ts = now_ts + repeat_seconds
    remaining = future_todos(todos, now_ts)
    for todo in due:
        remaining = remove_todos_by_ids(remaining, [str(todo["id"])])
        remaining.append(rescheduled_todo(todo, next_due_ts))
    return due, remaining
