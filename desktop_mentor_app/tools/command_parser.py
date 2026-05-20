"""Slash-command parsing for local control tools."""
from __future__ import annotations

import os
import shlex
from pathlib import Path

from ..security.policy import resolve_user_path

CONTROL_COMMANDS = {
    "append",
    "help",
    "ls",
    "mkdir",
    "open",
    "pwd",
    "read",
    "run",
    "search",
    "sys",
    "system",
    "touch",
    "write",
}

HELP_TEXT = """电脑控制命令：
/sys 或 /pwd：查看系统与工作目录
/ls [路径]：列目录
/read <路径>：读取文本文件预览
/search <关键词> [路径]：搜索文本
/open <路径或URL>：确认后打开文件、目录或链接
/run [--cwd 路径] <命令 参数...>：确认后运行本地命令
/mkdir <路径>、/touch <路径>：确认后创建目录或文件
/write <路径> :: <内容>、/append <路径> :: <内容>：确认后写入或追加文本
"""


def split_args(text: str) -> list[str]:
    return shlex.split(text, posix=(os.name != "nt"))


def split_command(text: str) -> tuple[str, list[str], str]:
    stripped = text.strip()
    if stripped.startswith("/"):
        stripped = stripped[1:].strip()
    elif stripped.startswith("@电脑"):
        stripped = stripped[3:].strip()
    elif stripped.startswith("电脑"):
        stripped = stripped[2:].strip()
    first_line, _sep, body = stripped.partition("\n")
    try:
        tokens = split_args(first_line)
    except ValueError:
        tokens = first_line.split()
    if not tokens:
        return "", [], body
    return tokens[0].lower(), tokens[1:], body


def parse_inline_body(tokens: list[str], body: str) -> tuple[list[str], str]:
    if "::" in tokens:
        marker = tokens.index("::")
        return tokens[:marker], " ".join(tokens[marker + 1 :])
    if body.strip():
        return tokens, body
    joined = " ".join(tokens)
    if " :: " in joined:
        path_text, content = joined.split(" :: ", 1)
        try:
            return split_args(path_text), content
        except ValueError:
            return path_text.split(), content
    return tokens, ""


def parse_run_args(tokens: list[str], workspace: Path) -> tuple[Path, list[str]]:
    cwd = workspace
    remaining = list(tokens)
    if len(remaining) >= 3 and remaining[0] == "--cwd":
        cwd = resolve_user_path(remaining[1], workspace)
        remaining = remaining[2:]
    return cwd, remaining
