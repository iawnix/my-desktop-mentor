"""Structured local agent state.

This store is intentionally separate from the chat JSONL files. Chat history is
for replaying a conversation; this database tracks agent work state, memory
candidates, and tool evidence that can be reused across turns.
"""
from __future__ import annotations

import json
import logging
import secrets
import sqlite3
import time
from contextlib import closing
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING

from ..config.store import agent_store_path

if TYPE_CHECKING:
    from ..tools.types import ControlPlan, ControlResult

LOGGER = logging.getLogger(__name__)

AGENT_STORE_SCHEMA_VERSION = 1
TEXT_LIMIT = 8000
INLINE_TEXT_LIMIT = 420
MEMORY_CANDIDATE_LIMIT = 12

TASK_STATUS_ACTIVE = "active"
TASK_STATUS_AWAITING_TOOL = "awaiting_tool"
TASK_STATUS_CANCELLED = "cancelled"
TASK_STATUS_DONE = "done"
TASK_STATUS_ERROR = "error"

MEMORY_STATUS_PENDING = "pending"
MEMORY_STATUS_APPROVED = "approved"
MEMORY_STATUS_IGNORED = "ignored"


@dataclass(frozen=True)
class AgentTaskRun:
    task_id: str
    session_id: str
    user_prompt: str
    status: str
    goal: str
    created_at: int
    updated_at: int
    use_context: bool = True
    agent_prompt: str = ""
    assistant_text: str = ""
    error: str = ""


@dataclass(frozen=True)
class AgentMemoryCandidate:
    candidate_id: str
    session_id: str
    task_id: str
    text: str
    kind: str
    scope: str
    source: str
    confidence: float
    importance: float
    sensitivity: str
    status: str
    evidence_id: str
    created_at: int
    updated_at: int


@dataclass(frozen=True)
class AgentToolEvent:
    event_id: str
    session_id: str
    task_id: str
    plan_id: str
    action: str
    title: str
    event: str
    ok: bool | None
    summary: str
    created_at: int


def now_ts() -> int:
    return int(time.time())


def new_agent_id(prefix: str) -> str:
    clean_prefix = "".join(ch for ch in str(prefix or "id") if ch.isalnum() or ch in {"-", "_"})[:20] or "id"
    return f"{clean_prefix}-{time.strftime('%Y%m%d-%H%M%S')}-{secrets.token_hex(4)}"


def compact_agent_text(text: str, limit: int = TEXT_LIMIT) -> str:
    clean = str(text or "").strip()
    if len(clean) <= limit:
        return clean
    return clean[: max(1, limit - 1)].rstrip() + "…"


def compact_inline_text(text: str, limit: int = INLINE_TEXT_LIMIT) -> str:
    return compact_agent_text(" ".join(str(text or "").split()), limit)


def normalize_text(text: str) -> str:
    return compact_inline_text(text, 1200).casefold()


def connect_agent_store(path: Path | None = None) -> sqlite3.Connection:
    target = path or agent_store_path()
    target.parent.mkdir(parents=True, exist_ok=True)
    connection = sqlite3.connect(str(target))
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys = ON")
    initialize_agent_store(connection)
    return connection


