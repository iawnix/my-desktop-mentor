# -*- mode: python ; coding: utf-8 -*-

from pathlib import Path
import subprocess
import sys

root = Path(__file__).resolve().parents[2]
default_image = root / "assets" / "cow.png"
default_icon = root / "assets" / "desktop_mentor.ico"
todo_badge = root / "assets" / "todo_badge.png"

if not default_icon.exists() or default_icon.stat().st_mtime < default_image.stat().st_mtime:
    subprocess.run([sys.executable, str(root / "desktop_mentor.py"), "--ensure-default-icon"], check=True)

a = Analysis(
    ["desktop_mentor.py"],
    pathex=[str(root)],
    binaries=[],
    datas=[
        (str(default_image), "assets"),
        (str(default_icon), "assets"),
        (str(todo_badge), "assets"),
    ],
    hiddenimports=[],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name="MyDesktopMentor",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=str(default_icon),
)
