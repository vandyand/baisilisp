"""Thread-safe ownership for ``basilisp.core.server`` socket servers."""

from __future__ import annotations

import builtins
import socketserver
import threading

if not hasattr(builtins, "_basilisp_core_server_registry"):
    builtins._basilisp_core_server_registry = (threading.RLock(), {})

_LOCK, _SERVERS = builtins._basilisp_core_server_registry


def register_and_start(
    name: str, server: socketserver.BaseServer, daemon: bool = True
) -> socketserver.BaseServer:
    """Atomically claim ``name`` and start a server's accept loop.

    Binding a socket happens before a server can be registered, so a competing
    startup may already own an unused socket when it loses the name race. Close
    that socket before raising; otherwise failed duplicate starts leak ports.
    """
    with _LOCK:
        if name in _SERVERS:
            server.server_close()
            raise ValueError(f"a server named {name!r} is already running")
        _SERVERS[name] = server
        thread = threading.Thread(
            target=server.serve_forever,
            name=f"basilisp.core.server/{name}",
            daemon=daemon,
        )
        try:
            thread.start()
        except BaseException:
            _SERVERS.pop(name, None)
            server.server_close()
            raise
    return server


def stop_server(name: str) -> str | None:
    """Stop and close a named server, returning its name when registered."""
    with _LOCK:
        server = _SERVERS.pop(name, None)
    if server is None:
        return None
    try:
        server.shutdown()
    finally:
        server.server_close()
    return name


def stop_all() -> None:
    """Best-effort shutdown for every registered server."""
    with _LOCK:
        names = tuple(_SERVERS)
    for name in names:
        try:
            stop_server(name)
        except BaseException:
            # ``clojure.core.server/stop-servers`` deliberately ignores errors.
            pass
