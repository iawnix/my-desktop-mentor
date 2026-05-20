"""Controlled local computer operations."""
from __future__ import annotations

from .types import ControlPlan, ControlResult, PermissionLevel


def build_control_plan(user_text: str, raw_workspace: str = "") -> ControlPlan | None:
    from ..tools.registry import build_control_plan as _build_control_plan

    return _build_control_plan(user_text, raw_workspace)


def build_control_plan_from_agent_reply(reply_text: str, raw_workspace: str = "") -> tuple[ControlPlan | None, str]:
    from ..tools.registry import build_control_plan_from_agent_reply as _build_control_plan_from_agent_reply

    return _build_control_plan_from_agent_reply(reply_text, raw_workspace)


def execute_control_plan(plan: ControlPlan) -> ControlResult:
    from ..tools.executor import execute_control_plan as _execute_control_plan

    return _execute_control_plan(plan)

__all__ = [
    "ControlPlan",
    "ControlResult",
    "PermissionLevel",
    "build_control_plan",
    "build_control_plan_from_agent_reply",
    "execute_control_plan",
]
