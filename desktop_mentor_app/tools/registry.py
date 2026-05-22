"""Build controlled operation plans from chat commands and model tool calls."""
from __future__ import annotations

import json
import shlex

from ..model_client.base import ModelResponse, ToolCall
from ..security.policy import can_read_path, can_run_command, can_write_path, control_workspace, resolve_user_path
from .command_parser import CONTROL_COMMANDS, HELP_TEXT, parse_inline_body, parse_run_args, split_command
from .natural_language import build_natural_language_plan
from .path_parser import desktop_path
from .plan_helpers import blocked_plan, new_plan_id
from .types import ControlPlan, PermissionLevel


def build_control_tool_schemas() -> list[dict[str, object]]:
    return [
        {
            "type": "function",
            "function": {
                "name": "system_info",
                "description": "查看系统、用户目录和当前控制工作目录。",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "workspace": {
                            "type": "string",
                            "description": "可选的控制工作目录提示，通常留空。",
                        }
                    },
                    "additionalProperties": False,
                },
            },
        },
        {
            "type": "function",
            "function": {
                "name": "list_dir",
                "description": "列出一个目录的内容。",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "path": {
                            "type": "string",
                            "description": "要列出的目录路径；省略时使用控制工作目录。",
                        }
                    },
                    "additionalProperties": False,
                },
            },
        },
        {
            "type": "function",
            "function": {
                "name": "path_info",
                "description": "查看路径是否存在、类型、大小和是否可执行，不读取文件内容。",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "path": {
                            "type": "string",
                            "description": "要检查的文件或目录路径。",
                        }
                    },
                    "required": ["path"],
                    "additionalProperties": False,
                },
            },
        },
        {
            "type": "function",
            "function": {
                "name": "read_file",
                "description": "读取一个文本文件的预览内容。",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "path": {
                            "type": "string",
                            "description": "要读取的文件路径。",
                        }
                    },
                    "required": ["path"],
                    "additionalProperties": False,
                },
            },
        },
        {
            "type": "function",
            "function": {
                "name": "search_text",
                "description": "在文件或目录中搜索文本。",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "pattern": {
                            "type": "string",
                            "description": "要搜索的关键词或短语。",
                        },
                        "path": {
                            "type": "string",
                            "description": "可选的搜索根路径；省略时使用控制工作目录。",
                        },
                    },
                    "required": ["pattern"],
                    "additionalProperties": False,
                },
            },
        },
        {
            "type": "function",
            "function": {
                "name": "open_path",
                "description": "打开文件、目录或 URL。",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "target": {
                            "type": "string",
                            "description": "要打开的文件、目录或 URL。",
                        }
                    },
                    "required": ["target"],
                    "additionalProperties": False,
                },
            },
        },
        {
            "type": "function",
            "function": {
                "name": "run_command",
                "description": "在本机运行一个命令。",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "cwd": {
                            "type": "string",
                            "description": "命令工作目录；省略时使用控制工作目录。",
                        },
                        "command": {
                            "type": "string",
                            "description": "要运行的命令名或可执行文件。",
                        },
                        "args": {
                            "type": "array",
                            "items": {"type": "string"},
                            "description": "命令参数列表。",
                        },
                    },
                    "required": ["command"],
                    "additionalProperties": False,
                },
            },
        },
        {
            "type": "function",
            "function": {
                "name": "make_dir",
                "description": "创建一个目录。",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "path": {
                            "type": "string",
                            "description": "要创建的目录路径。",
                        }
                    },
                    "required": ["path"],
                    "additionalProperties": False,
                },
            },
        },
        {
            "type": "function",
            "function": {
                "name": "touch_file",
                "description": "创建一个空文件。",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "path": {
                            "type": "string",
                            "description": "要创建的文件路径。",
                        }
                    },
                    "required": ["path"],
                    "additionalProperties": False,
                },
            },
        },
        {
            "type": "function",
            "function": {
                "name": "write_file",
                "description": "覆盖写入一个文本文件。",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "path": {
                            "type": "string",
                            "description": "要写入的文件路径。",
                        },
                        "content": {
                            "type": "string",
                            "description": "要写入的完整文本内容。",
                        },
                    },
                    "required": ["path", "content"],
                    "additionalProperties": False,
                },
            },
        },
        {
            "type": "function",
            "function": {
                "name": "append_file",
                "description": "向一个文本文件追加内容。",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "path": {
                            "type": "string",
                            "description": "要追加的文件路径。",
                        },
                        "content": {
                            "type": "string",
                            "description": "要追加的文本内容。",
                        },
                    },
                    "required": ["path", "content"],
                    "additionalProperties": False,
                },
            },
        },
    ]


