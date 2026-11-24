"""halo_harness.agent.ollama_window -- Halo 3.2.3.0 R1: the session side of
"the window follows the prompt" (`providers.ollama_prompt` holds the rule).

`agent/loop.py` calls these from its Ollama branch so the loop itself
only grows by the call sites:

- `prepare_window` runs inside `_build_ollama_body_for_ref`, before every
  Ollama call: the request's estimate (3.6.0.0 R8: with the model's
  measured ratio, agent/ollama_window_truth.py) and the window it gets. A
  saved cap under the prompt floor is raised over, never discarded to be
  measured again (no call measures the model; `halo local measure` does,
  when asked).
- `pre_send_line` is the one line when even the largest window this call
  can get does not hold the request: the turn compacts before sending.
- `trim_recovery` is the once-per-turn answer to a trimmed request (a low
  `prompt_eval_count`, or Ollama's 500 "no user query found in
  messages"): raise the window and re-send when there is room under the
  ceiling, else compact and re-send; a second trim in the same turn is an
  error line.
"""

from __future__ import annotations

import json
import logging
import math
from typing import Optional

log = logging.getLogger("bridge")


def _state(session) -> dict:
    st = getattr(session, "_ollama_window_state", None)
    if st is None:
        st = {"factor": {}, "trim_turn": None, "last": None}
        session._ollama_window_state = st
    return st


def window_reason(session, host, ref, decision, choice) -> Optional[str]:
    """3.6.0.20 E5: WHY the window sent is that size, for compact_budget.fixed_line: "memory estimate" (the memory
    estimate, nothing measured, no load seen), "steward profile", "host max_ctx", else the source as it is. A window
    the prompt floor raised to its ceiling is named by what holds the ceiling."""
    try:
        source, w = choice.source, choice.num_ctx
        if source == "prompt floor":
            if w != choice.ceiling:
                return source
            profile = getattr(decision, "profile", None) or {}
            fit = decision.fit_estimate if isinstance(decision.fit_estimate, int) else None
            bounds = [(profile.get("num_ctx"), "steward profile"), (getattr(host, "max_ctx", None), "host max_ctx"),
                      (fit, getattr(decision, "fit_source", "fit estimate")),
                      (decision.trained_context, "trained context")]
            source = next((label for v, label in bounds if v == w), "hard cap")
        if source == "fit estimate" and not getattr(decision, "learned_cap", None):
            from halo_harness.agent.ollama_window_truth import truth
            if not truth(getattr(session, "state_dir", None), host.url, ref.model).get("fits"):
                return "memory estimate"
        return source
    except Exception:
        return None


def prepare_window(session, *, host, ref, decision, base_num_ctx: int, base_source: str,
                   system_text: str, messages, tools, auto_calibrate: bool,
                   reply_tokens=None) -> "tuple[int, float]":
    """Returns `(estimate, factor)` for `build_ollama_request_body`'s
    `prompt_tokens`/`window_factor`; records the choice on the session for
    `pre_send_line`/`trim_recovery` when `ref` is the session's own model."""
    from halo_harness.agent.ollama_window_truth import prompt_estimate
    from halo_harness.providers.ollama_prompt import reply_reserve, tool_output_tokens, window_for
    del auto_calibrate  # 3.6.0.0 R8: no measurement from a call; a saved cap under the floor is raised over, kept
    st = _state(session)
    key = (host.url, ref.model)
    reserve = reply_reserve(reply_tokens)
    if ref is session.model_ref and getattr(session, "_switch_reserve", None):  # 3.3.5.0 R0: the switch's reserve
        reserve = max(reserve, int(session._switch_reserve))
    # 3.3.16.1: the body that is sent; 3.6.0.0 R8: with this model's measured ratio (agent/ollama_window_truth.py)
    raw_prompt, prompt = prompt_estimate(getattr(session, "state_dir", None), host.url, ref.model,
                                         system_text, messages, tools)
    estimate = prompt + reserve
    factor = st["factor"].get(key, 1.0)
    profile = getattr(decision, "profile", None) or {}  # 3.3.4.0 R3: the reply's room never under its num_predict
    choice = window_for(estimate, decision, base=base_num_ctx, base_source=base_source, factor=factor,
                        host_max_ctx=host.max_ctx, reserve=reserve, min_reply=profile.get("num_predict"),
                        hard_cap=_session_spill_cap(session, host, ref))
    # 3.3.4.0 R2: the ledger line of this call reads the window's source and the estimate back; 3.6.0.0 R8: the
    # raw chars / 3.5 too, for the ratio the answer's real count measures
    st.setdefault("sent", {})[(str(host.url).rstrip("/"), ref.model)] = {
        "estimate": estimate, "source": choice.source, "num_ctx": choice.num_ctx, "reserve": reserve,
        "raw_prompt": raw_prompt}
    if ref is session.model_ref:
        from halo_harness.agent.ollama_window_truth import is_main_call
        # "first" is the MAIN call's fact only (the review of 3.6.0.19): a helper call on the session's own model (a
        # title, the compaction's summary) holds one user message too and would switch a later compaction off
        st["last"] = {"estimate": estimate, "choice": choice, "host_name": host.name, "host_url": host.url,
                      "model": ref.model, "tool_tokens": tool_output_tokens(messages),
                      "gpu_fits_up_to": getattr(decision, "gpu_fits_up_to", None), "reserve": reserve,
                      "profile": profile, "first": _first_request(messages) and is_main_call(session, ref),
                      "parts": (system_text, tools),
                      "window_source": window_reason(session, host, ref, decision, choice)}
        from halo_harness.agent.ollama_window_steward import note_prepared
        note_prepared(st, estimate, reserve, session)
    return estimate, factor


