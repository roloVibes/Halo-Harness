"""halo_harness.freetoken.bench -- the speed card of a FreeToken server: the 3.3.6.0 battery's windows and reply
reserve against its OpenAI routes (Halo 3.3.9.1; `halo local bench --host freetoken`, docs/MODELS-freetoken.md).

    estimate(server, *, quick=False) -> {seconds, windows, line}   the cost line first: "local: ~N s on freetoken (its
        GPU, CPU and the host link are busy for it), writes its speed card; no tokens leave this machine"
    bench(server, *, quick=False, send=None, state_dir=None, on_line=None, now=time.time) -> SpeedCard | {ok: False}
    sender(server) -> send(messages, *, max_tokens) -> {prompt_tokens, completion_tokens, seconds, cut, error}
        POST <url>/chat/completions (stream off, temperature 0); SEAMS["send"] is the tests' runner
    speed_word(state_dir, host, model) -> "12.1 tok/s measured" | None

FreeToken's replies carry OpenAI `usage`, no per-phase timings, so each window is two calls: the prompt with a one-token
reply (its time is the first token: prompt tok/s), then the same prompt with a 256-token reply, whose prefill the radix
prefix cache (`--cache-type radix`, FreeToken's default: from the source, unverified against a live run) spares, so its
time is the decode. An untimed warm-up goes first: the first request after an install compiles FreeToken's CUDA
kernels for minutes (docs/install.md), which the card must not count. The window ceiling is the served model's
`context_length` from /v1/models. Card: host = the server's name, digest `freetoken|<model>`, runtime freetoken.
3.3.9.2: `runtime="strata"` runs the same card against a Strata server (strata/bench.py): digest `strata|<model>`.
"""

from __future__ import annotations

import time
from typing import Callable, Optional

SEAMS: dict = {}
WARM_TIMEOUT_S = 1800.0
COST = ("local: ~{s} s on {name} (its GPU, CPU and the host link are busy for it), writes its speed card; no tokens "
        "leave this machine")
PREFILL_ASSUMED, DECODE_ASSUMED = 300.0, 10.0
FIRST_WORDS = "a first request after an install compiles FreeToken's kernels"


def _ceiling(server) -> int:
    from halo_harness.providers.huggingface_local_probe import probe_models_endpoint
    got = probe_models_endpoint(str(server.url), name=server.name, api_key=getattr(server, "api_key", None), timeout=3.0)
    ctx = max((got.context_by_model or {}).values(), default=None) if got else None
    from halo_harness.providers.local_bench import MAX_WINDOW
    return min(int(ctx), MAX_WINDOW) if isinstance(ctx, int) else 32768


def estimate(server, *, quick: bool = False, ctx: Optional[int] = None) -> dict:
    from halo_harness.local_pool.bench import windows_for
    from halo_harness.providers.local_bench import REPLY, RESERVES, SHARE
    ws = windows_for(ctx or 32768, quick)
    secs = sum(w * SHARE / PREFILL_ASSUMED + REPLY / DECODE_ASSUMED for w in ws) + sum(RESERVES) / DECODE_ASSUMED
    s = max(1, int(round(secs)))
    return {"seconds": s, "windows": ws, "line": COST.format(s=s, name=server.name)}


def sender(server) -> Callable:
    from halo_harness.local_pool.bench import _flat, _post
    url, key = str(server.url).rstrip("/") + "/chat/completions", getattr(server, "api_key", None)
    model = getattr(server, "model", None)

    def send(messages: list, *, max_tokens: int) -> dict:
        body = {"model": model, "messages": _flat(messages), "max_tokens": int(max_tokens), "temperature": 0,
                "stream": False}
        t0 = time.monotonic()
        code, got = _post(url, body, key)
        took = time.monotonic() - t0
        if code != 200:
            return {"error": got.get("error") if code == 0 else f"the {getattr(server, 'label', 'FreeToken')} server answered {code}"}
        u, ch = got.get("usage") or {}, (got.get("choices") or [{}])[0]
        return {"prompt_tokens": u.get("prompt_tokens"), "completion_tokens": u.get("completion_tokens"),
                "seconds": took, "cut": ch.get("finish_reason") == "length", "error": None}
    return send


def _rate(n, s) -> Optional[float]:
    return round(n / s, 1) if isinstance(n, int) and isinstance(s, (int, float)) and s > 0 else None


