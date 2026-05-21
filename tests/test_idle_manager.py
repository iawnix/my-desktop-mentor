from __future__ import annotations

import unittest

from desktop_mentor_app.pet.idle_manager import IdleManager


class FakeClock:
    def __init__(self) -> None:
        self.now = 100.0

    def __call__(self) -> float:
        return self.now

    def advance(self, seconds: float) -> None:
        self.now += seconds


class IdleManagerTests(unittest.TestCase):
    def test_system_idle_probe_is_cached_between_intervals(self) -> None:
        clock = FakeClock()
        calls = 0

        def idle_provider() -> float | None:
            nonlocal calls
            calls += 1
            return 12.0

        manager = IdleManager(idle_provider=idle_provider, clock=clock, probe_interval_seconds=10)

        self.assertEqual(manager.idle_seconds(), 12.0)
        clock.advance(3)
        self.assertEqual(manager.idle_seconds(), 15.0)
        self.assertEqual(calls, 1)

        clock.advance(8)
        self.assertEqual(manager.idle_seconds(), 12.0)
        self.assertEqual(calls, 2)

    def test_fallback_uses_pet_local_interaction_clock(self) -> None:
        clock = FakeClock()
        manager = IdleManager(idle_provider=lambda: None, clock=clock, probe_interval_seconds=10)

        manager.mark_interaction()
        clock.advance(7)

        self.assertEqual(manager.idle_seconds(), 7.0)

    def test_failed_system_idle_probe_is_cached_between_intervals(self) -> None:
        clock = FakeClock()
        calls = 0

        def idle_provider() -> float | None:
            nonlocal calls
            calls += 1
            return None

        manager = IdleManager(idle_provider=idle_provider, clock=clock, probe_interval_seconds=10)

        self.assertEqual(manager.idle_seconds(), 0.0)
        clock.advance(3)
        self.assertEqual(manager.idle_seconds(), 3.0)
        self.assertEqual(calls, 1)

        clock.advance(8)
        self.assertEqual(manager.idle_seconds(), 11.0)
        self.assertEqual(calls, 2)

    def test_suppression_expires(self) -> None:
        clock = FakeClock()
        manager = IdleManager(idle_provider=lambda: None, clock=clock)

        manager.suppress_for(5)
        self.assertTrue(manager.is_suppressed())
        clock.advance(6)
        self.assertFalse(manager.is_suppressed())


if __name__ == "__main__":
    unittest.main()