def initialize_agent_store(connection: sqlite3.Connection | None = None) -> None:
    owns_connection = connection is None
    if owns_connection:
        agent_store_path().parent.mkdir(parents=True, exist_ok=True)
    conn = connection or sqlite3.connect(str(agent_store_path()))
    try:
        conn.execute("PRAGMA foreign_keys = ON")
        conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS meta (
                key TEXT PRIMARY KEY,
                value TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS task_runs (
                task_id TEXT PRIMARY KEY,
                session_id TEXT NOT NULL,
                user_prompt TEXT NOT NULL,
                agent_prompt TEXT NOT NULL DEFAULT '',
                assistant_text TEXT NOT NULL DEFAULT '',
                goal TEXT NOT NULL DEFAULT '',
                status TEXT NOT NULL,
                use_context INTEGER NOT NULL DEFAULT 1,
                error TEXT NOT NULL DEFAULT '',
                created_at INTEGER NOT NULL,
                updated_at INTEGER NOT NULL
            );

            CREATE INDEX IF NOT EXISTS idx_task_runs_session_updated
                ON task_runs(session_id, updated_at DESC);

            CREATE TABLE IF NOT EXISTS tool_events (
                event_id TEXT PRIMARY KEY,
                session_id TEXT NOT NULL,
                task_id TEXT NOT NULL DEFAULT '',
                plan_id TEXT NOT NULL DEFAULT '',
                action TEXT NOT NULL DEFAULT '',
                title TEXT NOT NULL DEFAULT '',
                event TEXT NOT NULL,
                ok INTEGER,
                summary TEXT NOT NULL DEFAULT '',
                payload_json TEXT NOT NULL DEFAULT '{}',
                created_at INTEGER NOT NULL
            );

            CREATE INDEX IF NOT EXISTS idx_tool_events_session_created
                ON tool_events(session_id, created_at DESC);

            CREATE TABLE IF NOT EXISTS memory_candidates (
                candidate_id TEXT PRIMARY KEY,
                session_id TEXT NOT NULL DEFAULT '',
                task_id TEXT NOT NULL DEFAULT '',
                text TEXT NOT NULL,
                normalized_text TEXT NOT NULL,
                kind TEXT NOT NULL DEFAULT 'preference',
                scope TEXT NOT NULL DEFAULT 'global',
                source TEXT NOT NULL DEFAULT 'chat',
                confidence REAL NOT NULL DEFAULT 0.6,
                importance REAL NOT NULL DEFAULT 0.5,
                sensitivity TEXT NOT NULL DEFAULT 'normal',
                status TEXT NOT NULL DEFAULT 'pending',
                evidence_id TEXT NOT NULL DEFAULT '',
                created_at INTEGER NOT NULL,
                updated_at INTEGER NOT NULL,
                UNIQUE(normalized_text, scope, source)
            );

            CREATE INDEX IF NOT EXISTS idx_memory_candidates_status_updated
                ON memory_candidates(status, updated_at DESC);
            """
        )
        conn.execute(
            "INSERT OR REPLACE INTO meta(key, value) VALUES(?, ?)",
            ("schema_version", str(AGENT_STORE_SCHEMA_VERSION)),
        )
        conn.commit()
    finally:
        if owns_connection:
            conn.close()


def _row_to_task(row: sqlite3.Row) -> AgentTaskRun:
    return AgentTaskRun(
        task_id=str(row["task_id"]),
        session_id=str(row["session_id"]),
        user_prompt=str(row["user_prompt"]),
        status=str(row["status"]),
        goal=str(row["goal"]),
        created_at=int(row["created_at"]),
        updated_at=int(row["updated_at"]),
        use_context=bool(row["use_context"]),
        agent_prompt=str(row["agent_prompt"]),
        assistant_text=str(row["assistant_text"]),
        error=str(row["error"]),
    )


def _row_to_candidate(row: sqlite3.Row) -> AgentMemoryCandidate:
    return AgentMemoryCandidate(
        candidate_id=str(row["candidate_id"]),
        session_id=str(row["session_id"]),
        task_id=str(row["task_id"]),
        text=str(row["text"]),
        kind=str(row["kind"]),
        scope=str(row["scope"]),
        source=str(row["source"]),
        confidence=float(row["confidence"]),
        importance=float(row["importance"]),
        sensitivity=str(row["sensitivity"]),
        status=str(row["status"]),
        evidence_id=str(row["evidence_id"]),
        created_at=int(row["created_at"]),
        updated_at=int(row["updated_at"]),
    )


def _row_to_tool_event(row: sqlite3.Row) -> AgentToolEvent:
    raw_ok = row["ok"]
    ok = None if raw_ok is None else bool(raw_ok)
    return AgentToolEvent(
        event_id=str(row["event_id"]),
        session_id=str(row["session_id"]),
        task_id=str(row["task_id"]),
        plan_id=str(row["plan_id"]),
        action=str(row["action"]),
        title=str(row["title"]),
        event=str(row["event"]),
        ok=ok,
        summary=str(row["summary"]),
        created_at=int(row["created_at"]),
    )


def infer_goal(user_prompt: str) -> str:
    text = compact_inline_text(user_prompt, 120)
    return text or "处理当前请求"


def start_task_run(
    session_id: str,
    user_prompt: str,
    *,
    agent_prompt: str = "",
    goal: str = "",
    use_context: bool = True,
) -> AgentTaskRun:
    created_at = now_ts()
    task = AgentTaskRun(
        task_id=new_agent_id("task"),
        session_id=compact_inline_text(session_id, 80),
        user_prompt=compact_agent_text(user_prompt),
        agent_prompt=compact_agent_text(agent_prompt),
        assistant_text="",
        goal=compact_inline_text(goal or infer_goal(user_prompt), 240),
        status=TASK_STATUS_ACTIVE,
        use_context=bool(use_context),
        error="",
        created_at=created_at,
        updated_at=created_at,
    )
    try:
        with closing(connect_agent_store()) as conn:
            conn.execute(
                """
                INSERT INTO task_runs(
                    task_id, session_id, user_prompt, agent_prompt, assistant_text,
                    goal, status, use_context, error, created_at, updated_at
                )
                VALUES(?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    task.task_id,
                    task.session_id,
                    task.user_prompt,
                    task.agent_prompt,
                    task.assistant_text,
                    task.goal,
                    task.status,
                    1 if task.use_context else 0,
                    task.error,
                    task.created_at,
                    task.updated_at,
                ),
            )
            conn.commit()
    except Exception:
        LOGGER.exception("failed to start agent task run")
    return task


