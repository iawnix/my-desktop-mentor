"""Compatibility exports for application logging setup.

New code should import from ``desktop_mentor_app.core.logging``.
"""
from __future__ import annotations

from .core.logging import LOG_FORMAT, app_log_path, configure_logging

__all__ = ["LOG_FORMAT", "app_log_path", "configure_logging"]
