"""File and folder drop-context collection for the desktop mentor."""
from __future__ import annotations

import os
from pathlib import Path

MAX_DROP_PATHS = 8
MAX_FOLDER_FILES = 36
MAX_PREVIEW_FILES_PER_FOLDER = 6
MAX_FILE_PREVIEW_BYTES = 8192
MAX_DROP_CONTEXT_CHARS = 24_000
DROP_CONTEXT_PROMPT_HEADER = "用户刚拖给桌宠的文件/文件夹上下文如下。请只基于这些可见内容和用户问题回答；如果上下文不足，直接说明还缺什么。"
SENSITIVE_DROP_NAME_PARTS = (
    ".env",
    "id_rsa",
    "id_dsa",
    "id_ecdsa",
    "id_ed25519",
    "token",
    "secret",
    "password",
    "passwd",
    "credential",
    "credentials",
)
SKIPPED_DROP_DIR_NAMES = {
    ".git",
    ".hg",
    ".svn",
    "__pycache__",
    ".pytest_cache",
    ".mypy_cache",
    ".venv",
    "venv",
    "env",
    "node_modules",
    "build",
    "dist",
    ".idea",
    ".vscode",
}
DROP_PRIORITY_SUFFIXES = {
    ".md": 0,
    ".txt": 1,
    ".py": 2,
    ".sh": 2,
    ".bat": 2,
    ".json": 3,
    ".yaml": 3,
    ".yml": 3,
    ".toml": 3,
    ".ini": 3,
    ".cfg": 3,
    ".conf": 3,
}
TEXT_FILE_SUFFIXES = {
    ".bat",
    ".c",
    ".cc",
    ".cfg",
    ".conf",
    ".cpp",
    ".csv",
    ".h",
    ".hpp",
    ".html",
    ".ini",
    ".java",
    ".js",
    ".json",
    ".log",
    ".md",
    ".py",
    ".rs",
    ".sh",
    ".tex",
    ".toml",
    ".ts",
    ".txt",
    ".xml",
    ".yaml",
    ".yml",
}


def human_size(size: int) -> str:
    value = float(max(0, size))
    for unit in ("B", "KB", "MB", "GB"):
        if value < 1024 or unit == "GB":
            return f"{value:.1f} {unit}" if unit != "B" else f"{int(value)} B"
        value /= 1024
    return f"{size} B"


def is_text_like(path: Path, sample: bytes) -> bool:
    if path.suffix.lower() in TEXT_FILE_SUFFIXES:
        return True
    if b"\x00" in sample:
        return False
    if not sample:
        return True
    printable = sum(1 for byte in sample if byte in b"\n\r\t" or 32 <= byte <= 126)
    return printable / max(1, len(sample)) > 0.78


def read_text_preview(path: Path) -> str:
    try:
        with path.open("rb") as handle:
            sample = handle.read(MAX_FILE_PREVIEW_BYTES)
    except OSError as exc:
        return f"[read failed: {type(exc).__name__}]"

    if not is_text_like(path, sample[:2048]):
        return "[binary file omitted]"

    text = sample.decode("utf-8", errors="replace").replace("\r\n", "\n").replace("\r", "\n")
    text = "\n".join(line.rstrip() for line in text.splitlines())
    if len(text) > 4000:
        text = text[:4000] + "\n[preview truncated]"
    return text or "[empty file]"


def drop_path_label(path: Path, *, base: Path | None = None) -> str:
    if base is not None:
        try:
            return str(path.relative_to(base))
        except ValueError:
            pass
    return str(path)


def drop_skip_reason(path: Path) -> str:
    parts = [part.lower() for part in path.parts]
    name = path.name.lower()
    if any(part in SKIPPED_DROP_DIR_NAMES for part in parts):
        return "skipped generated/cache folder"
    if name in SENSITIVE_DROP_NAME_PARTS or any(token in name for token in SENSITIVE_DROP_NAME_PARTS):
        return "skipped sensitive filename"
    return ""


