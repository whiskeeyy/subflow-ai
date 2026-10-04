# -*- mode: python ; coding: utf-8 -*-
"""
SubFlow AI - PyInstaller Spec File.
Builds a standalone, native Windows Desktop package in --onedir mode
with console window disabled (windowed mode) and bundled Edge Chromium (WebView2) GUI.
"""
import os
import sys
from pathlib import Path
from PyInstaller.utils.hooks import collect_data_files, collect_submodules

block_cipher = None

project_dir = Path.cwd().resolve()

# 1. Collect Data Assets
datas = [
    (str(project_dir / 'frontend'), 'frontend'),
    (str(project_dir / 'ffmpeg_bin'), 'ffmpeg_bin'),
]

if (project_dir / '.env').exists():
    datas.append((str(project_dir / '.env'), '.'))

# Collect model engine data files (Faster-Whisper & CTranslate2)
try:
    datas += collect_data_files('faster_whisper')
except Exception:
    pass

try:
    datas += collect_data_files('ctranslate2')
except Exception:
    pass

# 2. Comprehensive Hidden Imports
hiddenimports = [
    'uvicorn',
    'uvicorn.logging',
    'uvicorn.loops',
    'uvicorn.loops.auto',
    'uvicorn.protocols',
    'uvicorn.protocols.http',
    'uvicorn.protocols.http.auto',
    'uvicorn.protocols.websockets',
    'uvicorn.protocols.websockets.auto',
    'uvicorn.lifespan',
    'uvicorn.lifespan.on',
    'engineio.async_drivers.asgi',
    'fastapi',
    'fastapi.staticfiles',
    'starlette',
    'starlette.staticfiles',
    'starlette.middleware',
    'starlette.middleware.cors',
    'websockets',
    'faster_whisper',
    'ctranslate2',
    'webview',
    'webview.platforms.winforms',
    'huggingface_hub',
    'deep_translator',
    'backend',
    'backend.app',
    'backend.config',
    'backend.settings_manager',
    'backend.model_downloader',
    'backend.batch_manager',
    'backend.history_store',
    'backend.workflows.video_pipeline',
    'backend.tasks.extract_task',
    'backend.tasks.transcribe_task',
    'backend.tasks.translate_task',
    'backend.tasks.merge_task',
]

# 3. Explicit Exclusions (Models & Outputs reside in %APPDATA%\SubFlowAI)
excludes = [
    'models',
    'outputs',
    'tkinter',
    'matplotlib',
    'scipy',
]

# Icon resolution
icon_path = str(project_dir / 'frontend' / 'assets' / 'logo.ico')
if not os.path.isfile(icon_path):
    icon_path = None

a = Analysis(
    ['main_desktop.py'],
    pathex=[str(project_dir)],
    binaries=[],
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=excludes,
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name='SubFlowAI',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=False,  # Windowed application (No black console window)
    icon=icon_path,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)

coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=False,
    upx_exclude=[],
    name='SubFlowAI',
)
