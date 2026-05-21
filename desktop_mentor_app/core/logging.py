"""Application logging setup."""
from __future__ import annotations

import logging
from logging.handlers import RotatingFileHandler
from pathlib import Path

from ..constants.app import APP_ID

LOG_FORMAT = "%(asctime)s %(levelname)s [%(name)s] %(message)s"


def app_log_path(config_file: Path | None = None) -> Path:
    if config_file is None:
        from ..config.store import config_path

        config_file = config_path()
    return config_file.parent / "logs" / "app.log"


def configure_logging(config_file: Path | None = None, *, debug: bool = False) -> Path:
    path = app_log_path(config_file)
    path.parent.mkdir(parents=True, exist_ok=True)
    root = logging.getLogger()
    root.setLevel(logging.DEBUG if debug else logging.INFO)
    marker = str(path)
    for handler in root.handlers:
        if getattr(handler, "_desktop_mentor_log_path", "") == marker:
            return path
    handler = RotatingFileHandler(path, maxBytes=1_000_000, backupCount=3, encoding="utf-8")
    handler.setFormatter(logging.Formatter(LOG_FORMAT))
    handler._desktop_mentor_log_path = marker  # type: ignore[attr-defined]
    root.addHandler(handler)
    logging.getLogger(__name__).info("%s logging initialized at %s", APP_ID, path)
    return path
