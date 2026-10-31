"""halo_harness.providers.local_bench -- Halo 3.3.6.0 R5: the bench, a short measured battery per model on its host
(plans/local-model-fit-brief.md D4 17, G4, E1's speed probe): the model's **speed card**.

    bench(host, model, *, quick=False, send=None, card=None, state_dir=None, on_line=None, sessions=None,
          client=None, now=time.time) -> SpeedCard | {ok: False, say}
    SpeedCard = {ok, model, host, digest, ollama_version, at, cold_load_s, windows: [{window, prompt_tok_s, tok_s, ttft_ms,
                 size_vram, size, layers, on_gpu, prompt_tokens, cut}], max_gpu_window, planner_window, reserve_floor,
                 reserve_probes, quick, kv: {type, verified_window}, took_s}

The order: the model unloaded if it was loaded (so the first load is cold, `cold_load_s` from its `load_duration`); per
window {8192, 32768, the planner's ceiling for this model on this card} (`quick`: the ceiling alone) one untimed
warm-up call that loads it at that window ("warming": the first call after a load is graph capture, never timed --
Part G4), then one timed call: a fixed prompt of about 60 % of the window and a 256-token reply; `/api/ps` says whether
it stayed on the GPU (`size_vram >= size`), the server log's newest load its layers. Then the reply reserve: at the
largest window that stayed on the GPU, the same short ask at num_predict 128 / 256 / 512 -- the first not cut is
`reserve_floor`. Every call goes through the gym's send path (gym_send.send_turn, the session's request builder and
stream decoder) with the window, the reply room and keep_alive set exactly. The card lands in the fit store
(providers/local_bench_runs.save). It waits (one line, nothing sent) while the host had a call in the last minute or a
session uses it, and runs against the test fake only under the test flag (capability_battery.test_guard).
"""

from __future__ import annotations

import time
from types import SimpleNamespace
from typing import Callable, Optional

WINDOWS = (8192, 32768)
MAX_WINDOW = 131072
RESERVES = (128, 256, 512)
REPLY = 256
SHARE = 0.6
CHARS_PER_TOKEN = 4.0
KEEP = "10m"
COST = "local: ~{n} min on {host}, the card is busy meanwhile, writes the speed card; no tokens leave this machine"
FILLER = ("The bench reads this passage to measure how fast the card works through a long prompt. Item {i}: a {w} "
          "record notes the window, the reply, the load and where the layers sit; nothing here is a task. ")
WORDS = ("plain", "short", "dated", "local", "steady", "measured", "small", "large")
ASK = "Summarize the passage above in about 150 words of plain prose."
SHORT = "In about 150 words, describe what a GPU does when a model is loaded. Plain prose."


def _k(n: int) -> str:
    return f"{n // 1024}k" if n >= 1024 else str(n)


def prompt_for(window: int) -> list:
    target = int(window * SHARE * CHARS_PER_TOKEN)
    parts, i, size = [f"Bench run at a {window:,}-token window."], 0, 0
    while size < target:
        s = FILLER.format(i=i, w=WORDS[i % len(WORDS)])
        parts.append(s)
        size += len(s)
        i += 1
    return [{"role": "user", "content": [{"type": "text", "text": "".join(parts) + "\n\n" + ASK}]}]


def _msg(text: str) -> list:
    return [{"role": "user", "content": [{"type": "text", "text": text}]}]


def plan_windows(card, row: dict, info: dict, *, quick: bool, profile_ctx=None) -> "tuple[list, int, str]":
    """(the windows to try, the ceiling, where the ceiling came from)."""
    trained = next((v for k, v in (info or {}).items() if k.endswith(".context_length") and isinstance(v, int)), None)
    ceiling, src = None, ""
    if card:
        from halo_harness.ollama_steward.fit import model_window_on_card
        ceiling = model_window_on_card(card, {**(row or {}), "model_info": info}, step=4096)
        src = "the planner (the card's fit)"
    if not ceiling:
        ceiling = profile_ctx or 32768
        src = "the steward profile" if profile_ctx else "no hardware card read: 32k"
    ceiling = min(int(ceiling), trained or MAX_WINDOW, MAX_WINDOW)
    ws = [ceiling] if quick else sorted({w for w in WINDOWS if w < ceiling} | {ceiling})
    return ws, ceiling, src


