"""Typed tool definitions."""
from __future__ import annotations

from dataclasses import dataclass, field

from ..control.types import PermissionLevel


@dataclass(frozen=True)
class ToolSpec:
    name: str
    description: str
    permission: PermissionLevel = PermissionLevel.READ_ONLY
    examples: tuple[str, ...] = field(default_factory=tuple)
