"""OpenAI-compatible chat completion client."""
from __future__ import annotations

import asyncio
import json
import urllib.error
import urllib.request
from typing import Any

from .base import ModelResponse, ToolCall


def _extract_content(data: dict[str, Any]) -> str:
    try:
        return str(data["choices"][0]["message"]["content"] or "")
    except Exception:
        return str(data.get("response") or data.get("text") or data.get("message") or "")


def _parse_tool_arguments(raw_arguments: object) -> tuple[dict[str, object], str]:
    if isinstance(raw_arguments, dict):
        return raw_arguments, json.dumps(raw_arguments, ensure_ascii=False)
    raw_text = str(raw_arguments or "").strip()
    if not raw_text:
        return {}, ""
    try:
        parsed = json.loads(raw_text)
    except Exception:
        return {}, raw_text
    if isinstance(parsed, dict):
        return parsed, raw_text
    return {}, raw_text


def _extract_tool_calls(data: dict[str, Any]) -> list[ToolCall]:
    try:
        message = data["choices"][0]["message"]
    except Exception:
        return []
    if not isinstance(message, dict):
        return []

    raw_tool_calls = message.get("tool_calls")
    parsed_calls: list[ToolCall] = []
    if isinstance(raw_tool_calls, list):
        for index, item in enumerate(raw_tool_calls):
            if not isinstance(item, dict):
                continue
            function = item.get("function")
            function_data = function if isinstance(function, dict) else {}
            arguments, raw_arguments = _parse_tool_arguments(function_data.get("arguments"))
            name = str(function_data.get("name", item.get("name", "")) or "").strip()
            if not name:
                continue
            tool_id = str(item.get("id") or item.get("tool_call_id") or f"tool_call_{index}")
            parsed_calls.append(
                ToolCall(
                    id=tool_id,
                    name=name,
                    arguments=arguments,
                    raw_arguments=raw_arguments,
                    raw=item,
                )
            )
        if parsed_calls:
            return parsed_calls

    raw_function_call = message.get("function_call")
    if isinstance(raw_function_call, dict):
        arguments, raw_arguments = _parse_tool_arguments(raw_function_call.get("arguments"))
        name = str(raw_function_call.get("name", "") or "").strip()
        if name:
            parsed_calls.append(
                ToolCall(
                    id=str(raw_function_call.get("id") or "function_call"),
                    name=name,
                    arguments=arguments,
                    raw_arguments=raw_arguments,
                    raw=raw_function_call,
                )
            )
    return parsed_calls


def _build_payload(
    *,
    model: str,
    messages: list[dict[str, object]],
    temperature: float,
    max_tokens: int,
    tools: list[dict[str, object]] | None = None,
    tool_choice: object | None = None,
) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "model": model,
        "messages": messages,
        "temperature": temperature,
        "max_tokens": max_tokens,
    }
    if tools:
        payload["tools"] = tools
        if tool_choice is not None:
            payload["tool_choice"] = tool_choice
    elif tool_choice is not None:
        payload["tool_choice"] = tool_choice
    return payload


def _extract_response(data: dict[str, Any]) -> ModelResponse:
    return ModelResponse(
        _extract_content(data),
        tool_calls=_extract_tool_calls(data) or None,
        raw=data if isinstance(data, dict) else None,
    )


class OpenAICompatibleModelClient:
    async def complete(
        self,
        *,
        url: str,
        api_key: str,
        model: str,
        messages: list[dict[str, object]],
        max_tokens: int,
        temperature: float,
        tools: list[dict[str, object]] | None = None,
        tool_choice: object | None = None,
    ) -> ModelResponse:
        payload = _build_payload(
            model=model,
            messages=messages,
            temperature=temperature,
            max_tokens=max_tokens,
            tools=tools,
            tool_choice=tool_choice,
        )
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
                tools=tools,
                tool_choice=tool_choice,
            )
        async with httpx.AsyncClient(timeout=20) as client:
            response = await client.post(url, json=payload, headers=headers)
            response.raise_for_status()
            data = response.json()
        return _extract_response(data)

    def complete_sync(
        self,
        *,
        url: str,
        api_key: str,
        model: str,
        messages: list[dict[str, object]],
        max_tokens: int,
        temperature: float,
        tools: list[dict[str, object]] | None = None,
        tool_choice: object | None = None,
    ) -> ModelResponse:
        payload = _build_payload(
            model=model,
            messages=messages,
            temperature=temperature,
            max_tokens=max_tokens,
            tools=tools,
            tool_choice=tool_choice,
        )
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
        return _extract_response(data)
