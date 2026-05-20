"""Pointer coordinate adapters across Qt mouse/touch variants."""
from __future__ import annotations

from PySide6.QtCore import QPoint, QPointF
from PySide6.QtGui import QGuiApplication
from PySide6.QtWidgets import QWidget


def as_global_pos(widget: QWidget, event_or_point: object) -> QPoint:
    """Return a screen coordinate for mouse or touch input across Qt variants."""
    for name in ("globalPosition", "scenePosition"):
        getter = getattr(event_or_point, name, None)
        if getter is None:
            continue
        try:
            value = getter()
            if isinstance(value, QPointF):
                return value.toPoint()
            if isinstance(value, QPoint):
                return value
        except Exception:
            pass

    pos_getter = getattr(event_or_point, "position", None)
    if pos_getter is not None:
        try:
            value = pos_getter()
            if isinstance(value, QPointF):
                return widget.mapToGlobal(value.toPoint())
            if isinstance(value, QPoint):
                return widget.mapToGlobal(value)
        except Exception:
            pass

    pos_getter = getattr(event_or_point, "pos", None)
    if pos_getter is not None:
        try:
            return widget.mapToGlobal(pos_getter())
        except Exception:
            pass

    return QGuiApplication.primaryScreen().availableGeometry().center()


def as_local_pos(widget: QWidget, event_or_point: object) -> QPoint:
    for name in ("position", "scenePosition"):
        getter = getattr(event_or_point, name, None)
        if getter is None:
            continue
        try:
            value = getter()
            if isinstance(value, QPointF):
                return value.toPoint()
            if isinstance(value, QPoint):
                return value
        except Exception:
            pass

    pos_getter = getattr(event_or_point, "pos", None)
    if pos_getter is not None:
        try:
            return pos_getter()
        except Exception:
            pass

    return widget.mapFromGlobal(as_global_pos(widget, event_or_point))


def as_context_menu_pos(widget: QWidget, event_or_point: object) -> QPoint:
    getter = getattr(event_or_point, "globalPos", None)
    if getter is not None:
        try:
            value = getter()
            if isinstance(value, QPoint):
                return value
        except Exception:
            pass
    return as_global_pos(widget, event_or_point)