def cost_minutes(size_bytes, windows: list, speed: Optional[dict] = None) -> int:
    sp = speed or {}
    load_s = sp.get("cold_load_s") or ((size_bytes or 8e9) / 1e9) * 1.5
    tok = sp.get("tok_s") or 30.0
    secs = load_s * (len(windows) + 1) + sum(w * SHARE / 1500.0 + REPLY / tok for w in windows) + 3 * 400 / tok
    return max(1, int(-(-secs // 60)))


def cost_line(host_name: str, minutes: int) -> str:
    return COST.format(n=minutes, host=host_name)


def estimate(host, model: str, *, card=None, state_dir=None, quick: bool = False) -> "tuple[int, str]":
    """(minutes, the cost line) from the cached catalog row, the windows it would try and the battery's speed."""
    from halo_harness.ollama_steward.profiles import lookup
    from halo_harness.providers.ollama import ollama_names_match
    from halo_harness.studio import ollama_hosts_view as V
    row = next((r for r in V.catalog_of(host).get("models") or [] if isinstance(r, dict)
                and ollama_names_match(r.get("model") or r.get("name"), model)), {})
    ws, _c, _s = plan_windows(card, row, row.get("model_info") or {}, quick=quick,
                              profile_ctx=(lookup(host, model) or {}).get("num_ctx"))
    from halo_harness.providers.ollama_capability import profile_for
    p = profile_for(state_dir, model, getattr(host, "name", None)) if state_dir is not None else None
    n = cost_minutes(row.get("size"), ws, (p or {}).get("speed"))
    return n, cost_line(getattr(host, "name", "") or "this host", n)


def sender(host, model: str, state_dir) -> Callable:
    """send(messages, *, num_ctx, num_predict) -> {eval_count, eval_duration, prompt_eval_count, prompt_eval_duration,
    load_duration, done_reason, error, text, thinking} through gym_send.send_turn."""
    from halo_harness.gym_send import send_turn
    from halo_harness.providers.profiles import resolve_profile
    from halo_harness.providers.routing import Route
    route = Route(provider="ollama", upstream_model=model, dialect="ollama")
    profile = resolve_profile(route, state_dir=state_dir)

    def send(messages: list, *, num_ctx: int, num_predict: int) -> dict:
        d = SimpleNamespace(num_ctx=num_ctx, trained_context=None, fit_estimate=None, learned_cap=None, remote=False,
                            recorded_does_not_fit=False, cpu_only=False)
        r = send_turn(host=host, route=route, profile=profile, decision=d, system_text="", messages=messages,
                      tools=None, requested_max_tokens=num_predict, state_dir=state_dir,
                      overrides={"options": {"num_ctx": num_ctx, "num_predict": num_predict, "temperature": 0},
                                 "keep_alive": KEEP})
        return {**(r.timing_ns or {}), "done_reason": "length" if r.stop_reason == "max_tokens" else "stop",
                "error": r.error, "text": r.text, "thinking": r.thinking}
    return send


def _rate(n, ns) -> Optional[float]:
    return round(n / (ns / 1e9), 1) if isinstance(n, int) and isinstance(ns, (int, float)) and ns > 0 else None


def _ps(client, model: str) -> dict:
    from halo_harness.providers.capability_battery import _ps_entry
    return _ps_entry(client.call("GET", "/api/ps", timeout=10.0), model) or {}


def _layers(state_dir, host_name: str, model: str, window: int):
    """The layers on the GPU from the server log's newest load of this model at this window (None: no log read)."""
    if state_dir is None:
        return None
    try:
        from halo_harness.ollama_steward.fingerprint_facts import newest_load
        ld = newest_load(state_dir, host_name, model, time.time())
        return ld.get("layers") if ld and ld.get("window") == window else None
    except Exception:
        return None


def _fail(model: str, host_name: str, say: str, **extra) -> dict:
    return {"ok": False, "model": model, "host": host_name, "say": say, "error": say, **extra}


def bench(host, model: str, *, quick: bool = False, send: Optional[Callable] = None, card=None, state_dir=None,
          on_line: Optional[Callable[[str], None]] = None, sessions: Optional[Callable] = None, client=None,
          check_busy: bool = True, now: Callable[[], float] = time.time) -> dict:
    from halo_harness.providers import capability_battery as CB
    from halo_harness.providers.local_bench_runs import busy, save
    name, say = getattr(host, "name", "") or "this host", on_line or (lambda _s: None)
    why = CB.test_guard(host) or (busy(state_dir, name, sessions=sessions) if check_busy and state_dir is not None else "")
    if why:
        return _fail(model, name, why)
    t0, client = now(), client or CB.HostClient(host)
    version = (client.call("GET", "/api/version", timeout=10.0) or {}).get("version")
    row = CB._row(client.call("GET", "/api/tags", timeout=15.0), model)
    if row is None:
        return _fail(model, name, f"no model named {model} on {name}")
    info = (client.call("POST", "/api/show", body={"model": model}, timeout=15.0) or {}).get("model_info") or {}
    from halo_harness.ollama_steward.profiles import lookup
    windows, ceiling, src = plan_windows(card, row, info, quick=quick, profile_ctx=(lookup(host, model) or {}).get("num_ctx"))
    if _ps(client, model):
        client.call("POST", "/api/generate", body={"model": model, "keep_alive": 0}, timeout=60.0)
        say(f"{model} was loaded: unloaded first, so the first load is a cold one")
    send = send or sender(host, model, state_dir)
    out = {"ok": True, "model": model, "host": name, "digest": row.get("digest"), "ollama_version": version, "at": t0,
           "cold_load_s": None, "windows": [], "max_gpu_window": None, "planner_window": ceiling, "ceiling_from": src,
           "reserve_floor": None, "reserve_probes": [], "quick": quick, "warmups": 0}
    loaded_at = None
    for w in windows:
        warm = send(_msg("Reply with the word ready."), num_ctx=w, num_predict=8)
        out["warmups"] += 1
        if warm.get("error"):
            out["windows"].append({"window": w, "error": f"it did not load at {w:,}: {warm['error']}", "on_gpu": False})
            say(f"{_k(w)}: it did not load ({warm['error']})")
            break
        if out["cold_load_s"] is None and isinstance(warm.get("load_duration"), (int, float)):
            out["cold_load_s"] = round(warm["load_duration"] / 1e9, 1)
            say(f"cold load {out['cold_load_s']:g} s (loaded at {_k(w)})")
        say(f"{_k(w)}: warming (the first call after a load is never timed)")
        r = send(prompt_for(w), num_ctx=w, num_predict=REPLY)
        loaded_at = w
        ps = _ps(client, model)
        size, vram = ps.get("size"), ps.get("size_vram")
        got = {"window": w, "prompt_tok_s": _rate(r.get("prompt_eval_count"), r.get("prompt_eval_duration")),
               "tok_s": _rate(r.get("eval_count"), r.get("eval_duration")),
               "ttft_ms": round(((r.get("prompt_eval_duration") or 0) + (r.get("load_duration") or 0)) / 1e6)
               if isinstance(r.get("prompt_eval_duration"), (int, float)) else None,
               "size": size, "size_vram": vram, "layers": _layers(state_dir, name, model, w),
               "on_gpu": (vram >= size) if isinstance(size, int) and isinstance(vram, int) and size > 0 else None,
               "prompt_tokens": r.get("prompt_eval_count"), "cut": r.get("done_reason") == "length"}
        if r.get("error"):
            got.update(error=f"the timed call at {w:,} failed: {r['error']}", on_gpu=False)
        out["windows"].append(got)
        from halo_harness.providers.local_bench_runs import _row_line
        say(_row_line(got))
        if r.get("error"):
            break
    gpu = [x["window"] for x in out["windows"] if x.get("on_gpu") and not x.get("error")]
    out["max_gpu_window"] = max(gpu) if gpu else None
    at = out["max_gpu_window"] or (windows[0] if out["windows"] and not out["windows"][0].get("error") else None)
    if at:
        if at != loaded_at:
            send(_msg("Reply with the word ready."), num_ctx=at, num_predict=8)
            out["warmups"] += 1
        for n in RESERVES:
            r = send(_msg(SHORT), num_ctx=at, num_predict=n)
            cut = r.get("done_reason") == "length" or bool(r.get("error"))
            out["reserve_probes"].append({"num_predict": n, "cut": cut, "window": at})
            say(f"reply reserve {n}: " + ("cut" if cut else "the reply ended on its own"))
            if not cut:
                out["reserve_floor"] = n
                break
    from halo_harness.ollama_steward.fit import card_budget
    out["kv"] = {"type": card_budget(card or {})["kv"] if card else None, "verified_window": out["max_gpu_window"]}
    out["took_s"] = round(now() - t0, 1)
    if state_dir is not None:
        save(state_dir, {k: v for k, v in out.items() if k != "ok"})
    return out
