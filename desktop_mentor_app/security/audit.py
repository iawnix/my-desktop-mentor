"""Control audit facade."""
from __future__ import annotations

from ..control.audit_log import append_audit_entry, audit_log_path

__all__ = ["append_audit_entry", "audit_log_path"]
