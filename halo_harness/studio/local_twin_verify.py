"""halo_harness.studio.local_twin_verify -- Halo 3.3.6.0 R1: Studio verifies a
twin it just made (providers/ollama_twin_verify.py) on a daemon thread, so the
twin route answers at once; the result is kept in the tune store and
published as

    {session_id: "local", event: "twin-verify", ts, data: {host, twin, state, line, ...}}

after which the Models rows read again (the twin's chip says the line).
`raw_and_twins(host, rows, state_dir)` marks each Models row: a twin
(`twin` {of, state, line}) or a raw library tag (`raw` {twins, verified, offer}),
where `offer` is "delete the raw tag, keep the twin" once a twin is verified.
"""

from __future__ import annotations

import threading
import time
from typing import Callable, Optional

OFFER = "delete the raw tag, keep the twin {twin} (it is verified on the GPU and shares no extra disk)"


def start_verify(host, twin: str, window, publish: Optional[Callable] = None, *, state_dir=None,
                 runner: Optional[Callable] = None) -> str:
    from halo_harness.providers.ollama_twin_verify import verify
    fn = runner or verify

    def body() -> None:
        try:
            r = fn(host, twin, window, state_dir=state_dir)
        except Exception as e:
            r = {"state": "unverified", "line": f"unverified: {type(e).__name__}: {e}"}
        from halo_harness.studio.local_pull_job import after_change
        after_change()
        if publish is not None:
            try:
                publish({"session_id": "local", "event": "twin-verify", "ts": time.time(),
                         "data": {"host": host.name, "twin": twin, **{k: r.get(k) for k in ("state", "line", "tok_s",
                                                                                           "layers", "splits", "window")}}})
            except Exception:
                pass

    threading.Thread(target=body, name=f"halo-twin-verify-{twin}", daemon=True).start()
    return "running"


def raw_and_twins(host, rows: list, state_dir) -> None:
    """Each row gets `twin` or `raw` (in place); rows without either are left as they are."""
    from halo_harness.providers.ollama import ollama_names_match
    from halo_harness.providers.ollama_tune_store import twin_verify
    twins = {}
    for r in rows:
        of = r.get("twin_of")
        if of:
            v = twin_verify(state_dir, host_url=host.url, twin=r["model"]) or {}
            r["twin"] = {"of": of, "state": v.get("state") or "unverified", "line": v.get("line") or
                         "unverified: not checked yet (halo models twin verifies a new twin)"}
            twins.setdefault(of, []).append(r)
    for r in rows:
        mine = [t for of, ts in twins.items() if ollama_names_match(of, r["model"]) for t in ts]
        if mine and not r.get("twin_of"):
            ok = [t for t in mine if t["twin"]["state"] == "verified"]
            r["raw"] = {"twins": [t["model"] for t in mine], "verified": bool(ok),
                        "offer": OFFER.format(twin=ok[0]["model"]) if ok else ""}
