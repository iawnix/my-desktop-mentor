"""OpenAI-compatible agent client and local fallback."""
from __future__ import annotations

import json
import logging
import time
from typing import TYPE_CHECKING

from ..constants.model import DEFAULT_MODEL, DEFAULT_PERSONALITY_PROMPT, MAX_AGENT_REPLY_CHARS, MAX_AGENT_REPLY_TOKENS
from ..constants.pet import DEFAULT_IDLE_MESSAGE
from ..tools.registry import build_control_tool_schemas
from .base import ModelClient, SyncModelClient
from .openai_compatible import OpenAICompatibleModelClient

if TYPE_CHECKING:
    from ..config.store import AgentConfig

LOGGER = logging.getLogger(__name__)

CONTROL_AWARENESS_PROMPT = """运行边界：
- 这个桌宠内置受控电脑操作层，可读取文件、列目录、搜索文本，并在写入/打开/运行前弹出确认卡。
- 当系统提供工具调用时，优先使用工具调用，不要在正文里伪造命令字符串。
- 用户要求读取、查看、分析桌面或本机文件时，不要让用户手动运行 type/cat/powershell 等系统命令再复制输出。
- 需要本机操作时，直接调用对应工具；多步骤任务要拆成多次工具调用，先读再写再运行。
- 不要声称已经读取、写入或运行没有实际执行的电脑操作。"""


def normalize_chat_url(raw_url: str) -> str:
    url = raw_url.strip().rstrip("/")
    if not url:
        return ""
    if url.endswith("/chat/completions"):
        return url
    if url.endswith("/v1"):
        return f"{url}/chat/completions"
    return f"{url}/v1/chat/completions"


def compact_text(text: str, limit: int = 72) -> str:
    clean = " ".join(str(text or "").split())
    if len(clean) <= limit:
        return clean
    return clean[: max(1, limit - 1)] + "…"


def limit_formatted_text(text: str, limit: int) -> str:
    clean = str(text or "").strip()
    if len(clean) <= limit:
        return clean
    return clean[: max(1, limit - 1)].rstrip() + "…"


def local_agent_reply(user_text: str, *, idle: bool = False) -> str:
    if idle:
        return DEFAULT_IDLE_MESSAGE
    text = user_text.lower()
    research_words = (
        "科研",
        "实验",
        "论文",
        "paper",
        "nature",
        "science",
        "计算",
        "模型",
        "催化",
        "量子",
        "药物",
        "数据",
    )
    if any(word in text for word in research_words):
        return "先把问题拆成目标、证据和下一步验证。你把当前材料发我，我们一起把路线理清楚。"
    return "我在。先说目标和卡点，我帮你压缩成下一步行动。"


def load_memory_messages(limit_turns: int) -> list[dict[str, str]]:
    from ..config.store import memory_path

    path = memory_path()
    if not path.exists():
        return []
    rows: list[dict[str, str]] = []
    try:
        for line in path.read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            item = json.loads(line)
            role = str(item.get("role", ""))
            content = str(item.get("content", "")).strip()
            if role in {"user", "assistant"} and content:
                rows.append({"role": role, "content": compact_text(content, 1200)})
    except Exception:
        return []
    return rows[-max(2, limit_turns * 2) :]


def append_memory_turn(user_text: str, assistant_text: str) -> None:
    from ..config.store import memory_path

    path = memory_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    timestamp = int(time.time())
    records = [
        {"ts": timestamp, "role": "user", "content": compact_text(user_text, 2000)},
        {"ts": timestamp, "role": "assistant", "content": compact_text(assistant_text, 2000)},
    ]
    with path.open("a", encoding="utf-8") as handle:
        for record in records:
            handle.write(json.dumps(record, ensure_ascii=False) + "\n")


def agent_system_prompt(config: AgentConfig) -> str:
    base_prompt = str(config.system_prompt or DEFAULT_PERSONALITY_PROMPT).strip()
    if CONTROL_AWARENESS_PROMPT in base_prompt:
        return base_prompt
    return f"{base_prompt}\n\n{CONTROL_AWARENESS_PROMPT}"


def build_agent_messages(
    config: AgentConfig,
    user_text: str,
    *,
    include_legacy_memory: bool | None = None,
) -> list[dict[str, object]]:
    messages = [
        {"role": "system", "content": agent_system_prompt(config)},
    ]
    should_include_legacy_memory = config.memory_enabled if include_legacy_memory is None else include_legacy_memory
    if should_include_legacy_memory:
        messages.extend(load_memory_messages(config.memory_turns))
    messages.append({"role": "user", "content": user_text})
    return messages


def _build_agent_tools(config: AgentConfig, tools: list[dict[str, object]] | None) -> list[dict[str, object]] | None:
    if tools is not None:
        return tools
    if getattr(config, "control_enabled", False):
        return build_control_tool_schemas()
    return None


