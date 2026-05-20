"""Reusable chat input and message card widgets."""
from __future__ import annotations

import os

from PySide6.QtCore import QTimer, Qt, QUrl, Signal
from PySide6.QtGui import QColor, QKeyEvent
from PySide6.QtWidgets import QFrame, QHBoxLayout, QSizePolicy, QTextBrowser, QTextEdit, QVBoxLayout, QWidget

try:
    from PySide6.QtWebEngineWidgets import QWebEngineView
except Exception:
    QWebEngineView = None  # type: ignore[assignment]

from .dialog_chrome import styled_label
from .markdown_rendering import markdown_css, render_markdown_document, render_markdown_fragment


def webengine_markdown_enabled() -> bool:
    if QWebEngineView is None:
        return False
    disabled = os.environ.get("DESKTOP_MENTOR_DISABLE_WEBENGINE", "").lower()
    if disabled in {"1", "true", "yes", "on"}:
        return False
    platform = os.environ.get("QT_QPA_PLATFORM", "").lower()
    return "offscreen" not in platform and "minimal" not in platform


class ChatInputEdit(QTextEdit):
    submitted = Signal()

    def keyPressEvent(self, event: QKeyEvent) -> None:  # type: ignore[override]
        if event.key() in {Qt.Key.Key_Return, Qt.Key.Key_Enter}:
            if event.modifiers() & Qt.KeyboardModifier.ShiftModifier:
                super().keyPressEvent(event)
            else:
                self.submitted.emit()
                event.accept()
            return
        super().keyPressEvent(event)


class TextMarkdownMessageView(QTextBrowser):
    def __init__(self, markdown: str, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("chatMarkdownMessage")
        self.setReadOnly(True)
        self.setOpenExternalLinks(True)
        self.setFrameShape(QFrame.Shape.NoFrame)
        self.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.setTextInteractionFlags(
            Qt.TextInteractionFlag.TextSelectableByMouse
            | Qt.TextInteractionFlag.LinksAccessibleByMouse
        )
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Minimum)
        self.document().setDocumentMargin(0)
        self.document().setDefaultStyleSheet(markdown_css())
        self.setHtml(render_markdown_fragment(markdown))
        self.sync_height_to_document()

    def resizeEvent(self, event) -> None:  # type: ignore[override]
        super().resizeEvent(event)
        self.sync_height_to_document()

    def showEvent(self, event) -> None:  # type: ignore[override]
        super().showEvent(event)
        self.sync_height_to_document()

    def sync_height_to_document(self) -> None:
        width = max(1, self.viewport().width())
        self.document().setTextWidth(width)
        self.setFixedHeight(max(24, int(self.document().size().height()) + 4))


if QWebEngineView is not None:

    class WebMarkdownMessageView(QWebEngineView):  # type: ignore[misc, valid-type]
        def __init__(self, markdown: str, parent: QWidget | None = None) -> None:
            super().__init__(parent)
            self.setObjectName("chatMarkdownMessage")
            self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
            self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Minimum)
            self.page().setBackgroundColor(QColor(0, 0, 0, 0))
            self.loadFinished.connect(self._on_load_finished)
            self.setHtml(render_markdown_document(markdown), QUrl("about:blank"))
            self.setFixedHeight(32)

        def resizeEvent(self, event) -> None:  # type: ignore[override]
            super().resizeEvent(event)
            QTimer.singleShot(0, self.sync_height_to_document)

        def _on_load_finished(self, _ok: bool) -> None:
            self.sync_height_to_document()

        def sync_height_to_document(self) -> None:
            script = "Math.ceil(document.documentElement.scrollHeight || document.body.scrollHeight || 24)"
            try:
                self.page().runJavaScript(script, self._apply_document_height)
            except RuntimeError:
                return

        def _apply_document_height(self, height: object) -> None:
            try:
                value = int(float(str(height)))
            except (TypeError, ValueError):
                value = 24
            try:
                self.setFixedHeight(max(24, value + 4))
            except RuntimeError:
                return


def create_markdown_message_view(markdown: str) -> QWidget:
    if webengine_markdown_enabled() and QWebEngineView is not None:
        return WebMarkdownMessageView(markdown)  # type: ignore[name-defined]
    return TextMarkdownMessageView(markdown)


class ChatMessageCard(QFrame):
    def __init__(self, role: str, text: str, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.role = "assistant" if role == "assistant" else "user"
        self.setObjectName("chatMessageCardAssistant" if self.role == "assistant" else "chatMessageCardUser")
        self.setMaximumWidth(880 if self.role == "assistant" else 700)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Maximum)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(14, 12, 14, 12)
        layout.setSpacing(7)

        header = QHBoxLayout()
        header.setContentsMargins(0, 0, 0, 0)
        header.setSpacing(8)
        role_label = styled_label("导师" if self.role == "assistant" else "你", "chatRole")
        header.addWidget(role_label, 0)
        header.addStretch(1)
        layout.addLayout(header)

        if self.role == "assistant":
            layout.addWidget(create_markdown_message_view(text), 1)
        else:
            message_label = styled_label(text, "chatText", True)
            message_label.setTextFormat(Qt.TextFormat.PlainText)
            message_label.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
            layout.addWidget(message_label)