def _tool_source_text(tool_call: ToolCall) -> str:
    raw_arguments = str(tool_call.raw_arguments or "").strip()
    if raw_arguments:
        return f"{tool_call.name} {raw_arguments}".strip()
    if isinstance(tool_call.arguments, dict) and tool_call.arguments:
        try:
            return f"{tool_call.name} {json.dumps(tool_call.arguments, ensure_ascii=False)}".strip()
        except Exception:
            pass
    return str(tool_call.name or "").strip()


def _tool_args(tool_call: ToolCall) -> dict[str, object]:
    if isinstance(tool_call.arguments, dict):
        return tool_call.arguments
    return {}


def _tool_string_arg(args: dict[str, object], key: str, default: str = "") -> str:
    value = args.get(key, default)
    return str(value or "").strip()


def _tool_list_arg(args: dict[str, object], key: str) -> list[str]:
    value = args.get(key, [])
    if isinstance(value, list):
        return [str(item).strip() for item in value if str(item).strip()]
    if isinstance(value, str):
        try:
            return [part for part in shlex.split(value) if part]
        except ValueError:
            return [part for part in value.split() if part]
    return []


def _tool_run_argv(args: dict[str, object]) -> list[str]:
    argv = _tool_list_arg(args, "argv")
    if argv:
        return argv
    command = _tool_string_arg(args, "command")
    if not command:
        return []
    extra_args = _tool_list_arg(args, "args")
    if extra_args:
        return [command, *extra_args]
    try:
        return [part for part in shlex.split(command) if part]
    except ValueError:
        return [part for part in command.split() if part]


