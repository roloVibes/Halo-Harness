"""halo_harness.local_pool.bench -- the pool's speed card: the 3.3.6.0 battery against the running pool (Halo 3.3.8.0
R4; docs/POOL.md "Measured or extrapolated"; `halo local bench --host pool [--quick]`, the Pool page's Bench).

    estimate(run=None, *, quick=False, state_dir=None) -> {seconds, windows, line}   the cost line first: "local: ~N s
        on the pool (pc, me: their GPUs are busy for it), writes the pool's speed card; no tokens leave the LAN"
    bench(*, quick=False, send=None, state_dir=None, on_line=None, now=time.time) -> SpeedCard | {ok: False, say}
    sender(run) -> send(messages, *, num_predict) -> {prompt_eval_count, prompt_eval_duration, eval_count,
        eval_duration, done_reason, error}   POST <the pool's url>/chat/completions with its key (llama-server's
        `timings`); SEAMS["send"] is the tests' runner (it answers the battery)

The order is the 3.3.6.0 battery's: per window {8192, 32768, the pool's -c} under its -c (`quick`: the -c alone) one
untimed warm-up, then a timed call -- a prompt of ~60 % of the window and a 256-token reply (prompt tok/s, tok/s,
TTFT = the prompt's time); then the reply reserve at the largest window (128 / 256 / 512, the first not cut). The
pool's window is fixed at its launch (-c), so each window is a prompt size inside it. The cold load is the launch's
(spawn to /health: run.json `ready_s`). SpeedCard (local_bench_runs' shape) + {pool: true, runtime, members, split,
order, rpc [{member, addr, rtt_ms, link}], cache, ctx, display, layers}; host `pool`, cache key `pool|<model>`. It waits
(one line, nothing sent) while the pool answered a call in the last minute, is degraded, or is not running.
"""

from __future__ import annotations

import json
import re
import time
from typing import Callable, Optional

SEAMS: dict = {}
TIMEOUT_S = 900.0
PREFILL_ASSUMED = 300.0
COST = ("local: ~{s} s on the pool ({who}: their GPUs are busy for it), writes the pool's speed card; no tokens leave "
        "the LAN")
_OFFLOAD = re.compile(r"offloaded (\d+)/(\d+) layers")


def _state(state_dir=None):
    from halo_harness.local_pool.claims import _state as s
    return s(state_dir)


def windows_for(ctx: int, quick: bool) -> list:
    from halo_harness.providers.local_bench import WINDOWS
    ctx = int(ctx or 0)
    return [ctx] if quick else sorted({w for w in WINDOWS if w < ctx} | {ctx})


def estimate(run: Optional[dict] = None, *, quick: bool = False, state_dir=None) -> dict:
    from halo_harness.local_pool import catalog as C, launch, speed
    from halo_harness.providers.local_bench import REPLY, RESERVES, SHARE
    r = run if run is not None else launch.run(state_dir)
    model = C.get((r or {}).get("model") or "") or {}
    card = speed.card_for(model, state_dir) if model else None
    tok = speed.floor(card) or ((model.get("speed") or {}).get("tok_s_low")) or 10.0
    pp = min([float(x["prompt_tok_s"]) for x in (card or {}).get("windows") or []
              if isinstance(x.get("prompt_tok_s"), (int, float))] or [PREFILL_ASSUMED])
    ws = windows_for((r or {}).get("ctx") or 32768, quick)
    secs = sum(w * SHARE / pp + REPLY / tok + 8 / tok for w in ws) + sum(RESERVES) / tok
    who = ", ".join((r or {}).get("members") or []) or "its members"
    s = max(1, int(round(secs)))
    return {"seconds": s, "windows": ws, "line": COST.format(s=s, who=who)}


def _flat(messages: list) -> list:
    out = []
    for m in messages:
        c = m.get("content")
        text = "".join(str(p.get("text") or "") for p in c if isinstance(p, dict)) if isinstance(c, list) else str(c or "")
        out.append({"role": m.get("role") or "user", "content": text})
    return out


def _post(url: str, body: dict, key: Optional[str]) -> "tuple[int, dict]":
    """One POST through providers/http.open_upstream (the choke point: the offline rule, the allow-list)."""
    import http.client
    import urllib.parse
    from halo_harness.providers.http import UpstreamConnectError, open_upstream
    u, conn = urllib.parse.urlparse(url), None
    try:
        conn = open_upstream(u.hostname or "127.0.0.1", u.port or 80, u.scheme == "https", connect_timeout=10)
        if conn.sock:
            conn.sock.settimeout(TIMEOUT_S)
        conn.request("POST", u.path or "/", body=json.dumps(body).encode("utf-8"),
                     headers={"Content-Type": "application/json", "Accept-Encoding": "identity",
                              **({"Authorization": f"Bearer {key}"} if key else {})})
        resp = conn.getresponse()
        code, raw = resp.status, resp.read()
    except (UpstreamConnectError, OSError, http.client.HTTPException, ValueError) as e:
        return 0, {"error": f"{type(e).__name__}: {str(e)[:160]}"}
    finally:
        if conn is not None:
            conn.close()
    try:
        return code, json.loads(raw or b"{}")
    except ValueError:
        return code, {}


