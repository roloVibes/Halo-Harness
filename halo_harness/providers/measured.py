"""halo_harness.providers.measured -- Halo 3.3.6.0 R4: the measured card
(plans/local-model-fit-brief.md D4 item 17): what this model did on this host,
every number with its source, its date and how many calls it stands on.

    measured_for(host, model, *, state_dir, n=20) -> {tok_s, ttft_ms, load_s, cache_reused_pct, kv_per_token,
        window, modality, spec_decode, tool_call_accuracy, quirks: [...], n_calls, at}
        each field {value, source, at, n} (value None: nothing measured it yet); `window`'s value is
        {verified, assumed}; `quirks` is a list of {value, source, at, n}
    lines(m) -> ["187 tok/s (the ledger, 2026-10-30, 12 calls)", ...]   the card's Measured block
    speed_chip(m) -> "187 tok/s" | ""                                    the Models rows' chip

Sources, in order: the ledger's answered calls (status 200, never a `warming` one: the first call after a
load is never counted -- Part G4), medians over the newest `n`; the server log's `timing` (print_timing),
`load-result` and `spec-decode` events and its "forcing full prompt re-processing" line; the fit evidence
(providers/fit_evidence.py: the window a load was verified at) and a fitted twin's verify; the battery's
profile (the multi-tool probe's accuracy, KV per token, the quirks it saw, its warm speed when the ledger
has none). Cached under the capability cache's record, cache[digest]["measured"][host], and read again from
the ledger on every read (CACHE_S keeps one read per host per few seconds). No request is sent.
"""

from __future__ import annotations

import statistics
import time
from typing import Optional

CACHE_S = 10.0
SINCE_S = 30 * 86400.0
MIN_EVAL = 8  # a reply under 8 tokens says little about the rate
_ROWS: dict = {}
LEDGER, LOG, PROBE, FIT = "the ledger", "the server log", "the battery", "the fit evidence"


def _day(at) -> Optional[str]:
    from halo_harness.ollama_steward.ledger import parse_at
    t = parse_at(at) if isinstance(at, str) else at if isinstance(at, (int, float)) else None
    return time.strftime("%Y-%m-%d", time.localtime(t)) if t else None


def fact(value, source: Optional[str] = None, at=None, n: Optional[int] = None) -> dict:
    return {"value": value, "source": source if value is not None else None, "at": _day(at) if value is not None else None,
            "n": n if value is not None else None}


def _rows(state_dir, host: str) -> "tuple[list, list]":
    key, now = (str(state_dir), host), time.monotonic()
    hit = _ROWS.get(key)
    if hit and now - hit[0] < CACHE_S:
        return hit[1], hit[2]
    from halo_harness.ollama_steward.ledger import read_calls
    from halo_harness.ollama_steward.server_events import read_events
    calls = [x for x in read_calls(state_dir, since=SINCE_S, host=host) if x.get("kind") != "calibrate"]
    evs = [e for e in read_events(state_dir, since=SINCE_S, host=host)
           if e.get("kind") in ("timing", "load-result", "spec-decode", "no-prompt-cache")]
    _ROWS[key] = (now, calls, evs)
    return calls, evs


def _mine(rows: list, model: str) -> list:
    from halo_harness.providers.ollama import ollama_names_match
    return [r for r in rows if r.get("model") and ollama_names_match(r["model"], model)]


def _median(xs: list, nd: int = 1):
    xs = [x for x in xs if isinstance(x, (int, float)) and not isinstance(x, bool)]
    return (round(statistics.median(xs), nd) if nd else int(round(statistics.median(xs)))) if xs else None


def _speed(answered: list, timing: list, p: Optional[dict]) -> "tuple[dict, dict]":
    rated = [x for x in answered if isinstance(x.get("eval_tok_s"), (int, float)) and (x.get("eval_count") or 0) >= MIN_EVAL]
    if rated:
        tok = fact(_median([x["eval_tok_s"] for x in rated]), LEDGER, rated[-1].get("at"), len(rated))
    elif timing:
        tok = fact(_median([(e.get("data") or {}).get("eval_tok_s") for e in timing]), LOG, timing[-1].get("at"), len(timing))
    else:
        sp = (p or {}).get("speed") or {}
        tok = fact(sp.get("tok_s"), PROBE, (p or {}).get("probed_at"), 1)
    firsts = [x for x in answered if isinstance(x.get("prompt_eval_ms"), (int, float))]
    if firsts:
        ttft = fact(_median([x["prompt_eval_ms"] + (x.get("load_ms") or 0) for x in firsts], 0), LEDGER,
                    firsts[-1].get("at"), len(firsts))
    elif timing and any((e.get("data") or {}).get("prompt_ms") is not None for e in timing):
        rows = [e for e in timing if (e.get("data") or {}).get("prompt_ms") is not None]
        ttft = fact(_median([e["data"]["prompt_ms"] for e in rows], 0), LOG, rows[-1].get("at"), len(rows))
    else:
        sp = (p or {}).get("speed") or {}
        ttft = fact(sp.get("ttft_ms"), PROBE, (p or {}).get("probed_at"), 1)
    return tok, ttft


