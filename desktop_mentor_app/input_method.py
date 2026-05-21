"""Compatibility exports for Qt input-method platform helpers.

New code should import from ``desktop_mentor_app.platforms.input_method``.
"""
from __future__ import annotations

from .platforms.input_method import (
    FCITX_PLUGIN_NAMES,
    KNOWN_QT_PLUGIN_ROOTS,
    configure_linux_input_method_environment,
    configure_linux_session_bus,
    configure_qt_input_method_runtime,
    fcitx_qt_plugin_files,
    fcitx_qt_plugin_roots,
    input_method_diagnostics,
    is_linux,
    preferred_x11_display,
)

__all__ = [
    "FCITX_PLUGIN_NAMES",
    "KNOWN_QT_PLUGIN_ROOTS",
    "configure_linux_input_method_environment",
    "configure_linux_session_bus",
    "configure_qt_input_method_runtime",
    "fcitx_qt_plugin_files",
    "fcitx_qt_plugin_roots",
    "input_method_diagnostics",
    "is_linux",
    "preferred_x11_display",
]
