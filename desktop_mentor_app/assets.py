"""Resource paths and icon generation."""
from __future__ import annotations

import hashlib
import re
import struct
import sys
from pathlib import Path

from PySide6.QtCore import QByteArray, QBuffer, QIODevice, Qt
from PySide6.QtGui import QImage, QPainter

from .constants import ICON_SIZES


def app_root() -> Path:
    bundle_root = getattr(sys, "_MEIPASS", "")
    if bundle_root:
        return Path(bundle_root)
    return Path(__file__).resolve().parents[1]


ROOT = app_root()
DEFAULT_IMAGE = ROOT / "assets" / "cow.png"
DEFAULT_ICON = ROOT / "assets" / "desktop_mentor.ico"
TODO_BADGE_IMAGE = ROOT / "assets" / "todo_badge.png"
DEFAULT_STICKERS_DIR = ROOT / "assets" / "stickers"


def file_digest(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def safe_stem(path: Path) -> str:
    stem = re.sub(r"[^A-Za-z0-9_.-]+", "-", path.stem).strip(".-")
    return (stem or "mentor")[:48]


def icon_cache_path_for_image(image_path: Path) -> Path:
    from .config_store import config_path

    source = image_path.expanduser().resolve()
    digest = file_digest(source)[:16]
    return config_path().parent / "icons" / f"{safe_stem(source)}-{digest}.ico"


def qimage_png_bytes(image: QImage) -> bytes:
    data = QByteArray()
    buffer = QBuffer(data)
    if not buffer.open(QIODevice.OpenModeFlag.WriteOnly):
        raise RuntimeError("failed to open PNG buffer")
    if not image.save(buffer, "PNG"):
        raise RuntimeError("failed to encode PNG icon layer")
    buffer.close()
    return bytes(data)


def centered_icon_layer(source: QImage, size: int) -> QImage:
    canvas = QImage(size, size, QImage.Format.Format_ARGB32)
    canvas.fill(Qt.GlobalColor.transparent)
    scaled = source.scaled(size, size, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation)
    painter = QPainter(canvas)
    painter.drawImage((size - scaled.width()) // 2, (size - scaled.height()) // 2, scaled)
    painter.end()
    return canvas


def write_ico(layers: list[tuple[int, bytes]], output_path: Path) -> Path:
    if not layers:
        raise RuntimeError("no icon layers to write")
    output_path = output_path.expanduser().resolve()
    output_path.parent.mkdir(parents=True, exist_ok=True)

    offset = 6 + 16 * len(layers)
    directory = bytearray()
    payload = bytearray()
    for size, data in layers:
        width_byte = 0 if size >= 256 else size
        height_byte = 0 if size >= 256 else size
        directory.extend(struct.pack("<BBBBHHII", width_byte, height_byte, 0, 0, 1, 32, len(data), offset))
        payload.extend(data)
        offset += len(data)

    output_path.write_bytes(struct.pack("<HHH", 0, 1, len(layers)) + bytes(directory) + bytes(payload))
    return output_path


def convert_image_to_ico(image_path: Path, output_path: Path, *, force: bool = True) -> Path:
    source = image_path.expanduser().resolve()
    target = output_path.expanduser().resolve()
    if not source.exists():
        raise RuntimeError(f"source image does not exist: {source}")
    if target.exists() and not force:
        try:
            if target.stat().st_mtime >= source.stat().st_mtime and target.stat().st_size > 0:
                return target
        except OSError:
            pass

    image = QImage(str(source))
    if image.isNull():
        raise RuntimeError(f"failed to load source image: {source}")

    layers = [(size, qimage_png_bytes(centered_icon_layer(image, size))) for size in ICON_SIZES]
    return write_ico(layers, target)


def ensure_default_icon(*, force: bool = False) -> Path:
    return convert_image_to_ico(DEFAULT_IMAGE, DEFAULT_ICON, force=force)
