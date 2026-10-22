# -*- mode: python ; coding: utf-8 -*-

from pathlib import Path
from PyInstaller.utils.hooks import collect_data_files

block_cipher = None

spec_dir = Path(SPECPATH).resolve()

datas = [
    (
        str(spec_dir / "edge_ergo" / "vision" / "models" / "pose_landmarker_lite.task"),
        "edge_ergo/vision/models",
    ),
]

# Collect MediaPipe model and resource dependencies
datas += collect_data_files("mediapipe")

hiddenimports = [
    "keyring.backends.Windows",
    "cv2",
    "mediapipe",
    "matplotlib",
    "numpy",
    "PySide6",
    "sqlite3",
    "edge_ergo",
    "edge_ergo.app",
    "edge_ergo.main",
    "edge_ergo.storage",
    "edge_ergo.storage.database",
    "edge_ergo.storage.migrations",
    "edge_ergo.storage.repository",
    "edge_ergo.storage.credentials",
    "edge_ergo.sync",
    "edge_ergo.sync.worker",
    "edge_ergo.sync.client",
    "edge_ergo.sync.enrollment",
    "edge_ergo.camera",
    "edge_ergo.camera.opencv_source",
    "edge_ergo.camera.fake_source",
    "edge_ergo.vision",
    "edge_ergo.vision.mediapipe_estimator",
    "edge_ergo.vision.synthetic_estimator",
    "edge_ergo.quality",
    "edge_ergo.features",
    "edge_ergo.scoring",
    "edge_ergo.overlay",
    "edge_ergo.overlay.widget",
]

a = Analysis(
    [str(spec_dir / "edge_ergo" / "main.py")],
    pathex=[str(spec_dir)],
    binaries=[],
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=["tkinter", "pytest", "unittest"],
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
    name="edge-ergo",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=True,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    version=str(spec_dir / "resources" / "file_version_info.txt"),
    icon=str(spec_dir / "resources" / "icon.ico"),
)

coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name="edge-ergo",
)
