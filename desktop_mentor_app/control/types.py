"""Types for controlled local computer operations."""
from __future__ import annotations

import time
from dataclasses import dataclass, field
from enum import Enum


class PermissionLevel(str, Enum):
    READ_ONLY = "read_only"
    USER_APPROVAL = "user_approval"
    BLOCKED = "blocked"


@dataclass(frozen=True)
class ControlPlan:
    plan_id: str
    source_text: str
    action: str
    title: str
    steps: list[str]
    args: dict[str, object] = field(default_factory=dict)
    permission: PermissionLevel = PermissionLevel.READ_ONLY
    blocked_reason: str = ""
    created_at: int = field(default_factory=lambda: int(time.time()))

    @property
    def requires_confirmation(self) -> bool:
        return self.permission == PermissionLevel.USER_APPROVAL

    @property
    def is_blocked(self) -> bool:
        return self.permission == PermissionLevel.BLOCKED

    def summary(self) -> str:
        lines = [self.title, f"权限：{self.permission.value}"]
        if self.blocked_reason:
            lines.append(f"阻止原因：{self.blocked_reason}")
        lines.extend(f"{index}. {step}" for index, step in enumerate(self.steps, start=1))
        return "\n".join(lines)


@dataclass(frozen=True)
class ControlResult:
    plan_id: str
    title: str
    ok: bool
    output: str
    permission: PermissionLevel
    error: str = ""

    def display_text(self) -> str:
        status = "完成" if self.ok else "失败"
        lines = [f"{self.title}", f"状态：{status}"]
        if self.error:
            lines.append(f"错误：{self.error}")
        if self.output:
            lines.append(self.output)
        return "\n".join(lines)
