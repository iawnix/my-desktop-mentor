"""Model client interfaces."""
from __future__ import annotations

from .base import ModelClient, ModelResponse
from .openai_compatible import OpenAICompatibleModelClient

__all__ = ["ModelClient", "ModelResponse", "OpenAICompatibleModelClient"]
