"""Runtime configuration storage."""
from __future__ import annotations

import json
import logging
import os
import sys
from dataclasses import asdict, dataclass, field
from pathlib import Path

from ..core.assets import DEFAULT_STICKERS_DIR
from ..constants.app import APP_ID, CONFIG_POINTER_NAME
from ..constants.control import DEFAULT_CONTROL_ENABLED, DEFAULT_CONTROL_WORKSPACE
from ..constants.memory import (
    DEFAULT_LONG_TERM_MEMORY_ENABLED,
    DEFAULT_LONG_TERM_MEMORY_ITEMS,
    DEFAULT_MEMORY_ENABLED,
    DEFAULT_MEMORY_TURNS,
    MAX_LONG_TERM_MEMORY_ITEMS,
    MAX_MEMORY_TURNS,
)
from ..constants.model import DEFAULT_MODEL, DEFAULT_PERSONALITY_PROMPT
from ..constants.pet import (
    DEFAULT_CLICK_MESSAGE,
    DEFAULT_DROP_MESSAGE,
    DEFAULT_IDLE_MESSAGE,
    DEFAULT_IDLE_MODE,
    DEFAULT_IDLE_SECONDS,
    DEFAULT_MESSAGE_SECONDS,
    IDLE_MODE_OPTIONS,
    MAX_IDLE_SECONDS,
    MAX_MESSAGE_SECONDS,
    MIN_IDLE_SECONDS,
    MIN_MESSAGE_SECONDS,
)
from ..constants.stickers import (
    DEFAULT_STICKER_ANIMATION_SPEED,
    MAX_STICKER_ANIMATION_SPEED,
    MIN_STICKER_ANIMATION_SPEED,
)
from ..constants.todos import DEFAULT_TODO_REPEAT_SECONDS, MAX_TODO_REPEAT_SECONDS, MIN_TODO_REPEAT_SECONDS
from ..pet.stickers import discover_sticker_sets, normalize_sticker_sets
from .migration import CURRENT_CONFIG_SCHEMA_VERSION, backup_config_before_migration, migrate_config_data

LOGGER = logging.getLogger(__name__)


@dataclass
class AgentConfig:
    schema_version: int = CURRENT_CONFIG_SCHEMA_VERSION
    api_url: str = ""
    api_key: str = ""
    model: str = DEFAULT_MODEL
    image_path: str = ""
    icon_path: str = ""
    config_dir: str = ""
    click_message: str = DEFAULT_CLICK_MESSAGE
    idle_message: str = DEFAULT_IDLE_MESSAGE
    drop_message: str = DEFAULT_DROP_MESSAGE
    message_seconds: float = DEFAULT_MESSAGE_SECONDS
    todo_repeat_seconds: int = DEFAULT_TODO_REPEAT_SECONDS
    idle_seconds: int = DEFAULT_IDLE_SECONDS
    idle_mode: str = DEFAULT_IDLE_MODE
    memory_enabled: bool = DEFAULT_MEMORY_ENABLED
    memory_turns: int = DEFAULT_MEMORY_TURNS
    long_term_memory_enabled: bool = DEFAULT_LONG_TERM_MEMORY_ENABLED
    long_term_memory_items: int = DEFAULT_LONG_TERM_MEMORY_ITEMS
    control_enabled: bool = DEFAULT_CONTROL_ENABLED
    control_workspace: str = DEFAULT_CONTROL_WORKSPACE
    sticker_animation_speed: float = DEFAULT_STICKER_ANIMATION_SPEED
    sticker_sets: dict[str, list[str]] = field(default_factory=dict)
    system_prompt: str = DEFAULT_PERSONALITY_PROMPT


def default_sticker_sets() -> dict[str, list[str]]:
    return discover_sticker_sets(DEFAULT_STICKERS_DIR)


def sticker_sets_have_existing_frames(sticker_sets: dict[str, list[str]]) -> bool:
    for paths in sticker_sets.values():
        for raw_path in paths:
            try:
                if Path(raw_path).expanduser().is_file():
                    return True
            except OSError:
                continue
    return False


def effective_sticker_sets(value: object) -> dict[str, list[str]]:
    sticker_sets = normalize_sticker_sets(value)
    if sticker_sets and sticker_sets_have_existing_frames(sticker_sets):
        return sticker_sets
    return default_sticker_sets()


