"""halo_harness.http_bind -- 3.6.0.0: every HTTP server Halo starts binds through here, so none asks a name service
anything between bind() and listen().

The standard library's `http.server.HTTPServer.server_bind` ends in `self.server_name = socket.getfqdn(host)`: a
reverse name lookup of the address just bound (for 0.0.0.0, of the machine's own host name). Where the resolver is
slow for that question (the hosted macOS CI runner: about 35 s; VPN and managed-DNS machines) the port refuses
connections for the whole wait: Studio printed its address 35 s late and `halo init` gave up on it. Nothing in Halo
reads `server_name`; it is set to the bound address as given. Tested by tests/test_http_bind.py.
"""
from __future__ import annotations

import http.server
import socketserver


def bind_no_lookup(server: socketserver.TCPServer) -> None:
    """What `HTTPServer.server_bind` does, without the reverse lookup: bind (with the class's own socket options),
    then `server_name` / `server_port` from the bound address."""
    socketserver.TCPServer.server_bind(server)
    host, port = server.server_address[:2]
    server.server_name, server.server_port = str(host), port


class HTTPServer(http.server.HTTPServer):
    def server_bind(self):
        bind_no_lookup(self)


class ThreadingHTTPServer(socketserver.ThreadingMixIn, HTTPServer):
    daemon_threads = True
