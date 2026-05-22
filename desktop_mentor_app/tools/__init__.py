"""Tool registry and execution facade."""
from __future__ import annotations

__all__ = [
    "ControlPlan",
    "ControlResult",
    "PermissionLevel",
    "build_control_plan",
    "build_control_plan_from_model_response",
    "build_control_plan_from_tool_call",
    "build_control_tool_schemas",
    "execute_control_plan",
    "execute_control_plan_async",
]


def __getattr__(name: str):
    if name in {"ControlPlan", "ControlResult", "PermissionLevel"}:
        from . import types

        return getattr(types, name)
    if name in {
        "build_control_plan",
        "build_control_plan_from_model_response",
        "build_control_plan_from_tool_call",
        "build_control_tool_schemas",
    }:
        from . import registry

        return getattr(registry, name)
    if name in {"execute_control_plan", "execute_control_plan_async"}:
        from . import executor

        return getattr(executor, name)
    raise AttributeError(name)
