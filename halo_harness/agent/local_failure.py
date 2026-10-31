"""halo_harness.agent.local_failure -- Halo 3.3.6.0 R1: when a local model
fails in a role, say why in one plain line with the fix
(plans/local-model-fit-brief.md E5), read off its battery profile
(providers/battery_profile.py). `agent/loop.py`'s Ollama path calls these;
the steward's events get theirs in ollama_steward/failure_lines.py.

    thinking_retry(body, blocks, text, tool_uses, meta) -> (body, line) | None
        empty `content` with `thinking` present, the budget cut it: once more with a raised reserve
        ("it answered in thinking; the reply budget was too small: retried with 300 tokens")
    no_tools_line(session) -> line | None
        an empty reply with no tool call on a model the battery found with no tool calling
    empty_line(session) -> line   the same symptom on a model with no such profile (never a raw error)
    after_call(session, meta, blocks) -> [lines]
        a cold load ("cold load of 17 GB, ~25 s: pin it (keep_alive -1) or pre-warm"), an identifier
        from a model whose ids are unverified -- each said once per session and model
"""

from __future__ import annotations

import logging
import re
from typing import Optional

log = logging.getLogger("bridge")

RESERVE = 300
COLD_S = 10.0
_IDS = re.compile(r"\b(?:CVE-\d{4}-\d{3,7}|CWE-\d{1,4})\b")


def _thought(blocks, meta) -> bool:
    if any(isinstance(b, dict) and b.get("type") == "thinking" and str(b.get("text") or b.get("thinking") or "").strip()
           for b in blocks or ()):
        return True
    return bool(str((meta or {}).get("reasoning_text") or "").strip())


def thinking_retry(body: dict, blocks, text: str, tool_uses: int, meta: dict):
    if (text or "").strip() or tool_uses or not _thought(blocks, meta):
        return None
    opts = dict(body.get("options") or {})
    cur = opts.get("num_predict") if isinstance(opts.get("num_predict"), int) else body.get("max_tokens")
    cut = (meta or {}).get("done_reason") == "length"
    if not isinstance(cur, int) or (cur >= RESERVE and not cut):
        return None
    timing, ctx_n = (meta or {}).get("timing_ns") or {}, opts.get("num_ctx")
    seen, ev = timing.get("prompt_eval_count"), timing.get("eval_count")
    if isinstance(ctx_n, int) and isinstance(seen, int) and isinstance(ev, int) and seen + ev >= ctx_n * 0.98:
        return None  # the window filled, not the reply budget: the window-cut path handles it
    new = max(RESERVE, cur * 2) if cut else RESERVE
    out = dict(body)
    if "options" in body or "max_tokens" not in body:
        out["options"] = {**opts, "num_predict": new}
    else:
        out["max_tokens"] = new
    return out, f"it answered in thinking; the reply budget was too small: retried with {new:,} tokens"


def _profile(session) -> Optional[dict]:
    from halo_harness.providers.placement import profile_for_ref
    return profile_for_ref(getattr(session, "model_ref", None), getattr(session, "state_dir", None))


def no_tools_line(session) -> Optional[str]:
    p = _profile(session)
    if not p or p.get("tools") != "no":
        return None
    from halo_harness.providers.battery_profile import date_of
    from halo_harness.providers.placement import with_tools
    better = (with_tools(getattr(session, "state_dir", None), exclude=getattr(session.model_ref, "raw", "")) or
              ["a model with tools"])[0]
    return (f"no tool calling on this model (probed {date_of(p)}): it can't run agentic steps; use it for "
            f"single-shot extraction, or route this step to {better}")


def empty_line(session) -> str:
    raw = getattr(getattr(session, "model_ref", None), "raw", "this model")
    return (f"{raw} returned an empty reply twice (no text, no tool call): `halo models probe {raw}` says what it can "
            "do here; route this step to another model, or ask it without tools")


def _said(session, key: str) -> bool:
    seen = getattr(session, "_local_failure_said", None)
    if not isinstance(seen, set):
        seen = session._local_failure_said = set()
    if key in seen:
        return True
    seen.add(key)
    return False


def after_call(session, meta: dict, blocks) -> list:
    out = []
    try:
        raw = getattr(getattr(session, "model_ref", None), "raw", "") or ""
        timing = (meta or {}).get("timing_ns") or {}
        load = timing.get("load_duration")
        p = None
        if isinstance(load, (int, float)) and load / 1e9 >= COLD_S and not _said(session, f"cold|{raw}"):
            p = _profile(session)
            size = f"{p['size_gb']:g} GB" if p and p.get("size_gb") else "the model"
            out.append(f"cold load of {size}, ~{load / 1e9:.0f} s: pin it (`keep_alive -1`) or pre-warm "
                       f"(halo models load {raw.split(':', 1)[-1].split('@')[0]})")
        text = " ".join(str(b.get("text") or "") for b in blocks or () if isinstance(b, dict) and b.get("type") == "text")
        ids = sorted(set(_IDS.findall(text)))
        if ids:
            p = p or _profile(session)
            if p and p.get("identifiers") == "unverified" and not _said(session, f"ids|{raw}|{','.join(ids)}"):
                from halo_harness.providers.battery_profile import date_of
                from halo_harness.providers.placement import with_tools
                better = next((r for r in with_tools(session.state_dir) if r != raw), "a stronger model")
                out.append(f"its reference IDs are unverified (probed {date_of(p)}: {p.get('identifiers_why') or 'it got one wrong'}): "
                           f"resolve {', '.join(ids[:3])} with a tool or {better}")
    except Exception:
        log.debug("local_failure: after_call failed", exc_info=True)
    for line in out:
        log.info("local model: %s", line)
    return out
