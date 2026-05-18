"""Central QSS theme for Qt widget surfaces."""
from __future__ import annotations

from typing import Protocol

from .tokens import FLUENT_DARK_COLORS, FLUENT_FONT_STACK, FLUENT_METRICS, FLUENT_RADII


class StyleTarget(Protocol):
    def setStyleSheet(self, style_sheet: str) -> None:
        ...


THEME_VALUES: dict[str, object] = {
    "font_family": FLUENT_FONT_STACK,
    **FLUENT_DARK_COLORS,
    **FLUENT_RADII,
    **FLUENT_METRICS,
}

APP_STYLESHEET = """
* {
    font-family: %(font_family)s;
}
QDialog {
    background: transparent;
    color: %(text_primary)s;
    font-size: 13px;
}
QWidget#dialogSurface {
    background: transparent;
}
QWidget#transparentSurface, QFrame#transparentSurface, QWidget#transparentViewport {
    background: transparent;
    border: 0;
}
QScrollArea#transparentScrollArea {
    background: transparent;
    border: 0;
}
QScrollArea#transparentScrollArea > QWidget, QScrollArea#transparentScrollArea QWidget#transparentViewport {
    background: transparent;
    border: 0;
}
QFrame#dialogShell {
    background: %(surface_window)s;
    border: 1px solid %(border)s;
    border-radius: %(dialog)spx;
}
QFrame#titleBar {
    background: %(surface_panel)s;
    border-top-left-radius: %(dialog)spx;
    border-top-right-radius: %(dialog)spx;
    border-bottom: 1px solid %(border)s;
}
QFrame#settingsRail {
    background: %(surface_panel)s;
    border: 1px solid %(border)s;
    border-radius: %(surface)spx;
}
QFrame#chatSurface {
    background: %(canvas)s;
    border: 0;
    border-radius: %(surface)spx;
}
QFrame#chatSessionRail {
    background: %(surface_sidebar)s;
    border-right: 1px solid %(border)s;
    border-top-left-radius: %(surface)spx;
    border-bottom-left-radius: %(surface)spx;
}
QFrame#chatControlBar {
    background: %(canvas)s;
    border: 0;
}
QFrame#conversationCanvas {
    background: %(canvas)s;
    border: 0;
}
QFrame#toolRail {
    background: %(surface_panel)s;
    border-left: 1px solid %(border)s;
    border-top-right-radius: %(surface)spx;
    border-bottom-right-radius: %(surface)spx;
}
QFrame#toolGroup {
    background: %(surface_card)s;
    border: 1px solid %(border_card)s;
    border-radius: %(surface)spx;
}
QFrame#sectionCard, QFrame#glassPanel {
    background: %(surface_card)s;
    border: 1px solid %(border_card)s;
    border-radius: %(surface)spx;
}
QFrame#contextChip {
    background: %(surface_control)s;
    border: 1px solid %(border_control)s;
    border-radius: %(control)spx;
}
QFrame#chatTranscript {
    background: %(canvas)s;
    border: 0;
    border-radius: 0;
}
QFrame#chatBubbleAssistant {
    background: transparent;
    border: 0;
    border-radius: %(surface)spx;
}
QFrame#chatBubbleUser {
    background: %(accent_soft)s;
    border: 1px solid %(accent_border)s;
    border-radius: %(surface)spx;
}
QFrame#chatComposer {
    background: %(surface_card)s;
    border: 1px solid %(border_control)s;
    border-radius: %(surface)spx;
}
QFrame#sessionRail {
    background: %(surface_panel)s;
    border: 1px solid %(border)s;
    border-radius: %(surface)spx;
}
QFrame#conversationHeader {
    background: %(surface_card)s;
    border: 1px solid %(border_card)s;
    border-radius: %(surface)spx;
}
QFrame#controlPlan {
    background: %(plan_surface)s;
    border: 1px solid %(plan_border)s;
    border-left: 3px solid %(tool_edit)s;
    border-radius: %(surface)spx;
}
QFrame#toolDetailPanel {
    background: %(canvas)s;
    border: 1px solid %(border)s;
    border-radius: %(surface)spx;
}
QFrame#permissionFooter {
    background: %(surface_control)s;
    border: 1px solid %(border_control)s;
    border-radius: %(surface)spx;
}
QFrame#assistantAvatar {
    background: %(accent_soft)s;
    border: 1px solid %(accent_border)s;
    border-radius: 15px;
}
QFrame#emptyState {
    background: transparent;
    border: 0;
    border-radius: 0;
}
QFrame#hairline {
    background: %(divider)s;
    border: 0;
    min-height: 1px;
    max-height: 1px;
}
QFrame#settingsFooter {
    background: %(surface_panel)s;
    border-top: 1px solid %(border)s;
    border-bottom-left-radius: %(dialog)spx;
    border-bottom-right-radius: %(dialog)spx;
}
QLabel {
    color: %(text_primary)s;
    background: transparent;
}
QLabel#dialogTitle {
    color: %(text_on_accent)s;
    font-size: 18px;
    font-weight: 700;
}
QLabel#windowCaption {
    color: %(text_primary)s;
    font-size: 13px;
    font-weight: 650;
}
QLabel#dialogSubtitle, QLabel#mutedLabel {
    color: %(text_muted)s;
}
QLabel#sectionTitle {
    color: %(text_primary)s;
    font-size: 14px;
    font-weight: 650;
}
QLabel#railTitle {
    color: %(text_primary)s;
    font-size: 15px;
    font-weight: 700;
}
QLabel#chatRole {
    color: %(text_muted)s;
    font-size: 11px;
    font-weight: 650;
}
QLabel#chatText {
    color: %(text_primary)s;
    font-size: 13px;
    line-height: 1.35em;
}
QLabel#chatMeta {
    color: %(text_subtle)s;
    font-size: 11px;
}
QLabel#avatarText {
    color: %(text_on_accent)s;
    font-size: 13px;
    font-weight: 700;
}
QLabel#statusPill {
    color: %(info_text)s;
    background: %(info_surface)s;
    border: 1px solid %(info_border)s;
    border-radius: %(control)spx;
    padding: 4px 9px;
    font-size: 11px;
    font-weight: 650;
}
QLabel#sessionTitle {
    color: %(text_primary)s;
    font-size: 14px;
    font-weight: 700;
}
QLabel#railSectionTitle {
    color: %(text_subtle)s;
    font-size: 10px;
    font-weight: 700;
    padding: 6px 2px 2px 2px;
}
QLabel#toolDetailText {
    color: %(text_secondary)s;
    font-family: "SFMono-Regular", "SF Mono", Consolas, "Liberation Mono", monospace;
    font-size: 12px;
}
QLineEdit, QTextEdit, QSpinBox, QDoubleSpinBox, QDateTimeEdit, QComboBox, QListWidget {
    background: %(input)s;
    border: 1px solid %(border_control)s;
    border-radius: %(control)spx;
    color: %(text_primary)s;
    padding: 9px 11px;
    selection-background-color: %(accent)s;
    selection-color: %(text_on_accent)s;
    placeholder-text-color: %(text_subtle)s;
}
QLineEdit:hover, QTextEdit:hover, QSpinBox:hover, QDoubleSpinBox:hover, QDateTimeEdit:hover, QComboBox:hover, QListWidget:hover {
    border-color: %(border_hover)s;
}
QLineEdit:focus, QTextEdit:focus, QSpinBox:focus, QDoubleSpinBox:focus, QDateTimeEdit:focus, QComboBox:focus, QListWidget:focus {
    border: 1px solid %(focus)s;
    background: %(input_focus)s;
}
QLineEdit:disabled, QTextEdit:disabled, QSpinBox:disabled, QDoubleSpinBox:disabled, QDateTimeEdit:disabled, QComboBox:disabled, QListWidget:disabled {
    background: %(disabled)s;
    border-color: %(disabled_border)s;
    color: %(text_disabled)s;
}
QLineEdit#sessionSearch {
    background: %(input)s;
    border: 1px solid %(border_control)s;
    padding: 8px 10px;
}
QTextEdit#chatInput {
    background: %(input)s;
    border: 1px solid %(border_control)s;
    border-radius: %(control)spx;
    padding: 11px 12px;
}
QAbstractItemView {
    background: %(input)s;
    border: 1px solid %(border_control)s;
    color: %(text_primary)s;
    outline: 0;
    selection-background-color: %(accent_soft)s;
    selection-color: %(text_on_accent)s;
}
QAbstractItemView::item {
    min-height: 24px;
    padding: 7px 10px;
}
QAbstractItemView::item:hover {
    background: %(surface_hover)s;
}
QAbstractItemView::item:selected {
    background: %(accent_soft)s;
    color: %(text_on_accent)s;
}
QTextEdit {
    padding: 12px;
}
QCheckBox {
    color: %(text_primary)s;
    spacing: 9px;
}
QCheckBox:disabled {
    color: %(text_disabled)s;
}
QCheckBox::indicator {
    width: 17px;
    height: 17px;
    border-radius: %(checkbox)spx;
    border: 1px solid %(border_hover)s;
    background: %(input)s;
}
QCheckBox::indicator:hover {
    border-color: %(focus)s;
}
QCheckBox::indicator:checked {
    background: %(accent)s;
    border-color: %(focus)s;
}
QCheckBox::indicator:disabled {
    background: %(disabled)s;
    border-color: %(disabled_border)s;
}
QPushButton {
    background: %(surface_control)s;
    border: 1px solid %(border_control)s;
    border-radius: %(control)spx;
    color: %(text_primary)s;
    padding: 9px 15px;
    min-height: 18px;
}
QPushButton:hover {
    background: %(surface_hover)s;
    border-color: %(border_hover)s;
}
QPushButton:pressed {
    background: %(surface_pressed)s;
}
QPushButton:disabled {
    background: %(disabled)s;
    border-color: %(disabled_border)s;
    color: %(text_disabled)s;
}
QPushButton#primaryButton {
    background: %(accent)s;
    border: 1px solid %(focus)s;
    color: %(text_on_accent)s;
    font-weight: 650;
}
QPushButton#primaryButton:hover {
    background: %(accent_hover)s;
}
QPushButton#primaryButton:pressed {
    background: %(accent_pressed)s;
}
QPushButton#secondaryButton {
    background: %(surface_control)s;
}
QPushButton#quietButton {
    background: transparent;
    border: 1px solid %(border_control)s;
    color: %(text_secondary)s;
}
QPushButton#quietButton:hover {
    background: %(surface_control)s;
    border-color: %(border_hover)s;
    color: %(text_primary)s;
}
QPushButton#miniButton {
    padding: 8px 12px;
    min-width: 58px;
}
QPushButton#toolChipButton {
    background: %(surface_control)s;
    border: 1px solid %(border_control)s;
    border-radius: %(control)spx;
    color: %(text_primary)s;
    padding: 8px 10px;
    text-align: left;
    min-height: 18px;
}
QPushButton#toolChipButton:hover {
    background: %(surface_hover)s;
    border-color: %(focus)s;
    color: %(text_on_accent)s;
}
QPushButton#toolChipButton:pressed {
    background: %(accent_soft)s;
}
QPushButton#railToggleButton {
    background: transparent;
    border: 1px solid %(border_control)s;
    border-radius: %(control)spx;
    color: %(text_secondary)s;
    padding: 6px 10px;
    min-height: 18px;
}
QPushButton#railToggleButton:hover {
    background: %(surface_control)s;
    border-color: %(focus)s;
    color: %(text_primary)s;
}
QPushButton#railNavButton, QPushButton#railNavButtonActive {
    text-align: left;
    border-radius: %(control)spx;
    padding: 9px 11px;
    min-height: 20px;
}
QPushButton#railNavButton {
    background: transparent;
    border: 1px solid transparent;
    color: %(text_secondary)s;
}
QPushButton#railNavButton:hover {
    background: %(surface_control)s;
    border-color: %(border_control)s;
    color: %(text_primary)s;
}
QPushButton#railNavButtonActive {
    background: %(accent_soft)s;
    border: 1px solid %(accent_border)s;
    color: %(text_on_accent)s;
}
QPushButton#chipCloseButton {
    background: %(surface_control)s;
    border: 1px solid %(border_control)s;
    border-radius: %(control)spx;
    color: %(text_muted)s;
    padding: 2px 8px;
    min-width: 22px;
    max-width: 26px;
    min-height: 22px;
    max-height: 26px;
}
QPushButton#chipCloseButton:hover {
    background: %(surface_hover)s;
    color: %(text_on_accent)s;
    border-color: %(focus)s;
}
QPushButton#dangerButton {
    background: %(danger)s;
    border-color: %(danger_border)s;
}
QPushButton#dangerButton:hover {
    background: %(danger_hover)s;
    border-color: %(danger_border_hover)s;
}
QPushButton#titleCloseButton {
    background: transparent;
    border: 1px solid transparent;
    border-radius: %(control)spx;
    color: %(text_secondary)s;
    font-size: 15px;
    padding: 0;
    min-width: %(title_close_size)spx;
    max-width: %(title_close_size)spx;
    min-height: %(title_close_size)spx;
    max-height: %(title_close_size)spx;
}
QPushButton#titleCloseButton:hover {
    background: %(close_hover)s;
    border-color: %(close_hover)s;
    color: %(text_on_accent)s;
}
QSizeGrip#resizeGrip {
    width: %(resize_grip_size)spx;
    height: %(resize_grip_size)spx;
    background: transparent;
}
QSizeGrip#resizeGrip:hover {
    background: %(surface_control)s;
    border: 1px solid %(focus)s;
    border-radius: %(tooltip)spx;
}
QToolTip {
    background: %(input)s;
    color: %(text_primary)s;
    border: 1px solid %(border_control)s;
    border-radius: %(tooltip)spx;
    padding: 6px 8px;
}
QDialogButtonBox QPushButton {
    min-width: 78px;
}
QComboBox::drop-down, QDateTimeEdit::drop-down, QSpinBox::up-button, QSpinBox::down-button, QDoubleSpinBox::up-button, QDoubleSpinBox::down-button {
    border: 0;
    width: 24px;
}
QComboBox QAbstractItemView {
    background: %(input)s;
    border: 1px solid %(border_control)s;
    selection-background-color: %(accent_soft)s;
}
QScrollArea {
    background: transparent;
    border: 0;
}
QScrollBar:vertical {
    background: transparent;
    width: %(scrollbar_width)spx;
    margin: 8px 2px 8px 2px;
}
QScrollBar::handle:vertical {
    background: %(scroll)s;
    border-radius: 5px;
    min-height: 34px;
}
QScrollBar::handle:vertical:hover {
    background: %(scroll_hover)s;
}
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {
    height: 0;
}
QScrollBar:horizontal {
    background: transparent;
    height: %(scrollbar_width)spx;
    margin: 2px 8px 2px 8px;
}
QScrollBar::handle:horizontal {
    background: %(scroll)s;
    border-radius: 5px;
    min-width: 34px;
}
QScrollBar::handle:horizontal:hover {
    background: %(scroll_hover)s;
}
QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal {
    width: 0;
}
QListWidget {
    outline: 0;
    padding: 6px;
}
QListWidget#sessionList {
    background: transparent;
    border: 0;
    padding: 2px;
}
QListWidget::item {
    border-radius: %(control)spx;
    padding: 10px 12px;
    margin: 3px 0;
    color: %(text_primary)s;
}
QListWidget::item:hover {
    background: %(surface_control)s;
}
QListWidget::item:selected {
    background: %(accent_soft)s;
    color: %(text_on_accent)s;
}
QListWidget#sessionList::item {
    border-left: 3px solid transparent;
    padding: 10px 9px;
}
QListWidget#sessionList::item:selected {
    background: %(surface_control)s;
    border-left: 3px solid %(focus)s;
    color: %(text_on_accent)s;
}
QMenu {
    background-color: %(menu)s;
    border: 1px solid %(border_control)s;
    border-radius: %(control)spx;
    color: %(text_primary)s;
    padding: 7px;
    margin: 0;
}
QMenu::item {
    background: transparent;
    border-radius: %(control)spx;
    padding: 9px 34px 9px 14px;
}
QMenu::item:selected {
    background: %(surface_hover)s;
    color: %(text_on_accent)s;
}
QMenu::item:disabled {
    color: %(text_disabled)s;
}
QMenu::separator {
    height: 1px;
    background: %(border_control)s;
    margin: 7px 9px;
}
""" % THEME_VALUES


def apply_app_theme(target: StyleTarget) -> None:
    target.setStyleSheet(APP_STYLESHEET)
