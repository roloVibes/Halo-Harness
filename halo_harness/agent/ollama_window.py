"""halo_harness.agent.ollama_window -- Halo 3.2.3.0 R1: the session side of
"the window follows the prompt" (`providers.ollama_prompt` holds the rule).

`agent/loop.py` calls these from its Ollama branch so the loop itself
only grows by the call sites:

- `prepare_window` runs inside `_build_ollama_body_for_ref`, before every
  Ollama call: the request's estimate, the window it gets, and a saved
  calibration cap under the prompt floor discarded (the model is measured
  again on the next turn, once per process).
- `pre_send_line` is the one line when even the largest window this call
  can get does not hold the request: the turn compacts before sending.
- `trim_recovery` is the once-per-turn answer to a trimmed request (a low
  `prompt_eval_count`, or Ollama's 500 "no user query found in
  messages"): raise the window and re-send when there is room under the
  ceiling, else compact and re-send; a second trim in the same turn is an
  error line.
"""

from __future__ import annotations

import logging
import math
from typing import Optional

log = logging.getLogger("bridge")


def _state(session) -> dict:
    st = getattr(session, "_ollama_window_state", None)
    if st is None:
        st = {"factor": {}, "discarded": set(), "trim_turn": None, "late": [], "last": None}
        session._ollama_window_state = st
    return st


def prepare_window(session, *, host, ref, decision, base_num_ctx: int, base_source: str,
                   system_text: str, messages, tools, auto_calibrate: bool,
                   reply_tokens=None) -> "tuple[int, float]":
    """Returns `(estimate, factor)` for `build_ollama_request_body`'s
    `prompt_tokens`/`window_factor`; records the choice on the session for
    `pre_send_line`/`trim_recovery` when `ref` is the session's own model."""
    from halo_harness.providers.ollama_prompt import (
        estimate_request_tokens, reply_reserve, tool_output_tokens, window_for,
    )
    st = _state(session)
    key = (host.url, ref.model)
    reserve = reply_reserve(reply_tokens)
    estimate = estimate_request_tokens(messages, tools, system_text, reply_tokens=reply_tokens)
    factor = st["factor"].get(key, 1.0)
    choice = window_for(estimate, decision, base=base_num_ctx, base_source=base_source, factor=factor,
                        host_max_ctx=host.max_ctx, reserve=reserve)
    cap = getattr(decision, "learned_cap", None)
    if auto_calibrate and isinstance(cap, int) and cap < estimate and key not in st["discarded"]:
        st["discarded"].add(key)
        try:
            from halo_harness.providers.ollama_calibrate import discard_calibration, remeasured_after_floor
            if session.state_dir is not None and not remeasured_after_floor(
                    session.state_dir, host_url=host.url, model=ref.model) and discard_calibration(
                    session.state_dir, host_url=host.url, model=ref.model):
                session._ollama_calibrate_attempted.discard(key)
                log.info("ollama: discarded the saved cap %s for %s on %s (under the prompt floor %s)",
                         cap, ref.model, host.name, estimate)
        except Exception:
            log.debug("ollama: discarding a cap under the floor failed", exc_info=True)
    # 3.3.4.0 R2: the ledger line of this call reads the window's source and the estimate back
    st.setdefault("sent", {})[(str(host.url).rstrip("/"), ref.model)] = {
        "estimate": estimate, "source": choice.source, "num_ctx": choice.num_ctx, "reserve": reserve}
    if ref is session.model_ref:
        st["last"] = {"estimate": estimate, "choice": choice, "host_name": host.name, "host_url": host.url,
                      "model": ref.model, "tool_tokens": tool_output_tokens(messages),
                      "gpu_fits_up_to": getattr(decision, "gpu_fits_up_to", None), "reserve": reserve}
    return estimate, factor


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
                  current_num_ctx: Optional[int], cut_at: Optional[int] = None) -> "tuple[str, Optional[int], str]":
    """`("resend", num_ctx, line)` -- raise the window and send again;
    `("compact", None, line)` -- compact, then send again; `("error",
    None, line)` -- a second trim in this turn, or no room left at all."""
    from halo_harness.providers.ollama_fit import power_of_two_ceil
    from halo_harness.providers.ollama_prompt import TRIM_RESEND_FACTOR, fmt_tokens, prompt_part, trim_line
    st = _state(session)
    last = st["last"] or {}
    estimate = last.get("estimate") or 0
    reserve = last.get("reserve") or 1024
    host_name = last.get("host_name") or "the Ollama host"
    if st["trim_turn"] == turn_no:
        seen_part = f"{fmt_tokens(seen)} of " if isinstance(seen, int) and seen > 0 else ""
        return "error", None, (f"{host_name} trimmed the request again ({seen_part}"
                               f"{fmt_tokens(prompt_part(estimate or 1))} tokens) in this turn: stopped")
    st["trim_turn"] = turn_no
    choice = last.get("choice")
    ceiling = choice.ceiling if choice is not None else 0
    # Ollama read less than the window held, so the real prompt is larger
    # than the window sent: at least double it (floor x 1.5 when larger).
    want = max(power_of_two_ceil(int(math.ceil(estimate * TRIM_RESEND_FACTOR))) if estimate else 0,
               2 * current_num_ctx if isinstance(current_num_ctx, int) else 0)
    target = min(ceiling, want)
    if isinstance(current_num_ctx, int) and target > current_num_ctx:
        if last.get("host_url"):
            st["factor"][(last["host_url"], last["model"])] = TRIM_RESEND_FACTOR
        return "resend", target, trim_line(host_name, seen, estimate, window=target, reserve=reserve, cut_at=cut_at)
    if not overflow_handled:
        return "compact", None, trim_line(host_name, seen, estimate, reserve=reserve, cut_at=cut_at)
    return "error", None, (f"{host_name} trimmed the request ({fmt_tokens(prompt_part(estimate or 1))} tokens) "
                           f"and the window is already at its ceiling after compaction: stopped")


def track_late_calibration(session, done, notice_box: list) -> None:
    """A first-use calibration still running when the turn's wait ended:
    its outcome line is shown on a later drain, once it finishes."""
    _state(session)["late"].append((done, notice_box))


def drain_late_calibrations(session) -> list:
    st = _state(session)
    out, keep = [], []
    for done, box in st["late"]:
        if done.is_set():
            if box and box[0]:
                out.append(box[0])
        else:
            keep.append((done, box))
    st["late"] = keep
    return out


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
