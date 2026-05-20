"""OpenAI-compatible chat completion client."""
from __future__ import annotations

import asyncio
import json
import urllib.error
import urllib.request
from typing import Any

from .base import ModelResponse


def _extract_content(data: dict[str, Any]) -> str:
    try:
        return str(data["choices"][0]["message"]["content"] or "")
    except Exception:
        return str(data.get("response") or data.get("text") or data.get("message") or "")


class OpenAICompatibleModelClient:
    async def complete(
        self,
        *,
        url: str,
        api_key: str,
        model: str,
        messages: list[dict[str, str]],
        max_tokens: int,
        temperature: float,
    ) -> ModelResponse:
        payload = {
            "model": model,
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
        }
        headers = {"Content-Type": "application/json"}
        if api_key.strip():
            headers["Authorization"] = f"Bearer {api_key.strip()}"
        try:
            import httpx
        except Exception:
            return await asyncio.to_thread(
                self.complete_sync,
                url=url,
                api_key=api_key,
                model=model,
                messages=messages,
                max_tokens=max_tokens,
                temperature=temperature,
            )
        async with httpx.AsyncClient(timeout=20) as client:
            response = await client.post(url, json=payload, headers=headers)
            response.raise_for_status()
            data = response.json()
        return ModelResponse(_extract_content(data), raw=data if isinstance(data, dict) else None)

    def complete_sync(
        self,
        *,
        url: str,
        api_key: str,
        model: str,
        messages: list[dict[str, str]],
        max_tokens: int,
        temperature: float,
    ) -> ModelResponse:
        payload = {
            "model": model,
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
        }
        headers = {"Content-Type": "application/json"}
        if api_key.strip():
            headers["Authorization"] = f"Bearer {api_key.strip()}"
        request = urllib.request.Request(
            url,
            data=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
            headers=headers,
            method="POST",
        )
        with urllib.request.urlopen(request, timeout=20) as response:  # noqa: S310 - user-configured endpoint
            data = json.loads(response.read().decode("utf-8"))
        return ModelResponse(_extract_content(data), raw=data if isinstance(data, dict) else None)
