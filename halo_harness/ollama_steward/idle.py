"""halo_harness.ollama_steward.idle -- is a card idle, and who holds it (Halo 3.3.7.0 R4; plans/local-model-fit-brief.md
G13 and D5 21: the traffic view including foreign clients, "so contention is visible before it hurts").

    explained(state_dir, host_name, model, *, now=None) -> "" | what explains it
        a Halo record of that model on that host: a ledger call (this machine's, and every peer's that pushes `POST
        ledger` to a halo host here) or a load the scheduler made (local_sched/loads.jsonl) within EXPLAIN_S, a
        battery profile or a speed card written within EXPLAIN_S (the battery and the bench load models with no ledger
        line), the host's residency clock (host/residency.py: a warm, pin or pivot through the host), or the duty
        steward's helper model
    foreign(state_dir, host, *, ps=None, now=None) -> [{model, size, size_gb, since, since_text, expires}]
        the models `/api/ps` lists that nothing above explains. Ollama names the model, never the client, so all it
        says is "a client that is not a halo" (a halo that pushes no ledger lines here looks the same); `since` is when
        a halo first saw it so (<state>/ollama/foreign.json)
    foreign_line(rows) -> "foreign: 1 model, 17.3 GB, since 14:02" | ""
    busy_reason(rows, host_name) -> "a client that is not a halo holds qwen3-coder:30b (17.3 GB) since 14:02 ..." | ""
    idle_since(state_dir, host, *, ps=None, sessions=None, now=None) -> {idle_s, last, last_what, busy, foreign, line}
        the newest use of the card (a ledger call, a scheduler load, a residency mark); `busy` says why it is not idle
        now (a foreign model, a session on it); idle_s is None when nothing used it in the last day
Read-only: one `/api/ps` read (providers/ollama_control.loaded) unless `ps` is given; nothing loads or unloads.
"""

from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Callable, Optional

EXPLAIN_S = 1800.0
DAY_S = 86400.0
FILE = "foreign.json"
NOT_A_HALO = "a client that is not a halo"
HOW = "Ollama's /api/ps names the model, never the client"


def _at(text) -> Optional[float]:
    from halo_harness.ollama_steward.ledger import parse_at
    return text if isinstance(text, (int, float)) else parse_at(text)


def _match(a, b) -> bool:
    from halo_harness.providers.ollama import ollama_names_match
    return ollama_names_match(a, b)


def _helper(model: str) -> bool:
    try:
        from halo_harness.theme import get_config_value
        if get_config_value("host.steward.enabled", default=False) is not True:
            return False
        ref = str(get_config_value("host.steward.model", default="") or "")
        return _match(ref[3:].rsplit("@", 1)[0] if ref.startswith("ol:") else ref, model)
    except Exception:
        return False


def _records(state_dir, host_name: str, since: float) -> list:
    """[(at, what, model)] of every Halo record on that host newer than `since`."""
    from halo_harness.ollama_steward.ledger import read_calls
    out = []
    try:
        for x in read_calls(state_dir, since=since, host=host_name):
            out.append((_at(x.get("at")) or 0.0, "a call from " + (x.get("from") or "this machine"), x.get("model")))
    except Exception:
        pass
    from halo_harness.local_sched.loads import recent
    for r in recent(state_dir, host=host_name, since=since):
        out.append((_at(r.get("at")) or 0.0, f"the scheduler's {r.get('why') or 'load'}", r.get("model")))
    return out


def _measured(state_dir, host_name: str, model: str, since: float) -> str:
    try:
        from halo_harness.providers.local_bench_runs import load
        from halo_harness.providers.ollama_capability import profile_for
        p = profile_for(state_dir, model, host_name) or {}
        if float(p.get("probed_at") or 0) >= since:
            return "the battery"
        sc = load(state_dir, host_name, model) or {}
        if float(sc.get("at") or 0) + float(sc.get("took_s") or 0) >= since:
            return "the bench"
    except Exception:
        pass
    return ""


def _resident(state_dir, host_name: str, model: str) -> str:
    try:
        from halo_harness.host import residency
        for r in residency.rows(state_dir):
            if str(r.get("host") or "") == host_name.lower() and _match(r.get("model"), model):
                return f"the host's residency clock ({r.get('op')} by {r.get('by') or 'a peer'})"
    except Exception:
        pass
    return ""


def explained(state_dir, host_name: str, model: str, *, now: Optional[float] = None) -> str:
    now = time.time() if now is None else now
    if _helper(model):
        return "the duty steward's helper"
    hit = next((what for at, what, m in _records(state_dir, host_name, EXPLAIN_S) if _match(m, model)
                and at >= now - EXPLAIN_S), "")
    return hit or _measured(state_dir, host_name, model, now - EXPLAIN_S) or _resident(state_dir, host_name, model)


def _ps(host) -> "tuple[list, bool]":
    from halo_harness.providers.ollama_control import loaded
    try:
        got = loaded(host)
    except Exception:
        return [], False
    return list(got.get("models") or []), bool(got.get("ok"))


