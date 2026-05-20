"""Versioned configuration helpers."""
from __future__ import annotations

from .migration import CURRENT_CONFIG_SCHEMA_VERSION, migrate_config_data

__all__ = ["CURRENT_CONFIG_SCHEMA_VERSION", "migrate_config_data"]
