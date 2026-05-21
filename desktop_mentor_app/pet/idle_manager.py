"""Idle reminder state and system-idle sampling."""
from __future__ import annotations

import time
from collections.abc import Callable
from typing import Any

from ..platforms.idle import idle_detection_diagnostics, system_idle_seconds

IdleProvider = Callable[[], float | None]
DiagnosticsProvider = Callable[[], dict[str, Any]]
Clock = Callable[[], float]


class IdleManager:
    """Cache system idle probes and keep pet-local interaction state."""

    def __init__(
        self,
        *,
        idle_provider: IdleProvider = system_idle_seconds,
        diagnostics_provider: DiagnosticsProvider = idle_detection_diagnostics,
        clock: Clock = time.monotonic,
        probe_interval_seconds: float = 10.0,
    ) -> None:
        self._idle_provider = idle_provider
        self._diagnostics_provider = diagnostics_provider
        self._clock = clock
        self._probe_interval_seconds = max(1.0, float(probe_interval_seconds))
        now = self._clock()
        self.last_interaction = now
        self.suppressed_until = 0.0
        self._last_probe_at = 0.0
        self._last_system_idle: float | None = None

    def mark_interaction(self) -> None:
        self.last_interaction = self._clock()
        self._last_system_idle = None
        self._last_probe_at = 0.0

    def suppress_for(self, seconds: float) -> None:
        self.suppressed_until = max(self.suppressed_until, self._clock() + max(0.0, seconds))

    def is_suppressed(self) -> bool:
        return self._clock() < self.suppressed_until

    def idle_seconds(self) -> float:
        now = self._clock()
        if self._last_probe_at and now - self._last_probe_at < self._probe_interval_seconds:
            if self._last_system_idle is not None:
                return max(0.0, self._last_system_idle + (now - self._last_probe_at))
            return max(0.0, now - self.last_interaction)

        self._last_probe_at = now
        self._last_system_idle = self._idle_provider()
        if self._last_system_idle is not None:
            return max(0.0, self._last_system_idle)
        return max(0.0, now - self.last_interaction)

    def diagnostics(self) -> dict[str, Any]:
        data = self._diagnostics_provider()
        data["pet_idle_manager"] = {
            "last_interaction_age_seconds": max(0.0, self._clock() - self.last_interaction),
            "suppressed": self.is_suppressed(),
            "probe_interval_seconds": self._probe_interval_seconds,
            "last_probe_age_seconds": max(0.0, self._clock() - self._last_probe_at) if self._last_probe_at else None,
            "last_system_idle_seconds": self._last_system_idle,
        }
        return data
