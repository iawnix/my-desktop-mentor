"""Permission helpers for local computer operations."""
from __future__ import annotations

import os
import tempfile
from pathlib import Path

from ..tools.types import PermissionLevel

SENSITIVE_NAME_PARTS = (
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
    "private_key",
)

SKIP_DIR_NAMES = {
    ".git",
    ".hg",
    ".svn",
    "__pycache__",
    ".mypy_cache",
    ".pytest_cache",
    ".ruff_cache",
    "node_modules",
    "dist",
    "build",
    ".venv",
    "venv",
}

BLOCKED_EXECUTABLES = {
    "dd",
    "del",
    "diskpart",
    "format",
    "halt",
    "mkfs",
    "passwd",
    "rd",
    "reboot",
    "reg",
    "rm",
    "rmdir",
    "shutdown",
    "su",
    "sudo",
}

SHELL_EXECUTABLES = {"bash", "cmd", "cmd.exe", "powershell", "powershell.exe", "pwsh", "pwsh.exe", "sh", "zsh"}


def control_workspace(raw_workspace: str = "") -> Path:
    raw = str(raw_workspace or "").strip()
    if not raw:
        return Path.home().resolve()
    return Path(raw).expanduser().resolve()


def resolve_user_path(raw_path: str, workspace: Path) -> Path:
    text = str(raw_path or "").strip()
    path = Path(text).expanduser() if text else workspace
    if not path.is_absolute():
        path = workspace / path
    return path.resolve(strict=False)


def is_under(parent: Path, child: Path) -> bool:
    try:
        child.resolve(strict=False).relative_to(parent.resolve(strict=False))
        return True
    except ValueError:
        return False


def is_sensitive_path(path: Path) -> bool:
    lowered = [part.lower() for part in path.parts]
    for part in lowered:
        if part in {".ssh", ".gnupg", ".aws", ".config/gcloud"}:
            return True
        if any(marker in part for marker in SENSITIVE_NAME_PARTS):
            return True
    return False


def can_read_path(path: Path) -> tuple[PermissionLevel, str]:
    if is_sensitive_path(path):
        return PermissionLevel.BLOCKED, "路径看起来包含密钥、token、密码或凭据。"
    return PermissionLevel.READ_ONLY, ""


def can_write_path(path: Path) -> tuple[PermissionLevel, str]:
    if is_sensitive_path(path):
        return PermissionLevel.BLOCKED, "路径看起来包含密钥、token、密码或凭据。"
    home = Path.home().resolve()
    temp_root = Path(tempfile.gettempdir()).resolve()
    if not is_under(home, path) and not is_under(temp_root, path):
        return PermissionLevel.BLOCKED, "第一版只允许写入用户 home 或系统临时目录下的文件。"
    return PermissionLevel.USER_APPROVAL, ""


def normalize_executable_name(value: str) -> str:
    name = Path(str(value or "")).name.lower()
    if os.name == "nt" and name.endswith(".exe"):
        return name[:-4]
    return name


def can_run_command(argv: list[str]) -> tuple[PermissionLevel, str]:
    if not argv:
        return PermissionLevel.BLOCKED, "没有提供要运行的命令。"
    executable = normalize_executable_name(argv[0])
    if executable in BLOCKED_EXECUTABLES:
        return PermissionLevel.BLOCKED, f"命令 `{argv[0]}` 在当前安全策略中被阻止。"
    if executable in SHELL_EXECUTABLES and any(arg.lower() in {"-c", "/c", "-command", "-encodedcommand"} for arg in argv[1:]):
        return PermissionLevel.BLOCKED, "第一版不允许通过 shell 字符串执行任意命令。"
    return PermissionLevel.USER_APPROVAL, ""