def _load(loads: list, calls: list, p: Optional[dict]) -> dict:
    timed = [e for e in loads if isinstance((e.get("data") or {}).get("load_s"), (int, float))]
    if timed:
        return fact(_median([e["data"]["load_s"] for e in timed]), LOG, timed[-1].get("at"), len(timed))
    warm = [x for x in calls if x.get("warming") and isinstance(x.get("load_ms"), (int, float))]
    if warm:
        return fact(_median([x["load_ms"] / 1000.0 for x in warm]), LEDGER + " (the first call after a load)",
                    warm[-1].get("at"), len(warm))
    sp = (p or {}).get("speed") or {}
    return fact(sp.get("cold_load_s"), PROBE, (p or {}).get("probed_at"), 1)


def _window(state_dir, host: str, model: str, p: Optional[dict]) -> dict:
    from halo_harness.providers.fit_evidence import evidence
    ev = evidence(state_dir, host, model)
    pw = (p or {}).get("window") or {}
    verified, source, at = None, None, None
    if ev.get("state") == "verified" and isinstance(ev.get("window"), int):
        verified, source, at = ev["window"], f"{FIT} ({ev.get('source')})", ev.get("at")
    elif pw.get("verified") and isinstance(pw.get("used"), int):
        verified, source, at = pw["used"], PROBE + " (/api/ps after the run)", (p or {}).get("probed_at")
    try:
        from halo_harness.ollama_steward.profiles import lookup
        assumed = (lookup(host, model) or {}).get("num_ctx") or pw.get("used") or pw.get("trained")
    except Exception:
        assumed = pw.get("used")
    value = {"verified": verified, "assumed": assumed}
    out = fact(value if (verified or assumed) else None, source or "the steward profile / the battery's window", at,
               1 if verified else None)
    return out


def _modality(p: Optional[dict]) -> dict:
    caps = (p or {}).get("capabilities") or []
    if not caps:
        return fact(None)
    kinds = ["text"] + (["images"] if "vision" in caps else []) + (["audio"] if "audio" in caps else [])
    word = "embeddings only" if "embedding" in caps and "completion" not in caps else " + ".join(kinds)
    return fact(word, "/api/show (declared; the vision probe is not in the battery yet)", (p or {}).get("probed_at"), 1)


def _quirks(calls: list, evs: list, p: Optional[dict]) -> list:
    out = []
    if (p or {}).get("system_role") == "weak":
        out.append(fact("ignores system prompt", PROBE, p.get("probed_at"), 1))
    if (p or {}).get("reasoning") == "thinking":
        out.append(fact("answers in thinking", PROBE, p.get("probed_at"), 1))
    loops = [x for x in calls if x.get("loop")]
    if loops:
        out.append(fact("loops", LEDGER + " (the loop guard stopped it)", loops[-1].get("at"), len(loops)))
    nc = [e for e in evs if e.get("kind") == "no-prompt-cache"]
    if nc:
        out.append(fact("no prompt cache", LOG + " (forcing full prompt re-processing)", nc[-1].get("at"), len(nc)))
    return out


def measured_for(host, model: str, *, state_dir, n: int = 20) -> dict:
    """See the module docstring. `host` is an OllamaHost or a host name. Never raises."""
    name = getattr(host, "name", host)
    try:
        return _measured(str(name or ""), model, state_dir, n)
    except Exception:
        import logging
        logging.getLogger("bridge").debug("measured: %s on %s could not be read", model, name, exc_info=True)
        return {"n_calls": 0, "quirks": []}


