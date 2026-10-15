"""halo_harness.fleet.relay_stream -- the hub's SSE command stream as the
relay reads it (Halo 3.0.5.0 "Fleet" round R2).

`open_stream(sock, host_port, path, headers)` writes the signed GET by hand
on an already connected (and, over TLS, pinned) socket and returns a
`Stream` once the response head is in; `Stream.read(timeout)` returns the
SSE docs that arrived within `timeout`. It reads the socket itself because a
buffered socket file refuses every read after its first timeout, and the
relay thread polls the stream between its other work.
"""

from __future__ import annotations

import json
import socket
import time
from typing import Optional

CRLF = b"\r\n"
HEAD_END = b"\r\n\r\n"
EVENT_END = b"\n\n"


class StreamError(Exception):
    def __init__(self, message: str, status: int = 0, body: bytes = b"") -> None:
        super().__init__(message)
        self.status, self.body = status, body


class Stream:
    def __init__(self, sock) -> None:
        self.sock, self._buf = sock, b""
        self.last_data = time.monotonic()

    def _recv(self, timeout: float) -> Optional[bytes]:
        try:
            self.sock.settimeout(max(0.01, timeout))
            chunk = self.sock.recv(65536)
        except (socket.timeout, TimeoutError):
            return None
        except OSError as e:
            raise StreamError(f"the stream broke: {e}") from None
        if chunk == b"":
            raise StreamError("the hub closed the stream")
        self.last_data = time.monotonic()
        return chunk

    def head(self, timeout: float) -> "tuple[int, int]":
        """`(status, content length or -1)` once the response head is in."""
        end = time.monotonic() + timeout
        while HEAD_END not in self._buf:
            if time.monotonic() >= end:
                raise StreamError("the hub did not answer the stream request")
            self._buf += self._recv(end - time.monotonic()) or b""
        head, _, self._buf = self._buf.partition(HEAD_END)
        lines = head.decode("latin-1").split("\r\n")
        try:
            status = int(lines[0].split()[1])
        except (IndexError, ValueError):
            raise StreamError("the hub sent no HTTP status") from None
        length = -1
        for ln in lines[1:]:
            name, _, value = ln.partition(":")
            if name.strip().lower() == "content-length" and value.strip().isdigit():
                length = int(value.strip())
        return status, length

    def body(self, length: int, timeout: float = 3.0) -> bytes:
        end = time.monotonic() + timeout
        try:
            while (length < 0 or len(self._buf) < length) and time.monotonic() < end:
                self._buf += self._recv(end - time.monotonic()) or b""
        except StreamError:
            pass
        return self._buf[:length] if length >= 0 else self._buf

    def read(self, timeout: float = 0.25) -> list:
        chunk = self._recv(timeout)
        if chunk:
            self._buf += chunk
        docs = []
        while EVENT_END in self._buf:
            block, _, self._buf = self._buf.partition(EVENT_END)
            data = b"\n".join(ln[5:].strip() for ln in block.split(b"\n") if ln.startswith(b"data:"))
            if data:
                try:
                    docs.append(json.loads(data.decode("utf-8")))
                except ValueError:
                    continue
        return docs

    def close(self) -> None:
        try:
            self.sock.close()
        except Exception:
            pass


def open_stream(sock, host_port: str, path: str, headers: dict, timeout: float = 5.0) -> Stream:
    """A GET of `path` with `headers` on `sock`: the Stream on a 200, StreamError (with the body) otherwise."""
    lines = [f"GET {path} HTTP/1.1", f"Host: {host_port}", "Accept: text/event-stream"]
    lines += [f"{k}: {v}" for k, v in headers.items()]
    try:
        sock.sendall(CRLF.join(ln.encode("utf-8") for ln in lines) + HEAD_END)
    except OSError as e:
        raise StreamError(f"the stream request failed: {e}") from None
    stream = Stream(sock)
    status, length = stream.head(timeout)
    if status != 200:
        body = stream.body(length)
        stream.close()
        raise StreamError(f"the hub answered {status}", status, body)
    return stream
