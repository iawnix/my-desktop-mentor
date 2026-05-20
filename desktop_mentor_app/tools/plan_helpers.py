"""Shared helpers for control-plan construction."""
from __future__ import annotations

import secrets

from ..control.types import ControlPlan, PermissionLevel


def new_plan_id() -> str:
    return "control-" + secrets.token_hex(4)


def blocked_plan(source_text: str, title: str, reason: str, steps: list[str] | None = None) -> ControlPlan:
    return ControlPlan(
        plan_id=new_plan_id(),
        source_text=source_text,
        action="blocked",
        title=title,
        steps=steps or ["不执行该操作。"],
        permission=PermissionLevel.BLOCKED,
        blocked_reason=reason,
    )
