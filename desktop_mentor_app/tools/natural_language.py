"""Natural-language control-plan builders."""
from __future__ import annotations

from pathlib import Path

from ..control.types import ControlPlan, PermissionLevel
from ..security.policy import can_read_path, can_write_path
from .path_parser import (
    WRITABLE_TEXT_SUFFIXES,
    desktop_path,
    extract_filename,
    extract_read_target,
    extract_write_content,
)
from .plan_helpers import blocked_plan, new_plan_id


def build_natural_language_read_plan(text: str, workspace: Path) -> ControlPlan | None:
    normalized = " ".join(text.split())
    lowered = normalized.lower()
    wants_read = any(
        keyword in normalized
        for keyword in (
            "读取",
            "读一下",
            "读下",
            "读它",
            "读这个",
            "读该",
            "查看",
            "看一下",
            "看下",
            "看它",
            "帮我看",
            "检查",
            "分析",
            "总结",
            "审稿",
            "润色",
        )
    ) or any(keyword in lowered for keyword in ("read", "view", "check", "review", "analyze", "summarize", "type "))
    wants_file_change = any(keyword in normalized for keyword in ("创建", "新建", "生成", "写入", "写上", "保存"))
    path_context = "路径" in normalized or "文件" in normalized or "path" in lowered
    target = extract_read_target(normalized, workspace)
    if target is None or wants_file_change or not (wants_read or path_context):
        return None
    permission, reason = can_read_path(target)
    if permission == PermissionLevel.BLOCKED:
        return blocked_plan(text, "读取本机文件被阻止", reason, [f"目标：{target}"])
    return ControlPlan(
        new_plan_id(),
        text,
        "read_file",
        "读取本机文件",
        [f"目标文件：{target}", "读取后会把文本预览显示在会话里。"],
        {"path": str(target), "workspace": str(workspace)},
        PermissionLevel.USER_APPROVAL,
    )


def build_natural_language_list_plan(text: str, workspace: Path) -> ControlPlan | None:
    normalized = " ".join(text.split())
    lowered = normalized.lower()
    wants_file_change = any(keyword in normalized for keyword in ("创建", "新建", "生成", "写入", "写上", "保存"))
    if wants_file_change:
        return None

    mentions_desktop = "桌面" in normalized or "desktop" in lowered
    mentions_file_list = (
        "文件列表" in normalized
        or "目录列表" in normalized
        or "列文件" in normalized
        or "列桌面" in normalized
        or "列出文件" in normalized
        or "列一下" in normalized
        or "列出" in normalized
        or "看看有哪些" in normalized
        or "有哪些文件" in normalized
        or "list files" in lowered
        or "list desktop" in lowered
    )
    if not (mentions_desktop and mentions_file_list):
        return None

    target = desktop_path()
    permission, reason = can_read_path(target)
    if permission == PermissionLevel.BLOCKED:
        return blocked_plan(text, "列出桌面文件被阻止", reason, [f"目标目录：{target}"])
    return ControlPlan(
        new_plan_id(),
        text,
        "list_dir",
        "列出桌面文件",
        [f"目标目录：{target}", "执行后会把桌面文件列表显示在会话里。"],
        {"path": str(target), "workspace": str(workspace)},
        PermissionLevel.USER_APPROVAL,
    )


def build_natural_language_write_plan(text: str, workspace: Path) -> ControlPlan | None:
    normalized = " ".join(text.split())
    lowered = normalized.lower()
    mentions_desktop = "桌面" in normalized or "desktop" in lowered
    wants_file_change = any(keyword in normalized for keyword in ("创建", "新建", "生成", "写入", "写上", "保存"))
    mentions_file = "文件" in normalized or any(suffix in lowered for suffix in WRITABLE_TEXT_SUFFIXES)
    wants_write = any(keyword in normalized for keyword in ("写", "写入", "写上", "内容"))
    if not (mentions_desktop and wants_file_change and mentions_file and wants_write):
        return None

    filename = extract_filename(normalized)
    content = extract_write_content(normalized)
    if not content:
        return None
    target = (desktop_path() / filename).expanduser().resolve(strict=False)
    permission, reason = can_write_path(target)
    if permission == PermissionLevel.BLOCKED:
        return blocked_plan(text, "创建桌面文件被阻止", reason, [f"目标：{target}"])
    return ControlPlan(
        new_plan_id(),
        text,
        "write_file",
        "创建并写入桌面文件",
        [
            f"目标文件：{target}",
            f"写入内容预览：{content[:120]}",
            f"写入字符数：{len(content)}",
        ],
        {"path": str(target), "content": content},
        PermissionLevel.USER_APPROVAL,
    )


NATURAL_LANGUAGE_PLAN_BUILDERS = (
    build_natural_language_read_plan,
    build_natural_language_list_plan,
    build_natural_language_write_plan,
)


def build_natural_language_plan(text: str, workspace: Path) -> ControlPlan | None:
    for builder in NATURAL_LANGUAGE_PLAN_BUILDERS:
        plan = builder(text, workspace)
        if plan is not None:
            return plan
    return None