def update_task_run(
    task_id: str,
    *,
    status: str,
    assistant_text: str = "",
    error: str = "",
) -> AgentTaskRun | None:
    clean_id = compact_inline_text(task_id, 96)
    if not clean_id:
        return None
    updated_at = now_ts()
    try:
        with closing(connect_agent_store()) as conn:
            conn.execute(
                """
                UPDATE task_runs
                SET status = ?, assistant_text = ?, error = ?, updated_at = ?
                WHERE task_id = ?
                """,
                (
                    compact_inline_text(status, 40),
                    compact_agent_text(assistant_text),
                    compact_agent_text(error, 1200),
                    updated_at,
                    clean_id,
                ),
            )
            conn.commit()
            row = conn.execute("SELECT * FROM task_runs WHERE task_id = ?", (clean_id,)).fetchone()
    except Exception:
        LOGGER.exception("failed to update agent task run")
        return None
    return _row_to_task(row) if row is not None else None


def list_recent_task_runs(session_id: str, limit: int = 4) -> list[AgentTaskRun]:
    try:
        max_rows = max(1, int(limit))
    except Exception:
        max_rows = 4
    try:
        with closing(connect_agent_store()) as conn:
            rows = conn.execute(
                """
                SELECT * FROM task_runs
                WHERE session_id = ?
                ORDER BY updated_at DESC
                LIMIT ?
                """,
                (compact_inline_text(session_id, 80), max_rows),
            ).fetchall()
    except Exception:
        LOGGER.exception("failed to list recent task runs")
        return []
    return [_row_to_task(row) for row in rows]


