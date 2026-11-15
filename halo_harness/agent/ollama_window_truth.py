"""halo_harness.agent.ollama_window_truth -- Halo 3.6.0.0 R8: a model on another machine answers as fast as that
machine can. The owner's rule for all local-model upkeep: check on use, measure on change only when asked, show on
view, diagnose on failure; no background watcher.

    prompt_estimate(state_dir, host_url, model, system, messages, tools) -> (raw, tokens)
        the prompt's tokens by chars / 3.5 (`raw`) and with this model's measured ratio applied (`tokens`)
    start_window(session, *, host, ref, decision, cap, cap_source, request, requested) -> (window, source, hold)
        the window a call starts from (B): a loaded window that holds the request (`hold`), else the request's
        need on the ladder (8,192 / 16,384 / 32,768 / ...) up to `cap`; a steward profile's window wins
    resident_options(session, host, model, body, source) -> body   `num_gpu` the way the resident runner has it
    after_call(session, req, meta)    one `/api/ps` read after an answer: the window truth, the ratio, the "loaded" line
    loading_line(session, body) -> str | None    "loading <model> on <host> (16.6 GB)" when this call loads it (F)
    drain_loaded(session) -> [line]   "<model> loaded on <host> in 12.3 s", once the call answered
    compaction_window(session) -> int | None     the most the window can be (auto-compaction's 80 % is of this)

Kept in `<state>/ollama-fit.json` beside the calibration entries (providers/ollama_calibrate.py):
`window_truth["<url>|<model>"] = {fits, spills, num_ctx, num_gpu, digest, at}` -- the largest window seen wholly on
the card (`size_vram == size` after a call), the smallest seen partly on the CPU, and the options the last call sent
(a resident runner keeps them; asking for others reloads it) -- and `token_ratio["<url>|<model>"] = {ratio, n, at}`,
Ollama's `prompt_eval_count` over chars / 3.5 for this model (applied when it is off by more than 15 %).

The seam for the steward's redesign (3.6.0.0 R7a job 0, not landed in this round): `after_call` is the one check on
use, called from `agent/loop.Session._stream` after an Ollama answer; it runs in the call's own thread, never in the
background, and never loads anything. A measurement (the ladder of loads) is `halo local measure` / Studio's Local
Measure only (providers/ollama_measure.py).
"""

from __future__ import annotations

import logging
import math
import time
from typing import Optional

log = logging.getLogger("bridge")

LADDER_START = 8192
RATIO_DEADBAND = 0.15
RATIO_MIN, RATIO_MAX = 0.5, 3.0
RATIO_MIN_COUNT = 256
_GB = 1024 ** 3


def _pos(v) -> Optional[int]:
    return v if isinstance(v, int) and not isinstance(v, bool) and v > 0 else None


def _key(host_url: str, model: str) -> str:
    from halo_harness.providers.ollama import normalize_ollama_model_name
    return f"{str(host_url).rstrip('/')}|{normalize_ollama_model_name(model)}"


def _store(state_dir) -> dict:
    from halo_harness.providers.ollama_calibrate import load_fit_store
    return load_fit_store(state_dir) if state_dir is not None else {}


def _section(state_dir, name: str, key: str) -> dict:
    sec = _store(state_dir).get(name)
    got = sec.get(key) if isinstance(sec, dict) else None
    return got if isinstance(got, dict) else {}


def _update(state_dir, name: str, key: str, fn) -> None:
    if state_dir is None:
        return
    from halo_harness.filelock import file_lock
    from halo_harness.providers.ollama_calibrate import _fit_store_path, load_fit_store, save_fit_store
    try:
        with file_lock(_fit_store_path(state_dir)):
            store = load_fit_store(state_dir)
            sec = store.get(name) if isinstance(store.get(name), dict) else {}
            old = sec.get(key) if isinstance(sec.get(key), dict) else {}
            sec[key] = fn(dict(old))
            store[name] = sec
            save_fit_store(state_dir, store)
    except Exception:
        log.debug("ollama: recording %s for %s failed", name, key, exc_info=True)


# ---- C: the estimate starts from the measured ratio --------------------------------------------------------------

