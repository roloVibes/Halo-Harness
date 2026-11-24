"""halo_harness.agent.ollama_window_truth -- Halo 3.6.0.0 R8: a model on another machine answers as fast as that
machine can. The owner's rule for all local-model upkeep: check on use, measure on change only when asked, show on
view, diagnose on failure; no background watcher.

    prompt_estimate(state_dir, host_url, model, system, messages, tools) -> (raw, tokens)
        the prompt's tokens by chars / 3.5 (`raw`) and with this model's measured ratio applied (`tokens`)
    start_window(session, *, host, ref, decision, cap, cap_source, request, requested, reshape) -> (window, source, hold)
        the window a call starts from (B): a loaded window that holds the request (`hold`), else the request's
        need on the ladder (8,192 / 16,384 / 32,768 / ...) up to `cap`; a steward profile's window wins
    resident_options(session, host, model, body, source) -> body   `num_gpu` the way the resident runner has it
    after_call(session, req, meta)    after an answer, no request: the ratio, the "loaded" line, the read kept for...
    turn_end_check(session)           ...the one `/api/ps` read at the end of a turn (1 s at most): the window truth
    many_turns(session) -> bool       a session that takes more turns (loads once, at the largest window)
    loading_line(session, body) -> str | None    "loading <model> on <host> (16.6 GB)" when this call loads it (F)
    drain_loaded(session) -> [line]   "<model> loaded on <host> in 12.3 s", once the call answered
    compaction_window(session) -> int | None     the most the window can be (auto-compaction's 80 % is of this)

Kept in `<state>/ollama-fit.json` beside the calibration entries (providers/ollama_calibrate.py):
`window_truth["<url>|<model>"] = {fits, spills, num_ctx, num_gpu, digest, at}` -- the largest window seen wholly on
the card (`size_vram == size` after a call), the smallest seen partly on the CPU, and the options the last call sent
(a resident runner keeps them; asking for others reloads it) -- and `token_ratio["<url>|<model>"] = {ratio, n, at}`,
Ollama's `prompt_eval_count` over chars / 3.5 for this model (applied when it is off by more than 15 %).

The seam for the steward's redesign (3.6.0.0 R7a job 0, not landed in this round): `after_call` (called from
`agent/loop.Session._stream` after an Ollama answer) and `turn_end_check` (from `Session.turn` when the turn ends) are
the one check on use; they run in the turn's own thread (the read waited on for a second at most), never as a
background watcher, and never load anything. A measurement (the ladder of loads) is `halo local measure` / Studio's Local
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


def record_ratio(state_dir, host_url: str, model: str, *, raw_prompt, prompt_eval_count,
                 fresh: bool = False) -> Optional[float]:
    """Folds one answer's real count against the raw chars / 3.5 of what was sent into the running ratio. A count
    under 256 tokens, or a ratio outside 0.5-3 (a trimmed prompt), is not a measurement. Fix pass (S3): nor is a
    count a reused prefix may have shortened -- only the call that loaded the model (`fresh`: nothing cached) or a
    count at or above the raw estimate (no cache could have made it larger) is folded in."""
    if not (_pos(raw_prompt) and _pos(prompt_eval_count)) or prompt_eval_count < RATIO_MIN_COUNT:
        return None
    if not fresh and prompt_eval_count < raw_prompt:
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


def many_turns(session) -> bool:
    """A session that will take more turns (the TUI, Studio typing into it, `--input-format stream-json`): fix pass
    S4. `halo -p` with one prompt is a one-shot run. `session.many_turns` when set, else `session.interactive`."""
    got = getattr(session, "many_turns", None)
    return bool(got) if got is not None else bool(getattr(session, "interactive", False))


def start_window(session, *, host, ref, decision, cap: int, cap_source: str, request,
                 requested=None, reshape=None) -> "tuple[int, str, bool]":
    """`(window, source, hold)`: (1) a steward profile's window (the user's) as it is; (2) the window the model is
    loaded at on that server when it holds this request with the ladder's own need (`hold`: the prompt with a 15 %
    margin for the estimate, plus the reply's room at that window -- fix pass M1), unless the recorded truth says
    that window spills to the CPU (S1: reloaded under the spill, one line says why; 3.6.0.12 OS: a one-shot whose
    request does not fit under the spill keeps the larger loaded window, the line says that); a failed `/api/ps` read is
    unknown (S2): the window this session or the last call used, when it holds the request, so nothing is reloaded
    on that reading; (3) a load: a session that takes more turns, or any session that has to grow past the window
    it asked for, asks for `cap` at once (S4: one load, never a step at a time); a one-shot run's first call asks
    for the request's need on the ladder (8,192 / 16,384 / ...; Halo's own prompt at most half). Never above `cap`
    (the old `min()`: trained context, `max_ctx`, a measured cap, the memory estimate) nor above a window known to
    spill. A prompt larger than all of that is the prompt floor's to raise (agent/ollama_window.prepare_window).
    3.6.0.12 OS, `reshape` (prompt_wire.one_shot_shaper, a one-shot's main call only): each window is measured with the
    request's tool block shaped for THAT window, never smaller than an earlier call of the run sent; the window the
    block is shaped for is kept on `session._shape_window` (prompt_diet.call_window reads it)."""
    st = _state(session)
    key = (host.url, ref.model)
    own = is_main_call(session, ref)  # fix pass F4: helper calls (small model, compaction, titles, hooks) never grow
    asked = st.setdefault("asked", {})
    prev = asked.get(key) if own else None
    recent = process_asked(host.url, ref.model)  # fix pass F5: a window another call of this process just asked

    def _ask(window: int, source: str, hold: bool) -> "tuple[int, str, bool]":
        if own:
            asked[key] = window
        note_process_ask(host.url, ref.model, window)
        return window, source, hold

    if cap_source == "steward profile":
        st.setdefault("cap", {})[key] = cap
        return _ask(cap, cap_source, False)
    state_dir = getattr(session, "state_dir", None)
    from halo_harness.providers.ollama_hw import last_ps_entry, ps_gave_up
    if ps_gave_up(host.url):  # fix pass F6: the read before the call was given up on
        from halo_harness.agent.prompt_wire import _queue_line
        _queue_line(session, f"{host.name} did not answer /api/ps within 3 s: the window was chosen without "
                             "knowing what is loaded there")
    known, row = last_ps_entry(host.url, ref.model)
    loaded = _pos((row or {}).get("context_length")) if known else None
    live = _live_fit(row) if loaded else None  # fix pass F2: what the card holds right now decides
    t = truth(state_dir, host.url, ref.model)
    if live is True and _pos(t.get("spills")) and t["spills"] <= loaded:
        record_truth(state_dir, host.url, ref.model, num_ctx=loaded, size=row.get("size"),
                     size_vram=row.get("size_vram"), digest=row.get("digest"),
                     num_gpu=t.get("num_gpu") if t.get("num_ctx") == loaded else None)
        t = truth(state_dir, host.url, ref.model)
    spill = min([w for w in (_pos(t.get("spills")), loaded if live is False else None) if w] or [0]) or None
    if spill and cap >= spill:
        fits = _pos(t.get("fits"))
        cap, cap_source = max(_below(spill), fits if fits and fits < spill else 0), "known to spill"
    many = own and many_turns(session)
    kept = _pos((st.get("spill_cap") or {}).get(key)) if many else None
    if kept and cap > kept:  # 3.6.0.19 LM: a session of more turns stays at the window a spill lowered it to
        cap, cap_source = kept, "known to spill"
    st.setdefault("cap", {})[key] = cap
    _raw, prompt0 = prompt_estimate(state_dir, host.url, ref.model, *request)
    first = own and not getattr(session, "_reply_room_called", False)
    profile = getattr(decision, "profile", None) or {}
    one = own and not many_turns(session)  # 3.6.0.12 OS: a one-shot run (a session of more turns is untouched)
    reshape = reshape if one else None
    shaped_for = _pos(getattr(session, "_shape_window", None)) \
        if reshape and getattr(session, "_shape_model", None) == ref.raw else None  # an earlier call's block
    sized: dict = {}

    def _prompt(w) -> int:
        """3.6.0.12 OS: a one-shot's prompt with the tool block of a window of `w` (prompt_wire.one_shot_shaper),
        never a smaller block than an earlier call of it sent; else the request's own."""
        if reshape is None or not _pos(w):
            return prompt0
        at = max(w, shaped_for or 0)
        if at not in sized:
            sized[at] = prompt_estimate(state_dir, host.url, ref.model, *reshape(at))[1]
        return sized[at]

    def _room(w: int) -> int:
        if not own:
            from halo_harness.providers.ollama_prompt import reply_reserve
            return reply_reserve(requested)
        from halo_harness.agent.reply_room import _explicit, room
        return room(w, requested, profile_num_predict=profile.get("num_predict"), explicit=_explicit(session))[0]

    def _holds(w) -> bool:
        return bool(_pos(w)) and int(math.ceil(_prompt(w) * (1 + RATIO_DEADBAND))) + _room(w) <= w

    def _ok(w) -> bool:
        return _holds(w) and not (spill and w >= spill)

    def _choose() -> "tuple[int, str, bool]":
        if loaded and _holds(loaded):
            if not (spill and loaded >= spill):
                return loaded, "loaded", True
            from halo_harness.agent.prompt_wire import _queue_line
            from halo_harness.providers.ollama_prompt import fmt_window
            now = "runs partly on the CPU there now" if live is False else "ran partly on the CPU there"
            head = f"{ref.model} on {host.name} is loaded at a {fmt_window(loaded)} window that {now}: "
            if one and not _holds(cap):  # 3.6.0.12 OS: the request does not fit under the spill: the larger is sent
                _queue_line(session, head + f"kept there, the request does not fit {fmt_window(cap)}, the largest "
                                            "known to fit the card")
                return loaded, "loaded", True
            _queue_line(session, head + f"reloaded at {fmt_window(cap)}, the largest known to fit the card")
            if one and first and 2 * _prompt(cap) > cap:  # the first call's "at most half" gives way to the spill cap
                _queue_line(session, f"the prompt is more than half of it: the reply has {_room(cap):,} tokens")
                session._reply_room_said = True  # 3.6.0.19 LM: one line says the reply's room (reply_room.for_call)
            return cap, cap_source, False
        if not known:
            for w in (prev, _pos(t.get("num_ctx"))):  # unknown: the window most likely resident, when it holds this
                if _ok(w):
                    return w, "last used", True
        if own and (many_turns(session) or prev):
            return cap, cap_source, False
        for w in _ladder(_pos(cap) or LADDER_START):
            need = int(math.ceil(_prompt(w) * (1 + RATIO_DEADBAND))) + _room(w)
            if first:
                need = max(need, 2 * _prompt(w))
            if need <= w:
                return w, ("request size" if w < cap else cap_source), False
        return cap, cap_source, False

    window, source, hold = _choose()
    if recent and recent > window and _ok(recent) and not (many and cap_source == "known to spill" and recent > cap):
        # F5: another call of this process asked for a larger window a moment ago (it may still be loading): asking
        # for less would reload the model back and forth
        window, source, hold = recent, "asked here", True
    # 3.6.0.12 OS: a one-shot sent the cap a spill lowered, which holds its request: the reply's room never raises the
    # window past it (agent/reply_room.for_call), so the model runs wholly on the card and a "reloaded at" line is true
    held = one and spill and source == "known to spill" and window == cap and _holds(cap)
    # 3.6.0.19 LM: a session of more turns sent the cap a spill lowered keeps it every turn (the room and the prompt
    # floor never raise past it; a request larger than it is compacted, ollama_window.pre_send_line)
    held = held or (many and cap_source == "known to spill" and window <= cap)
    if own or not many_turns(session):  # a helper call of a session of more turns leaves the session's cap as it is
        st.setdefault("spill_cap", {})[key] = cap if held else None
    if reshape is not None:  # 3.6.0.12 OS: the block the call sends (reshape(None)) and every later call starts from
        session._shape_window, session._shape_model = max(window, shaped_for or 0), ref.raw
    return _ask(window, source, hold)


def _live_fit(row) -> Optional[bool]:
    """From a live `/api/ps` row: True wholly on the card, False partly on the CPU, None when it does not say."""
    size, vram = (row or {}).get("size"), (row or {}).get("size_vram")
    if not (_pos(size) and isinstance(vram, int) and not isinstance(vram, bool)):
        return None
    return vram >= size


def is_main_call(session, ref) -> bool:
    """The session's own model in its own conversation: not a helper call (the small model, compaction, a title, a
    hook) that runs on the same model (fix pass F4: only the main call grows straight to the largest window)."""
    return ref is getattr(session, "model_ref", None) and not getattr(session, "_ollama_helper_call", False)


# ---- F5: one map of the window last asked for, every session of this process ------------------------------------

PROCESS_ASK_TTL_S = 60.0
_ASKED: dict = {}  # (url, model) -> (window, monotonic)
_ASKED_LOCK = __import__("threading").Lock()


def note_process_ask(host_url: str, model: str, window: int) -> None:
    if not _pos(window):
        return
    with _ASKED_LOCK:
        _ASKED[_key(host_url, model)] = (window, time.monotonic())


def process_asked(host_url: str, model: str) -> Optional[int]:
    """The window a call of this process (the parent, a sub-agent, a parallel one) asked of this model on this server
    in the last minute, or None."""
    with _ASKED_LOCK:
        got = _ASKED.get(_key(host_url, model))
    if not got or time.monotonic() - got[1] > PROCESS_ASK_TTL_S:
        return None
    return got[0]


def resident_options(session, host, model: str, body: dict, source: str) -> dict:
    """A call that uses the loaded window sends `num_gpu` the way the runner was loaded: the last call's own when
    Halo loaded it at that window, else none (another client's load); any other `num_gpu` reloads it."""
    if source not in ("loaded", "last used"):
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


TURN_END_READ_S = 1.0


HALF_CUT_BAND = 8      # Ollama's runner keeps num_ctx - (num_ctx - keep) // 2 tokens: num_ctx // 2 + 2 with keep 4
SHRINK_TOLERANCE = 64


def cut_kind(*, count, num_ctx, num_predict=None, ceiling=None, prompt=None, raw=None, prev=None,
             reserve=None) -> Optional[str]:
    """Fix pass F1: the signs that Ollama cut the prompt (it answers 200 and `done_reason: "stop"` either way; a reply
    that ran out is `"length"` and is not one of these). Measured on Ollama 0.40.16:
    - "half": one over-long message is cut by the runner to half the window, `prompt_eval_count` =
      `num_ctx // 2 + 2` (a few tokens more with a larger keep), whatever the estimate said (one far under that
      half is a prompt the estimate undercounted, not a reason to trust the count);
    - "room": the count reaches into the room the call kept for the reply (`count > num_ctx - num_predict`; a chat
      that lost whole messages from the front lands a little under `num_ctx`), or the whole window -- below the
      largest window this call may use (at it, a full window is compaction's to fix);
    - "shrink": fewer tokens than the previous call of the same conversation (`prev` = (count, raw estimate)) by
      more than a small tolerance while Halo's own estimate did not shrink: the server dropped messages;
    - "low": under 70 % of the estimate (agent/ollama_window's older rule, `is_trimmed`).
    None when none applies."""
    from halo_harness.providers.ollama_prompt import is_cut_at_window, is_trimmed
    if not (_pos(count) and _pos(num_ctx)):
        return None
    half = num_ctx // 2 + 2
    # no floor on the estimate (fix1): a prompt several times Halo's estimate is the case this sign exists for, and
    # an honest count landing in this 9-token band is not a realistic false positive
    if half <= count <= half + HALF_CUT_BAND and _pos(prompt):
        return "half"
    below_top = not _pos(ceiling) or num_ctx < ceiling
    if is_cut_at_window(count, num_ctx) or (below_top and _pos(num_predict) and count > num_ctx - num_predict):
        return "room"
    if prev and _pos(prev[0]) and _pos(raw) and _pos(prev[1]) and raw >= prev[1] - SHRINK_TOLERANCE \
            and count < prev[0] - max(SHRINK_TOLERANCE, prev[0] // 50):
        return "shrink"
    if _pos(prompt) and is_trimmed(count, prompt + (reserve or 1024), reserve or 1024):
        return "low"
    return None


def take_cut(session, req) -> Optional[dict]:
    """The verdict `after_call` gave the call `req` (`{"kind", "count", "prev"}`) when it saw a cut, once."""
    got = getattr(session, "_ollama_cut_verdict", None)
    if not got or got.get("req") != id(req) or not got.get("kind"):
        return None
    session._ollama_cut_verdict = None
    return got


def cut_seen(session, req) -> bool:
    """For the ledger line: `after_call` saw a cut on `req` (the verdict is not consumed)."""
    got = getattr(session, "_ollama_cut_verdict", None)
    return bool(got and got.get("req") == id(req) and got.get("kind"))


def after_call(session, req, meta: Optional[dict], kind: str = "turn") -> None:
    """After an Ollama answer (status 200), with no request of its own: the count against the estimate
    (`token_ratio`; only from a call that loaded the model or a count at or above the raw estimate, never from a
    prompt the window cut -- fix pass S3/M1), the line that says how long a load took, and the window this call
    used, kept for the one `/api/ps` read at the end of the turn (`turn_end_check`, fix pass S10). Never raises;
    nothing here loads or unloads a model."""
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
        loading = getattr(session, "_ollama_loading", None)
        fresh = bool(loading and loading.get("model") == model)
        st = _state(session)
        skey = (str(host.url).rstrip("/"), model)
        sent = (st.get("sent") or {}).get(skey) or {}
        count = timing.get("prompt_eval_count")
        # fix pass F1: was the prompt cut? (any of four signs; never a ratio from such a count)
        last = st.get("last") or {}
        choice = last.get("choice") if last.get("model") == model else None
        ceiling = getattr(choice, "ceiling", None) or (st.get("cap") or {}).get((host.url, model))
        track = kind == "turn" and is_main_call(session, getattr(session, "model_ref", None)) \
            and getattr(getattr(session, "model_ref", None), "model", None) == model
        prev = (st.get("counts") or {}).get(skey) if track else None
        prompt = (sent.get("estimate") or 0) - (sent.get("reserve") or 0)
        cut = cut_kind(count=count, num_ctx=opts.get("num_ctx"), num_predict=opts.get("num_predict"),
                       ceiling=ceiling, prompt=prompt, raw=sent.get("raw_prompt"), prev=prev,
                       reserve=sent.get("reserve"))
        if kind == "turn":  # the main loop's resend and the ledger read it; any call's cut keeps its count out
            session._ollama_cut_verdict = {"req": id(req), "kind": cut, "count": count,
                                           "prev": (prev or (None,))[0]}
        if track and _pos(count) and not cut:
            st.setdefault("counts", {})[skey] = (count, sent.get("raw_prompt"))
        if sent.get("raw_prompt") and not cut:
            record_ratio(state_dir, host.url, model, raw_prompt=sent["raw_prompt"], prompt_eval_count=count,
                         fresh=fresh)
        pending = getattr(session, "_ollama_turn_reads", None)
        if not isinstance(pending, dict):
            pending = session._ollama_turn_reads = {}
        pending[(str(host.url).rstrip("/"), model)] = {"host": host, "model": model, "num_ctx": opts.get("num_ctx"),
                                                        "num_gpu": opts.get("num_gpu")}
        if fresh:
            session._ollama_loading = None
            load_s = (timing.get("load_duration") or 0) / 1e9
            took = load_s if load_s >= 0.5 else time.monotonic() - loading["t0"]
            lines = getattr(session, "_ollama_loaded_lines", None) or []
            session._ollama_loaded_lines = lines + [f"{model} loaded on {loading['host']} in {took:.1f} s"]
    except Exception:
        log.debug("ollama: the check after a call failed", exc_info=True)


def _read_ps_bounded(hosts: list, timeout: float) -> dict:
    """`{host.url: /api/ps reply}` for each host, read side by side and waited on for `timeout` seconds in all; a
    host that has not answered by then is left out (unknown), its read abandoned."""
    import threading
    from halo_harness.providers.ollama import fetch_ps
    got: dict = {}

    def _one(h) -> None:
        try:
            got[h.url] = fetch_ps(h, timeout=timeout)
        except Exception:
            pass
    threads = [threading.Thread(target=_one, args=(h,), daemon=True, name="halo-ollama-ps") for h in hosts]
    for th in threads:
        th.start()
    deadline = time.monotonic() + timeout
    for th in threads:
        th.join(max(0.0, deadline - time.monotonic()))
    return {u: got[u] for u in list(got)}


def turn_end_check(session, *, timeout: float = TURN_END_READ_S) -> None:
    """Fix pass S10: the check on use, once at the end of a turn -- one `/api/ps` read per server the turn called,
    waited on for at most `timeout` (1 s) in all: is each model wholly on the card at the window its last call used
    (`window_truth`), the offload marker, the next call's loaded window. A read that failed, came back unreadable or
    did not answer in time is unknown (S2): nothing is recorded from it. Never raises."""
    try:
        pending = getattr(session, "_ollama_turn_reads", None)
        session._ollama_turn_reads = {}
        if not pending:
            return
        hosts = {}
        for item in pending.values():
            hosts.setdefault(item["host"].url, item["host"])
        replies = _read_ps_bounded(list(hosts.values()), timeout)
        from halo_harness.providers.ollama import ollama_names_match
        from halo_harness.providers.ollama_hw import _record_last_known_offload, ps_rows
        state_dir = getattr(session, "state_dir", None)
        for item in pending.values():
            host, model = item["host"], item["model"]
            rows = ps_rows(replies.get(host.url))
            if rows is None:
                continue
            row = next((e for e in rows if ollama_names_match(e.get("model"), model)
                        or ollama_names_match(e.get("name"), model)), None)
            _record_last_known_offload(host.url, model, row)
            if row and row.get("context_length") in (None, item.get("num_ctx")):
                kind = record_truth(state_dir, host.url, model, num_ctx=item.get("num_ctx"), size=row.get("size"),
                                    size_vram=row.get("size_vram"), num_gpu=item.get("num_gpu"),
                                    digest=row.get("digest"))
                if kind and getattr(getattr(session, "model_ref", None), "model", None) == model:
                    session._last_ollama_offloaded = kind == "spills"
    except Exception:
        log.debug("ollama: the check at the end of a turn failed", exc_info=True)


def wrap_stream(session, req, gen, kind: str = "turn"):
    """`gen` (an Ollama call's wire events) passed through unchanged; `after_call` once it ended with an answer
    (`kind`: the ledger's turn / compaction / small / repair)."""
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
        after_call(session, req, meta, kind)