def build_control_plan_from_tool_call(tool_call: ToolCall, raw_workspace: str = "") -> ControlPlan:
    workspace = control_workspace(raw_workspace)
    args = _tool_args(tool_call)
    source_text = _tool_source_text(tool_call) or str(tool_call.id or "").strip()
    plan_id = str(tool_call.id or new_plan_id())
    tool_name = str(tool_call.name or "").strip().lower()

    if tool_name == "system_info":
        return ControlPlan(
            plan_id,
            source_text,
            "system_info",
            "查看本机状态",
            ["读取系统、用户目录和控制工作目录。"],
            {"workspace": str(workspace)},
            PermissionLevel.READ_ONLY,
        )

    if tool_name == "list_dir":
        target_text = _tool_string_arg(args, "path") or str(workspace)
        target = resolve_user_path(target_text, workspace)
        permission, reason = can_read_path(target)
        if permission == PermissionLevel.BLOCKED:
            return blocked_plan(source_text, "列目录被阻止", reason, [f"目标：{target}"])
        return ControlPlan(
            plan_id,
            source_text,
            "list_dir",
            "列出目录",
            [f"读取目录：{target}"],
            {"path": str(target)},
            permission,
        )

    if tool_name == "path_info":
        target_text = _tool_string_arg(args, "path")
        if not target_text:
            return blocked_plan(source_text, "路径检查被阻止", "缺少路径。", ["请提供 path。"])
        target = resolve_user_path(target_text, workspace)
        permission, reason = can_read_path(target)
        if permission == PermissionLevel.BLOCKED:
            return blocked_plan(source_text, "路径检查被阻止", reason, [f"目标：{target}"])
        return ControlPlan(
            plan_id,
            source_text,
            "path_info",
            "检查路径信息",
            [f"检查路径：{target}"],
            {"path": str(target)},
            permission,
        )

    if tool_name == "read_file":
        target_text = _tool_string_arg(args, "path")
        if not target_text:
            return blocked_plan(source_text, "读取文件被阻止", "缺少文件路径。", ["请提供 path。"])
        target = resolve_user_path(target_text, workspace)
        permission, reason = can_read_path(target)
        if permission == PermissionLevel.BLOCKED:
            return blocked_plan(source_text, "读取文件被阻止", reason, [f"目标：{target}"])
        return ControlPlan(
            plan_id,
            source_text,
            "read_file",
            "读取文件",
            [f"读取文本预览：{target}"],
            {"path": str(target)},
            permission,
        )

    if tool_name == "search_text":
        pattern = _tool_string_arg(args, "pattern")
        if not pattern:
            return blocked_plan(source_text, "搜索被阻止", "缺少搜索关键词。", ["请提供 pattern。"])
        root_text = _tool_string_arg(args, "path") or str(workspace)
        root = resolve_user_path(root_text, workspace)
        permission, reason = can_read_path(root)
        if permission == PermissionLevel.BLOCKED:
            return blocked_plan(source_text, "搜索被阻止", reason, [f"目标：{root}"])
        return ControlPlan(
            plan_id,
            source_text,
            "search_text",
            "搜索文本",
            [f"在 {root} 搜索：{pattern}"],
            {"pattern": pattern, "path": str(root)},
            permission,
        )

    if tool_name == "open_path":
        target_text = _tool_string_arg(args, "target")
        if not target_text:
            return blocked_plan(source_text, "打开被阻止", "缺少打开目标。", ["请提供 target。"])
        return ControlPlan(
            plan_id,
            source_text,
            "open_path",
            "打开路径或链接",
            [f"打开：{target_text}"],
            {"target": target_text, "workspace": str(workspace)},
            PermissionLevel.USER_APPROVAL,
        )

    if tool_name == "run_command":
        cwd_text = _tool_string_arg(args, "cwd") or str(workspace)
        cwd = resolve_user_path(cwd_text, workspace)
        argv = _tool_run_argv(args)
        permission, reason = can_run_command(argv)
        if permission == PermissionLevel.BLOCKED:
            return blocked_plan(
                source_text,
                "运行命令被阻止",
                reason,
                [f"工作目录：{cwd}", f"命令：{' '.join(argv)}"],
            )
        return ControlPlan(
            plan_id,
            source_text,
            "run_command",
            "运行本地命令",
            [f"工作目录：{cwd}", f"命令：{' '.join(argv)}"],
            {"cwd": str(cwd), "argv": argv},
            permission,
        )

    if tool_name == "make_dir":
        target_text = _tool_string_arg(args, "path")
        if not target_text:
            return blocked_plan(source_text, "创建目录被阻止", "缺少目标路径。", ["请提供 path。"])
        target = resolve_user_path(target_text, workspace)
        permission, reason = can_write_path(target)
        if permission == PermissionLevel.BLOCKED:
            return blocked_plan(source_text, "创建目录被阻止", reason, [f"目标：{target}"])
        return ControlPlan(
            plan_id,
            source_text,
            "make_dir",
            "创建目录",
            [f"目标：{target}"],
            {"path": str(target)},
            permission,
        )

    if tool_name == "touch_file":
        target_text = _tool_string_arg(args, "path")
        if not target_text:
            return blocked_plan(source_text, "创建文件被阻止", "缺少目标路径。", ["请提供 path。"])
        target = resolve_user_path(target_text, workspace)
        permission, reason = can_write_path(target)
        if permission == PermissionLevel.BLOCKED:
            return blocked_plan(source_text, "创建文件被阻止", reason, [f"目标：{target}"])
        return ControlPlan(
            plan_id,
            source_text,
            "touch_file",
            "创建文件",
            [f"目标：{target}"],
            {"path": str(target)},
            permission,
        )

    if tool_name in {"write_file", "append_file"}:
        target_text = _tool_string_arg(args, "path")
        content = _tool_string_arg(args, "content")
        if not target_text:
            return blocked_plan(source_text, "写入被阻止", "缺少目标路径。", ["请提供 path。"])
        if not content:
            return blocked_plan(source_text, "写入被阻止", "缺少要写入的内容。", ["请提供 content。"])
        target = resolve_user_path(target_text, workspace)
        permission, reason = can_write_path(target)
        if permission == PermissionLevel.BLOCKED:
            return blocked_plan(source_text, "写入被阻止", reason, [f"目标：{target}"])
        action = "write_file" if tool_name == "write_file" else "append_file"
        verb = "覆盖写入" if tool_name == "write_file" else "追加写入"
        return ControlPlan(
            plan_id,
            source_text,
            action,
            f"{verb}文件",
            [f"目标：{target}", f"写入字符数：{len(content)}"],
            {"path": str(target), "content": content},
            permission,
        )

    return blocked_plan(source_text, "未知工具调用", f"不支持的工具：{tool_call.name}", [f"工具：{tool_call.name}"])


def build_control_plan_from_model_response(response: ModelResponse, raw_workspace: str = "") -> tuple[ControlPlan | None, str]:
    tool_calls = list(response.tool_calls or [])
    if not tool_calls:
        return None, str(response.content or "").strip()
    plan = build_control_plan_from_tool_call(tool_calls[0], raw_workspace)
    return plan, str(response.content or "").strip()


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
    if command == "stat":
        if not tokens:
            return blocked_plan(text, "路径检查被阻止", "缺少路径。")
        target = resolve_user_path(tokens[0], workspace)
        permission, reason = can_read_path(target)
        if permission == PermissionLevel.BLOCKED:
            return blocked_plan(text, "路径检查被阻止", reason, [f"目标：{target}"])
        return ControlPlan(plan_id, text, "path_info", "检查路径信息", [f"检查路径：{target}"], {"path": str(target)}, permission)
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

__all__ = [
    "build_control_plan",
    "build_control_plan_from_model_response",
    "build_control_plan_from_tool_call",
    "build_control_tool_schemas",
    "desktop_path",
]
