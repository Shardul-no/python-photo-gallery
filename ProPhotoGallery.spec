# -*- mode: python ; coding: utf-8 -*-
import os

block_cipher = None

# We'll bundle ffmpeg and ffprobe if they are found in the system's PATH or provided location.
# Based on my research, they are at C:\ffmpeg\bin\
ffmpeg_paths = [
    (r'C:\ffmpeg\bin\ffmpeg.exe', '.'),
    (r'C:\ffmpeg\bin\ffprobe.exe', '.')
]

# Ensure we only include them if they actually exist to avoid PyInstaller errors.
datas = []
for src, dst in ffmpeg_paths:
    if os.path.exists(src):
        datas.append((src, dst))

a = Analysis(
    ['run.py'],
    pathex=[],
    binaries=[],
    datas=datas,
    hiddenimports=['PySide6.QtMultimedia', 'PySide6.QtMultimediaWidgets', 'pillow_heif'],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.zipfiles,
    a.datas,
    [],
    name='ProPhotoGallery',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=['icon.ico'],
)
