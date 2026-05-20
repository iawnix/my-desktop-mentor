"""Synchronous executors for approved control plans.

Call these from a background thread in the Qt app.
"""
from __future__ import annotations

import asyncio
import os
import platform
import shutil
import subprocess
import sys
import webbrowser
from pathlib import Path

from ..control.types import ControlPlan, ControlResult, PermissionLevel
from ..security.audit import append_audit_entry
from ..security.policy import SKIP_DIR_NAMES, control_workspace, is_sensitive_path, resolve_user_path

MAX_TEXT_BYTES = 32_000
MAX_OUTPUT_CHARS = 12_000
MAX_SEARCH_FILES = 400
MAX_SEARCH_MATCHES = 80
MAX_DIR_ENTRIES = 120
COMMAND_TIMEOUT_SECONDS = 60


def compact_output(text: str, limit: int = MAX_OUTPUT_CHARS) -> str:
    clean = str(text or "").strip()
    if len(clean) <= limit:
        return clean
    return clean[: max(1, limit - 80)] + "\n[output truncated]"


def result(plan: ControlPlan, ok: bool, output: str = "", error: str = "") -> ControlResult:
    control_result = ControlResult(plan.plan_id, plan.title, ok, compact_output(output), plan.permission, error)
    append_audit_entry(plan, control_result)
    return control_result


def format_entry(path: Path) -> str:
    try:
        stat = path.stat()
        kind = "dir " if path.is_dir() else "file"
        size = "-" if path.is_dir() else str(stat.st_size)
        return f"{kind:4} {size:>10}  {path.name}"
    except OSError as exc:
        return f"err           -  {path.name} ({type(exc).__name__})"


def execute_list_dir(plan: ControlPlan) -> ControlResult:
    path = Path(str(plan.args.get("path", ""))).expanduser()
    if not path.exists():
        return result(plan, False, error=f"路径不存在：{path}")
    if not path.is_dir():
        return result(plan, False, error=f"不是目录：{path}")
    entries = sorted(path.iterdir(), key=lambda item: (not item.is_dir(), item.name.lower()))[:MAX_DIR_ENTRIES]
    lines = [str(path), *[format_entry(entry) for entry in entries]]
    if len(entries) == MAX_DIR_ENTRIES:
        lines.append("[more entries omitted]")
    return result(plan, True, "\n".join(lines))


def execute_read_file(plan: ControlPlan) -> ControlResult:
    path = Path(str(plan.args.get("path", ""))).expanduser()
    if not path.exists():
        return result(plan, False, error=f"文件不存在：{path}")
    if not path.is_file():
        return result(plan, False, error=f"不是文件：{path}")
    try:
        data = path.read_bytes()[:MAX_TEXT_BYTES + 1]
    except OSError as exc:
        return result(plan, False, error=f"{type(exc).__name__}: {exc}")
    if b"\0" in data[:1024]:
        return result(plan, False, error="看起来是二进制文件，未读取。")
    truncated = len(data) > MAX_TEXT_BYTES
    text = data[:MAX_TEXT_BYTES].decode("utf-8", errors="replace")
    if truncated:
        text += "\n[file truncated]"
    return result(plan, True, text)


def iter_search_files(root: Path):
    if root.is_file():
        yield root
        return
    seen = 0
    for current, dirs, files in os.walk(root):
        dirs[:] = [name for name in dirs if name not in SKIP_DIR_NAMES and not is_sensitive_path(Path(current) / name)]
        for name in files:
            path = Path(current) / name
            if is_sensitive_path(path):
                continue
            seen += 1
            if seen > MAX_SEARCH_FILES:
                return
            yield path


def execute_search_text(plan: ControlPlan) -> ControlResult:
    pattern = str(plan.args.get("pattern", ""))
    root = Path(str(plan.args.get("path", ""))).expanduser()
    if not pattern:
        return result(plan, False, error="缺少搜索关键词。")
    if not root.exists():
        return result(plan, False, error=f"路径不存在：{root}")
    matches: list[str] = []
    lowered = pattern.lower()
    for path in iter_search_files(root):
        try:
            if path.stat().st_size > 1_000_000:
                continue
            text = path.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        for index, line in enumerate(text.splitlines(), start=1):
            if lowered in line.lower():
                matches.append(f"{path}:{index}: {line.strip()[:240]}")
                if len(matches) >= MAX_SEARCH_MATCHES:
                    return result(plan, True, "\n".join(matches) + "\n[more matches omitted]")
    return result(plan, True, "\n".join(matches) if matches else "未找到匹配。")