def token_ratio(state_dir, host_url: str, model: str) -> float:
    """This model's measured `prompt_eval_count` / (chars / 3.5); 1.0 until measured or within 15 % of 1."""
    got = _section(state_dir, "token_ratio", _key(host_url, model))
    ratio = got.get("ratio")
    if not isinstance(ratio, (int, float)) or isinstance(ratio, bool) or not RATIO_MIN <= ratio <= RATIO_MAX:
        return 1.0
    return float(ratio) if abs(float(ratio) - 1.0) > RATIO_DEADBAND else 1.0


def record_ratio(state_dir, host_url: str, model: str, *, raw_prompt, prompt_eval_count) -> Optional[float]:
    """Folds one answer's real count against the raw chars / 3.5 of what was sent into the running ratio. A count
    under 256 tokens, or a ratio outside 0.5-3 (a cache-shortened count, a trimmed prompt), is not a measurement."""
    if not (_pos(raw_prompt) and _pos(prompt_eval_count)) or prompt_eval_count < RATIO_MIN_COUNT:
        return None
    ratio = prompt_eval_count / raw_prompt
    if not RATIO_MIN <= ratio <= RATIO_MAX:
        return None

    def _fold(old: dict) -> dict:
        n = min(int(old.get("n") or 0) + 1, 5)
        prev = old.get("ratio") if isinstance(old.get("ratio"), (int, float)) else ratio
        return {"ratio": round(prev + (ratio - prev) / n, 4), "n": n, "at": time.time()}
    _update(state_dir, "token_ratio", _key(host_url, model), _fold)
    return ratio


def prompt_estimate(state_dir, host_url: str, model: str, system_text, messages, tools) -> "tuple[int, int]":
    """(raw, tokens): the request's prompt as it goes on the wire, by chars / 3.5, and with the measured ratio."""
    from halo_harness.providers.ollama_prompt import REPLY_RESERVE_TOKENS
    from halo_harness.providers.ollama_wire_estimate import wire_estimate
    raw = max(1, wire_estimate(system_text, messages, tools) - REPLY_RESERVE_TOKENS)
    return raw, max(1, int(math.ceil(raw * token_ratio(state_dir, host_url, model))))


# ---- A: the window truth, learned from the call itself -----------------------------------------------------------

def truth(state_dir, host_url: str, model: str) -> dict:
    return _section(state_dir, "window_truth", _key(host_url, model))


def record_truth(state_dir, host_url: str, model: str, *, num_ctx: int, size, size_vram, num_gpu=None,
                 digest=None) -> Optional[str]:
    """One read after a call: `fits` (wholly on the card at `num_ctx`) or `spills` (part on the CPU). A new digest
    starts over. Returns "fits" / "spills" / None."""
    if not (_pos(num_ctx) and _pos(size) and isinstance(size_vram, int)):
        return None
    kind = "fits" if size_vram >= size else "spills"

    def _fold(old: dict) -> dict:
        if digest and old.get("digest") and old.get("digest") != digest:
            old = {}
        out = {**old, "num_ctx": num_ctx, "num_gpu": num_gpu, "digest": digest or old.get("digest"), "at": time.time()}
        if kind == "fits":
            out["fits"] = max(num_ctx, _pos(old.get("fits")) or 0)
            if _pos(old.get("spills")) and old["spills"] <= num_ctx:
                out["spills"] = None  # the card has more room now than when it spilled
        else:
            out["spills"] = min(num_ctx, _pos(old.get("spills")) or num_ctx)
            if _pos(old.get("fits")) and old["fits"] >= num_ctx:
                out["fits"] = None
        return out
    _update(state_dir, "window_truth", _key(host_url, model), _fold)
    return kind


def known_spill(state_dir, host_url: str, model: str) -> Optional[int]:
    """The smallest window a call saw partly on the CPU (a window known not to fit), or None."""
    return _pos(truth(state_dir, host_url, model).get("spills"))


# ---- B: the window a call asks for -------------------------------------------------------------------------------

def _state(session) -> dict:
    from halo_harness.agent.ollama_window import _state as window_state
    return window_state(session)


def _ladder(cap: int) -> list:
    steps, w = [], LADDER_START
    while w < cap:
        steps.append(w)
        w *= 2
    return steps + [cap]