def bench(server, *, quick: bool = False, send: Optional[Callable] = None, state_dir=None,
          on_line: Optional[Callable[[str], None]] = None, now: Callable[[], float] = time.time,
          runtime: str = "freetoken", warm_words: str = FIRST_WORDS) -> dict:
    from halo_harness.local_pool.bench import windows_for
    from halo_harness.providers.local_bench import REPLY, RESERVES, SHORT, _msg, prompt_for
    from halo_harness.providers.local_bench_runs import _row_line, save
    say = on_line or (lambda _s: None)
    send = send or SEAMS.get("send") or sender(server)
    model = getattr(server, "model", None) or "the model"
    t0, ctx = now(), _ceiling(server)
    out = {"ok": True, "model": model, "host": server.name, "digest": f"{runtime}|{model}", "runtime": runtime,
           "ollama_version": None, "at": t0, "cold_load_s": None, "cold_load_from": "", "windows": [],
           "max_gpu_window": None, "planner_window": ctx, "ceiling_from": "the served model's context_length (/v1/models)",
           "reserve_floor": None, "reserve_probes": [], "quick": quick, "warmups": 0,
           "measured_from": "two calls per window: a one-token reply (the prompt), then the reply (the prefix cached)"}
    warm = send(_msg("Reply with the word ready."), max_tokens=8)
    out["warmups"] += 1
    say(f"warming (untimed: {warm_words}"
        f"{', ' + format(warm['seconds'], '.0f') + ' s' if isinstance(warm.get('seconds'), (int, float)) else ''})")
    for w in windows_for(ctx, quick):
        first = send(prompt_for(w), max_tokens=1) if not warm.get("error") else warm
        got = send(prompt_for(w), max_tokens=REPLY) if not first.get("error") else first
        row = {"window": w, "prompt_tok_s": _rate(first.get("prompt_tokens"), first.get("seconds")),
               "tok_s": _rate(got.get("completion_tokens"), got.get("seconds")),
               "ttft_ms": round(first["seconds"] * 1000) if isinstance(first.get("seconds"), (int, float)) else None,
               "size": None, "size_vram": None, "layers": None, "on_gpu": None,
               "prompt_tokens": first.get("prompt_tokens"), "cut": bool(got.get("cut"))}
        if got.get("error"):
            row.update(error=f"the timed call at {w:,} failed: {got['error']}")
        out["windows"].append(row)
        say(_row_line(row))
        if got.get("error"):
            break
    good = [x["window"] for x in out["windows"] if not x.get("error")]
    out["max_gpu_window"] = max(good) if good else None
    for n in RESERVES if good else ():
        got = send(_msg(SHORT), max_tokens=n)
        cut = bool(got.get("cut")) or bool(got.get("error"))
        out["reserve_probes"].append({"num_predict": n, "cut": cut, "window": max(good)})
        say(f"reply reserve {n}: " + ("cut" if cut else "the reply ended on its own"))
        if not cut:
            out["reserve_floor"] = n
            break
    out["kv"] = {"type": None, "verified_window": out["max_gpu_window"]}
    out["took_s"] = round(now() - t0, 1)
    if good:
        from halo_harness.config.paths import bridge_home
        save(state_dir if state_dir is not None else bridge_home(), {k: v for k, v in out.items() if k != "ok"})
    else:
        out.update(ok=False, say=(out["windows"] or [{}])[0].get("error") or warm.get("error") or "no window answered")
    return out


def speed_word(state_dir, host: str, model, runtime: str = "freetoken") -> Optional[str]:
    """The newest FreeToken speed card's reply tok/s for `model` (on the server named `host`, else any FreeToken one)."""
    if state_dir is None or not model:
        return None
    try:
        from halo_harness.providers.local_bench_runs import all_cards
        cards = [c for c in all_cards(state_dir) if c.get("runtime") == runtime
                 and str(c.get("model") or "").lower() == str(model).lower()]
    except Exception:
        return None
    pick = next((c for c in cards if str(c.get("host")).lower() == str(host).lower()), None) or (cards[0] if cards else None)
    rows = [r for r in (pick or {}).get("windows") or [] if isinstance(r.get("tok_s"), (int, float))]
    return f"{rows[-1]['tok_s']:g} tok/s measured" if rows else None