def execute_system_info(plan: ControlPlan) -> ControlResult:
    workspace = control_workspace(str(plan.args.get("workspace", "")))
    lines = [
        f"platform: {platform.platform()}",
        f"system: {platform.system()} {platform.release()}",
        f"python: {sys.version.split()[0]}",
        f"home: {Path.home()}",
        f"workspace: {workspace}",
        f"cwd: {Path.cwd()}",
    ]
    return result(plan, True, "\n".join(lines))


def execute_open_path(plan: ControlPlan) -> ControlResult:
    target = str(plan.args.get("target", "")).strip()
    workspace = control_workspace(str(plan.args.get("workspace", "")))
    if not target:
        return result(plan, False, error="缺少打开目标。")
    if target.startswith(("http://", "https://")):
        opened = webbrowser.open(target)
        return result(plan, opened, f"已请求打开链接：{target}" if opened else "", "" if opened else "系统拒绝打开链接。")
    path = resolve_user_path(target, workspace)
    if not path.exists():
        return result(plan, False, error=f"路径不存在：{path}")
    try:
        if sys.platform == "win32":
            os.startfile(str(path))  # type: ignore[attr-defined]
        elif sys.platform == "darwin":
            subprocess.Popen(["open", str(path)])
        else:
            opener = shutil.which("xdg-open")
            if not opener:
                return result(plan, False, error="未找到 xdg-open。")
            subprocess.Popen([opener, str(path)])
    except OSError as exc:
        return result(plan, False, error=f"{type(exc).__name__}: {exc}")
    return result(plan, True, f"已请求打开：{path}")


def execute_run_command(plan: ControlPlan) -> ControlResult:
    argv = [str(item) for item in plan.args.get("argv", []) if str(item)]
    cwd = Path(str(plan.args.get("cwd", ""))).expanduser()
    if not argv:
        return result(plan, False, error="缺少命令。")
    if not cwd.exists() or not cwd.is_dir():
        return result(plan, False, error=f"工作目录不可用：{cwd}")
    try:
        completed = subprocess.run(
            argv,
            cwd=str(cwd),
            shell=False,
            text=True,
            capture_output=True,
            timeout=COMMAND_TIMEOUT_SECONDS,
            check=False,
        )
    except Exception as exc:
        return result(plan, False, error=f"{type(exc).__name__}: {exc}")
    output = "\n".join(
        part
        for part in (
            f"exit_code: {completed.returncode}",
            completed.stdout.strip(),
            completed.stderr.strip(),
        )
        if part
    )
    return result(plan, completed.returncode == 0, output)


def execute_make_dir(plan: ControlPlan) -> ControlResult:
    path = Path(str(plan.args.get("path", ""))).expanduser()
    try:
        path.mkdir(parents=True, exist_ok=True)
    except OSError as exc:
        return result(plan, False, error=f"{type(exc).__name__}: {exc}")
    return result(plan, True, f"目录已创建：{path}")


def execute_touch_file(plan: ControlPlan) -> ControlResult:
    path = Path(str(plan.args.get("path", ""))).expanduser()
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.touch(exist_ok=True)
    except OSError as exc:
        return result(plan, False, error=f"{type(exc).__name__}: {exc}")
    return result(plan, True, f"文件已创建：{path}")


def execute_write_file(plan: ControlPlan, *, append: bool) -> ControlResult:
    path = Path(str(plan.args.get("path", ""))).expanduser()
    content = str(plan.args.get("content", ""))
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        mode = "a" if append else "w"
        with path.open(mode, encoding="utf-8") as handle:
            handle.write(content)
            if content and not content.endswith("\n"):
                handle.write("\n")
    except OSError as exc:
        return result(plan, False, error=f"{type(exc).__name__}: {exc}")
    verb = "追加写入" if append else "覆盖写入"
    return result(plan, True, f"{verb}完成：{path}")


def execute_control_plan(plan: ControlPlan) -> ControlResult:
    if plan.is_blocked:
        return result(plan, False, error=plan.blocked_reason or "操作被阻止。")
    if plan.action == "help":
        return result(plan, True, str(plan.args.get("help", "")))
    if plan.action == "system_info":
        return execute_system_info(plan)
    if plan.action == "list_dir":
        return execute_list_dir(plan)
    if plan.action == "read_file":
        return execute_read_file(plan)
    if plan.action == "search_text":
        return execute_search_text(plan)
    if plan.action == "open_path":
        return execute_open_path(plan)
    if plan.action == "run_command":
        return execute_run_command(plan)
    if plan.action == "make_dir":
        return execute_make_dir(plan)
    if plan.action == "touch_file":
        return execute_touch_file(plan)
    if plan.action == "write_file":
        return execute_write_file(plan, append=False)
    if plan.action == "append_file":
        return execute_write_file(plan, append=True)
    return result(plan, False, error=f"未知操作：{plan.action}")


async def execute_control_plan_async(plan: ControlPlan) -> ControlResult:
    return await asyncio.to_thread(execute_control_plan, plan)
