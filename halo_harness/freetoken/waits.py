"""halo_harness.freetoken.waits -- the session's wait for a FreeToken server (Halo 3.3.9.1; docs/MODELS-freetoken.md
"The first request").

The first request after an install compiles FreeToken's CUDA kernels on first use (docs/install.md: "CUDA kernels are
JIT-compiled on first use"; from the source, unverified against a live run), which can take minutes before the first
token; the session's socket waits five minutes for a byte by default (providers/http.open_upstream). For a FreeToken
server the wait is FIRST_WAIT_S, so that first request is never cut as a timeout; the steward says it afterwards
(ft-kernel-jit). Studio's sessions send through the same path.

    is_ft_url(url) -> the url is a FreeToken server's (a roster row of runtime freetoken, or a peer's entry for one)
    widen(conn, url) -> the connection's idle wait is FIRST_WAIT_S when it is one; never raises
"""

from __future__ import annotations

FIRST_WAIT_S = 1800.0


def is_ft_url(url) -> bool:
    if not url:
        return False
    try:
        from halo_harness.ollama_steward.servers_hf import for_url
        s = for_url(url)
        if s is not None:
            return s.runtime == "freetoken"
        from halo_harness.freetoken.peer import _CACHE
        from halo_harness.providers.huggingface import resolve_huggingface_local_servers
        u = str(url).rstrip("/")
        peers = [str((hit[1] or {}).get("url") or "").rstrip("/") for hit in _CACHE.values()]
        return u in peers or any(e.runtime == "freetoken" and str(e.url).rstrip("/") == u
                                 for e in resolve_huggingface_local_servers())
    except Exception:
        return False


def widen(conn, url) -> None:
    try:
        if getattr(conn, "sock", None) is not None and is_ft_url(url):
            conn.sock.settimeout(FIRST_WAIT_S)
    except Exception:
        pass
