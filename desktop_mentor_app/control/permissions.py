"""Compatibility wrapper for local control security policy."""
from __future__ import annotations

from ..security.policy import (
    BLOCKED_EXECUTABLES,
    SHELL_EXECUTABLES,
    SKIP_DIR_NAMES,
    SENSITIVE_NAME_PARTS,
    can_read_path,
    can_run_command,
    can_write_path,
    control_workspace,
    is_sensitive_path,
    is_under,
    normalize_executable_name,
    resolve_user_path,
)

__all__ = [
    "BLOCKED_EXECUTABLES",
    "SHELL_EXECUTABLES",
    "SKIP_DIR_NAMES",
    "SENSITIVE_NAME_PARTS",
    "can_read_path",
    "can_run_command",
    "can_write_path",
    "control_workspace",
    "is_sensitive_path",
    "is_under",
    "normalize_executable_name",
    "resolve_user_path",
]