def new_default_config(config_dir: Path | None = None) -> AgentConfig:
    config = AgentConfig()
    config.sticker_sets = default_sticker_sets()
    if config_dir is not None:
        config.config_dir = str(config_dir.expanduser())
    return config


def default_config_dir() -> Path:
    if sys.platform == "win32":
        base = Path(os.environ.get("APPDATA", Path.home() / "AppData" / "Roaming"))
        return base / "MyDesktopMentor"
    if sys.platform == "darwin":
        return Path.home() / "Library" / "Application Support" / "MyDesktopMentor"

    base = Path(os.environ.get("XDG_CONFIG_HOME", Path.home() / ".config"))
    return base / APP_ID


def legacy_config_dirs() -> list[Path]:
    if sys.platform == "win32":
        base = Path(os.environ.get("APPDATA", Path.home() / "AppData" / "Roaming"))
        names = ("MyDesktopMentor", "my-desktop-mentor", "XiaoheDesktopPet", "xiaohe-desktop-pet")
    elif sys.platform == "darwin":
        base = Path.home() / "Library" / "Application Support"
        names = ("MyDesktopMentor", "my-desktop-mentor", "XiaoheDesktopPet", "xiaohe-desktop-pet")
    else:
        base = Path(os.environ.get("XDG_CONFIG_HOME", Path.home() / ".config"))
        names = (APP_ID, "MyDesktopMentor", "xiaohe-desktop-pet", "xiaohe-agent")
    dirs: list[Path] = []
    for name in names:
        path = base / name
        if path not in dirs:
            dirs.append(path)
    return dirs


def config_dir_pointer_path() -> Path:
    return default_config_dir() / CONFIG_POINTER_NAME


def config_file_in_dir(directory: Path) -> Path:
    return directory.expanduser() / "config.json"


def first_existing_config_dir() -> Path | None:
    for directory in legacy_config_dirs():
        try:
            if config_file_in_dir(directory).exists():
                return directory.expanduser()
        except OSError:
            continue
    return None


def configured_config_dir() -> Path:
    override_dir = os.environ.get("DESKTOP_MENTOR_CONFIG_DIR", "").strip()
    if override_dir:
        return Path(override_dir).expanduser()

    override_file = os.environ.get("DESKTOP_MENTOR_CONFIG", "").strip()
    if override_file:
        return Path(override_file).expanduser().parent

    pointer = config_dir_pointer_path()
    pointed_dir: Path | None = None
    try:
        if pointer.exists():
            raw_path = pointer.read_text(encoding="utf-8").strip()
            if raw_path:
                pointed_dir = Path(raw_path).expanduser()
                if config_file_in_dir(pointed_dir).exists():
                    return pointed_dir
    except OSError:
        pass

    existing_dir = first_existing_config_dir()
    if existing_dir is not None:
        return existing_dir
    if pointed_dir is not None:
        return pointed_dir
    return default_config_dir()


def config_path() -> Path:
    override = os.environ.get("DESKTOP_MENTOR_CONFIG", "").strip()
    if override:
        return Path(override).expanduser()
    return configured_config_dir() / "config.json"


def save_config_directory(directory: Path) -> Path:
    target = directory.expanduser().resolve()
    target.mkdir(parents=True, exist_ok=True)
    pointer = config_dir_pointer_path()
    pointer.parent.mkdir(parents=True, exist_ok=True)
    pointer.write_text(str(target), encoding="utf-8")
    return target


def memory_path() -> Path:
    return config_path().parent / "memory.jsonl"


def user_memory_path() -> Path:
    return config_path().parent / "user_memory.json"


def chat_history_path() -> Path:
    return config_path().parent / "chat_history.jsonl"


def todos_path() -> Path:
    return config_path().parent / "todos.json"