def sender(run: dict) -> Callable:
    from halo_harness.local_pool.entry import key
    url, k = str(run.get("url") or "").rstrip("/") + "/chat/completions", key()

    def send(messages: list, *, num_predict: int) -> dict:
        body = {"model": run.get("model"), "messages": _flat(messages), "max_tokens": int(num_predict),
                "temperature": 0, "stream": False, "cache_prompt": False}
        code, got = _post(url, body, k)
        if code != 200:
            return {"error": got.get("error") if code == 0 else f"the pool's llama-server answered {code}"}
        t = got.get("timings") or {}
        ch = (got.get("choices") or [{}])[0]
        ns = lambda ms: int(float(ms) * 1e6) if isinstance(ms, (int, float)) else None  # noqa: E731
        return {"prompt_eval_count": t.get("prompt_n"), "prompt_eval_duration": ns(t.get("prompt_ms")),
                "eval_count": t.get("predicted_n"), "eval_duration": ns(t.get("predicted_ms")),
                "done_reason": "length" if ch.get("finish_reason") == "length" else "stop", "error": None}
    return send


def _guard(run: dict) -> str:
    import os
    import urllib.parse
    if not os.environ.get("BRIDGE_TEST_HOME") or "send" in SEAMS:
        return ""
    host = urllib.parse.urlparse(str(run.get("url") or "")).hostname
    return "" if host in ("127.0.0.1", "localhost") else "a test run benches a loopback pool only"


def _why_not(r: dict, state_dir) -> str:
    from halo_harness.local_pool import launch
    from halo_harness.local_pool.degrade import status
    from halo_harness.ollama_steward.ledger import read_calls
    from halo_harness.providers.local_bench_runs import BUSY_S
    if not r or not launch.alive(r):
        return "the pool is not running: Warm it first (halo local serve --pool <model>, or the Pool page's Warm)"
    st = status(state_dir)
    if st["state"] != "running":
        return f"{st['line']}: a bench needs every member up"
    recent = read_calls(_state(state_dir), since=BUSY_S, host="pool")
    if recent:
        return (f"the pool answered a call within the last {BUSY_S:.0f} s ({recent[-1].get('model') or 'a model'}): a "
                "bench needs it to itself; run it when it has been quiet for a minute")
    return _guard(r)


def _layers(r: dict):
    from halo_harness.local_pool.degrade import _log_tail
    hit = [m for m in (_OFFLOAD.search(x) for x in _log_tail(r)) if m]
    return [int(hit[-1].group(1)), int(hit[-1].group(2))] if hit else None


def bench(*, quick: bool = False, send: Optional[Callable] = None, state_dir=None,
          on_line: Optional[Callable[[str], None]] = None, now: Callable[[], float] = time.time) -> dict:
    from halo_harness.local_pool import launch
    from halo_harness.providers.local_bench import REPLY, RESERVES, SHORT, _msg, _rate, prompt_for
    from halo_harness.providers.local_bench_runs import _row_line, save
    say, r = on_line or (lambda _s: None), launch.run(state_dir)
    why = _why_not(r, state_dir)
    if why:
        return {"ok": False, "host": "pool", "model": (r or {}).get("model"), "say": why, "error": why}
    send = send or SEAMS.get("send") or sender(r)
    t0, layers = now(), _layers(r)
    on_gpu = None if layers is None else layers[0] >= layers[1]
    out = {"ok": True, "pool": True, "model": r["model"], "display": r.get("display"), "host": "pool",
           "digest": f"pool|{r['model']}", "runtime": "llama-server", "ollama_version": None, "at": t0,
           "cold_load_s": r.get("ready_s"), "cold_load_from": "the launch: spawn to /health", "windows": [],
           "max_gpu_window": None, "planner_window": r.get("ctx"), "ceiling_from": "the pool's -c (the fit's window)",
           "reserve_floor": None, "reserve_probes": [], "quick": quick, "warmups": 0, "members": list(r.get("members") or []),
           "split": list(r.get("split") or []), "order": list(r.get("order") or []), "cache": r.get("cache"),
           "ctx": r.get("ctx"), "layers": layers, "rpc": [{k: x.get(k) for k in ("member", "addr", "rtt_ms", "link")}
                                                         for x in r.get("rpc") or []]}
    for w in windows_for(r.get("ctx") or 0, quick):
        warm = send(_msg("Reply with the word ready."), num_predict=8)
        out["warmups"] += 1
        say(f"{w // 1024}k: warming (the first call after a load is never timed)")
        got = send(prompt_for(w), num_predict=REPLY) if not warm.get("error") else warm
        row = {"window": w, "prompt_tok_s": _rate(got.get("prompt_eval_count"), got.get("prompt_eval_duration")),
               "tok_s": _rate(got.get("eval_count"), got.get("eval_duration")),
               "ttft_ms": round(got["prompt_eval_duration"] / 1e6) if isinstance(got.get("prompt_eval_duration"),
                                                                                (int, float)) else None,
               "size": None, "size_vram": None, "layers": layers, "on_gpu": on_gpu,
               "prompt_tokens": got.get("prompt_eval_count"), "cut": got.get("done_reason") == "length"}
        if got.get("error"):
            row.update(error=f"the timed call at {w:,} failed: {got['error']}", on_gpu=False)
        out["windows"].append(row)
        say(_row_line(row))
        if got.get("error"):
            break
    good = [x["window"] for x in out["windows"] if not x.get("error")]
    out["max_gpu_window"] = max(good) if good and on_gpu is not False else None
    if good:
        for n in RESERVES:
            got = send(_msg(SHORT), num_predict=n)
            cut = got.get("done_reason") == "length" or bool(got.get("error"))
            out["reserve_probes"].append({"num_predict": n, "cut": cut, "window": max(good)})
            say(f"reply reserve {n}: " + ("cut" if cut else "the reply ended on its own"))
            if not cut:
                out["reserve_floor"] = n
                break
    out["kv"] = {"type": r.get("cache"), "verified_window": out["max_gpu_window"]}
    out["took_s"] = round(now() - t0, 1)
    if good:
        save(_state(state_dir), {k: v for k, v in out.items() if k != "ok"})
    else:
        out.update(ok=False, say=(out["windows"] or [{}])[0].get("error") or "no window answered")
    return out
