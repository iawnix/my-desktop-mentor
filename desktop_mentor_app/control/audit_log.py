"""Compatibility wrapper for control audit storage."""
from __future__ import annotations

from ..security.audit import append_audit_entry, audit_log_path

__all__ = ["append_audit_entry", "audit_log_path"]
