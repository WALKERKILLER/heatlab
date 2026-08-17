"""Launch the HeatLab Web workbench as a browser-backed desktop application.

The regular ``heatlab-web`` command is intentionally a development-server
entry point. This module is the packaging entry point used by PyInstaller:
it starts the local Flask backend, opens the default browser, and keeps the
backend alive until the executable is closed.
"""

from __future__ import annotations

import argparse
import sys
import webbrowser
from contextlib import suppress
from threading import Timer

from werkzeug.serving import BaseWSGIServer, make_server

from heatlab.web.app import create_app

DEFAULT_HOST = "127.0.0.1"
DEFAULT_PORT = 8765
PORT_SEARCH_LIMIT = 20


def _create_server(host: str, preferred_port: int) -> BaseWSGIServer:
    """Bind a local server, moving to a nearby free port when necessary."""

    application = create_app()
    for candidate_port in range(preferred_port, preferred_port + PORT_SEARCH_LIMIT):
        try:
            return make_server(host, candidate_port, application, threaded=True)
        except OSError:
            continue
    raise OSError(
        f"无法绑定本地端口 {preferred_port}–{preferred_port + PORT_SEARCH_LIMIT - 1}，"
        "请关闭占用这些端口的程序后重试。"
    )


def _browser_host(host: str) -> str:
    """Return a browser-friendly loopback host for wildcard bind addresses."""

    if host in {"0.0.0.0", "::", "[::]"}:
        return DEFAULT_HOST
    return host


def _open_browser(url: str) -> None:
    """Open the demo URL without making browser failures stop the backend."""

    # The local server remains useful when the operating system has no
    # registered browser or blocks programmatic browser launches.
    with suppress(Exception):
        webbrowser.open_new_tab(url)


def main(argv: list[str] | None = None) -> int:
    """Start the packaged browser application and serve until it is closed."""

    parser = argparse.ArgumentParser(
        prog="heatlab-web-desktop",
        description="HeatLab Web 一键演示版：启动本地后端并打开浏览器。",
    )
    parser.add_argument("--host", default=DEFAULT_HOST)
    parser.add_argument("--port", type=int, default=DEFAULT_PORT)
    parser.add_argument(
        "--no-browser",
        action="store_true",
        help="只启动本地服务，不自动打开浏览器（用于自动化检查）。",
    )
    args = parser.parse_args(argv)

    server = _create_server(args.host, args.port)
    browser_url = f"http://{_browser_host(args.host)}:{server.server_port}/"

    if not args.no_browser:
        # Binding completes before the timer is scheduled, so the first page
        # request cannot race the server startup even on slower machines.
        browser_timer = Timer(0.25, _open_browser, args=(browser_url,))
        browser_timer.daemon = True
        browser_timer.start()

    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()

    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