def drop_file_priority(path: Path) -> tuple[int, str]:
    name = path.name.lower()
    if name.startswith("readme."):
        return (0, name)
    if path.suffix.lower() in DROP_PRIORITY_SUFFIXES:
        return (DROP_PRIORITY_SUFFIXES[path.suffix.lower()] + 1, name)
    if path.suffix.lower() in TEXT_FILE_SUFFIXES:
        return (8, name)
    return (20, name)


def describe_file(path: Path, *, base: Path | None = None) -> list[str]:
    label = drop_path_label(path, base=base)
    reason = drop_skip_reason(path)
    if reason:
        return [f"- File: {label}: [{reason}]"]

    try:
        stat = path.stat()
    except OSError as exc:
        return [f"- {label}: [stat failed: {type(exc).__name__}]"]

    preview = read_text_preview(path)
    return [
        f"- File: {label}",
        f"  Size: {human_size(stat.st_size)}",
        "  Preview:",
        preview,
    ]


def describe_folder(path: Path) -> list[str]:
    lines = [f"- Folder: {path}"]
    sampled: list[Path] = []
    seen_files = 0
    seen_dirs = 0
    skipped_dirs = 0
    skipped_files = 0
    try:
        for root, dir_names, file_names in os.walk(path):
            root_path = Path(root)
            kept_dirs: list[str] = []
            for dir_name in dir_names:
                child_dir = root_path / dir_name
                if drop_skip_reason(child_dir):
                    skipped_dirs += 1
                    continue
                kept_dirs.append(dir_name)
            dir_names[:] = kept_dirs
            seen_dirs += len(kept_dirs)

            for file_name in file_names:
                child = root_path / file_name
                if drop_skip_reason(child):
                    skipped_files += 1
                    continue
                if not child.is_file():
                    continue
                seen_files += 1
                sampled.append(child)
            if seen_files >= MAX_FOLDER_FILES * 3:
                break
    except OSError as exc:
        lines.append(f"  [scan failed: {type(exc).__name__}]")
        return lines

    sampled = sorted(sampled, key=drop_file_priority)[:MAX_FOLDER_FILES]
    lines.append(f"  Sampled files: {len(sampled)}")
    if seen_dirs:
        lines.append(f"  Sampled subfolders: {seen_dirs}")
    if skipped_dirs or skipped_files:
        lines.append(f"  Skipped sensitive/cache items: {skipped_dirs + skipped_files}")
    for file_path in sampled[:MAX_PREVIEW_FILES_PER_FOLDER]:
        lines.extend(describe_file(file_path, base=path))
    if len(sampled) > MAX_PREVIEW_FILES_PER_FOLDER:
        lines.append(f"  [... {len(sampled) - MAX_PREVIEW_FILES_PER_FOLDER} more sampled files omitted]")
    return lines


def collect_drop_context(paths: list[Path]) -> str:
    lines = ["Dropped paths:"]
    for path in paths[:MAX_DROP_PATHS]:
        try:
            reason = drop_skip_reason(path)
            if reason:
                lines.append(f"- {path}: [{reason}]")
            elif path.is_dir():
                lines.extend(describe_folder(path))
            elif path.is_file():
                lines.extend(describe_file(path))
            else:
                lines.append(f"- {path}: [not a regular file or folder]")
        except OSError as exc:
            lines.append(f"- {path}: [read failed: {type(exc).__name__}]")
    if len(paths) > MAX_DROP_PATHS:
        lines.append(f"[... {len(paths) - MAX_DROP_PATHS} more dropped paths omitted]")

    context = "\n".join(lines)
    if len(context) > MAX_DROP_CONTEXT_CHARS:
        context = context[:MAX_DROP_CONTEXT_CHARS] + "\n[drop context truncated]"
    return context


def compose_prompt_with_drop_context(user_text: str, drop_context: str) -> str:
    context = str(drop_context or "").strip()
    if not context:
        return user_text
    return f"{user_text.strip()}\n\n---\n{DROP_CONTEXT_PROMPT_HEADER}\n\n{context}"