def _first_request(messages) -> bool:
    """3.6.0.19 LM: a request that holds nothing before the person's prompt: no answer (no assistant message, so no
    earlier turn and no tool step of this one) and no compaction's summary."""
    from halo_harness.agent.prompt_composition import SUMMARY_MARK
    for m in messages or []:
        if not isinstance(m, dict) or m.get("role") == "assistant":
            return False
        content = m.get("content")
        if SUMMARY_MARK in (content if isinstance(content, str) else json.dumps(content, default=str)):
            return False
    return bool(messages)


def no_earlier_turn(session) -> bool:
    """3.6.0.19 LM: the session's last request on its own Ollama model is its conversation's first (nothing answered
    yet): there is nothing to summarise, so it is never compacted (agent/preflight.run, agent/loop.py's compaction
    before a call and after the first reply)."""
    return (_state(session).get("last") or {}).get("first") is True


def first_refused_line(session, prompt_tokens=None) -> Optional[str]:
    """3.6.0.20 E8 after the check: the line that ends a FIRST request the server refused (the 400 "exceeds the
    available context size") once the retry ladder could not grow its window, or None for a later request (which
    compacts as before). Nothing earlier exists to summarise and no answer exists to keep."""
    if not no_earlier_turn(session):
        return None
    from halo_harness.providers.ollama_prompt import fmt_tokens, prompt_part
    last = _state(session).get("last") or {}
    host_name = last.get("host_name") or "the Ollama host"
    tokens = prompt_tokens if isinstance(prompt_tokens, int) and not isinstance(prompt_tokens, bool) \
        and prompt_tokens > 0 else prompt_part(last.get("estimate") or 1)
    return (f"{host_name} refused the first request ({fmt_tokens(tokens)} tokens) and its window cannot grow: "
            "nothing earlier to compact")


def _session_spill_cap(session, host, ref) -> Optional[int]:
    """3.6.0.19 LM: the cap a spill lowered, for every call of a session of more turns on that model (its main call
    and its helper calls, its compaction: ollama_window_truth.start_window keeps it every turn): the prompt floor never
    raises the window past it; a one-shot is unchanged."""
    from halo_harness.agent.ollama_window_truth import many_turns
    from halo_harness.agent.reply_room import _spill_cap
    if not many_turns(session):
        return None
    return _spill_cap(session, host, ref)


def session_spill_window(session, ref) -> Optional[int]:
    """3.6.0.19 LM: the window a spill holds this session of more turns at, when `ref` is the model its last Ollama
    call ran on (compaction's summary call is checked against it: model_switch_paths.summary_window); else None."""
    from halo_harness.agent.ollama_window_truth import many_turns
    st = getattr(session, "_ollama_window_state", None) or {}
    last = st.get("last") or {}
    if not (many_turns(session) and last.get("model") and last.get("model") == getattr(ref, "model", None)):
        return None
    got = (st.get("spill_cap") or {}).get((last.get("host_url"), last.get("model")))
    return got if isinstance(got, int) and not isinstance(got, bool) and got > 0 else None


def last_estimate(session) -> Optional[int]:
    last = _state(session)["last"]
    return last["estimate"] if last else None


def last_reserve(session) -> int:
    last = _state(session)["last"]
    return (last or {}).get("reserve") or 1024


