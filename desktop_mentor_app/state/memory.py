"""Legacy conversation memory facade."""
from __future__ import annotations

from ..agent_client import append_memory_turn, load_memory_messages

__all__ = ["append_memory_turn", "load_memory_messages"]
