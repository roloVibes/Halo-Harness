"""halo_harness.providers.ollama_prompt -- Halo 3.2.3.0 R1 "the window
follows the prompt".

Ollama trims a prompt that is longer than the request's `num_ctx` and
answers anyway (it returns 400 only in the narrower case its own
`exceed_context_size_error` covers). So before every Ollama call Halo
estimates the request's size and sends a window that holds it.

The one rule: a request's tokens are its serialized characters (system
text, messages and tool definitions as JSON, inline image bytes left out)
divided by 3.5, plus the reply's room: the request's `num_predict` (the
loop's max output for the call), 1,024 at least -- prompt + reply must
fit `num_ctx` (a reply that reaches the window's end is cut there). That
number is the prompt floor: `num_ctx` is never below it. When only the
prompt + 1,024 fits the ceiling, the window is the ceiling and the
reply's `num_predict` is lowered to the room left. The floor raises the
window above every smaller `min()` candidate (a saved calibration cap,
the remote default, a fallback) up to the ceiling: the trained context,
the memory estimate, `host.max_ctx` when set, and the hard cap. When the
floor is above the ceiling the turn compacts first.

After the call, `prompt_eval_count` (the tokens Ollama actually read) is
compared with the estimate: a count under 70 % of the estimate's prompt
part (the reserve is not prompt) on a request above 2,048 tokens is a
trimmed request.
"""

from __future__ import annotations

import json
import math
from dataclasses import dataclass
from typing import Optional

CHARS_PER_TOKEN = 3.5
REPLY_RESERVE_TOKENS = 1024
TRIM_RATIO = 0.7
TRIM_MIN_ESTIMATE = 2048
TRIM_RESEND_FACTOR = 1.5
_TOOL_PART_MIN_TOKENS = 500

_SOURCE_WORDS = {
    "learned cap": "calibrated", "fit estimate": "memory", "host max_ctx": "max_ctx",
    "trained context": "trained", "prompt floor": "prompt floor", "hard cap": "hard cap",
    "fallback": "fallback", "remote default": "remote default", "conservative default": "default",
    "steward profile": "profile",  # 3.3.4.0 R3 (ollama_steward/profiles.py)
}


def source_word(label: Optional[str]) -> str:
    """The short word `halo ollama` and the notices print for one
    `resolve_num_ctx_and_source` label: `trained`, `memory`,
    `calibrated`, `max_ctx`, `prompt floor` (and `hard cap`, `fallback`,
    `remote default`, `default` for the rest)."""
    return _SOURCE_WORDS.get(label or "", label or "?")


def _chars(obj) -> int:
    from halo_harness.providers.config import _strip_image_payloads_for_estimate
    try:
        stripped, _images = _strip_image_payloads_for_estimate(obj)
        return len(json.dumps(stripped, ensure_ascii=False, default=str))
    except (TypeError, ValueError):
        return len(str(obj))


def reply_reserve(num_predict=None) -> int:
    """The reply's room: `num_predict` when set, 1,024 at least."""
    return max(REPLY_RESERVE_TOKENS, num_predict if _pos_int(num_predict) else 0)


def estimate_request_tokens(messages, tools, system, *, reply_tokens=None) -> int:
    """chars / 3.5 + the reply's room (the module's one rule). `messages`
    and `tools` are the request's own lists (Anthropic-shaped or wire-
    shaped: the count is over their JSON either way), `system` the system
    text, `reply_tokens` the request's `num_predict`."""
    chars = _chars({"system": system or "", "messages": messages or [], "tools": tools or []})
    return int(math.ceil(chars / CHARS_PER_TOKEN)) + reply_reserve(reply_tokens)


def tool_output_tokens(messages) -> int:
    """The part of the estimate that is tool results (`tool_result`
    blocks, or `role: tool` messages), by the same chars / 3.5 rule."""
    chars = 0
    for msg in messages or []:
        if not isinstance(msg, dict):
            continue
        if msg.get("role") == "tool":
            chars += _chars(msg.get("content"))
            continue
        content = msg.get("content")
        if isinstance(content, list):
            for block in content:
                if isinstance(block, dict) and block.get("type") == "tool_result":
                    chars += _chars(block.get("content"))
    return int(math.ceil(chars / CHARS_PER_TOKEN))


