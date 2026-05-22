"""Context assembly for model requests."""
from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from ..state.agent_store import build_agent_state_context
from ..state.conversations import build_conversation_memory_context
from ..state.user_memory import build_user_memory_context
from .skills import build_skill_context

if TYPE_CHECKING:
    from ..config.store import AgentConfig

LOGGER = logging.getLogger(__name__)


def assemble_agent_prompt(
    config: AgentConfig,
    prompt: str,
    *,
    session_id: str,
    use_conversation_context: bool,
) -> str:
    """Build a bounded, source-labeled prompt envelope for the model."""
    if not use_conversation_context:
        return prompt

    parts: list[str] = []
    try:
        skill_context = build_skill_context(config, prompt)
        if skill_context:
            parts.append(skill_context)
    except Exception:
        LOGGER.exception("failed to build skill context")

    try:
        user_memory_context = (
            build_user_memory_context(
                prompt,
                getattr(config, "long_term_memory_items", getattr(config, "memory_turns", 8)),
            )
            if getattr(config, "long_term_memory_enabled", False)
            else ""
        )
        if user_memory_context:
            parts.append(user_memory_context)
    except Exception:
        LOGGER.exception("failed to build user memory context")

    try:
        agent_state_context = build_agent_state_context(session_id, max(3, int(getattr(config, "memory_turns", 8)) // 2))
        if agent_state_context:
            parts.append(agent_state_context)
    except Exception:
        LOGGER.exception("failed to build agent state context")

    try:
        memory_context = build_conversation_memory_context(session_id, int(getattr(config, "memory_turns", 8)))
        if memory_context:
            parts.append(memory_context)
    except Exception:
        LOGGER.exception("failed to build conversation memory context")

    if not parts:
        return prompt
    context_text = "\n\n".join(parts)
    return (
        "下面是本地 agent 内核整理的上下文。只在有帮助时使用；不要逐字复述，不要把候选信息当作已验证事实。\n\n"
        f"{context_text}\n\n当前输入:\n{prompt}"
    )
