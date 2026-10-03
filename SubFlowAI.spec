# -*- mode: python ; coding: utf-8 -*-
import os
import sys
from pathlib import Path
from PyInstaller.utils.hooks import collect_data_files, collect_submodules

block_cipher = None

project_dir = Path.cwd().resolve()

# Collect data files and hidden imports
datas = [
    (str(project_dir / 'frontend'), 'frontend'),
    (str(project_dir / 'ffmpeg_bin'), 'ffmpeg_bin'),
]

if (project_dir / '.env').exists():
    datas.append((str(project_dir / '.env'), '.'))

# Collect ctranslate2 and faster_whisper assets
try:
    datas += collect_data_files('faster_whisper')
except Exception:
    pass

try:
    datas += collect_data_files('ctranslate2')
except Exception:
    pass

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
    'fastapi',
    'fastapi.staticfiles',
    'starlette',
    'starlette.staticfiles',
    'starlette.middleware',
    'starlette.middleware.cors',
    'websockets',
    'faster_whisper',
    'ctranslate2',
    'deep_translator',
    'backend',
    'backend.app',
    'backend.config',
    'backend.batch_manager',
    'backend.history_store',
    'backend.workflows.video_pipeline',
    'backend.tasks.extract_task',
    'backend.tasks.transcribe_task',
    'backend.tasks.translate_task',
    'backend.tasks.merge_task',
]

a = Analysis(
    ['main_desktop.py'],
    pathex=[str(project_dir)],
    binaries=[],
    datas=datas,
    hiddenimports=hiddenimports,
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
    [],
    exclude_binaries=True,
    name='SubFlowAI',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=True,
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