def pre_send_line(session) -> Optional[str]:
    """The one line when the request is larger than the largest window
    this call can get (the caller compacts before sending), else None."""
    from halo_harness.providers.ollama_prompt import too_large_line
    last = _state(session)["last"]
    if not last or last["choice"].fits:
        return None
    return too_large_line(last["estimate"], last["tool_tokens"], last["model"], last["host_name"],
                          last["choice"].ceiling)


def floor_above(session, cap: int) -> Optional[int]:
    """The current request's estimate when it is above `cap`, else None."""
    est = last_estimate(session)
    return est if isinstance(est, int) and est > cap else None


def body_with_num_ctx(body: dict, num_ctx: int, gpu_fits_up_to: Optional[int] = None) -> dict:
    """`body` at another window; `num_gpu` (all layers on the GPU) stays
    only while the new window is one Halo knows fits there."""
    new_body = dict(body)
    new_body["options"] = dict(body.get("options") or {})
    new_body["options"]["num_ctx"] = num_ctx
    if not (isinstance(gpu_fits_up_to, int) and gpu_fits_up_to >= num_ctx):
        new_body["options"].pop("num_gpu", None)
    return new_body


def gpu_fits_up_to(session) -> Optional[int]:
    last = _state(session)["last"]
    return last.get("gpu_fits_up_to") if last else None


def trim_recovery(session, turn_no: int, seen: Optional[int], *, overflow_handled: bool,
                  current_num_ctx: Optional[int], cut_at: Optional[int] = None,
                  full_at: Optional[int] = None, shape: Optional[dict] = None,
                  answered: bool = True) -> "tuple[str, Optional[int], str]":
    """`("stands", None, line)` -- 3.6.0.20 E8: a first request's answer stands (`answered` False: the 500 carried
    none, "error");
    `("resend", num_ctx, line)` -- raise the window and send again;
    `("compact", None, line)` -- compact, then send again; `("error",
    None, line)` -- a second trim in this turn, or no room left at all.
    3.6.0.0 R8 fix pass: `full_at` -- the window Ollama cut the prompt in
    (`shape`: agent/ollama_window_truth.cut_kind's verdict, for the line);
    a resend grows the window
    once, to the largest this call may use (the session's cap, S4), never
    a step at a time."""
    from halo_harness.providers.ollama_fit import power_of_two_ceil
    from halo_harness.providers.ollama_prompt import TRIM_RESEND_FACTOR, fmt_tokens, prompt_part, trim_line
    st = _state(session)
    last = st["last"] or {}
    estimate = last.get("estimate") or 0
    reserve = last.get("reserve") or 1024
    host_name = last.get("host_name") or "the Ollama host"
    # 3.6.0.20 E8: a FIRST request (no earlier answer) is never compacted: its answer stands once the window cannot
    # grow (a raise is still taken first); with no answer (the 500) it stops
    first = no_earlier_turn(session)

    def _first_stands():
        from halo_harness.providers.ollama_prompt import stands_line
        if not answered:
            return "error", None, (f"{host_name} trimmed the first request ({fmt_tokens(prompt_part(estimate or 1))} "
                                   "tokens) and its window cannot grow: nothing earlier to compact")
        return "stands", None, stands_line(host_name, seen, estimate, window=current_num_ctx, reserve=reserve,
                                           cut_at=cut_at)
    if st["trim_turn"] == turn_no:
        if first and answered:
            return _first_stands()
        seen_part = f"{fmt_tokens(seen)} of " if isinstance(seen, int) and seen > 0 else ""
        return "error", None, (f"{host_name} trimmed the request again ({seen_part}"
                               f"{fmt_tokens(prompt_part(estimate or 1))} tokens) in this turn: stopped")
    st["trim_turn"] = turn_no
    if first and answered and cut_at is not None:
        return _first_stands()  # E8 after the check: a cut REPLY stands as it is, never thrown away for a raise
    choice = last.get("choice")
    ceiling = choice.ceiling if choice is not None else 0
    # Ollama read less than the window held, so the real prompt is larger
    # than the window sent: at least double it (floor x 1.5 when larger).
    want = max(power_of_two_ceil(int(math.ceil(estimate * TRIM_RESEND_FACTOR))) if estimate else 0,
               2 * current_num_ctx if isinstance(current_num_ctx, int) else 0)
    # 3.6.0.0 R8 fix pass S4: a reload to grow goes to the largest window the session may use at once
    largest = (st.get("cap") or {}).get((last.get("host_url"), last.get("model")))
    target = min(ceiling, max(want, largest if isinstance(largest, int) else 0))
    if isinstance(current_num_ctx, int) and target > current_num_ctx:
        if last.get("host_url"):
            st["factor"][(last["host_url"], last["model"])] = TRIM_RESEND_FACTOR
        return "resend", target, trim_line(host_name, seen, estimate, window=target, reserve=reserve, cut_at=cut_at,
                                           full_at=full_at, shape=shape)
    if first:
        return _first_stands()
    if not overflow_handled:
        return "compact", None, trim_line(host_name, seen, estimate, reserve=reserve, cut_at=cut_at, full_at=full_at,
                                         shape=shape)
    return "error", None, (f"{host_name} trimmed the request ({fmt_tokens(prompt_part(estimate or 1))} tokens) "
                           f"and the window is already at its ceiling after compaction: stopped")


