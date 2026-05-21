"""Runtime audit log for local computer operations."""
from __future__ import annotations

import json
import logging
from dataclasses import asdict
from pathlib import Path

from ..tools.types import ControlPlan, ControlResult

LOGGER = logging.getLogger(__name__)


def audit_log_path() -> Path:
    from ..config_store import config_path

    return config_path().parent / "control" / "audit.jsonl"


def append_audit_entry(plan: ControlPlan, result: ControlResult | None = None, event: str = "execute") -> None:
    try:
        path = audit_log_path()
        path.parent.mkdir(parents=True, exist_ok=True)
        payload: dict[str, object] = {
            "event": event,
            "plan": asdict(plan),
        }
        if result is not None:
            payload["result"] = asdict(result)
        with path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(payload, ensure_ascii=False) + "\n")
    except Exception:
        LOGGER.exception("failed to append control audit entry")
