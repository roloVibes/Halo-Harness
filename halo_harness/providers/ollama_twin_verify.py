"""halo_harness.providers.ollama_twin_verify -- Halo 3.3.6.0 R1: a fitted
twin, verified (plans/local-model-fit-brief.md Part A, item 3): after
`ollama_tune.create_twin` makes it, load it at its window, read `/api/ps`
(`size_vram == size`: every byte on the GPU), the host's server log when it
is readable here (`offloaded N/N layers`, `CUDA0 KV buffer size`, `graph
splits = 2` during a warm generate), and time one warm call (the first call
after the load warms it and is never timed -- Part G4).

    verify(host, twin, window=None, *, client=None, state_dir=None, log_lines=None) -> Result
    Result = {state: verified | unverified | spilled, line, layers [n, of] | None, splits, kv_mib,
              tok_s, window, on_gpu_pct, at}
    pull_warning(weights_bytes, budget_bytes) -> "23 GB on a 23 GB card: it will always spill" | ""

The result is kept on the twin's record in the tune store (`verify`,
providers/ollama_tune_store.py), which the Models rows and the twin's card
read: "verified -- 41/41 layers, splits = 2, 258 tok/s at 32,768",
"unverified -- <why>", "spilled -- 59/66 layers, 16 tok/s" (3.3.6.0 R3: the fit badge's line, fit_evidence.py).
"""

from __future__ import annotations

import re
import time
from typing import Optional

_OFFLOAD = re.compile(r"offloaded (\d+)/(\d+) layers")
_KV = re.compile(r"CUDA\d+ KV buffer size\s*=\s*([\d.]+) MiB")
_SPLITS = re.compile(r"graph splits\s*=\s*(\d+)")
TAIL_BYTES = 256 * 1024
WARM_PROMPT = "Count from one to twenty, words only."


def pull_warning(weights, budget) -> str:
    if not isinstance(weights, (int, float)) or not isinstance(budget, (int, float)) or budget <= 0 or weights < budget:
        return ""
    return f"{weights / 1e9:.0f} GB on a {budget / 1e9:.0f} GB card: it will always spill"


def log_facts(lines) -> dict:
    """The newest load's {layers, kv_mib, splits} from server-log lines (None where none says)."""
    out: dict = {"layers": None, "kv_mib": None, "splits": None}
    for line in lines or ():
        if m := _OFFLOAD.search(line):
            out["layers"] = [int(m.group(1)), int(m.group(2))]
        if m := _KV.search(line):
            out["kv_mib"] = float(m.group(1))
        if m := _SPLITS.search(line):
            out["splits"] = int(m.group(1))
    return out


def _log_tail(host) -> Optional[list]:
    try:
        from halo_harness.ollama_steward.server_log import source_for
        path, why = source_for(host)
        if path is None or why:
            return None
        with open(path, "rb") as f:
            f.seek(0, 2)
            f.seek(max(0, f.tell() - TAIL_BYTES))
            return f.read().decode("utf-8", "replace").splitlines()
    except OSError:
        return None


def _line(r: dict) -> str:
    """3.3.6.0 R3: the fit badge's own line (providers/fit_evidence.line_of)."""
    from halo_harness.providers.fit_evidence import line_of
    return line_of(r["state"], layers=r.get("layers"), splits=r.get("splits"), tok_s=r.get("tok_s"),
                   window=r.get("window") if r["state"] == "verified" else None, on_gpu_pct=r.get("on_gpu_pct"),
                   why=r.get("why") or ("it could not be checked" if r["state"] == "unverified" else ""))


def verify(host, twin: str, window: Optional[int] = None, *, client=None, state_dir=None, log_lines=None) -> dict:
    from halo_harness.providers.battery_probes import speed
    from halo_harness.providers.capability_battery import HostClient, _ps_entry, test_guard
    r: dict = {"state": "unverified", "layers": None, "splits": None, "kv_mib": None, "tok_s": None, "window": window,
               "on_gpu_pct": None, "at": time.time(), "why": ""}
    why = test_guard(host)
    if why:
        r["why"] = why
    else:
        c = client or HostClient(host)
        opts = {"num_ctx": window} if isinstance(window, int) and window > 0 else {}
        body = {"model": twin, "stream": False, "keep_alive": "5m", "options": {**opts, "num_predict": 48, "temperature": 0},
                "messages": [{"role": "user", "content": WARM_PROMPT}]}
        warm = c.call("POST", "/api/chat", body=body, timeout=600.0)  # loads it; the first call is never timed
        timed = c.call("POST", "/api/chat", body=body, timeout=180.0) if isinstance(warm, dict) else None
        entry = _ps_entry(c.call("GET", "/api/ps", timeout=10.0), twin)
        if not isinstance(timed, dict) or entry is None:
            r["why"] = f"{twin} did not load on {getattr(host, 'name', 'the host')}" if not isinstance(warm, dict) else \
                "/api/ps does not list it after the load"
        else:
            size, vram = entry.get("size"), entry.get("size_vram")
            r["tok_s"] = speed(timed)["tok_s"]
            r["window"] = entry.get("context_length") or window
            if isinstance(size, int) and size > 0 and isinstance(vram, int):
                r["on_gpu_pct"] = round(100.0 * vram / size)
                r["state"] = "verified" if vram >= size else "spilled"
            facts = log_facts(log_lines if log_lines is not None else (_log_tail(host) or []))
            r.update({k: v for k, v in facts.items() if v is not None})
            if r["layers"] and r["layers"][0] < r["layers"][1]:
                r["state"] = "spilled"
            if r["state"] == "verified" and isinstance(r.get("splits"), int) and r["splits"] > 2:
                r["state"] = "spilled"
    r["line"] = _line(r)
    if state_dir is not None:
        from halo_harness.providers.ollama_tune_store import set_twin_verify
        set_twin_verify(state_dir, host_url=host.url, twin=twin, result=r)
    return r