def _seen_path(state_dir) -> Path:
    from halo_harness.ollama_steward.ledger import ledger_dir
    return ledger_dir(state_dir) / FILE


def _seen(state_dir, host_name: str, models: list, now: float) -> dict:
    """{model: first seen} for the foreign models now; the ones gone are dropped (the read was a full /api/ps)."""
    p = _seen_path(state_dir)
    try:
        data = json.loads(p.read_text(encoding="utf-8"))
        data = data if isinstance(data, dict) else {}
    except (OSError, ValueError):
        data = {}
    pre = f"{host_name.lower()}|"
    keep = {k: v for k, v in data.items() if not k.startswith(pre)}
    mine = {m: float(data.get(pre + m) or now) for m in models}
    keep.update({pre + m: t for m, t in mine.items()})
    if keep != data:
        try:
            p.parent.mkdir(parents=True, exist_ok=True)
            p.write_text(json.dumps(keep), encoding="utf-8")
        except OSError:
            pass
    return mine


def when(t: Optional[float], now: Optional[float] = None) -> str:
    if not isinstance(t, (int, float)):
        return "?"
    now = time.time() if now is None else now
    return time.strftime("%H:%M" if now - t < DAY_S else "%Y-%m-%d %H:%M", time.localtime(t))


def foreign(state_dir, host, *, ps: Optional[list] = None, now: Optional[float] = None) -> list:
    if host is None or state_dir is None:
        return []
    now = time.time() if now is None else now
    name = str(getattr(host, "name", host) or "")
    rows, ok = (list(ps), True) if ps is not None else _ps(host)
    if not ok:
        return []
    out = [r for r in rows if isinstance(r, dict) and (r.get("model") or r.get("name"))
           and not explained(state_dir, name, r.get("model") or r.get("name"), now=now)]
    first = _seen(state_dir, name, [str(r.get("model") or r.get("name")) for r in out], now)
    res = []
    for r in out:
        m = str(r.get("model") or r.get("name"))
        size = r.get("size_vram") if isinstance(r.get("size_vram"), int) else r.get("size")
        res.append({"model": m, "size": size, "size_gb": round(size / 1e9, 1) if isinstance(size, int) else None,
                    "since": first.get(m, now), "since_text": when(first.get(m, now), now),
                    "expires": r.get("expires") or r.get("expires_at")})
    return res


def foreign_line(rows: list) -> str:
    if not rows:
        return ""
    gb = sum(r["size_gb"] or 0 for r in rows)
    since = min(r["since"] for r in rows)
    n = len(rows)
    return f"foreign: {n} model{'s' * (n != 1)}, {gb:.1f} GB, since {when(since)} ({NOT_A_HALO}; {HOW})"


def busy_reason(rows: list, host_name: str) -> str:
    if not rows:
        return ""
    r = rows[0]
    size = f" ({r['size_gb']:.1f} GB)" if r.get("size_gb") else ""
    more = f" and {len(rows) - 1} more" if len(rows) > 1 else ""
    return (f"{NOT_A_HALO} holds {r['model']}{size}{more} on {host_name} since {r['since_text']} ({HOW}): a bench "
            "needs the card to itself; it waits for that client like for any other user")


def idle_since(state_dir, host, *, ps: Optional[list] = None, sessions: Optional[Callable] = None,
               now: Optional[float] = None) -> dict:
    now = time.time() if now is None else now
    name = str(getattr(host, "name", host) or "")
    fr = foreign(state_dir, host, ps=ps, now=now)
    busy = busy_reason(fr, name)
    if not busy:
        from halo_harness.providers.local_bench_runs import _on_host, _sessions
        import os
        try:
            live = [r for r in (sessions or _sessions)() or [] if r.get("pid") != os.getpid() and _on_host(r.get("model"), name)]
        except Exception:
            live = []
        if live:
            busy = f"session {live[0].get('session_id') or '?'} is using {live[0].get('model')} on {name}"
    recs = [(at, what) for at, what, _m in _records(state_dir, name, DAY_S) if at]
    try:
        from halo_harness.host import residency
        recs += [(float(r["at"]), f"a {r.get('op')} through the host") for r in residency.rows(state_dir)
                 if r.get("host") == name.lower() and isinstance(r.get("at"), (int, float))]
    except Exception:
        pass
    last, what = max(recs) if recs else (None, "")
    idle = 0.0 if busy else (round(now - last, 1) if last else None)
    line = (f"{name}: busy -- {busy}" if busy else f"{name}: idle {int(idle // 60)} min (last: {what} at {when(last, now)})"
            if idle is not None else f"{name}: idle (nothing used it in the last day that Halo saw)")
    return {"idle_s": idle, "last": last, "last_what": what, "busy": busy, "foreign": fr, "line": line,
            "foreign_line": foreign_line(fr)}
