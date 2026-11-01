"""halo_harness.studio.pool_watch_api -- Local -> Pool's measured half (Halo 3.3.8.0 R4; docs/STUDIO-local-pool.md "The
speed card and the findings"), reached through studio/pool_api.dispatch_pool. The same loopback / origin / token guard
as every Studio route; never a model call but the bench itself, which runs only when pressed. Every answer carries
`cli`, the `halo` line that does the same.

    GET  local/pool/bench           {estimate {seconds, windows, line} | null, card {model, lines, ...} | null,
                                     speed {word, measured, tok_s, penalty_pct, penalty_from, vs} | null, bench {busy,
                                     ok, lines, say}, held [{bundle, model, priority, hours}]}: the cost line first
                                     (seconds; the members busy for them), the pool's speed card, its penalty line, the
                                     bundles that hold the pool
    POST local/pool/bench {quick?}  local_pool/bench.bench in the background: 202 with `busy`; 409 with the one line
                                     when the pool is not running, degraded, answered a call in the last minute, or a
                                     bench already runs
    GET  local/pool/findings        {findings [the steward's pool-degraded / pool-rtt / pool-spill, keyed pool|<model>]}
"""

from __future__ import annotations

import threading

_BENCH: dict = {}
_LOCK = threading.Lock()


def _figures(state_dir):
    from halo_harness.local_pool import catalog as C, launch, speed
    r = launch.run(state_dir)
    model = C.get((r or {}).get("model") or "")
    if model is None:
        return None, None
    card = speed.card_for(model, state_dir)
    f = speed.figures(model, state_dir, r)
    return card, {k: f.get(k) for k in ("word", "measured", "tok_s", "ttft_ms", "penalty_pct", "penalty_from", "vs",
                                        "stale", "extrapolated")}


def _held(state_dir) -> list:
    from halo_harness.local_sched.reserve import claims
    return [{k: c.get(k) for k in ("bundle", "model", "priority", "hours", "gb")} for c in claims(None, state_dir=state_dir)
            if str(c.get("host") or "").lower() == "pool"]


def get_bench(req):
    from halo_harness.local_pool import bench, launch
    from halo_harness.providers.local_bench_runs import lines
    r = launch.run(req.state_dir)
    est = bench.estimate(r, state_dir=req.state_dir) if r and launch.alive(r) else None
    card, speed = _figures(req.state_dir)
    with _LOCK:
        state = dict(_BENCH)
    view = {k: card.get(k) for k in ("model", "host", "members", "split", "cache", "ctx", "cold_load_s", "at",
                                      "reserve_floor", "verified_by")} if card else None
    if view is not None:
        view["lines"] = lines(card)
    return 200, {"estimate": est, "card": view, "speed": speed, "bench": state, "held": _held(req.state_dir),
                 "cli": "halo local bench --host pool"}


def post_bench(req):
    from halo_harness.local_pool import bench, launch
    quick = (req.body if isinstance(req.body, dict) else {}).get("quick") is True
    why = bench._why_not(launch.run(req.state_dir), req.state_dir)
    if why:
        return 409, {"error": why}
    with _LOCK:
        if _BENCH.get("busy"):
            return 409, {"error": "a bench of the pool is already running"}
        _BENCH.clear()
        _BENCH.update(busy=True, lines=[], ok=None, say="")
    state = req.state_dir

    def work() -> None:
        def said(line: str) -> None:
            with _LOCK:
                _BENCH.setdefault("lines", []).append(line)
        try:
            got = bench.bench(quick=quick, state_dir=state, on_line=said)
        except Exception as e:  # the page says it; the server keeps going
            got = {"ok": False, "say": f"the bench did not finish: {type(e).__name__}: {str(e)[:200]}"}
        with _LOCK:
            _BENCH.update(busy=False, ok=bool(got.get("ok")), say=got.get("say") or "")
    threading.Thread(target=work, name="halo-pool-bench", daemon=True).start()
    return 202, {"ok": True, "busy": True, "cli": "halo local bench --host pool" + (" --quick" if quick else "")}


def get_findings(req):
    from halo_harness.ollama_steward.rules import findings
    try:
        rows = [f for f in findings(req.state_dir) if str(f.get("host") or "").lower() == "pool"]
    except Exception as e:  # one bad read never takes the page down
        return 200, {"findings": [], "error": f"the rules did not run: {type(e).__name__}", "cli": "halo ollama steward findings"}
    keep = ("id", "rule", "severity", "finding", "key", "model")
    return 200, {"findings": [{k: f.get(k) for k in keep} for f in rows], "cli": "halo ollama steward findings"}


ROUTES = {("GET", "local/pool/bench"): get_bench, ("POST", "local/pool/bench"): post_bench,
          ("GET", "local/pool/findings"): get_findings}
