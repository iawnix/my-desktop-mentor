"""OpenAI-compatible agent client and local fallback."""
from __future__ import annotations

import json
import time
import urllib.error
import urllib.request

from .config_store import AgentConfig, memory_path
from .constants import (
    DEFAULT_IDLE_MESSAGE,
    DEFAULT_MODEL,
    DEFAULT_PERSONALITY_PROMPT,
    MAX_AGENT_REPLY_CHARS,
)


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


def call_agent(config: AgentConfig, user_text: str) -> str:
    url = normalize_chat_url(config.api_url)
    if not url:
        return local_agent_reply(user_text)

    payload = {
        "model": config.model or DEFAULT_MODEL,
        "messages": [
            {"role": "system", "content": config.system_prompt or DEFAULT_PERSONALITY_PROMPT},
        ],
        "temperature": 0.8,
        "max_tokens": 160,
    }
    if config.memory_enabled:
        payload["messages"].extend(load_memory_messages(config.memory_turns))
    payload["messages"].append({"role": "user", "content": user_text})
    headers = {"Content-Type": "application/json"}
    if config.api_key.strip():
        headers["Authorization"] = f"Bearer {config.api_key.strip()}"

    request = urllib.request.Request(
        url,
        data=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
        headers=headers,
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=20) as response:  # noqa: S310 - user-configured endpoint
            data = json.loads(response.read().decode("utf-8"))
    except (urllib.error.URLError, TimeoutError, json.JSONDecodeError, OSError) as exc:
        return f"接口没接上。我先给本地建议：把目标、材料和卡点列出来。{type(exc).__name__}"

    try:
        content = data["choices"][0]["message"]["content"]
    except Exception:
        content = data.get("response") or data.get("text") or data.get("message") or ""
    return compact_text(str(content or local_agent_reply(user_text)), MAX_AGENT_REPLY_CHARS)
