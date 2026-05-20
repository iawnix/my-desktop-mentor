"""Async task runner for Qt slots."""
from __future__ import annotations

import asyncio
import logging
import threading
from collections.abc import Awaitable, Callable
from concurrent.futures import ThreadPoolExecutor
from typing import TypeVar

from PySide6.QtCore import QObject, Signal

T = TypeVar("T")
LOGGER = logging.getLogger(__name__)


class AsyncTaskRunner(QObject):
    task_error = Signal(str)

    def __init__(self, parent: QObject | None = None, *, max_workers: int = 4) -> None:
        super().__init__(parent)
        self._executor = ThreadPoolExecutor(max_workers=max_workers, thread_name_prefix="desktop-mentor")

    def shutdown(self) -> None:
        self._executor.shutdown(wait=False, cancel_futures=True)

    def run_blocking(
        self,
        func: Callable[[], T],
        *,
        on_success: Callable[[T], None] | None = None,
        on_error: Callable[[Exception], None] | None = None,
    ) -> None:
        async def _run() -> None:
            loop = asyncio.get_running_loop()
            result = await loop.run_in_executor(self._executor, func)
            if on_success is not None:
                on_success(result)

        self.run_async(_run, on_error=on_error)

    def run_async(
        self,
        coro_factory: Callable[[], Awaitable[T]],
        *,
        on_success: Callable[[T], None] | None = None,
        on_error: Callable[[Exception], None] | None = None,
    ) -> None:
        async def _wrapped() -> None:
            try:
                result = await coro_factory()
            except Exception as exc:
                LOGGER.exception("background task failed")
                if on_error is not None:
                    on_error(exc)
                else:
                    self.task_error.emit(f"{type(exc).__name__}: {exc}")
                return
            if on_success is not None:
                on_success(result)

        try:
            loop = asyncio.get_running_loop()
        except RuntimeError:
            threading.Thread(target=lambda: asyncio.run(_wrapped()), daemon=True).start()
            return
        loop.create_task(_wrapped())
