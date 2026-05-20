"""Async tool execution facade."""
from __future__ import annotations

import asyncio

from ..control.executor import execute_control_plan
from ..control.types import ControlPlan, ControlResult


async def execute_control_plan_async(plan: ControlPlan) -> ControlResult:
    return await asyncio.to_thread(execute_control_plan, plan)