def _pos_int(v) -> Optional[int]:
    return v if isinstance(v, int) and not isinstance(v, bool) and v > 0 else None


def window_ceiling(*, trained_context=None, fit_estimate=None, host_max_ctx=None, hard_cap: Optional[int] = None) -> int:
    """The largest window this call can get: min(trained context, the
    memory estimate, `host.max_ctx`, the hard cap) over the ones known."""
    from halo_harness.providers.ollama import HARD_CONTEXT_CAP
    values = [_pos_int(hard_cap) or HARD_CONTEXT_CAP]
    for v in (trained_context, fit_estimate, host_max_ctx):
        if _pos_int(v) is not None:
            values.append(v)
    return min(values)


@dataclass(frozen=True)
class WindowChoice:
    num_ctx: int
    source: str       # a resolve_num_ctx_and_source label, or "prompt floor"
    floor: int        # the prompt floor (the estimate x the factor)
    ceiling: int      # the most this call can get
    fits: bool        # num_ctx >= floor
    num_predict: Optional[int] = None  # the reply's room when it had to shrink to fit the ceiling


def window_for(prompt_tokens: Optional[int], decision=None, *, base: Optional[int] = None,
               base_source: Optional[str] = None, factor: float = 1.0, trained_context=None,
               fit_estimate=None, host_max_ctx=None, hard_cap: Optional[int] = None,
               reserve: int = REPLY_RESERVE_TOKENS, min_reply: Optional[int] = None) -> WindowChoice:
    """`num_ctx` = max(the decision's `min()`, the floor), the raise
    rounded up to a power of two (a window that changes every turn
    reloads the model every turn) and capped at `window_ceiling`; never
    below `base`. `decision` (an `OllamaContextDecision`) supplies `base`
    (its `num_ctx`), the source label and the ceiling inputs unless they
    are passed explicitly. `min_reply` (3.3.4.0 R3: a profile's
    `num_predict`) is the least the reply's room may shrink to so the prompt
    fits the ceiling (1,024 when unset); below it the request does not fit
    and the turn compacts first."""
    if decision is not None:
        base = base if base is not None else decision.num_ctx
        base_source = base_source or decision.source
        trained_context = trained_context if trained_context is not None else decision.trained_context
        fit_estimate = fit_estimate if fit_estimate is not None else decision.fit_estimate
        if host_max_ctx is None:
            host_max_ctx = getattr(decision, "host_max_ctx", None)
    base = _pos_int(base) or 1
    ceiling = max(base, window_ceiling(trained_context=trained_context, fit_estimate=_pos_int(fit_estimate),
                                       host_max_ctx=host_max_ctx, hard_cap=hard_cap))
    if not _pos_int(prompt_tokens):
        return WindowChoice(base, base_source or "?", 0, ceiling, True)
    floor = int(math.ceil(prompt_tokens * max(1.0, factor)))
    if floor <= base:
        return WindowChoice(base, base_source or "?", floor, ceiling, True)
    from halo_harness.providers.ollama_fit import power_of_two_ceil
    num_ctx = max(base, min(power_of_two_ceil(floor), ceiling))
    prompt_only = floor - reserve
    keep = min(reserve, max(REPLY_RESERVE_TOKENS, _pos_int(min_reply) or 0))
    if num_ctx < floor and reserve > keep and prompt_only + keep <= ceiling:
        # the prompt fits with a smaller reply: the whole ceiling, the reply gets what is left
        return WindowChoice(ceiling, "prompt floor", floor, ceiling, True, num_predict=ceiling - prompt_only)
    return WindowChoice(num_ctx, "prompt floor", floor, ceiling, num_ctx >= floor)


def prompt_part(estimate: int, reserve: int = REPLY_RESERVE_TOKENS) -> int:
    """The estimate without the reply's room: what Ollama should read."""
    return max(1, int(estimate) - int(reserve))