async def complete_agent_response_async(
    config: AgentConfig,
    user_text: str,
    *,
    include_legacy_memory: bool | None = None,
    client: ModelClient | None = None,
    tools: list[dict[str, object]] | None = None,
    tool_choice: object | None = None,
) -> "ModelResponse":
    from .base import ModelResponse

    url = normalize_chat_url(config.api_url)
    if not url:
        return ModelResponse(local_agent_reply(user_text))
    model_client = client or OpenAICompatibleModelClient()
    request_tools = _build_agent_tools(config, tools)
    request_tool_choice = tool_choice
    if request_tools is not None and request_tool_choice is None:
        request_tool_choice = "auto"
    try:
        response = await model_client.complete(
            url=url,
            api_key=config.api_key,
            model=config.model or DEFAULT_MODEL,
            messages=build_agent_messages(config, user_text, include_legacy_memory=include_legacy_memory),
            max_tokens=MAX_AGENT_REPLY_TOKENS,
            temperature=0.8,
            tools=request_tools,
            tool_choice=request_tool_choice,
        )
        return response
    except Exception as exc:
        if request_tools is not None:
            LOGGER.warning("agent request with tools failed, retrying without tools: %s", exc)
            try:
                response = await model_client.complete(
                    url=url,
                    api_key=config.api_key,
                    model=config.model or DEFAULT_MODEL,
                    messages=build_agent_messages(config, user_text, include_legacy_memory=include_legacy_memory),
                    max_tokens=MAX_AGENT_REPLY_TOKENS,
                    temperature=0.8,
                )
                return response
            except Exception as retry_exc:
                exc = retry_exc
        LOGGER.warning("agent request failed: %s", exc)
        return ModelResponse(f"接口没接上。我先给本地建议：把目标、材料和卡点列出来。{type(exc).__name__}")


async def call_agent_async(
    config: AgentConfig,
    user_text: str,
    *,
    include_legacy_memory: bool | None = None,
    client: ModelClient | None = None,
    tools: list[dict[str, object]] | None = None,
    tool_choice: object | None = None,
) -> str:
    response = await complete_agent_response_async(
        config,
        user_text,
        include_legacy_memory=include_legacy_memory,
        client=client,
        tools=tools,
        tool_choice=tool_choice,
    )
    text = str(response.content or "")
    if response.tool_calls:
        return limit_formatted_text(text or local_agent_reply(user_text), MAX_AGENT_REPLY_CHARS)
    return limit_formatted_text(text or local_agent_reply(user_text), MAX_AGENT_REPLY_CHARS)


def complete_agent_response(
    config: AgentConfig,
    user_text: str,
    *,
    include_legacy_memory: bool | None = None,
    client: SyncModelClient | None = None,
    tools: list[dict[str, object]] | None = None,
    tool_choice: object | None = None,
) -> "ModelResponse":
    from .base import ModelResponse

    url = normalize_chat_url(config.api_url)
    if not url:
        return ModelResponse(local_agent_reply(user_text))
    model_client = client or OpenAICompatibleModelClient()
    request_tools = _build_agent_tools(config, tools)
    request_tool_choice = tool_choice
    if request_tools is not None and request_tool_choice is None:
        request_tool_choice = "auto"
    try:
        response = model_client.complete_sync(
            url=url,
            api_key=config.api_key,
            model=config.model or DEFAULT_MODEL,
            messages=build_agent_messages(config, user_text, include_legacy_memory=include_legacy_memory),
            max_tokens=MAX_AGENT_REPLY_TOKENS,
            temperature=0.8,
            tools=request_tools,
            tool_choice=request_tool_choice,
        )
        return response
    except Exception as exc:
        if request_tools is not None:
            LOGGER.warning("agent request with tools failed, retrying without tools: %s", exc)
            try:
                response = model_client.complete_sync(
                    url=url,
                    api_key=config.api_key,
                    model=config.model or DEFAULT_MODEL,
                    messages=build_agent_messages(config, user_text, include_legacy_memory=include_legacy_memory),
                    max_tokens=MAX_AGENT_REPLY_TOKENS,
                    temperature=0.8,
                )
                return response
            except Exception as retry_exc:
                exc = retry_exc
        LOGGER.warning("agent request failed: %s", exc)
        return ModelResponse(f"接口没接上。我先给本地建议：把目标、材料和卡点列出来。{type(exc).__name__}")


def call_agent(
    config: AgentConfig,
    user_text: str,
    *,
    include_legacy_memory: bool | None = None,
    client: SyncModelClient | None = None,
    tools: list[dict[str, object]] | None = None,
    tool_choice: object | None = None,
) -> str:
    response = complete_agent_response(
        config,
        user_text,
        include_legacy_memory=include_legacy_memory,
        client=client,
        tools=tools,
        tool_choice=tool_choice,
    )
    text = str(response.content or "")
    if response.tool_calls:
        return limit_formatted_text(text or local_agent_reply(user_text), MAX_AGENT_REPLY_CHARS)
    return limit_formatted_text(text or local_agent_reply(user_text), MAX_AGENT_REPLY_CHARS)