def _below(spill: int) -> int:
    """The largest ladder step under a window known to spill (half of it under the ladder's start)."""
    w = LADDER_START
    if spill <= w:
        return max(2048, spill // 2)
    while w * 2 < spill:
        w *= 2
    return w


def start_window(session, *, host, ref, decision, cap: int, cap_source: str, request,
                 requested=None) -> "tuple[int, str, bool]":
    """`(window, source, hold)`: (1) a steward profile's window (the user's) as it is; (2) the window the model is
    loaded at on that server when it holds this request (`hold`: the reply's room fits inside it, nobody's model is
    reloaded); (3) the request's need -- the prompt (the measured ratio applied) plus the reply's room, the first
    call of a session with room to grow (Halo's own prompt at most half) -- on the ladder, never above `cap` (the
    old `min()`: trained context, `max_ctx`, a measured cap, the memory estimate) nor above a window known to
    spill. A prompt larger than all of that is the prompt floor's to raise (agent/ollama_window.prepare_window)."""
    st = _state(session)
    key = (host.url, ref.model)
    if cap_source == "steward profile":
        st.setdefault("cap", {})[key] = cap
        return cap, cap_source, False
    state_dir = getattr(session, "state_dir", None)
    spill = known_spill(state_dir, host.url, ref.model)
    if spill and cap >= spill:
        cap, cap_source = _below(spill), "known to spill"
    st.setdefault("cap", {})[key] = cap
    _raw, prompt = prompt_estimate(state_dir, host.url, ref.model, *request)
    from halo_harness.providers.ollama_hw import last_ps_entry
    from halo_harness.providers.ollama_prompt import REPLY_RESERVE_TOKENS
    known, row = last_ps_entry(host.url, ref.model)
    loaded = _pos((row or {}).get("context_length")) if known else None
    if loaded and prompt + REPLY_RESERVE_TOKENS <= loaded:
        return loaded, "loaded", True
    own = ref is getattr(session, "model_ref", None)
    first = own and not getattr(session, "_reply_room_called", False)
    profile = getattr(decision, "profile", None) or {}

    def _room(w: int) -> int:
        if not own:
            from halo_harness.providers.ollama_prompt import reply_reserve
            return reply_reserve(requested)
        from halo_harness.agent.reply_room import _explicit, room
        return room(w, requested, profile_num_predict=profile.get("num_predict"), explicit=_explicit(session))[0]

    for w in _ladder(_pos(cap) or LADDER_START):
        need = prompt + _room(w)
        if first:
            need = max(need, 2 * prompt)
        if need <= w:
            return w, ("request size" if w < cap else cap_source), False
    return cap, cap_source, False


def resident_options(session, host, model: str, body: dict, source: str) -> dict:
    """A call that uses the loaded window sends `num_gpu` the way the runner was loaded: the last call's own when
    Halo loaded it at that window, else none (another client's load); any other `num_gpu` reloads it."""
    if source != "loaded":
        return body
    opts = dict(body.get("options") or {})
    t = truth(getattr(session, "state_dir", None), host.url, model)
    if t.get("num_ctx") == opts.get("num_ctx") and _pos(t.get("num_gpu")):
        opts["num_gpu"] = t["num_gpu"]
    else:
        opts.pop("num_gpu", None)
    return {**body, "options": opts}


def compaction_window(session) -> Optional[int]:
    """The most the session's own model's window can be on this host (auto-compaction's share is of this, not of
    the smaller window a call asked for), or None for anything that is not an Ollama call."""
    st = getattr(session, "_ollama_window_state", None) or {}
    last = st.get("last") or {}
    cap = (st.get("cap") or {}).get((last.get("host_url"), last.get("model")))
    return _pos(cap)


# ---- F: the wait says what it is ---------------------------------------------------------------------------------

def _size_words(host, model: str) -> str:
    try:
        from halo_harness.providers.ollama import get_catalog
        from halo_harness.providers.ollama_hw import catalog_row
        size = (catalog_row(get_catalog(host), model) or {}).get("size")
    except Exception:
        size = None
    return f" ({size / _GB:.1f} GB)" if _pos(size) else ""


def loading_line(session, host, body: dict) -> Optional[str]:
    """"loading <model> on <host> (16.6 GB)" when the call is going to load the model: it is not loaded there at
    the window and `num_gpu` this body asks for, by the call's own `/api/ps` read; None when it is resident (or the
    read is missing)."""
    from halo_harness.providers.ollama_hw import last_ps_entry
    model = body.get("model")
    opts = body.get("options") or {}
    known, row = last_ps_entry(host.url, model)
    if not known or not model:
        return None
    if row and row.get("context_length") == opts.get("num_ctx"):
        t = truth(getattr(session, "state_dir", None), host.url, model)
        same_gpu = opts.get("num_gpu") is None or (t.get("num_ctx") == opts.get("num_ctx")
                                                   and t.get("num_gpu") == opts.get("num_gpu"))
        if same_gpu:
            return None
    from halo_harness.providers.ollama_prompt import fmt_window
    again = f" again at a {fmt_window(opts['num_ctx'])} window" if row and _pos(opts.get("num_ctx")) else ""
    line = f"loading {model} on {host.name}{again}{_size_words(host, model)}"
    session._ollama_loading = {"model": model, "host": host.name, "t0": time.monotonic()}
    return line


def drain_loaded(session) -> list:
    out = getattr(session, "_ollama_loaded_lines", None) or []
    session._ollama_loaded_lines = []
    return out


# ---- the check after a call ---------------------------------------------------------------------------------------

def _host_for_url(session, url: str):
    from halo_harness.ollama_steward.ledger_call import _base
    from halo_harness.providers.ollama import resolve_ollama_hosts
    env = session.settings.effective_env if getattr(session, "settings", None) is not None else None
    for h in resolve_ollama_hosts(env):
        if _base(h.url) == _base(url):
            return h
    return None


def after_call(session, req, meta: Optional[dict]) -> None:
    """After an Ollama answer (status 200): one `/api/ps` read of that server -- is the model wholly on the card at
    the window this call used (`window_truth`), the offload marker and the next call's loaded window from it -- the
    count against the estimate (`token_ratio`), and, when this call loaded the model, the line that says how long
    it took. Never raises; nothing here loads or unloads a model."""
    try:
        body = getattr(req, "prebuilt_ollama_body", None) or {}
        url = str(getattr(getattr(req, "creds", None), "base_url", "") or "") or getattr(
            session, "_last_ollama_host_url", None)
        model = body.get("model")
        if not model or not url:
            return
        host = _host_for_url(session, url)
        if host is None:
            return
        opts = body.get("options") or {}
        state_dir = getattr(session, "state_dir", None)
        timing = (meta or {}).get("timing_ns") or {}
        sent = (_state(session).get("sent") or {}).get((str(host.url).rstrip("/"), model)) or {}
        if sent.get("raw_prompt"):
            record_ratio(state_dir, host.url, model, raw_prompt=sent["raw_prompt"],
                         prompt_eval_count=timing.get("prompt_eval_count"))
        from halo_harness.providers.ollama import fetch_ps, ollama_names_match
        from halo_harness.providers.ollama_hw import _record_last_known_offload
        ps = fetch_ps(host, timeout=5.0)
        if isinstance(ps, dict):
            row = next((e for e in ps.get("models") or [] if isinstance(e, dict) and (
                ollama_names_match(e.get("model"), model) or ollama_names_match(e.get("name"), model))), None)
            _record_last_known_offload(host.url, model, row)
            if row and row.get("context_length") in (None, opts.get("num_ctx")):
                kind = record_truth(state_dir, host.url, model, num_ctx=opts.get("num_ctx"), size=row.get("size"),
                                    size_vram=row.get("size_vram"), num_gpu=opts.get("num_gpu"),
                                    digest=row.get("digest"))
                if kind and getattr(session, "model_ref", None) is not None \
                        and getattr(session.model_ref, "model", None) == model:
                    session._last_ollama_offloaded = kind == "spills"
        loading = getattr(session, "_ollama_loading", None)
        if loading and loading.get("model") == model:
            session._ollama_loading = None
            load_s = (timing.get("load_duration") or 0) / 1e9
            took = load_s if load_s >= 0.5 else time.monotonic() - loading["t0"]
            lines = getattr(session, "_ollama_loaded_lines", None) or []
            session._ollama_loaded_lines = lines + [f"{model} loaded on {loading['host']} in {took:.1f} s"]
    except Exception:
        log.debug("ollama: the check after a call failed", exc_info=True)


def wrap_stream(session, req, gen):
    """`gen` (an Ollama call's wire events) passed through unchanged; `after_call` once it ended with an answer."""
    meta: dict = {}
    answered = False
    for ev in gen:
        if isinstance(ev, dict) and ev.get("type") == "message_delta":
            got = ev.get("harness_meta")
            if isinstance(got, dict):
                meta.update(got)
            answered = True
        yield ev
    if answered:
        after_call(session, req, meta)
