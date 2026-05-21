"""Editor widget for action sticker frame sets."""
from __future__ import annotations

from pathlib import Path

from PySide6.QtWidgets import QFileDialog, QHBoxLayout, QLabel, QPushButton, QTextEdit, QVBoxLayout, QWidget

from ..constants import MAX_STICKER_FRAMES, STICKER_ACTION_LABELS, STICKER_ACTIONS, STICKER_IMAGE_FILTER
from ..pet.stickers import discover_sticker_sets, normalize_sticker_sets
from .dialog_chrome import make_transparent, mark_button, styled_label


class StickerSetEditor(QWidget):
    def __init__(self, sticker_sets: dict[str, list[str]], parent: QWidget | None = None) -> None:
        super().__init__(parent)
        make_transparent(self)
        self.edits: dict[str, QTextEdit] = {}
        self.count_labels: dict[str, QLabel] = {}
        normalized = normalize_sticker_sets(sticker_sets)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(12)
        intro = QHBoxLayout()
        intro.setContentsMargins(0, 0, 0, 0)
        intro.setSpacing(8)
        intro.addWidget(styled_label("每行一张图片，按播放顺序排列；也可一次导入包含 8 个动作子目录的素材根目录。", "mutedLabel", True), 1)
        import_button = QPushButton("导入动作目录")
        mark_button(import_button, "miniButton")
        import_button.clicked.connect(self.browse_root_dir)
        intro.addWidget(import_button)
        layout.addLayout(intro)

        for action in STICKER_ACTIONS:
            header = QHBoxLayout()
            header.setContentsMargins(0, 0, 0, 0)
            header.setSpacing(8)
            header.addWidget(styled_label(STICKER_ACTION_LABELS[action], "sectionTitle"), 1)
            count_label = styled_label("", "mutedLabel")
            self.count_labels[action] = count_label
            header.addWidget(count_label)

            select_button = QPushButton("按顺序选择")
            mark_button(select_button, "miniButton")
            select_button.clicked.connect(lambda _checked=False, target=action: self.browse_action(target))
            header.addWidget(select_button)

            clear_button = QPushButton("清空")
            mark_button(clear_button, "miniButton")
            clear_button.clicked.connect(lambda _checked=False, target=action: self.clear_action(target))
            header.addWidget(clear_button)

            edit = QTextEdit()
            edit.setAcceptRichText(False)
            edit.setMinimumHeight(58)
            edit.setMaximumHeight(86)
            edit.setPlaceholderText("每行一张图片路径；第一行是第 1 帧。")
            edit.setPlainText("\n".join(normalized.get(action, [])))
            edit.textChanged.connect(lambda target=action: self.update_count(target))
            self.edits[action] = edit

            layout.addLayout(header)
            layout.addWidget(edit)
            self.update_count(action)

    def action_paths(self, action: str) -> list[str]:
        edit = self.edits.get(action)
        if edit is None:
            return []
        return normalize_sticker_sets({action: edit.toPlainText()}).get(action, [])

    def browse_action(self, action: str) -> None:
        current_paths = self.action_paths(action)
        if current_paths:
            start_dir = str(Path(current_paths[0]).expanduser().parent)
        else:
            start_dir = str(Path.home())
        paths, _selected_filter = QFileDialog.getOpenFileNames(
            self,
            f"选择 {STICKER_ACTION_LABELS[action]} 贴纸帧",
            start_dir,
            STICKER_IMAGE_FILTER,
        )
        if not paths:
            return
        self.edits[action].setPlainText("\n".join(paths[:MAX_STICKER_FRAMES]))
        self.update_count(action)

    def browse_root_dir(self) -> None:
        path = QFileDialog.getExistingDirectory(self, "选择动作贴纸根目录", str(Path.home()))
        if not path:
            return
        discovered = discover_sticker_sets(Path(path))
        for action, paths in discovered.items():
            edit = self.edits.get(action)
            if edit is not None:
                edit.setPlainText("\n".join(paths))
                self.update_count(action)

    def clear_action(self, action: str) -> None:
        edit = self.edits.get(action)
        if edit is None:
            return
        edit.clear()
        self.update_count(action)

    def update_count(self, action: str) -> None:
        label = self.count_labels.get(action)
        if label is None:
            return
        count = len(self.action_paths(action))
        label.setText(f"{count} frames")

    def to_sticker_sets(self) -> dict[str, list[str]]:
        return normalize_sticker_sets({action: self.action_paths(action) for action in STICKER_ACTIONS})
