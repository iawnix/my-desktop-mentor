"""Build controlled operation plans from chat commands."""
from __future__ import annotations

import secrets
import os
import shlex
from pathlib import Path

from .permissions import can_read_path, can_run_command, can_write_path, control_workspace, resolve_user_path
from .types import ControlPlan, PermissionLevel

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


def new_plan_id() -> str:
    return "control-" + secrets.token_hex(4)


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


def blocked_plan(source_text: str, title: str, reason: str, steps: list[str] | None = None) -> ControlPlan:
    return ControlPlan(
        plan_id=new_plan_id(),
        source_text=source_text,
        action="blocked",
        title=title,
        steps=steps or ["不执行该操作。"],
        permission=PermissionLevel.BLOCKED,
        blocked_reason=reason,
    )


def build_control_plan(user_text: str, raw_workspace: str = "") -> ControlPlan | None:
    text = str(user_text or "").strip()
    if not text:
        return None
    is_control = text.startswith("/") or text.startswith("@电脑") or text.startswith("电脑")
    if not is_control:
        return None
    command, tokens, body = split_command(text)
    if command not in CONTROL_COMMANDS:
        return None

    workspace = control_workspace(raw_workspace)
    plan_id = new_plan_id()
    if command == "help":
        return ControlPlan(plan_id, text, "help", "电脑控制帮助", ["显示可用命令。"], {"help": HELP_TEXT})
    if command in {"pwd", "sys", "system"}:
        return ControlPlan(plan_id, text, "system_info", "查看本机状态", ["读取系统、用户目录和控制工作目录。"], {"workspace": str(workspace)})
    if command == "ls":
        target = resolve_user_path(tokens[0], workspace) if tokens else workspace
        permission, reason = can_read_path(target)
        if permission == PermissionLevel.BLOCKED:
            return blocked_plan(text, "列目录被阻止", reason, [f"目标：{target}"])
        return ControlPlan(plan_id, text, "list_dir", "列出目录", [f"读取目录：{target}"], {"path": str(target)}, permission)
    if command == "read":
        if not tokens:
            return blocked_plan(text, "读取文件被阻止", "缺少文件路径。")
        target = resolve_user_path(tokens[0], workspace)
        permission, reason = can_read_path(target)
        if permission == PermissionLevel.BLOCKED:
            return blocked_plan(text, "读取文件被阻止", reason, [f"目标：{target}"])
        return ControlPlan(plan_id, text, "read_file", "读取文件", [f"读取文本预览：{target}"], {"path": str(target)}, permission)
    if command == "search":
        if not tokens:
            return blocked_plan(text, "搜索被阻止", "缺少搜索关键词。")
        root = resolve_user_path(tokens[1], workspace) if len(tokens) > 1 else workspace
        permission, reason = can_read_path(root)
        if permission == PermissionLevel.BLOCKED:
            return blocked_plan(text, "搜索被阻止", reason, [f"目标：{root}"])
        return ControlPlan(plan_id, text, "search_text", "搜索文本", [f"在 {root} 搜索：{tokens[0]}"], {"pattern": tokens[0], "path": str(root)}, permission)
    if command == "open":
        if not tokens:
            return blocked_plan(text, "打开被阻止", "缺少路径或 URL。")
        return ControlPlan(
            plan_id,
            text,
            "open_path",
            "打开路径或链接",
            [f"打开：{' '.join(tokens)}"],
            {"target": " ".join(tokens), "workspace": str(workspace)},
            PermissionLevel.USER_APPROVAL,
        )
    if command == "run":
        cwd, argv = parse_run_args(tokens, workspace)
        permission, reason = can_run_command(argv)
        if permission == PermissionLevel.BLOCKED:
            return blocked_plan(text, "运行命令被阻止", reason, [f"工作目录：{cwd}", f"命令：{' '.join(argv)}"])
        return ControlPlan(
            plan_id,
            text,
            "run_command",
            "运行本地命令",
            [f"工作目录：{cwd}", f"命令：{' '.join(argv)}"],
            {"cwd": str(cwd), "argv": argv},
            permission,
        )
    if command in {"mkdir", "touch"}:
        if not tokens:
            return blocked_plan(text, "创建被阻止", "缺少目标路径。")
        target = resolve_user_path(tokens[0], workspace)
        permission, reason = can_write_path(target)
        if permission == PermissionLevel.BLOCKED:
            return blocked_plan(text, "创建被阻止", reason, [f"目标：{target}"])
        action = "make_dir" if command == "mkdir" else "touch_file"
        return ControlPlan(plan_id, text, action, "创建本地项目文件" if command == "touch" else "创建目录", [f"目标：{target}"], {"path": str(target)}, permission)
    if command in {"write", "append"}:
        path_tokens, content = parse_inline_body(tokens, body)
        if not path_tokens:
            return blocked_plan(text, "写入被阻止", "缺少目标路径。")
        if not content:
            return blocked_plan(text, "写入被阻止", "缺少要写入的内容。")
        target = resolve_user_path(path_tokens[0], workspace)
        permission, reason = can_write_path(target)
        if permission == PermissionLevel.BLOCKED:
            return blocked_plan(text, "写入被阻止", reason, [f"目标：{target}"])
        action = "write_file" if command == "write" else "append_file"
        verb = "覆盖写入" if command == "write" else "追加写入"
        return ControlPlan(plan_id, text, action, f"{verb}文件", [f"目标：{target}", f"写入字符数：{len(content)}"], {"path": str(target), "content": content}, permission)
    return None
