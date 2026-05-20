"""Path and filename extraction for control planning."""
from __future__ import annotations

import os
import re
import time
from pathlib import Path

from ..security.policy import resolve_user_path

WRITABLE_TEXT_SUFFIXES = (".txt", ".md", ".log", ".csv", ".json")
READABLE_TEXT_SUFFIXES = WRITABLE_TEXT_SUFFIXES + (".tex", ".rst")
WINDOWS_FORBIDDEN_FILENAME_CHARS = re.compile(r'[<>:"/\\|?*\x00-\x1f]')
WINDOWS_ABSOLUTE_PATH = re.compile(r"([A-Za-z]:[\\/][^\n`\"'，。；;]+?\.(?:txt|md|log|csv|json|tex|rst))", re.IGNORECASE)
POSIX_ABSOLUTE_PATH = re.compile(r"(/[^\n`\"'，。；;\s]+?\.(?:txt|md|log|csv|json|tex|rst))", re.IGNORECASE)


def expand_xdg_user_dir(raw_value: str) -> Path | None:
    value = str(raw_value or "").strip().strip("'\"")
    if not value:
        return None
    home_text = str(Path.home().expanduser())
    value = value.replace("${HOME}", home_text).replace("$HOME", home_text)
    return Path(value).expanduser()


def configured_desktop_path() -> Path | None:
    env_path = expand_xdg_user_dir(os.environ.get("XDG_DESKTOP_DIR", ""))
    if env_path is not None:
        return env_path
    config_home = Path(os.environ.get("XDG_CONFIG_HOME") or Path.home().expanduser() / ".config").expanduser()
    user_dirs = config_home / "user-dirs.dirs"
    try:
        lines = user_dirs.read_text(encoding="utf-8").splitlines()
    except OSError:
        return None
    for line in lines:
        clean = line.strip()
        if not clean or clean.startswith("#") or not clean.startswith("XDG_DESKTOP_DIR="):
            continue
        _key, _sep, raw_value = clean.partition("=")
        return expand_xdg_user_dir(raw_value)
    return None


def desktop_path() -> Path:
    home = Path.home().expanduser()
    configured = configured_desktop_path()
    if configured is not None:
        return configured.resolve(strict=False)
    candidates = [home / "Desktop", home / "桌面"]
    unique_candidates: list[Path] = []
    seen: set[str] = set()
    for candidate in candidates:
        key = str(candidate)
        if key not in seen:
            unique_candidates.append(candidate)
            seen.add(key)
    for candidate in unique_candidates:
        if candidate.exists():
            return candidate.resolve(strict=False)
    return unique_candidates[0].resolve(strict=False) if unique_candidates else (home / "Desktop").resolve(strict=False)


def quoted_segments(text: str) -> list[str]:
    segments: list[str] = []
    patterns = (
        r"`([^`]+)`",
        r"「([^」]+)」",
        r"『([^』]+)』",
        r"“([^”]+)”",
        r"\"([^\"]+)\"",
        r"'([^']+)'",
    )
    for pattern in patterns:
        segments.extend(match.group(1).strip() for match in re.finditer(pattern, text) if match.group(1).strip())
    return segments


def looks_like_filename(value: str) -> bool:
    lowered = value.strip().lower()
    return any(lowered.endswith(suffix) for suffix in READABLE_TEXT_SUFFIXES)


def extract_mentioned_filename(text: str) -> str:
    for segment in quoted_segments(text):
        name = segment.replace("\\", "/").rsplit("/", 1)[-1]
        if looks_like_filename(name):
            return safe_desktop_filename(name)
    match = re.search(r"([A-Za-z0-9_\-\u4e00-\u9fff][A-Za-z0-9_\-\u4e00-\u9fff .]*\.(?:txt|md|log|csv|json|tex|rst))", text, re.IGNORECASE)
    if match:
        name = match.group(1).replace("\\", "/").rsplit("/", 1)[-1].split()[-1]
        return safe_desktop_filename(name)
    return ""


def looks_like_path(value: str) -> bool:
    clean = str(value or "").strip()
    lowered = clean.lower()
    return (
        bool(WINDOWS_ABSOLUTE_PATH.search(clean))
        or clean.startswith(("/", "~"))
        or "%userprofile%" in lowered
        or "\\" in clean
        or "/" in clean
    )


def path_from_mentioned_path(raw_path: str, workspace: Path) -> Path | None:
    clean = str(raw_path or "").strip().strip("'\"")
    filename = extract_mentioned_filename(clean)
    if not filename:
        return None
    lowered = clean.lower()
    if "%userprofile%" in lowered and ("desktop" in lowered or "桌面" in clean):
        return (desktop_path() / filename).expanduser().resolve(strict=False)
    if WINDOWS_ABSOLUTE_PATH.search(clean) or POSIX_ABSOLUTE_PATH.search(clean) or clean.startswith("~"):
        return Path(clean).expanduser().resolve(strict=False)
    if looks_like_path(clean):
        return resolve_user_path(clean, workspace)
    return None


def extract_read_target(text: str, workspace: Path) -> Path | None:
    for segment in quoted_segments(text):
        target = path_from_mentioned_path(segment, workspace)
        if target is not None:
            return target
    windows_match = WINDOWS_ABSOLUTE_PATH.search(text)
    if windows_match:
        target = path_from_mentioned_path(windows_match.group(1), workspace)
        if target is not None:
            return target
    posix_match = POSIX_ABSOLUTE_PATH.search(text)
    if posix_match:
        target = path_from_mentioned_path(posix_match.group(1), workspace)
        if target is not None:
            return target
    lowered = text.lower()
    filename = extract_mentioned_filename(text)
    if filename and ("桌面" in text or "desktop" in lowered or "%userprofile%" in lowered):
        return (desktop_path() / filename).expanduser().resolve(strict=False)
    return None


def safe_desktop_filename(value: str) -> str:
    name = WINDOWS_FORBIDDEN_FILENAME_CHARS.sub("-", str(value or "").strip())
    name = re.sub(r"\s+", " ", name).strip(" .")
    if not name or name in {".", ".."}:
        stamp = time.strftime("%Y%m%d-%H%M%S")
        return f"desktop-mentor-note-{stamp}.txt"
    if not looks_like_filename(name):
        name = f"{name}.txt"
    return name


def extract_filename(text: str) -> str:
    mentioned_name = extract_mentioned_filename(text)
    if mentioned_name:
        return mentioned_name
    name_match = re.search(
        r"(?:文件名|名字|命名为|名为|叫)[是为叫：:\s]*([A-Za-z0-9_\-\u4e00-\u9fff][A-Za-z0-9_\-\u4e00-\u9fff .]{0,48})",
        text,
    )
    if name_match:
        raw_name = name_match.group(1).split("文件", 1)[0].strip(" ，。；;,")
        if raw_name:
            return safe_desktop_filename(raw_name)
    stamp = time.strftime("%Y%m%d-%H%M%S")
    return f"desktop-mentor-note-{stamp}.txt"


def extract_write_content(text: str) -> str:
    markers = (
        "内容是",
        "内容为",
        "内容：",
        "内容:",
        "写入：",
        "写入:",
        "写上：",
        "写上:",
        "写一段话：",
        "写一段话:",
        "写一句话：",
        "写一句话:",
    )
    for marker in markers:
        if marker in text:
            tail = text.split(marker, 1)[1].strip()
            segments = quoted_segments(tail)
            content = segments[0] if segments else tail
            return content.strip("，。；; ")
    segments = quoted_segments(text)
    for segment in segments:
        if not looks_like_filename(segment):
            return segment
    return ""
