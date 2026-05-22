"""Local skill discovery and prompt injection."""
from __future__ import annotations

import logging
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING

from ..config.store import config_path
from ..core.assets import ROOT

if TYPE_CHECKING:
    from ..config.store import AgentConfig

LOGGER = logging.getLogger(__name__)

MAX_SKILL_TEXT_CHARS = 3200
MAX_ACTIVE_SKILLS = 3

BUILTIN_SKILLS_DIR = ROOT / "desktop_mentor_app" / "skills"


@dataclass(frozen=True)
class LocalSkill:
    name: str
    path: Path
    triggers: tuple[str, ...]
    content: str


def compact_skill_text(text: str, limit: int = MAX_SKILL_TEXT_CHARS) -> str:
    clean = str(text or "").strip()
    if len(clean) <= limit:
        return clean
    return clean[: max(1, limit - 1)].rstrip() + "…"


def parse_skill_file(path: Path) -> LocalSkill | None:
    try:
        content = path.read_text(encoding="utf-8")
    except OSError as exc:
        LOGGER.warning("failed to read skill %s: %s", path, exc)
        return None
    name = path.parent.name
    triggers: list[str] = []
    for line in content.splitlines()[:40]:
        stripped = line.strip()
        lowered = stripped.lower()
        if lowered.startswith("name:"):
            name = stripped.split(":", 1)[1].strip() or name
        elif lowered.startswith("triggers:"):
            raw_triggers = stripped.split(":", 1)[1]
            triggers.extend(part.strip().lower() for part in raw_triggers.split(",") if part.strip())
    if not triggers:
        triggers = [name.lower()]
    return LocalSkill(
        name=name,
        path=path,
        triggers=tuple(dict.fromkeys(triggers)),
        content=compact_skill_text(content),
    )


def skill_roots(config: AgentConfig) -> list[Path]:
    roots = [BUILTIN_SKILLS_DIR]
    configured_dir = str(getattr(config, "config_dir", "") or "").strip()
    runtime_root = Path(configured_dir).expanduser() if configured_dir else config_path().parent
    roots.append(runtime_root / "skills")
    return roots


def discover_local_skills(config: AgentConfig) -> list[LocalSkill]:
    skills: list[LocalSkill] = []
    seen: set[Path] = set()
    for root in skill_roots(config):
        try:
            candidates = sorted(root.glob("*/SKILL.md"))
        except OSError:
            continue
        for path in candidates:
            resolved = path.resolve(strict=False)
            if resolved in seen:
                continue
            seen.add(resolved)
            skill = parse_skill_file(path)
            if skill is not None:
                skills.append(skill)
    return skills


def match_local_skills(config: AgentConfig, prompt: str) -> list[LocalSkill]:
    text = str(prompt or "").lower()
    if not text:
        return []
    matched: list[LocalSkill] = []
    for skill in discover_local_skills(config):
        if any(trigger and trigger in text for trigger in skill.triggers):
            matched.append(skill)
        if len(matched) >= MAX_ACTIVE_SKILLS:
            break
    return matched


def build_skill_context(config: AgentConfig, prompt: str) -> str:
    skills = match_local_skills(config, prompt)
    if not skills:
        return ""
    blocks = []
    for skill in skills:
        blocks.append(f"## {skill.name}\nSource: {skill.path}\n{skill.content}")
    return (
        "以下是本地 skill 目录按当前输入匹配到的工作流说明。"
        "它们只能指导如何组合基础工具，不会新增专用 function；执行仍必须通过工具结果验证。\n\n"
        + "\n\n".join(blocks)
    )
