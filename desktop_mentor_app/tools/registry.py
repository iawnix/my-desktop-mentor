"""Tool plan registry facade."""
from __future__ import annotations

from ..control.tool_registry import build_control_plan, build_control_plan_from_agent_reply

__all__ = ["build_control_plan", "build_control_plan_from_agent_reply"]
