"""Build controlled operation plans from chat commands."""
from __future__ import annotations

import re
from dataclasses import replace

from ..control.types import ControlPlan, PermissionLevel
from ..security.policy import can_read_path, can_run_command, can_write_path, control_workspace, resolve_user_path
from .command_parser import CONTROL_COMMANDS, HELP_TEXT, parse_inline_body, parse_run_args, split_command
from .natural_language import build_natural_language_plan
from .path_parser import desktop_path
from .plan_helpers import blocked_plan, new_plan_id

CONTROL_REQUEST_RE = re.compile(
    r"^\s*(?:CONTROL_REQUEST|COMPUTER_CONTROL|Computer control|电脑控制请求|电脑控制|工具请求)\s*[:：]\s*(.+?)\s*$",
    re.IGNORECASE | re.MULTILINE,
)
CONTROL_REPLY_HINTS = (
    "Computer control",
    "电脑控制",
    "内置电脑控制",
    "确认卡",
    "授权卡",
    "允许本次",
)


def build_control_plan(user_text: str, raw_workspace: str = "") -> ControlPlan | None:
    text = str(user_text or "").strip()
    if not text:
        return None
    is_control = text.startswith("/") or text.startswith("@电脑") or text.startswith("电脑")
    workspace = control_workspace(raw_workspace)
    if not is_control:
        return build_natural_language_plan(text, workspace)
    command, tokens, body = split_command(text)
    if command not in CONTROL_COMMANDS:
        return None

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


def split_agent_control_request(reply_text: str) -> tuple[str, str]:
    text = str(reply_text or "")
    match = CONTROL_REQUEST_RE.search(text)
    if match is None:
        return "", text
    request = match.group(1).strip()
    cleaned_lines = [line for line in text.splitlines() if CONTROL_REQUEST_RE.match(line) is None]
    return request, "\n".join(cleaned_lines).strip()


def build_control_plan_from_agent_reply(reply_text: str, raw_workspace: str = "") -> tuple[ControlPlan | None, str]:
    request_text, cleaned_reply = split_agent_control_request(reply_text)
    source_text = request_text
    lowered_reply = str(reply_text or "").lower()
    if not source_text and any(hint.lower() in lowered_reply for hint in CONTROL_REPLY_HINTS):
        source_text = str(reply_text or "")
    if not source_text:
        return None, str(reply_text or "")

    plan = build_control_plan(source_text, raw_workspace)
    if plan is not None and plan.permission == PermissionLevel.READ_ONLY:
        plan = replace(plan, permission=PermissionLevel.USER_APPROVAL)
    return plan, cleaned_reply


__all__ = [
    "build_control_plan",
    "build_control_plan_from_agent_reply",
    "desktop_path",
    "split_agent_control_request",
]
