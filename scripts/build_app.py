"""Build dist/JevVoice.app: native menu-bar wrapper around `openjev voice-app`.

LSUIElement (no Dock icon), executable shell shim into this repo's venv.
Run: `.venv/bin/python scripts/build_app.py` — then `open dist/JevVoice.app`.
"""

from __future__ import annotations

import stat
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
APP = ROOT / "dist" / "JevVoice.app"

INFO_PLIST = """<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>CFBundleName</key>
    <string>JevVoice</string>
    <key>CFBundleDisplayName</key>
    <string>JevVoice</string>
    <key>CFBundleIdentifier</key>
    <string>com.alistair.jevvoice</string>
    <key>CFBundleVersion</key>
    <string>0.1.0</string>
    <key>CFBundleShortVersionString</key>
    <string>0.1.0</string>
    <key>CFBundlePackageType</key>
    <string>APPL</string>
    <key>CFBundleExecutable</key>
    <string>JevVoice</string>
    <key>LSUIElement</key>
    <true/>
    <key>LSMinimumSystemVersion</key>
    <string>13.0</string>
    <key>NSMicrophoneUsageDescription</key>
    <string>JevVoice listens for your push-to-talk voice commands.</string>
</dict>
</plist>
"""


def main() -> None:
    console = Path(sys.executable).resolve().parent / "openjev"
    macos = APP / "Contents" / "MacOS"
    macos.mkdir(parents=True, exist_ok=True)
    (APP / "Contents" / "Info.plist").write_text(INFO_PLIST)
    shim = macos / "JevVoice"
    shim.write_text(f'#!/bin/sh\nexec "{console}" voice-app "$@"\n')
    shim.chmod(shim.stat().st_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)
    subprocess.run(["xattr", "-cr", str(APP)], check=False)
    print(f"built {APP}")
    print("launch: open dist/JevVoice.app  (first run: right-click > Open, then allow Mic)")


if __name__ == "__main__":
    main()