def _measured(name: str, model: str, state_dir, n: int) -> dict:
    from halo_harness.providers.ollama_capability import profile_for
    p = profile_for(state_dir, model, name) if state_dir is not None else None
    calls, evs = _rows(state_dir, name) if state_dir is not None and name else ([], [])
    calls, evs = _mine(calls, model), _mine(evs, model)
    answered = [x for x in calls if x.get("status") == 200 and not x.get("warming")][-n:]
    timing = [e for e in evs if e.get("kind") == "timing"][-n:]
    tok, ttft = _speed(answered, timing, p)
    cache = [x["cache_reused_pct"] for x in answered if isinstance(x.get("cache_reused_pct"), int)]
    spec = [e for e in evs if e.get("kind") == "spec-decode"]
    rate = [e["data"]["accept_rate"] for e in spec if isinstance((e.get("data") or {}).get("accept_rate"), (int, float))]
    acc = (p or {}).get("tool_call_accuracy")
    out = {"tok_s": tok, "ttft_ms": ttft, "load_s": _load([e for e in evs if e.get("kind") == "load-result"], calls, p),
           "cache_reused_pct": fact(_median(cache, 0), LEDGER, answered[-1].get("at") if cache else None, len(cache)),
           "kv_per_token": fact((p or {}).get("kv_per_token"), PROBE + " (/api/show, the host's KV type)",
                                (p or {}).get("probed_at"), 1),
           "window": _window(state_dir, name, model, p), "modality": _modality(p),
           "spec_decode": fact(({"on": True, "accept_rate": _median(rate, 2)} if spec else None), LOG,
                               spec[-1].get("at") if spec else None, len(spec)),
           "tool_call_accuracy": fact(acc if isinstance(acc, (int, float)) else None,
                                      PROBE + " (the multi-tool probe)", (p or {}).get("probed_at"), 1),
           "quirks": _quirks(calls, evs, p), "n_calls": len(answered), "model": model, "host": name}
    out["at"] = time.time()
    _keep(state_dir, p, name, out)
    return out


def _keep(state_dir, p: Optional[dict], host: str, m: dict) -> None:
    """cache[digest]["measured"][host], written only when what it says changed."""
    digest = (p or {}).get("digest")
    if not digest or state_dir is None:
        return
    from halo_harness.providers import ollama_capability as C
    body = {k: v for k, v in m.items() if k != "at"}
    entry = C.load_capability_cache(state_dir).get(digest)
    if isinstance(entry, dict) and ((entry.get("measured") or {}).get(host) or {}).get("facts") == body:
        return
    from halo_harness.filelock import file_lock
    with file_lock(C._capability_cache_path(state_dir)):
        cache = C.load_capability_cache(state_dir)
        e = cache.get(digest) if isinstance(cache.get(digest), dict) else {}
        e.setdefault("measured", {})[host] = {"facts": body, "at": m["at"]}
        cache[digest] = e
        C.save_capability_cache(state_dir, cache)


WORDS = {"tok_s": "{v:g} tok/s", "ttft_ms": "first token {v:,} ms", "load_s": "load {v:g} s",
         "cache_reused_pct": "cache reused {v} %", "kv_per_token": "{kb} KB of cache per token",
         "tool_call_accuracy": "tool-call accuracy {pct}"}


def _value_text(key: str, v) -> str:
    if key == "window":
        bits = [f"verified {v['verified']:,}" if v.get("verified") else "not verified",
                f"assumed {v['assumed']:,}" if v.get("assumed") else ""]
        return "window " + " · ".join(b for b in bits if b)
    if key == "spec_decode":
        return "speculative decoding on" + (f", {v['accept_rate']:.0%} accepted" if v.get("accept_rate") else "")
    if key == "modality":
        return f"sees: {v}"
    return WORDS[key].format(v=v, kb=(v // 1024 if isinstance(v, int) else v), pct=f"{v:.0%}" if isinstance(v, float) else v)


def lines(m: dict) -> list:
    """One line per measured fact: "<value> (<source>, <date>, <n> calls)"; the unmeasured ones left out."""
    out = []
    for key in ("tok_s", "ttft_ms", "load_s", "cache_reused_pct", "window", "kv_per_token", "modality", "spec_decode",
                "tool_call_accuracy"):
        f = (m or {}).get(key) or {}
        if f.get("value") is None:
            continue
        tail = ", ".join(b for b in (f.get("source"), f.get("at"), (f"{f['n']} call{'s' if f['n'] != 1 else ''}"
                                                                    if f.get("n") and f.get("source", "").startswith(LEDGER)
                                                                    else f"n={f['n']}" if f.get("n") else "")) if b)
        out.append(f"{_value_text(key, f['value'])} ({tail})")
    for q in (m or {}).get("quirks") or []:
        out.append(f"quirk: {q['value']} ({', '.join(b for b in (q.get('source'), q.get('at')) if b)})")
    return out


def speed_chip(m: Optional[dict]) -> str:
    f = (m or {}).get("tok_s") or {}
    return f"{f['value']:g} tok/s" if isinstance(f.get("value"), (int, float)) else ""
