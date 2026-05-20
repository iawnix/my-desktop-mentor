"""Painting helpers for the desktop pet widget."""
from __future__ import annotations

import math
import time
from typing import Any

from PySide6.QtCore import QPointF, QRectF, Qt
from PySide6.QtGui import QColor, QPainter, QPainterPath, QPen, QPixmap

from .tokens import (
    BUBBLE_MIN_WIDTH,
    BUBBLE_TEXT_PAD_X,
    BUBBLE_TOP,
    DRAG_RELEASE_EFFECT_DURATION,
    DROP_EFFECT_DURATION,
    DROP_HOTZONE_PAD,
    TODO_BUBBLE_TEXT_PAD_X,
    TODO_BUBBLE_TEXT_PAD_Y,
)


class PetPainter:
    def __init__(self, pet: Any) -> None:
        self.pet = pet

    def paint(self) -> None:
        pet = self.pet
        painter = QPainter(pet)
        painter.setCompositionMode(QPainter.CompositionMode.CompositionMode_Source)
        painter.fillRect(pet.rect(), QColor(0, 0, 0, 0))
        painter.setCompositionMode(QPainter.CompositionMode.CompositionMode_SourceOver)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        painter.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform, True)

        self.draw_bubble(painter)
        self.draw_todo_bubbles(painter)
        self.draw_drop_effect(painter)
        self.draw_drag_effect(painter)
        self.draw_sticker(painter)
        self.draw_action_buttons(painter)

    def draw_sticker(self, painter: QPainter) -> None:
        pet = self.pet
        sticker = pet.sticker_rect()
        active_pixmap = pet.current_sticker_pixmap()
        source_rect = pet.current_sticker_source_rect()
        visual = self.pixmap_fit_rect(sticker, source_rect)
        center = sticker.center()
        scale = pet.scale()
        painter.save()
        painter.translate(center.x(), center.y())
        painter.scale(scale, scale)
        painter.translate(-center.x(), -center.y())
        painter.drawPixmap(visual, active_pixmap, source_rect)
        painter.restore()

    def pixmap_fit_rect(self, target: QRectF, source_rect: QRectF | None = None) -> QRectF:
        pet = self.pet
        source = source_rect or pet.pixmap_content_rect(pet.pixmap)
        image_ratio = source.width() / max(1.0, source.height())
        target_ratio = target.width() / max(1.0, target.height())
        if image_ratio >= target_ratio:
            width = target.width()
            height = width / image_ratio
        else:
            height = target.height()
            width = height * image_ratio
        return QRectF(target.center().x() - width / 2, target.center().y() - height / 2, width, height)

    def current_sticker_visual_rect(self) -> QRectF:
        pet = self.pet
        return self.pixmap_fit_rect(pet.sticker_rect(), pet.current_sticker_source_rect())

    def effect_intensity(self, until: float, duration: float) -> float:
        remaining = until - time.monotonic()
        if remaining <= 0:
            return 0.0
        return min(1.0, max(0.0, remaining / max(0.01, duration)))

    def drop_zone_rect(self) -> QRectF:
        pet = self.pet
        zone = pet.sticker_rect().united(pet.chat_button_rect()).united(pet.settings_button_rect()).united(pet.quit_button_rect())
        expanded = zone.adjusted(-DROP_HOTZONE_PAD, -DROP_HOTZONE_PAD, DROP_HOTZONE_PAD, DROP_HOTZONE_PAD)
        return expanded.intersected(QRectF(pet.rect()))

    def draw_drop_effect(self, painter: QPainter) -> None:
        pet = self.pet
        intensity = 1.0 if pet.drop_hover else self.effect_intensity(pet.drop_effect_until, DROP_EFFECT_DURATION)
        if intensity <= 0:
            return
        zone = self.drop_zone_rect()
        painter.save()
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        painter.setOpacity(0.72 * intensity)
        painter.setPen(QPen(QColor(76, 201, 240, 210), 2.2))
        painter.setBrush(QColor(20, 184, 166, 34))
        painter.drawRoundedRect(zone, 22, 22)
        painter.setPen(QPen(QColor(255, 255, 255, 230), 1.8))
        icon = QRectF(zone.center().x() - 20, zone.top() + 13, 40, 28)
        painter.drawRoundedRect(icon, 5, 5)
        painter.drawLine(QPointF(icon.left() + 8, icon.top() - 5), QPointF(icon.right() - 8, icon.top() - 5))
        painter.drawLine(QPointF(icon.center().x(), icon.top() - 6), QPointF(icon.center().x(), icon.center().y() + 5))
        painter.drawLine(QPointF(icon.center().x(), icon.center().y() + 5), QPointF(icon.center().x() - 7, icon.center().y() - 2))
        painter.drawLine(QPointF(icon.center().x(), icon.center().y() + 5), QPointF(icon.center().x() + 7, icon.center().y() - 2))
        painter.restore()

    def draw_drag_effect(self, painter: QPainter) -> None:
        pet = self.pet
        intensity = 1.0 if pet.dragging else self.effect_intensity(pet.drag_effect_until, DRAG_RELEASE_EFFECT_DURATION)
        if intensity <= 0:
            return
        pad = max(5.0, min(14.0, pet.pet_size * 0.04))
        sticker = self.current_sticker_visual_rect().adjusted(-pad, -pad, pad, pad)
        painter.save()
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        painter.setOpacity(0.45 * intensity)
        painter.setPen(QPen(QColor(125, 92, 255, 190), 2.0))
        painter.setBrush(QColor(14, 165, 233, 24))
        painter.drawEllipse(sticker)
        painter.setPen(QPen(QColor(255, 255, 255, 150), 1.2))
        painter.drawArc(sticker.adjusted(pad, pad, -pad, -pad), 25 * 16, 145 * 16)
        painter.restore()

    def draw_bubble(self, painter: QPainter) -> None:
        pet = self.pet
        now = time.monotonic()
        if now >= pet.message_until:
            return

        remaining = pet.message_until - now
        opacity = min(1.0, max(0.0, remaining / 0.22)) if remaining < 0.22 else 1.0
        painter.save()
        painter.setOpacity(opacity)

        bubble_width = min(max(BUBBLE_MIN_WIDTH, pet.bubble_width), pet.width() - 12)
        body = QRectF((pet.width() - bubble_width) / 2, pet.todo_stack_height + BUBBLE_TOP, bubble_width, pet.bubble_body_height)
        tail = QPainterPath()
        tail.moveTo(pet.width() / 2 - 10, body.bottom() - 1)
        tail.lineTo(pet.width() / 2, body.bottom() + 14)
        tail.lineTo(pet.width() / 2 + 10, body.bottom() - 1)
        tail.closeSubpath()

        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QColor(0, 0, 0, 66))
        radius = min(18, max(8, pet.bubble_body_height / 3))
        painter.drawRoundedRect(body.translated(0, 3), radius, radius)
        painter.drawPath(tail.translated(0, 3))

        painter.setBrush(QColor(25, 30, 38, 238))
        painter.setPen(QPen(QColor(255, 255, 255, 75), 1.2))
        painter.drawRoundedRect(body, radius, radius)
        painter.drawPath(tail)

        painter.setFont(pet.bubble_font())
        painter.setPen(QColor(255, 255, 255))
        painter.drawText(
            body.adjusted(BUBBLE_TEXT_PAD_X, 0, -BUBBLE_TEXT_PAD_X, -2),
            Qt.AlignmentFlag.AlignCenter | Qt.TextFlag.TextWordWrap,
            pet.current_message,
        )
        painter.restore()

    def draw_todo_bubbles(self, painter: QPainter) -> None:
        pet = self.pet
        rects = pet.todo_bubble_rects()
        if not rects:
            return
        hidden_count = max(0, len(pet.todo_bubbles) - len(rects))
        painter.save()
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        painter.setFont(pet.todo_bubble_font())
        for index, (bubble, rect) in enumerate(rects):
            text = pet.todo_bubble_text(bubble)
            if hidden_count and index == 0:
                text = f"还有 {hidden_count} 次旧提醒；{text}"
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(QColor(0, 0, 0, 74))
            painter.drawRoundedRect(rect.translated(0, 3), 15, 15)
            painter.setBrush(QColor(35, 48, 68, 244))
            painter.setPen(QPen(QColor(115, 200, 255, 132), 1.2))
            painter.drawRoundedRect(rect, 15, 15)
            painter.setPen(QColor(238, 246, 255))
            painter.drawText(
                rect.adjusted(TODO_BUBBLE_TEXT_PAD_X, TODO_BUBBLE_TEXT_PAD_Y, -TODO_BUBBLE_TEXT_PAD_X, -TODO_BUBBLE_TEXT_PAD_Y),
                Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter | Qt.TextFlag.TextWordWrap,
                text,
            )
        painter.restore()

    def draw_action_buttons(self, painter: QPainter) -> None:
        self.draw_chat_button(painter)
        self.draw_settings_button(painter)
        self.draw_quit_button(painter)

    def draw_round_button_base(self, painter: QPainter, button: QRectF, *, pressed: bool) -> None:
        painter.save()
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)

        if pressed:
            bg = QColor(55, 122, 255, 238)
            shadow = QColor(0, 0, 0, 80)
        else:
            bg = QColor(25, 30, 38, 226)
            shadow = QColor(0, 0, 0, 58)

        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(shadow)
        painter.drawEllipse(button.translated(0, 2))
        painter.setBrush(bg)
        painter.drawEllipse(button)
        painter.restore()

    def draw_chat_button(self, painter: QPainter) -> None:
        pet = self.pet
        button = pet.chat_button_rect()
        self.draw_round_button_base(painter, button, pressed=pet.chat_button_pressed)

        painter.save()
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        painter.setPen(QPen(QColor(255, 255, 255, 235), max(1.7, button.width() * 0.055)))
        painter.setBrush(Qt.BrushStyle.NoBrush)
        bubble = button.adjusted(button.width() * 0.24, button.height() * 0.25, -button.width() * 0.22, -button.height() * 0.34)
        radius = max(3.0, button.width() * 0.10)
        painter.drawRoundedRect(bubble, radius, radius)

        tail = QPainterPath()
        tail.moveTo(bubble.left() + bubble.width() * 0.30, bubble.bottom() - 0.5)
        tail.lineTo(bubble.left() + bubble.width() * 0.22, bubble.bottom() + button.height() * 0.16)
        tail.lineTo(bubble.left() + bubble.width() * 0.48, bubble.bottom() - 0.5)
        painter.drawPath(tail)
        painter.restore()

    def draw_settings_button(self, painter: QPainter) -> None:
        pet = self.pet
        button = pet.settings_button_rect()
        self.draw_round_button_base(painter, button, pressed=pet.settings_button_pressed)

        painter.save()
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        center = button.center()
        outer = button.width() * 0.22
        inner = button.width() * 0.08
        painter.setPen(QPen(QColor(255, 255, 255, 235), max(1.6, button.width() * 0.052)))
        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.drawEllipse(center, outer, outer)
        painter.drawEllipse(center, inner, inner)
        for index in range(8):
            angle = math.tau * index / 8
            start = QPointF(center.x() + math.cos(angle) * outer, center.y() + math.sin(angle) * outer)
            end = QPointF(center.x() + math.cos(angle) * outer * 1.34, center.y() + math.sin(angle) * outer * 1.34)
            painter.drawLine(start, end)
        painter.restore()

    def draw_quit_button(self, painter: QPainter) -> None:
        pet = self.pet
        button = pet.quit_button_rect()
        self.draw_round_button_base(painter, button, pressed=pet.quit_button_pressed)

        painter.save()
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        pad = button.width() * 0.32
        painter.setPen(QPen(QColor(255, 255, 255, 235), max(1.8, button.width() * 0.06), Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap))
        painter.drawLine(QPointF(button.left() + pad, button.top() + pad), QPointF(button.right() - pad, button.bottom() - pad))
        painter.drawLine(QPointF(button.right() - pad, button.top() + pad), QPointF(button.left() + pad, button.bottom() - pad))
        painter.restore()

    @staticmethod
    def cover_source_rect(pixmap: QPixmap, target: QRectF) -> QRectF:
        image_ratio = pixmap.width() / max(1, pixmap.height())
        target_ratio = target.width() / max(1.0, target.height())
        if image_ratio > target_ratio:
            source_width = pixmap.height() * target_ratio
            x = (pixmap.width() - source_width) / 2
            return QRectF(x, 0, source_width, pixmap.height())
        source_height = pixmap.width() / target_ratio
        y = (pixmap.height() - source_height) / 2
        return QRectF(0, y, pixmap.width(), source_height)
