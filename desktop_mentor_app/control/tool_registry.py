"""Build controlled operation plans from chat commands."""
from __future__ import annotations

import os
import re
import secrets
import shlex
import time
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

WRITABLE_TEXT_SUFFIXES = (".txt", ".md", ".log", ".csv", ".json")
READABLE_TEXT_SUFFIXES = WRITABLE_TEXT_SUFFIXES + (".tex", ".rst")
WINDOWS_FORBIDDEN_FILENAME_CHARS = re.compile(r'[<>:"/\\|?*\x00-\x1f]')
WINDOWS_ABSOLUTE_PATH = re.compile(r"([A-Za-z]:[\\/][^\n`\"'，。；;]+?\.(?:txt|md|log|csv|json|tex|rst))", re.IGNORECASE)
POSIX_ABSOLUTE_PATH = re.compile(r"(/[^\n`\"'，。；;\s]+?\.(?:txt|md|log|csv|json|tex|rst))", re.IGNORECASE)


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


def build_natural_language_read_plan(text: str, workspace: Path) -> ControlPlan | None:
    normalized = " ".join(text.split())
    lowered = normalized.lower()
    wants_read = any(
        keyword in normalized
        for keyword in ("读取", "读一下", "读下", "查看", "看一下", "看下", "帮我看", "检查", "分析", "总结", "审稿", "润色")
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