def is_window_cut(done_reason, prompt_eval_count, eval_count, num_ctx, num_predict=None) -> bool:
    """A reply cut at the window's end: `done_reason: "length"` with prompt
    + reply at 97 % of `num_ctx` or more (a reply that stopped at its own
    smaller `num_predict` ends well before that). Ollama answers 200."""
    del num_predict  # implied: prompt + num_predict under 97 % never reaches the test below
    if done_reason != "length" or not (_pos_int(prompt_eval_count) and _pos_int(eval_count) and _pos_int(num_ctx)):
        return False
    return prompt_eval_count + eval_count >= 0.97 * num_ctx


def is_trimmed(prompt_eval_count, estimate: Optional[int], reserve: int = REPLY_RESERVE_TOKENS) -> bool:
    """True when Ollama read under 70 % of the request's prompt part and
    the estimate is above 2,048 tokens (a small request's estimate is too
    rough to call)."""
    if not _pos_int(estimate) or estimate <= TRIM_MIN_ESTIMATE:
        return False
    if not isinstance(prompt_eval_count, int) or isinstance(prompt_eval_count, bool) or prompt_eval_count <= 0:
        return False
    return prompt_eval_count < TRIM_RATIO * prompt_part(estimate, reserve)


def fmt_tokens(n: int) -> str:
    """4100 -> "4.1k", 9000 -> "9k", 11000 -> "11k", 900 -> "900"."""
    n = int(n)
    if n < 1000:
        return str(n)
    if n < 10000:
        return f"{n / 1000:.1f}".rstrip("0").rstrip(".") + "k"
    return f"{int(n / 1000 + 0.5)}k"


def fmt_window(n: int) -> str:
    """A window size: 8192 -> "8k", 32768 -> "32k", 65536 -> "65k"."""
    n = int(n)
    return f"{n // 1000}k" if n >= 1000 else str(n)


def too_large_line(prompt_tokens: int, tool_tokens: int, model: str, host_name: str, window: int) -> str:
    """The one line before a compaction the window forced."""
    tool = f", {fmt_tokens(tool_tokens)} of it tool output" if tool_tokens >= _TOOL_PART_MIN_TOKENS else ""
    return (f"the request ({fmt_tokens(prompt_tokens)} tokens{tool}) is larger than {model}'s window on "
            f"{host_name} ({fmt_window(window)}): compacted")


def trim_line(host_name: str, seen: Optional[int], estimate: int, *, window: Optional[int] = None,
              reserve: int = REPLY_RESERVE_TOKENS, cut_at: Optional[int] = None) -> str:
    """The one line for a trimmed request (or, `cut_at` = the window the
    reply ran into, a reply cut there): re-sent with a larger window
    (`window` given) or compacted and re-sent. `seen` is Ollama's own
    count (None for the 500, which carries none)."""
    done = f"re-sent with a {fmt_window(window)} window" if window else "compacted and re-sent"
    if cut_at:
        return f"{host_name} cut the reply at the window ({fmt_tokens(seen or 0)} of {fmt_window(cut_at)} tokens): {done}"
    part = fmt_tokens(prompt_part(estimate, reserve))
    of = f"{fmt_tokens(seen)} of {part} tokens" if _pos_int(seen) else f"{part} tokens"
    return f"{host_name} trimmed the request ({of}): {done}"


PROMPT_SPEED_MIN_TOKENS = 256


def prompt_speed(prompt_eval_count, prompt_eval_duration_ns) -> Optional[float]:
    """Prompt reading speed (tokens/s) from one Ollama reply's
    `prompt_eval_count` / `prompt_eval_duration` (nanoseconds); None for a
    prompt under 256 tokens (too short to time) or missing fields."""
    if not isinstance(prompt_eval_count, int) or isinstance(prompt_eval_count, bool):
        return None
    if prompt_eval_count < PROMPT_SPEED_MIN_TOKENS:
        return None
    if not isinstance(prompt_eval_duration_ns, (int, float)) or prompt_eval_duration_ns <= 0:
        return None
    return prompt_eval_count / (prompt_eval_duration_ns / 1_000_000_000.0)


def fmt_duration(seconds: float) -> str:
    """110 -> "1 min 50 s", 12.4 -> "12 s"."""
    total = int(round(max(0.0, float(seconds))))
    minutes, secs = divmod(total, 60)
    return f"{minutes} min {secs} s" if minutes else f"{secs} s"