def _block_text(content) -> "Optional[str]":
    if isinstance(content, str):
        return content
    if isinstance(content, list) and all(isinstance(b, dict) and b.get("type") == "text" for b in content):
        return "".join(b.get("text") or "" for b in content)
    return None


def cut_tool_output(messages: list, *, excess_tokens: int, host_name: str, window: int) -> "tuple[list, int]":
    """The wire copy of `messages` with tool results cut (largest first,
    the head kept) by about `excess_tokens`; returns `(messages, tokens
    cut)`. The logged transcript is never touched. Used when compaction
    already ran and the current turn's own tool output still does not fit
    the window (compaction keeps the turn in progress)."""
    from halo_harness.providers.ollama_prompt import CHARS_PER_TOKEN, fmt_window
    to_cut = int(excess_tokens * CHARS_PER_TOKEN * 1.05) + 200
    spots = []
    for mi, msg in enumerate(messages or []):
        content = msg.get("content") if isinstance(msg, dict) else None
        if not isinstance(content, list):
            continue
        for bi, block in enumerate(content):
            if isinstance(block, dict) and block.get("type") == "tool_result":
                text = _block_text(block.get("content"))
                if text and len(text) > 1000:
                    spots.append((len(text), mi, bi, text))
    if not spots or to_cut <= 0:
        return messages, 0
    out = [dict(m) if isinstance(m, dict) else m for m in messages]
    cut_chars = 0
    for size, mi, bi, text in sorted(spots, reverse=True):
        if cut_chars >= to_cut:
            break
        keep = max(1000, size - (to_cut - cut_chars))
        note = (f"\n[... {size - keep} characters of this tool output were cut: the window on {host_name} "
                f"holds {fmt_window(window)} tokens]")
        blocks = list(out[mi]["content"])
        blocks[bi] = {**blocks[bi], "content": text[:keep] + note}
        out[mi]["content"] = blocks
        cut_chars += size - keep
    return out, int(cut_chars / CHARS_PER_TOKEN)


def fit_after_compaction(session, *, host, ref, decision, base_num_ctx: int, base_source: str,
                         system_text: str, messages, tools, reply_tokens=None) -> "tuple[list, int, float]":
    """After compaction (the step's `overflow_handled`), a request that
    still does not fit has its tool output cut on the wire to the window;
    one `↳` line is queued for the step. Returns `(messages, estimate,
    factor)` (unchanged when it fits)."""
    from halo_harness.providers.ollama_prompt import fmt_tokens
    st = _state(session)
    last = st["last"]
    if not last or last["choice"].fits or ref is not session.model_ref:
        return messages, last["estimate"] if last else 0, st["factor"].get((host.url, ref.model), 1.0)
    choice = last["choice"]
    new_messages, cut = cut_tool_output(messages, excess_tokens=last["estimate"] - choice.ceiling,
                                        host_name=host.name, window=choice.ceiling)
    estimate, factor = prepare_window(session, host=host, ref=ref, decision=decision, base_num_ctx=base_num_ctx,
                                      base_source=base_source, system_text=system_text, messages=new_messages,
                                      tools=tools, auto_calibrate=False, reply_tokens=reply_tokens)
    if cut:
        st["markers"] = st.get("markers", []) + [
            f"the request is still larger than {ref.model}'s window on {host.name} after compaction: "
            f"{fmt_tokens(cut)} tokens of tool output cut to fit"]
    return new_messages, estimate, factor


def drain_markers(session) -> list:
    st = _state(session)
    out = st.get("markers") or []
    st["markers"] = []
    return out
