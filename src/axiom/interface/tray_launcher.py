"""
Tray launcher — M10 (design.md S9, US-07): starts axiom's backend and
frontend dev servers as subprocesses, opens the default browser to the UI,
and offers Start/Stop/Open/Quit from a system-tray icon.

Two subprocesses (backend `axiom-web`, frontend `npm run dev`, D20's Vite
dev-server proxy) rather than one -- production static-file serving from a
single process is Future Work (design.md D20), out of M10's scope.
"""

from __future__ import annotations

import subprocess
import sys
import webbrowser
from pathlib import Path

import pystray
from PIL import Image, ImageDraw

_REPO_ROOT = Path(__file__).resolve().parent.parent.parent.parent
_WEB_DIR = _REPO_ROOT / "web"
_FRONTEND_URL = "http://localhost:5173"

_processes: list[subprocess.Popen] = []


def _make_icon_image() -> Image.Image:
    image = Image.new("RGB", (64, 64), "#0d1117")
    draw = ImageDraw.Draw(image)
    draw.rectangle((8, 8, 56, 56), outline="#58a6ff", width=4)
    return image


def _is_running() -> bool:
    return any(p.poll() is None for p in _processes)


def _start(
    _icon: pystray.Icon | None = None, _item: pystray.MenuItem | None = None
) -> None:
    if _is_running():
        return
    _processes.clear()
    _processes.append(
        subprocess.Popen([sys.executable, "-m", "axiom.interface.web_cli"])
    )
    _processes.append(
        subprocess.Popen(
            ["npm", "run", "dev"], cwd=_WEB_DIR, shell=sys.platform == "win32"
        )
    )


def _stop(
    _icon: pystray.Icon | None = None, _item: pystray.MenuItem | None = None
) -> None:
    for process in _processes:
        if process.poll() is None:
            process.terminate()
    _processes.clear()


def _open(
    _icon: pystray.Icon | None = None, _item: pystray.MenuItem | None = None
) -> None:
    if not _is_running():
        _start()
    webbrowser.open(_FRONTEND_URL)


def _quit(icon: pystray.Icon, _item: pystray.MenuItem | None = None) -> None:
    _stop()
    icon.stop()


def main() -> None:
    menu = pystray.Menu(
        pystray.MenuItem("Open", _open),
        pystray.MenuItem("Start", _start),
        pystray.MenuItem("Stop", _stop),
        pystray.MenuItem("Quit", _quit),
    )
    icon = pystray.Icon("axiom", _make_icon_image(), "Axiom", menu)
    _start()
    _open()
    icon.run()


if __name__ == "__main__":
    main()
