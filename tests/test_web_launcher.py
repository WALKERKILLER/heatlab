"""Focused checks for the browser-backed desktop launcher."""

from heatlab.web.launcher import _browser_host, _create_server


def test_browser_host_uses_loopback_for_wildcard_bind_addresses() -> None:
    assert _browser_host("0.0.0.0") == "127.0.0.1"
    assert _browser_host("::") == "127.0.0.1"
    assert _browser_host("127.0.0.1") == "127.0.0.1"


def test_launcher_binds_a_live_flask_server() -> None:
    server = _create_server("127.0.0.1", 0)
    try:
        assert server.server_port > 0
        assert server.app.name == "heatlab.web.app"
    finally:
        server.server_close()
