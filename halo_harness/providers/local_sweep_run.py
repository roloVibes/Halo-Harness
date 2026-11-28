"""halo_harness.providers.local_sweep_run -- Halo 3.6.0.25 T: the sweep run, Halo alone (no model involved).

    measure_window(host, model, window, *, send, client, memory=None, num_gpu=None, before=None) -> row
    sweep(host, model, *, state_dir, card=None, send=None, client=None, memory=None, stop=None, on_line=None,
          sessions=None, check_busy=True, max_loads=6, again=False, start=None, measure=None) -> result
    measure_one(host, model, window, *, state_dir, ...) -> result   (one more window, the tuner's ask; the same cap)

The measured step loads the model at one window with every layer on the card (the bench's own load: the untimed
warm-up through the gym's send path, `num_gpu` = every layer), then ONE warm timed call (the bench's prompt of about
60 % of the window and a 256-token reply; a second one only when the first reply speed is more than 40 % off the
window measured before, to rule out noise, the faster kept), `/api/ps` (wholly on the card or spilled) and the card's
used and free memory where it can be read (this machine; a host with an `ssh:` entry; else unknown). Everything runs
inside `ollama_measure_guard.measuring()` (one measurement per server across processes, the loaded models put back),
after the bench's wait for an idle host. Each window is saved as it lands; a Stop ends the sweep after the running
load and keeps what was measured; a second start goes on from there. The pick is written as the measured window
(ollama_calibrate.record_calibration, keyed by digest + the server's version and fit settings), so `halo local
measure`, the estimate and the tuned twin read the same number.
"""

from __future__ import annotations

import time
from typing import Callable, Optional

from halo_harness.providers import local_sweep as S

MIB = 1024 * 1024
COST = ("local: ~{n} min on {host}, at most {loads} loads of {model}; it unloads what is loaded and puts it back after; "
        "writes the sweep and the measured window in Halo's own files, nothing to the Ollama store; no tokens leave "
        "this machine")


def card_memory(host) -> Optional[dict]:
    """{used, free, total} in bytes for the host's card(s): this machine's probe, a host's `ssh:` probe, else None."""
    from halo_harness.providers.ollama_hw import get_local_gpu_memories, get_ssh_gpu_memory, is_local_host
    try:
        if is_local_host(host):
            cards = get_local_gpu_memories(force=True)
        elif getattr(host, "ssh", None):
            cards = [get_ssh_gpu_memory(host.ssh, force=True)]
        else:
            return None
    except Exception:
        return None
    cards = [c for c in cards if c is not None and isinstance(c.total_bytes, int) and isinstance(c.free_bytes, int)]
    if not cards:
        return None
    total, free = sum(c.total_bytes for c in cards), sum(c.free_bytes for c in cards)
    return {"used": total - free, "free": free, "total": total}


def _ready() -> list:
    return [{"role": "user", "content": [{"type": "text", "text": "Reply with the word ready."}]}]


