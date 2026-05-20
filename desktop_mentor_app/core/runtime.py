"""Qt/qasync runtime bootstrap."""
from __future__ import annotations

import asyncio
import logging
import signal
from collections.abc import Callable

from PySide6.QtCore import QTimer
from PySide6.QtWidgets import QApplication, QWidget

LOGGER = logging.getLogger(__name__)


def _install_sigint_handler(app: QApplication) -> None:
    def _handle_sigint(*_args: object) -> None:
        app.quit()

    try:
        signal.signal(signal.SIGINT, _handle_sigint)
    except (ValueError, OSError):
        LOGGER.debug("SIGINT handler unavailable", exc_info=True)


def run_qt_app(app: QApplication, show_window: Callable[[], QWidget], *, quit_after: float = 0.0) -> int:
    _install_sigint_handler(app)
    try:
        import qasync
    except Exception:
        LOGGER.warning("qasync is unavailable; falling back to QApplication.exec()", exc_info=True)
        window = show_window()
        window.show()
        if quit_after > 0:
            QTimer.singleShot(int(quit_after * 1000), app.quit)
        return int(app.exec())

    loop = qasync.QEventLoop(app)
    asyncio.set_event_loop(loop)
    window = show_window()
    window.show()
    if quit_after > 0:
        QTimer.singleShot(int(quit_after * 1000), app.quit)
    with loop:
        loop.run_forever()
    return 0