def load_config(path: Path | None = None) -> AgentConfig:
    target = path or config_path()
    if not target.exists():
        return new_default_config(target.parent)
    try:
        data = json.loads(target.read_text(encoding="utf-8"))
    except Exception as exc:
        LOGGER.warning("failed to read config %s; using defaults: %s", target, exc)
        return new_default_config(target.parent)
    if not isinstance(data, dict):
        LOGGER.warning("config %s does not contain an object; using defaults", target)
        return new_default_config(target.parent)
    backup_config_before_migration(target, data)
    data = migrate_config_data(data)

    config = AgentConfig()
    for key in asdict(config):
        if key in data:
            setattr(config, key, data[key])
    try:
        config.schema_version = min(CURRENT_CONFIG_SCHEMA_VERSION, max(1, int(config.schema_version)))
    except Exception:
        config.schema_version = CURRENT_CONFIG_SCHEMA_VERSION
    config.model = str(config.model or DEFAULT_MODEL)
    config.image_path = str(config.image_path or "").strip()
    config.icon_path = str(config.icon_path or "").strip()
    config.sticker_sets = effective_sticker_sets(config.sticker_sets)
    config.config_dir = str(target.parent.expanduser())
    config.click_message = str(config.click_message or DEFAULT_CLICK_MESSAGE)
    config.idle_message = str(config.idle_message or DEFAULT_IDLE_MESSAGE)
    config.drop_message = str(config.drop_message or DEFAULT_DROP_MESSAGE)
    try:
        config.message_seconds = max(
            MIN_MESSAGE_SECONDS,
            min(MAX_MESSAGE_SECONDS, float(config.message_seconds)),
        )
    except Exception:
        config.message_seconds = DEFAULT_MESSAGE_SECONDS
    try:
        config.sticker_animation_speed = max(
            MIN_STICKER_ANIMATION_SPEED,
            min(MAX_STICKER_ANIMATION_SPEED, float(config.sticker_animation_speed)),
        )
    except Exception:
        config.sticker_animation_speed = DEFAULT_STICKER_ANIMATION_SPEED
    try:
        config.todo_repeat_seconds = max(
            MIN_TODO_REPEAT_SECONDS,
            min(MAX_TODO_REPEAT_SECONDS, int(config.todo_repeat_seconds)),
        )
    except Exception:
        config.todo_repeat_seconds = DEFAULT_TODO_REPEAT_SECONDS
    try:
        config.idle_seconds = max(MIN_IDLE_SECONDS, min(MAX_IDLE_SECONDS, int(config.idle_seconds)))
    except Exception:
        config.idle_seconds = DEFAULT_IDLE_SECONDS
    if isinstance(config.memory_enabled, str):
        config.memory_enabled = config.memory_enabled.strip().lower() in {"1", "true", "yes", "on"}
    else:
        config.memory_enabled = bool(config.memory_enabled)
    if isinstance(config.long_term_memory_enabled, str):
        config.long_term_memory_enabled = config.long_term_memory_enabled.strip().lower() in {"1", "true", "yes", "on"}
    else:
        config.long_term_memory_enabled = bool(config.long_term_memory_enabled)
    if isinstance(config.control_enabled, str):
        config.control_enabled = config.control_enabled.strip().lower() in {"1", "true", "yes", "on"}
    else:
        config.control_enabled = bool(config.control_enabled)
    config.control_workspace = str(config.control_workspace or "").strip()
    try:
        config.memory_turns = max(1, min(MAX_MEMORY_TURNS, int(config.memory_turns)))
    except Exception:
        config.memory_turns = DEFAULT_MEMORY_TURNS
    try:
        config.long_term_memory_items = max(1, min(MAX_LONG_TERM_MEMORY_ITEMS, int(config.long_term_memory_items)))
    except Exception:
        config.long_term_memory_items = DEFAULT_LONG_TERM_MEMORY_ITEMS
    valid_idle_modes = {value for value, _label in IDLE_MODE_OPTIONS}
    config.idle_mode = str(config.idle_mode or DEFAULT_IDLE_MODE)
    if config.idle_mode not in valid_idle_modes:
        config.idle_mode = DEFAULT_IDLE_MODE
    config.system_prompt = str(config.system_prompt or DEFAULT_PERSONALITY_PROMPT)
    return config


def save_config(config: AgentConfig, path: Path | None = None) -> Path:
    target = path or config_path()
    target.parent.mkdir(parents=True, exist_ok=True)
    config.schema_version = CURRENT_CONFIG_SCHEMA_VERSION
    target.write_text(json.dumps(asdict(config), ensure_ascii=False, indent=2), encoding="utf-8")
    return target
