"""Open Bindery in its own window, like a normal desktop app."""

from __future__ import annotations

import ctypes
import os
import socket
import sys
import threading
import time
import urllib.error
import urllib.request
from pathlib import Path

os.environ["BINDERY_WINDOW"] = "1"

import uvicorn

from server import HOST, PORT, SESSIONS, _packaged, app

URL = f"http://{HOST}:{PORT}"


def _root() -> Path:
    if _packaged():
        return Path(sys.executable).resolve().parent
    return Path(__file__).resolve().parent


def _alert(message: str) -> None:
    ctypes.windll.user32.MessageBoxW(0, message, "36x Bindery", 0x10)


def _port_open() -> bool:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.settimeout(0.2)
        return sock.connect_ex((HOST, PORT)) == 0


def _is_bindery() -> bool:
    try:
        with urllib.request.urlopen(f"{URL}/api/health", timeout=0.6) as resp:
            body = resp.read().decode("utf-8", errors="ignore")
        return '"ok":true' in body.replace(" ", "") or '"ok": true' in body
    except (urllib.error.URLError, TimeoutError, OSError):
        return False


class QuietServer(uvicorn.Server):
    def install_signal_handlers(self) -> None:
        pass


def _start_server() -> QuietServer:
    SESSIONS.mkdir(exist_ok=True)
    config = uvicorn.Config(app, host=HOST, port=PORT, log_level="warning", log_config=None)
    server = QuietServer(config)
    thread = threading.Thread(target=server.run, daemon=True)
    thread.start()
    for _ in range(80):
        if _is_bindery():
            return server
        time.sleep(0.1)
    raise RuntimeError("Bindery started but the window could not reach it.")


def _icon_path() -> str | None:
    icon = _root() / "static" / "bindery.ico"
    return str(icon) if icon.exists() else None


def main() -> None:
    owned = False
    server: QuietServer | None = None
    if _port_open():
        if not _is_bindery():
            _alert(f"Port {PORT} is already in use by another program. Close it, then open 36x Bindery again.")
            return
    else:
        try:
            server = _start_server()
            owned = True
        except Exception as exc:
            _alert(f"Bindery could not start.\n\n{exc}")
            return

    import webview

    webview.create_window(
        "36x Bindery",
        URL,
        width=1280,
        height=840,
        min_size=(900, 600),
        background_color="#121916",
    )
    webview.start()
    if owned and server is not None:
        server.should_exit = True


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        _alert(str(exc))
        raise
