"""halo_harness.ollama_steward.traffic -- Halo 3.3.4.0 R2: the ledger's
rollups (`halo ollama traffic`).

`rollup(lines, hosts)` groups the ledger's lines per host and model:
calls, compaction calls, p50 / p95 prompt tokens (`prompt_eval_count`)
against the window sent (the most common `num_ctx_sent`) and p95's share
of it, trims, cuts (`done_reason: length`), 499 / 500 / timeouts / other
failures, reloads inferred (a `load_ms` over RELOAD_MS: the model was
loaded for that call), the eval rate's p50, and the calls per machine
(`from`; None is this machine).

A line names its host as the machine that made the call knew it (the Mac's
`lan` is this PC's `default`): `canonical_host` maps it to a host
configured here by url, and a url that points at this machine (fleet/
ollama_share.served_here) to the local host on the same port, so the
serving machine sees one row per model with every halo's calls in it.
"""

from __future__ import annotations

import urllib.parse
from collections import Counter
from typing import Optional

RELOAD_MS = 2000.0


def percentile(values: list, p: float) -> Optional[float]:
    vals = sorted(v for v in values if isinstance(v, (int, float)) and not isinstance(v, bool))
    if not vals:
        return None
    k = (len(vals) - 1) * p / 100.0
    lo, hi = int(k), min(int(k) + 1, len(vals) - 1)
    return vals[lo] + (vals[hi] - vals[lo]) * (k - lo)


def _port(url: str) -> Optional[int]:
    try:
        p = urllib.parse.urlparse(url or "")
        return p.port or (443 if p.scheme == "https" else 11434)
    except ValueError:
        return None


def canonical_host(host: dict, hosts: list) -> "tuple[str, Optional[object]]":
    """(the host name to show, the configured OllamaHost or None) for a line's {name, url}."""
    from halo_harness.fleet.ollama_share import served_here
    name, url = str((host or {}).get("name") or "?"), str((host or {}).get("url") or "").rstrip("/")
    for h in hosts:
        if str(h.url).rstrip("/") == url:
            return h.name, h
    if url and served_here(url):
        for h in hosts:
            if served_here(h.url) and _port(h.url) == _port(url):
                return h.name, h
    return name, None


def rollup(lines: list, hosts: list) -> list:
    """One row per (host, model), the hosts in the order they were first seen."""
    groups: dict = {}
    for line in lines:
        name, host = canonical_host(line.get("host") or {}, hosts)
        key = (name, str(line.get("model") or "?"))
        g = groups.setdefault(key, {"host": name, "host_obj": host, "model": key[1], "lines": []})
        g["lines"].append(line)
    rows = []
    for g in groups.values():
        ls = g.pop("lines")
        prompts = [x.get("prompt_eval_count") for x in ls if x.get("status") == 200]
        windows = Counter(x.get("num_ctx_sent") for x in ls if isinstance(x.get("num_ctx_sent"), int))
        window = windows.most_common(1)[0][0] if windows else None
        p95 = percentile(prompts, 95)
        status = Counter(str(x.get("status")) for x in ls)
        machines = Counter(x.get("from") or "this machine" for x in ls)
        rows.append({**g, "calls": len(ls), "compaction": sum(1 for x in ls if x.get("kind") == "compaction"),
                     "p50_prompt": percentile(prompts, 50), "p95_prompt": p95, "window": window,
                     "windows": len(windows),
                     "p95_pct": round(100.0 * p95 / window, 1) if p95 is not None and window else None,
                     "trims": sum(1 for x in ls if x.get("trimmed")),
                     "cuts": sum(1 for x in ls if x.get("done_reason") == "length"),
                     "s499": status.get("499", 0), "s500": status.get("500", 0), "timeouts": status.get("timeout", 0),
                     "failed": sum(n for k, n in status.items() if k not in ("200", "499", "500", "timeout")),
                     "reloads": sum(1 for x in ls if isinstance(x.get("load_ms"), (int, float))
                                    and x["load_ms"] > RELOAD_MS),
                     "eval_tok_s": percentile([x.get("eval_tok_s") for x in ls if not x.get("warming")], 50),  # R4
                     "machines": dict(machines), "model_window": _model_window(g)})
    return rows


def _model_window(g: dict) -> Optional[dict]:
    """3.3.5.0 R0: the model's window on this host and its source (`agent/model_window.window_of`)."""
    if g.get("host_obj") is None:
        return None
    from halo_harness.agent.model_window import window_on_host
    w = window_on_host(g["model"], g["host_obj"])
    return {"tokens": w.get("tokens"), "source": w.get("source")}


def _k(n) -> str:
    if not isinstance(n, (int, float)):
        return "?"
    return f"{n / 1000:.1f}k" if n >= 1000 else f"{n:.0f}"


def format_row(r: dict) -> str:
    comp = f" ({r['compaction']} compaction)" if r["compaction"] else ""
    window = f" of {_k(r['window'])}" + (f" ({r['p95_pct']:.0f}%)" if r["p95_pct"] is not None else "") \
        if r["window"] else ""
    if r["windows"] > 1:
        window += f", {r['windows']} windows sent"
    rate = f"{r['eval_tok_s']:.0f} tok/s" if r["eval_tok_s"] is not None else "?"
    who = ", ".join(f"{k} {v}" for k, v in sorted(r["machines"].items(), key=lambda kv: -kv[1]))
    failed = f", other failures {r['failed']}" if r["failed"] else ""
    return (f"  {r['model']}: {r['calls']} calls{comp}; prompt p50 {_k(r['p50_prompt'])} / p95 {_k(r['p95_prompt'])}"
            f"{window}; trims {r['trims']}, cuts {r['cuts']}; 499 {r['s499']}, 500 {r['s500']}, timeouts "
            f"{r['timeouts']}{failed}; reloads {r['reloads']}; eval {rate}; from {who}{_window_part(r)}")


def _window_part(r: dict) -> str:
    w = r.get("model_window") or {}
    return f"; window {w['tokens']:,} ({w.get('source')})" if w.get("tokens") else ""


def card_summary(host) -> str:
    """The host's hardware card in one line (the GPU and the server's settings)."""
    if host is None:
        return "not a host configured on this machine"
    try:
        from halo_harness.ollama_steward.hardware import format_card, hardware_card
        lines = format_card(hardware_card(host))
    except Exception as e:  # the card never stops the rollups
        return f"card not read ({type(e).__name__})"
    keep = [x for x in lines if x.startswith(("GPU ", "server ", "memory: unified"))]
    return "; ".join(keep[:3]) or "card: nothing read"


def format_rollups(rows: list, *, card=card_summary) -> list:
    out, seen = [], []
    for r in rows:
        if r["host"] not in seen:
            seen.append(r["host"])
    for i, name in enumerate(seen):
        mine = [r for r in rows if r["host"] == name]
        if i:
            out.append("")
        out.append(f"'{name}': {card(mine[0]['host_obj'])}")
        out.extend(format_row(r) for r in mine)
    return out
