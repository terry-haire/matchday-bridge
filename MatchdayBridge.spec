# -*- mode: python ; coding: utf-8 -*-
# Build: pyinstaller MatchdayBridge.spec   (with requirements.txt installed; tools\gen.py first if sheets/ changed)
import glob
import importlib.util
import os

# windows-capture's native Windows Graphics Capture core only (its Python wrapper pulls in OpenCV);
# spfl_scorers loads it from wgc/ to read SPFL26's goal captions while other windows cover the game.
_wc = importlib.util.find_spec("windows_capture")      # located without importing it (that would import cv2)
WGC = glob.glob(os.path.join(_wc.submodule_search_locations[0], "windows_capture*.pyd")) if _wc else []
if not WGC:
    raise SystemExit("windows-capture is not installed in the Python running PyInstaller (pip install -r requirements.txt)")
a = Analysis(
    ["bridge/matchday_bridge.py"],
    pathex=["bridge"],
    binaries=[(p, "wgc") for p in WGC],
    datas=[("sheets/*.json", "sheets"), ("spfl/modules/matchday.lua", "spfl/modules"),
           ("spfl/xinput/xinput1_3.dll", "spfl/xinput")],
    hiddenimports=["fm_reader", "fm_writer", "fm_drive", "fm_graphics", "spfl_scorers", "spfl_drive", "spfl_pad",
                   "spfl_live", "spfl_select", "spfl_faces", "ui",
                   "zstandard", "PIL.Image", "PIL.ImageGrab", "PIL.PngImagePlugin", "PIL.ImageTk", "PIL.ImageOps",
                   "PIL.ImageDraw", "PIL.ImageFont",
                   "winrt.windows.media.ocr", "winrt.windows.graphics.imaging", "winrt.windows.storage.streams",
                   "winrt.windows.foundation", "winrt.windows.foundation.collections",
                   "winrt.windows.globalization"],
    excludes=["matplotlib", "pytest", "cv2", "windows_capture"],
)
pyz = PYZ(a.pure)
exe = EXE(
    pyz, a.scripts, a.binaries, a.datas, [],
    name="MatchdayBridge",
    console=False,
    uac_admin=True,
    upx=False,
)
