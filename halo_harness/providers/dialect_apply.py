"""halo_harness.providers.dialect_apply -- Halo 3.3.6.0 R4: the dialect record
(providers/dialect.py) applied before and after every call to a local model
(an `ol:` model, an `hf:local` server's), by agent/loop.py and agent/prompt_wire.py.

    record_for(session) -> the record in force for the session's model ({} for a cloud model)
    apply_body(session, body) -> body    the stop quirks as `stop` options, the reply reserve as a floor
        on `num_predict` / `max_tokens`, `think: false` when thinking is off (only when the body sets none)
    strips(session) -> bool              fence stripping in the parse paths (the repair round, the JSON
                                         repair loop); on unless you set strip_fences off
    repair_attempts(session) -> int      the JSON repair loop's bound (0: off)
    tools_max(session) -> int | None     the record's tools_max (None: the window and the profile decide)
    LoopGuard(window, stop)              .feed(text) -> "stop" | "seen" | None: the same `window`-token
                                         span three times; a guard that is off only marks it ("seen")
    guard_for(session) -> LoopGuard | None
    after_reply(session, blocks)         thinking "strip": `<think>...</think>` cut out of the text blocks
    refine_lines(session) -> [lines]     the ledger's refinements after a call (providers/dialect_refine.py)
    ledger_view(session) -> {placement, reserve, repair, guard, thinking, tools_max} | None (the ledger line)
"""

from __future__ import annotations

import logging
import re
from typing import Optional

log = logging.getLogger("bridge")
_THINK = re.compile(r"<think>.*?</think>\s*", re.DOTALL)
_TOKEN = re.compile(r"\S+")


def _target(session) -> "tuple[Optional[str], Optional[str]]":
    ref = getattr(session, "model_ref", None)
    provider = getattr(ref, "provider", "")
    if provider == "ollama":
        try:
            from halo_harness.providers.ollama import resolve_ollama_host
            env = getattr(getattr(session, "settings", None), "effective_env", None)
            host = resolve_ollama_host(getattr(ref, "host", None), env)
            return (getattr(host, "name", None) or getattr(ref, "host", None)), ref.model
        except Exception:
            return getattr(ref, "host", None), getattr(ref, "model", None)
    if provider == "huggingface" and getattr(ref, "local", False):
        return getattr(ref, "host", None) or "local", ref.model
    return None, None


def record_for(session) -> dict:
    """Cached on the session per model and turn (an edit applies from the next turn)."""
    host, model = _target(session)
    if not host or not model:
        return {}
    key = (getattr(getattr(session, "model_ref", None), "raw", None), getattr(session, "turn_count", None))
    hit = getattr(session, "_dialect_record", None)
    if isinstance(hit, tuple) and hit[0] == key:
        return hit[1]
    try:
        from halo_harness.providers.dialect import record
        rec = record(host, model, state_dir=getattr(session, "state_dir", None))
    except Exception:
        log.debug("dialect: no record for %s", model, exc_info=True)
        rec = {}
    try:
        session._dialect_record = (key, rec)
    except Exception:
        pass
    return rec


def apply_body(session, body: dict) -> dict:
    rec = record_for(session)
    if not rec or not isinstance(body, dict):
        return body
    frm = rec.get("from") or {}
    out = dict(body)
    if "options" in body or getattr(getattr(session, "route", None), "dialect", None) == "ollama":
        opts = dict(body.get("options") or {})
        if rec.get("stop_quirks"):
            opts["stop"] = list(dict.fromkeys(list(opts.get("stop") or []) + list(rec["stop_quirks"])))
        cur = opts.get("num_predict")
        if frm.get("reply_reserve") not in (None, "default") and isinstance(cur, int) and 0 < cur < rec["reply_reserve"]:
            opts["num_predict"] = rec["reply_reserve"]
        out["options"] = opts
        if rec.get("thinking") == "off" and "think" not in body:
            out["think"] = False
    else:
        if rec.get("stop_quirks"):
            out["stop"] = list(dict.fromkeys(list(body.get("stop") or []) + list(rec["stop_quirks"])))[:4]
        cur = body.get("max_tokens")
        if frm.get("reply_reserve") not in (None, "default") and isinstance(cur, int) and 0 < cur < rec["reply_reserve"]:
            out["max_tokens"] = rec["reply_reserve"]
    return out


def strips(session) -> bool:
    rec = record_for(session)
    return rec.get("strip_fences", True) is not False


def parse_text(session, text: str) -> str:
    from halo_harness.providers.battery_probes import strip_fences
    return strip_fences(text) if strips(session) else (text or "").strip()


def repair_attempts(session) -> int:
    rec = record_for(session)
    jr = rec.get("json_repair") if rec else None
    if not isinstance(jr, dict):
        return 1
    return int(jr.get("attempts") or 0) if jr.get("on") else 0


def tools_max(session) -> Optional[int]:
    v = record_for(session).get("tools_max")
    return v if isinstance(v, int) and not isinstance(v, bool) else None


class LoopGuard:
    """The same span of `window` tokens three times in a reply."""

    def __init__(self, window: int = 40, stop: bool = True):
        self.window, self.stop, self.text, self.since, self.cut_at = max(8, int(window)), stop, "", 0, None

    def feed(self, text: str) -> Optional[str]:
        self.text += text or ""
        self.since += len(_TOKEN.findall(text or ""))
        if self.cut_at is not None or self.since < max(4, self.window // 4):
            return None
        self.since = 0
        spans = [(m.start(), m.group()) for m in _TOKEN.finditer(self.text[-12000:])]
        if len(spans) < self.window * 3:
            return None
        base = max(0, len(self.text) - 12000)
        tail = [t for _s, t in spans[-self.window:]]
        words = [t for _s, t in spans]
        hits, i = [], len(words) - self.window
        while i >= 0:
            if words[i:i + self.window] == tail:
                hits.append(i)
                i -= self.window
            else:
                i -= 1
        if len(hits) < 3:
            return None
        self.cut_at = base + spans[sorted(hits)[1]][0]  # keep the first span and its first repeat's start
        return "stop" if self.stop else "seen"


def guard_for(session) -> Optional[LoopGuard]:
    rec = record_for(session)
    if not rec:
        return None
    g = rec.get("loop_guard") or {}
    return LoopGuard(int(g.get("window") or 40), stop=bool(g.get("on")))


def after_reply(session, blocks) -> None:
    rec = record_for(session)
    if rec.get("thinking") != "strip":
        return
    for b in blocks or ():
        if isinstance(b, dict) and b.get("type") == "text" and "<think>" in str(b.get("text") or ""):
            b["text"] = _THINK.sub("", b["text"])


def refine_lines(session) -> list:
    """The ledger's refinements of this model's record after a call (providers/dialect_refine.py); never raises."""
    host, model = _target(session)
    if not host or not model or getattr(session, "state_dir", None) is None:
        return []
    try:
        from halo_harness.providers.dialect_refine import refine
        return refine(host, model, state_dir=session.state_dir)
    except Exception:
        log.debug("dialect: refining %s failed", model, exc_info=True)
        return []


def ledger_view(session) -> Optional[dict]:
    rec = record_for(session)
    if not rec:
        return None
    return {"placement": rec.get("instruction_placement"), "reserve": rec.get("reply_reserve"),
            "repair": repair_attempts(session), "guard": bool((rec.get("loop_guard") or {}).get("on")),
            "thinking": rec.get("thinking"), "tools_max": rec.get("tools_max"),
            "stop": list(rec.get("stop_quirks") or [])}
