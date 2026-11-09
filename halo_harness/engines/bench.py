"""halo_harness.engines.bench -- `halo local bench --host <engine id | server name> [--quick] [--yes] [--json]`: the
3.3.6.0 battery's windows and reply reserve through the engine's OpenAI-compatible route, the cost line first, the
card saved as one of runtime <id> (digest `<id>|<model>`), the figure the fit then says as "measured".

    server_named(name) -> the roster's engine server named `name` (or the first of an engine id) | None
    estimate(server, *, quick=False) -> {seconds, windows, line}
    bench(server, *, runtime, quick=False, send=None, state_dir=None, on_line=None, now=time.time) -> card | {ok: False}
    bench_cli(host, *, quick, yes, as_json, ask) -> exit code      speed_word(state_dir, host, model, runtime) -> words
Replies carry OpenAI `usage`, no per-phase timings, so each window is two calls: the prompt with a one-token reply (the
first token: prompt tok/s), then the reply (its prefill cached). An untimed warm-up goes first (a first request may
compile kernels or fill an expert cache). A local op: the seconds the cost line says, no tokens leave this machine.
"""

from __future__ import annotations

import json
import time
from types import SimpleNamespace
from typing import Callable, Optional

from halo_harness.engines.descriptors import TABLE, get

SEAMS: dict = {}
COST = "local: ~{s} s on {name} (its GPU, CPU and RAM are busy for it), writes its speed card; no tokens leave this machine"
PREFILL_ASSUMED, DECODE_ASSUMED = 300.0, 10.0


def server_named(name: str):
    from halo_harness.ollama_steward.servers_hf import roster
    rows = [s for s in roster() if s.runtime in TABLE]
    want = str(name or "").lower()
    return next((s for s in rows if s.name.lower() == want), None) or next((s for s in rows if s.runtime == want), None)


def _srv(s):
    from halo_harness.providers.huggingface import resolve_huggingface_local_servers
    e = next((x for x in resolve_huggingface_local_servers() if x.name.lower() == s.name.lower()), None)
    url = s.url if str(s.url).rstrip("/").endswith("/v1") else str(s.url).rstrip("/") + "/v1"
    return SimpleNamespace(name=s.name, url=url, model=s.model, api_key=getattr(e, "api_key", None),
                           label=get(s.runtime)["label"], runtime=s.runtime)


def _ceiling(server) -> int:
    from halo_harness.providers.huggingface_local_probe import probe_models_endpoint
    from halo_harness.providers.local_bench import MAX_WINDOW
    got = probe_models_endpoint(str(server.url), name=server.name, api_key=getattr(server, "api_key", None), timeout=3.0)
    ctx = max((got.context_by_model or {}).values(), default=None) if got else None
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

    def send(messages: list, *, max_tokens: int) -> dict:
        body = {"model": getattr(server, "model", None), "messages": _flat(messages), "max_tokens": int(max_tokens),
                "temperature": 0, "stream": False}
        t0 = time.monotonic()
        code, got = _post(url, body, key)
        took = time.monotonic() - t0
        if code != 200:
            return {"error": got.get("error") if code == 0 else f"the {getattr(server, 'label', 'engine')} server answered {code}"}
        u, ch = got.get("usage") or {}, (got.get("choices") or [{}])[0]
        return {"prompt_tokens": u.get("prompt_tokens"), "completion_tokens": u.get("completion_tokens"),
                "seconds": took, "cut": ch.get("finish_reason") == "length", "error": None}
    return send


def _rate(n, s) -> Optional[float]:
    return round(n / s, 1) if isinstance(n, int) and isinstance(s, (int, float)) and s > 0 else None


def bench(server, *, runtime: str, quick: bool = False, send: Optional[Callable] = None, state_dir=None,
          on_line: Optional[Callable[[str], None]] = None, now: Callable[[], float] = time.time) -> dict:
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
    took = f", {warm['seconds']:.0f} s" if isinstance(warm.get("seconds"), (int, float)) else ""
    say(f"warming (untimed: a first request may compile kernels or fill a cache{took})")
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


def bench_cli(host: str, *, quick: bool = False, yes: bool = False, as_json: bool = False,
              ask: Callable[[str, bool], bool]) -> int:
    from halo_harness.config.paths import bridge_home
    s = server_named(host)
    if s is None:
        print(f"no {get(host)['label'] if get(host) else host} server here: halo local serve --runtime {host} --model "
              "<model> starts one, or the auto-detect names one you started")
        return 1
    srv = _srv(s)
    print(estimate(srv, quick=quick)["line"])
    if not ask("Run the bench now?", yes):
        return 1
    print(f"{srv.model} on {srv.name}:")
    got = bench(srv, runtime=s.runtime, quick=quick, state_dir=bridge_home(),
                on_line=(lambda _s: None) if as_json else (lambda line: print(f"  {line}")))
    from halo_harness.engines.models import match
    row = match(s.runtime, srv.model) if got.get("ok") else None
    if row is not None and row["id"] != srv.model:  # the card under the model's own id too: the fit reads it by that
        from halo_harness.providers.local_bench_runs import save
        save(bridge_home(), {**{k: v for k, v in got.items() if k != "ok"}, "model": row["id"],
                             "digest": f"{s.runtime}|{row['id']}"})
    if as_json:
        print(json.dumps(got, indent=2, default=str))
    elif got.get("ok"):
        from halo_harness.providers.local_bench_runs import _row_line
        print(f"  speed card: {len(got['windows'])} windows, reply reserve "
              + (f"at least {got['reserve_floor']:,}" if got.get("reserve_floor") else "not found") + f", {got['took_s']:g} s")
        for r in got["windows"]:
            print("    " + _row_line(r))
    else:
        print(f"  {got.get('say')}")
    return 0 if got.get("ok") else 1


def speed_word(state_dir, host: str, model, runtime: str) -> Optional[str]:
    """The newest speed card's reply tok/s for `model` of this runtime (on the server named `host`, else any)."""
    if not model:
        return None
    try:
        from halo_harness.config.paths import bridge_home
        from halo_harness.providers.local_bench_runs import all_cards
        cards = [c for c in all_cards(state_dir if state_dir is not None else bridge_home())
                 if c.get("runtime") == runtime and str(c.get("model") or "").lower() == str(model).lower()]
    except Exception:
        return None
    pick = next((c for c in cards if str(c.get("host")).lower() == str(host).lower()), None) or (cards[0] if cards else None)
    rows = [r for r in (pick or {}).get("windows") or [] if isinstance(r.get("tok_s"), (int, float))]
    return f"{rows[-1]['tok_s']:g} tok/s measured" if rows else None
