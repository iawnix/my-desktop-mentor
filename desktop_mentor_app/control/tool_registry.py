"""Compatibility wrapper for control tool planning."""
from __future__ import annotations

from ..tools.registry import (
    build_control_plan,
    build_control_plan_from_agent_reply,
    desktop_path,
    split_agent_control_request,
)

__all__ = [
    "build_control_plan",
    "build_control_plan_from_agent_reply",
    "desktop_path",
    "split_agent_control_request",
]
