"""Config schema migration helpers."""
from __future__ import annotations

import json
import logging
import shutil
from pathlib import Path
from typing import Any

CURRENT_CONFIG_SCHEMA_VERSION = 2
LOGGER = logging.getLogger(__name__)


def config_schema_version(data: dict[str, Any]) -> int:
    try:
        return int(data.get("schema_version", 1))
    except (TypeError, ValueError):
        return 1


def migrate_config_data(data: object) -> dict[str, Any]:
    if not isinstance(data, dict):
        return {"schema_version": CURRENT_CONFIG_SCHEMA_VERSION}
    migrated = dict(data)
    version = config_schema_version(migrated)
    if version < 2:
        migrated["schema_version"] = 2
    if config_schema_version(migrated) > CURRENT_CONFIG_SCHEMA_VERSION:
        LOGGER.warning("config schema is newer than runtime: %s", migrated.get("schema_version"))
    migrated["schema_version"] = min(config_schema_version(migrated), CURRENT_CONFIG_SCHEMA_VERSION)
    return migrated


def backup_config_before_migration(path: Path, data: dict[str, Any]) -> Path | None:
    if config_schema_version(data) >= CURRENT_CONFIG_SCHEMA_VERSION:
        return None
    backup_path = path.with_name("config.v1.bak.json")
    if backup_path.exists():
        return backup_path
    try:
        if path.exists():
            shutil.copy2(path, backup_path)
        else:
            backup_path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
        return backup_path
    except OSError as exc:
        LOGGER.warning("failed to back up v1 config %s: %s", path, exc)
        return None