def append_tool_event(
    session_id: str,
    *,
    event: str,
    plan: ControlPlan | None = None,
    result: ControlResult | None = None,
    task_id: str = "",
    summary: str = "",
) -> AgentToolEvent | None:
    created_at = now_ts()
    payload: dict[str, object] = {}
    if plan is not None:
        payload["plan"] = {
            "plan_id": plan.plan_id,
            "source_text": plan.source_text,
            "action": plan.action,
            "title": plan.title,
            "steps": list(plan.steps),
            "args": dict(plan.args),
            "permission": str(plan.permission.value),
            "blocked_reason": plan.blocked_reason,
            "created_at": int(plan.created_at),
        }
    if result is not None:
        payload["result"] = {
            "plan_id": result.plan_id,
            "title": result.title,
            "ok": bool(result.ok),
            "output": compact_agent_text(result.output, 2400),
            "permission": str(result.permission.value),
            "error": compact_agent_text(result.error, 1200),
        }
    if not summary:
        if result is not None:
            state = "完成" if result.ok else "失败"
            detail = result.error or result.output
            summary = f"{result.title}：{state}"
            if detail:
                summary += f"；{compact_inline_text(detail, 260)}"
        elif plan is not None:
            summary = plan.summary()
        else:
            summary = event
    tool_event = AgentToolEvent(
        event_id=new_agent_id("tool"),
        session_id=compact_inline_text(session_id, 80),
        task_id=compact_inline_text(task_id, 96),
        plan_id=compact_inline_text(plan.plan_id if plan is not None else (result.plan_id if result is not None else ""), 96),
        action=compact_inline_text(plan.action if plan is not None else "", 80),
        title=compact_inline_text(plan.title if plan is not None else (result.title if result is not None else ""), 180),
        event=compact_inline_text(event, 80),
        ok=None if result is None else bool(result.ok),
        summary=compact_agent_text(summary, 1600),
        created_at=created_at,
    )
    try:
        with closing(connect_agent_store()) as conn:
            conn.execute(
                """
                INSERT INTO tool_events(
                    event_id, session_id, task_id, plan_id, action, title,
                    event, ok, summary, payload_json, created_at
                )
                VALUES(?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    tool_event.event_id,
                    tool_event.session_id,
                    tool_event.task_id,
                    tool_event.plan_id,
                    tool_event.action,
                    tool_event.title,
                    tool_event.event,
                    None if tool_event.ok is None else (1 if tool_event.ok else 0),
                    tool_event.summary,
                    json.dumps(payload, ensure_ascii=False),
                    tool_event.created_at,
                ),
            )
            conn.commit()
    except Exception:
        LOGGER.exception("failed to append tool event")
        return None
    return tool_event


def list_recent_tool_events(session_id: str, limit: int = 5) -> list[AgentToolEvent]:
    try:
        max_rows = max(1, int(limit))
    except Exception:
        max_rows = 5
    try:
        with closing(connect_agent_store()) as conn:
            rows = conn.execute(
                """
                SELECT * FROM tool_events
                WHERE session_id = ?
                ORDER BY created_at DESC
                LIMIT ?
                """,
                (compact_inline_text(session_id, 80), max_rows),
            ).fetchall()
    except Exception:
        LOGGER.exception("failed to list recent tool events")
        return []
    return [_row_to_tool_event(row) for row in rows]


def classify_memory_candidate(text: str) -> tuple[str, str, float, float, str]:
    lowered = str(text or "").casefold()
    kind = "preference"
    scope = "global"
    confidence = 0.68
    importance = 0.55
    sensitivity = "normal"
    if any(token in lowered for token in ("不要", "别", "禁止", "必须", "需要确认", "约束", "规范")):
        kind = "constraint"
        importance = 0.78
    if any(token in lowered for token in ("项目", "仓库", "接口", "素材", "路径", "目录")):
        scope = "project"
        importance = max(importance, 0.68)
    if any(token in lowered for token in ("目标", "下一步", "待办", "todo")):
        kind = "task_state"
        scope = "session"
        confidence = 0.62
    if any(token in lowered for token in ("key", "api key", "token", "密码", "secret", "凭据")):
        sensitivity = "secret"
        confidence = 0.2
    return kind, scope, confidence, importance, sensitivity


def add_memory_candidate(
    text: str,
    *,
    session_id: str = "",
    task_id: str = "",
    kind: str = "",
    scope: str = "",
    source: str = "chat",
    confidence: float | None = None,
    importance: float | None = None,
    sensitivity: str = "",
    evidence_id: str = "",
    status: str = MEMORY_STATUS_PENDING,
) -> AgentMemoryCandidate | None:
    clean = compact_agent_text(text, 1200)
    if not clean:
        return None
    inferred_kind, inferred_scope, inferred_confidence, inferred_importance, inferred_sensitivity = classify_memory_candidate(clean)
    candidate = AgentMemoryCandidate(
        candidate_id=new_agent_id("mem"),
        session_id=compact_inline_text(session_id, 80),
        task_id=compact_inline_text(task_id, 96),
        text=clean,
        kind=compact_inline_text(kind or inferred_kind, 40),
        scope=compact_inline_text(scope or inferred_scope, 40),
        source=compact_inline_text(source or "chat", 40),
        confidence=float(inferred_confidence if confidence is None else confidence),
        importance=float(inferred_importance if importance is None else importance),
        sensitivity=compact_inline_text(sensitivity or inferred_sensitivity, 40),
        status=compact_inline_text(status or MEMORY_STATUS_PENDING, 40),
        evidence_id=compact_inline_text(evidence_id, 96),
        created_at=now_ts(),
        updated_at=now_ts(),
    )
    if candidate.sensitivity == "secret":
        LOGGER.info("skipped secret-like memory candidate")
        return None
    try:
        with closing(connect_agent_store()) as conn:
            conn.execute(
                """
                INSERT INTO memory_candidates(
                    candidate_id, session_id, task_id, text, normalized_text,
                    kind, scope, source, confidence, importance, sensitivity,
                    status, evidence_id, created_at, updated_at
                )
                VALUES(?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(normalized_text, scope, source) DO UPDATE SET
                    session_id = excluded.session_id,
                    task_id = excluded.task_id,
                    text = excluded.text,
                    kind = excluded.kind,
                    confidence = MAX(memory_candidates.confidence, excluded.confidence),
                    importance = MAX(memory_candidates.importance, excluded.importance),
                    sensitivity = excluded.sensitivity,
                    status = CASE
                        WHEN memory_candidates.status = ? THEN memory_candidates.status
                        ELSE excluded.status
                    END,
                    evidence_id = excluded.evidence_id,
                    updated_at = excluded.updated_at
                """,
                (
                    candidate.candidate_id,
                    candidate.session_id,
                    candidate.task_id,
                    candidate.text,
                    normalize_text(candidate.text),
                    candidate.kind,
                    candidate.scope,
                    candidate.source,
                    candidate.confidence,
                    candidate.importance,
                    candidate.sensitivity,
                    candidate.status,
                    candidate.evidence_id,
                    candidate.created_at,
                    candidate.updated_at,
                    MEMORY_STATUS_APPROVED,
                ),
            )
            conn.commit()
            row = conn.execute(
                "SELECT * FROM memory_candidates WHERE normalized_text = ? AND scope = ? AND source = ?",
                (normalize_text(candidate.text), candidate.scope, candidate.source),
            ).fetchone()
    except Exception:
        LOGGER.exception("failed to add memory candidate")
        return None
    return _row_to_candidate(row) if row is not None else candidate


def extract_memory_candidate_texts(user_text: str, assistant_text: str = "") -> list[str]:
    source = compact_agent_text(user_text, 1600)
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
        "下一步",
        "待办",
    )
    if not any(trigger in source for trigger in triggers):
        return []
    candidates: list[str] = []
    for chunk in source.replace("；", "\n").replace("。", "\n").replace(";", "\n").splitlines():
        item = compact_inline_text(chunk, 520)
        if len(item) < 6:
            continue
        if item not in candidates:
            candidates.append(item)
        if len(candidates) >= MEMORY_CANDIDATE_LIMIT:
            break
    return candidates


def record_memory_candidates_from_turn(
    user_text: str,
    assistant_text: str = "",
    *,
    session_id: str = "",
    task_id: str = "",
) -> list[AgentMemoryCandidate]:
    recorded: list[AgentMemoryCandidate] = []
    for text in extract_memory_candidate_texts(user_text, assistant_text):
        candidate = add_memory_candidate(text, session_id=session_id, task_id=task_id, source="chat", evidence_id=task_id)
        if candidate is not None:
            recorded.append(candidate)
    return recorded


def set_memory_candidate_status(candidate_id: str, status: str) -> AgentMemoryCandidate | None:
    clean_id = compact_inline_text(candidate_id, 96)
    if not clean_id:
        return None
    try:
        with closing(connect_agent_store()) as conn:
            conn.execute(
                "UPDATE memory_candidates SET status = ?, updated_at = ? WHERE candidate_id = ?",
                (compact_inline_text(status, 40), now_ts(), clean_id),
            )
            conn.commit()
            row = conn.execute("SELECT * FROM memory_candidates WHERE candidate_id = ?", (clean_id,)).fetchone()
    except Exception:
        LOGGER.exception("failed to update memory candidate status")
        return None
    return _row_to_candidate(row) if row is not None else None


def list_memory_candidates(status: str = MEMORY_STATUS_PENDING, limit: int = 20) -> list[AgentMemoryCandidate]:
    try:
        max_rows = max(1, int(limit))
    except Exception:
        max_rows = 20
    try:
        with closing(connect_agent_store()) as conn:
            if status:
                rows = conn.execute(
                    """
                    SELECT * FROM memory_candidates
                    WHERE status = ?
                    ORDER BY importance DESC, updated_at DESC
                    LIMIT ?
                    """,
                    (compact_inline_text(status, 40), max_rows),
                ).fetchall()
            else:
                rows = conn.execute(
                    """
                    SELECT * FROM memory_candidates
                    ORDER BY importance DESC, updated_at DESC
                    LIMIT ?
                    """,
                    (max_rows,),
                ).fetchall()
    except Exception:
        LOGGER.exception("failed to list memory candidates")
        return []
    return [_row_to_candidate(row) for row in rows]


def build_agent_state_context(session_id: str, limit: int = 4) -> str:
    tasks = list_recent_task_runs(session_id, limit)
    tool_events = list_recent_tool_events(session_id, limit)
    parts: list[str] = []
    if tasks:
        lines = []
        for task in tasks:
            lines.append(
                "- "
                + "; ".join(
                    part
                    for part in (
                        f"status={task.status}",
                        f"goal={compact_inline_text(task.goal, 140)}",
                        f"last={compact_inline_text(task.assistant_text or task.error, 180)}" if task.assistant_text or task.error else "",
                    )
                    if part
                )
            )
        parts.append("最近任务状态:\n" + "\n".join(lines))
    if tool_events:
        lines = []
        for event in tool_events:
            state = "" if event.ok is None else ("ok" if event.ok else "failed")
            lines.append(
                "- "
                + "; ".join(
                    part
                    for part in (
                        f"event={event.event}",
                        f"state={state}" if state else "",
                        compact_inline_text(event.summary, 220),
                    )
                    if part
                )
            )
        parts.append("最近工具证据:\n" + "\n".join(lines))
    if not parts:
        return ""
    return "Agent 运行状态:\n" + "\n\n".join(parts)