def measure_window(host, model: str, window: int, *, send: Callable, client, memory: Optional[Callable] = None,
                   num_gpu: Optional[int] = None, before: Optional[float] = None) -> dict:
    from halo_harness.providers.local_bench import REPLY, _ps, _rate, prompt_for
    row = {"window": window, "at": time.time(), "on_card": None, "free_mib": None, "used_mib": None,
           "prompt_tok_s": None, "tok_s": None, "timed": 0, "size": None, "size_vram": None}
    warm = send(_ready(), num_ctx=window, num_predict=8, num_gpu=num_gpu)
    if warm.get("error"):
        return {**row, "on_card": False, "error": str(warm["error"])[:300]}
    best = None
    for n in (1, 2):
        r = send(prompt_for(window), num_ctx=window, num_predict=REPLY, num_gpu=num_gpu)
        if r.get("error"):
            if best is None:
                return {**row, "on_card": False, "error": f"the timed call failed: {str(r['error'])[:280]}"}
            break
        got = (_rate(r.get("prompt_eval_count"), r.get("prompt_eval_duration")), _rate(r.get("eval_count"), r.get("eval_duration")))
        if best is None or (got[1] or 0) > (best[1] or 0):
            best = got
        row["timed"] = n
        off = isinstance(before, (int, float)) and before > 0 and isinstance(got[1], (int, float)) \
            and abs(got[1] - before) / before > S.NOISE
        if not off:
            break
    row["prompt_tok_s"], row["tok_s"] = best
    ps = _ps(client, model)
    size, vram = ps.get("size"), ps.get("size_vram")
    row.update(size=size, size_vram=vram,
               on_card=(vram >= size) if isinstance(size, int) and isinstance(vram, int) and size > 0 else False)
    mem = None
    try:
        mem = memory() if memory is not None else None
    except Exception:
        mem = None
    if mem:
        row.update(free_mib=int(mem["free"] // MIB), used_mib=int(mem["used"] // MIB))
    return row


def _sender(host, model: str, state_dir) -> Callable:
    from halo_harness.providers.local_bench import sender
    return sender(host, model, state_dir)


def _facts(host, model: str, client) -> dict:
    from halo_harness.providers import capability_battery as CB
    from halo_harness.providers.ollama_hw import load_server
    version = (client.call("GET", "/api/version", timeout=10.0) or {}).get("version")
    row = CB._row(client.call("GET", "/api/tags", timeout=15.0), model)
    if row is None:
        return {}
    info = (client.call("POST", "/api/show", body={"model": model}, timeout=15.0) or {}).get("model_info") or {}
    trained = next((v for k, v in info.items() if k.endswith(".context_length") and isinstance(v, int)), None)
    return {"row": row, "info": info, "version": version, "server": load_server(host, version), "trained": trained,
            "digest": row.get("digest")}


def _start(host, model: str, f: dict, card) -> int:
    from halo_harness.providers.local_bench import plan_windows
    from halo_harness.ollama_steward.profiles import lookup
    _ws, ceiling, _src = plan_windows(card, f["row"], f["info"], quick=True, profile_ctx=(lookup(host, model) or {}).get("num_ctx"))
    if not card:
        from halo_harness.providers.ollama import get_catalog
        from halo_harness.providers.ollama_hw import estimate_fit_for_host
        try:
            est = estimate_fit_for_host(host, model, get_catalog(host))
        except Exception:
            est = None
        ceiling = est if isinstance(est, int) and not isinstance(est, bool) and est > 0 else ceiling
    return S.grid(ceiling)


def _top(host, f: dict) -> int:
    from halo_harness.providers.local_bench import MAX_WINDOW
    cap = host.max_ctx if isinstance(getattr(host, "max_ctx", None), int) and host.max_ctx > 0 else None
    return min(x for x in (f.get("trained") or MAX_WINDOW, cap or MAX_WINDOW))


def _fail(model: str, name: str, say: str) -> dict:
    return {"ok": False, "model": model, "host": name, "say": say, "error": say}


def _finish(state_dir, host, rec: dict, *, stopped: bool, max_loads: int, gpu_total=None) -> None:
    S.mark(rec["windows"])
    w, why = S.pick(rec["windows"], top=rec["top"], trained=rec.get("trained"), loads_left=max_loads - len(rec["windows"]),
                    stopped=stopped)
    rec.update(pick=w, why=why, done=S.next_window(rec["windows"], start=rec["start"], top=rec["top"]) is None)
    S.save(state_dir, rec)
    floor = rec["done"] and rec["windows"] and not any(r.get("state") == S.FAILED for r in rec["windows"]) \
        and S.step_down(min(r["window"] for r in rec["windows"])) is None
    if w or floor:  # a pick, or measured down to the floor and nothing fits (a load that failed is no fit reading)
        from halo_harness.providers.ollama_calibrate import record_calibration
        srv = rec.get("server") or {}
        record_calibration(state_dir, host_url=host.url, model=rec["model"], digest=rec.get("digest"), max_full_gpu_ctx=w,
                           ollama_version=srv.get("version"), gpu_total=gpu_total,
                           fit_settings={k: v for k, v in srv.items() if k != "version"} or None)


def sweep(host, model: str, *, state_dir, card=None, send: Optional[Callable] = None, client=None,
          memory: Optional[Callable] = None, stop=None, on_line: Optional[Callable[[str], None]] = None,
          sessions: Optional[Callable] = None, check_busy: bool = True, max_loads: int = S.MAX_LOADS,
          again: bool = False, start: Optional[int] = None, only: Optional[int] = None) -> dict:
    """`only`: measure that one window (the tuner's ask), under the same cap and the same record."""
    from halo_harness.providers import capability_battery as CB
    from halo_harness.providers.local_bench_runs import busy
    from halo_harness.providers.ollama_calibrate_steps import gpu_layers_for
    from halo_harness.providers.ollama_measure_guard import measuring
    name, say = getattr(host, "name", "") or "this host", on_line or (lambda _s: None)
    why = CB.test_guard(host) or (busy(state_dir, name, sessions=sessions) if check_busy else "")
    if why:
        return _fail(model, name, why)
    client = client or CB.HostClient(host)
    f = _facts(host, model, client)
    if not f:
        return _fail(model, name, f"no model named {model} on {name}")
    rec = None if again else S.load(state_dir, host.url, model, digest=f["digest"], server=f["server"])
    if rec is None:
        rec = {"host_url": host.url, "host": name, "model": model, "digest": f["digest"], "server": f["server"],
               "trained": f["trained"], "start": start or _start(host, model, f, card), "windows": [], "pick": None,
               "why": "", "done": False, "proposals": []}
    rec["top"] = _top(host, f)
    if only is not None:
        if f["trained"] and only > f["trained"]:
            return {**_fail(model, name, f"{only:,} is above {model}'s trained window ({f['trained']:,}): refused"),
                    "refused": True}
        if any(r["window"] == only for r in rec["windows"]):
            return {"ok": True, "model": model, "host": name, "record": rec, "say": f"{only:,} is measured already",
                    "row": next(r for r in rec["windows"] if r["window"] == only)}
    if len(rec["windows"]) >= max_loads:
        S.mark(rec["windows"])
        rec.setdefault("pick", None)
        return {"ok": True, "model": model, "host": name, "record": rec, "capped": True,
                "say": f"the {max_loads} loads of this sweep were used: {rec.get('why') or 'no pick'}"}
    if only is None and rec["windows"] and rec.get("done"):
        return {"ok": True, "model": model, "host": name, "record": rec, "already": True,
                "say": f"swept already for this digest and server: {rec.get('why')} (--again sweeps it again)"}
    send = send or _sender(host, model, state_dir)
    memory = memory if memory is not None else (lambda: card_memory(host))
    layers = gpu_layers_for(f["info"])
    stopped, row = False, None
    with measuring(host, model, state_dir) as g:
        if not g.ok:
            return _fail(model, name, g.say)
        while len(rec["windows"]) < max_loads:
            if stop is not None and stop.is_set():
                stopped = True
                break
            w = only if only is not None else S.next_window(rec["windows"], start=rec["start"], top=rec["top"])
            if w is None:
                break
            say(f"{w:,}: loading with every layer on the card, then one timed call")
            before = rec["windows"][-1].get("tok_s") if rec["windows"] else None
            row = measure_window(host, model, w, send=send, client=client, memory=memory, num_gpu=layers, before=before)
            rec["windows"].append(row)
            S.mark(rec["windows"])
            S.save(state_dir, rec)  # saved as it lands
            say(S.row_line(row))
            if only is not None:
                break
    if g.left:
        say(g.left)
    mem = None
    try:
        mem = memory()
    except Exception:
        mem = None
    _finish(state_dir, host, rec, stopped=stopped, max_loads=max_loads, gpu_total=(mem or {}).get("total"))
    say(f"the pick: {rec['why']}" if rec.get("pick") else f"no pick: {rec['why']}")
    return {"ok": True, "model": model, "host": name, "record": rec, "stopped": stopped, "row": row, "left": g.left,
            "say": (f"the pick: {rec['why']}" if rec.get("pick") else f"no pick: {rec['why']}")
            + (" (stopped: start it again to go on)" if stopped else "")}


def estimate(host, model: str, *, card=None, state_dir=None, max_loads: int = S.MAX_LOADS) -> "tuple[int, str]":
    """(minutes, the line said before a sweep) from the bench's own cost model over `max_loads` windows."""
    from halo_harness.providers.local_bench import cost_minutes
    from halo_harness.providers.ollama import ollama_names_match
    from halo_harness.studio import ollama_hosts_view as V
    row = next((r for r in V.catalog_of(host).get("models") or [] if isinstance(r, dict)
                and ollama_names_match(r.get("model") or r.get("name"), model)), {})
    ws = [S.STEP_BIG * (i + 2) for i in range(max_loads)]
    n = cost_minutes(row.get("size"), ws)
    return n, COST.format(n=n, host=getattr(host, "name", "") or "this host", loads=max_loads, model=model)
