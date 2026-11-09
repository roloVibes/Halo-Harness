"""halo_harness.ollama_steward.rules_reply_bound -- Halo 3.3.13.1 (the steward hotfix, plans/ROADMAP.md F1): the
reply reserve the reply rules propose (rules_reply.py `reply-cut`, `cut-resent`) is bounded. The owner's PC showed
the loop: each cut reply proposed `max(4096, 2 x num_predict)`, auto mode applied it, the next cut doubled it again,
and the profiles ended at values of 2^160.

- the target comes from the measured cut: twice the cut reply's own length, at least RESERVE_MIN, rounded up to
  1,024 -- never from the profile's current value, so it cannot compound
- never above the model's own context minus the cut call's prompt: the trained context in the catalog's
  `model_info`, else the measured cap, else the profile's window, else the window the call was sent with; and
  never above half the window in use (the profile's, else the one sent), so the prompt keeps the other half
- at most one num_predict proposal per model per hour, whatever the session (the journal's apply and proposal
  rows; the loop ran across sessions, a new one every ten minutes)
- never twice for the same cut (`cut` = "<session>|<at>" in the finding's evidence numbers; a journal row that
  names it holds the proposal back)
- `reserve-loop`: where the old doubling would have proposed again and a bound held it, one finding says so.
"""

from __future__ import annotations

import time
from typing import Optional

RESERVE_MIN = 4096
STEP = 1024
HOUR_S = 3600.0
SANE_MAX = 2 ** 21  # no local model has a window past 2M tokens: a bigger profile value is not a measurement


def say_n(v) -> str:
    """A token count for a line: 4,096; an absurd one by its size (the owner's profiles held 141-digit values)."""
    if isinstance(v, int) and not isinstance(v, bool):
        return f"{v:,}" if v < 10 ** 12 else f"{str(v)[:4]}... ({len(str(v))} digits)"
    return "unset" if v is None else str(v)


def target(cut_reply) -> int:
    n = 2 * cut_reply if isinstance(cut_reply, int) and not isinstance(cut_reply, bool) and cut_reply > 0 else 0
    return max(RESERVE_MIN, -(-n // STEP) * STEP)


def _sane(v) -> Optional[int]:
    return v if isinstance(v, int) and not isinstance(v, bool) and 0 < v <= SANE_MAX else None


def trained(g: dict, ctx: dict) -> Optional[int]:
    """The model's trained context from its catalog row (`<family>.context_length`), or None."""
    row = ((ctx.get("catalogs") or {}).get(g["host"]) or {}).get(g["model"])
    info = row.get("model_info") if isinstance(row, dict) else None
    for k, v in (info.items() if isinstance(info, dict) else ()):
        if str(k).endswith(".context_length") and _sane(v):
            return v
    return None


def model_context(g: dict, ctx: dict, sent=None) -> "tuple[Optional[int], str]":
    t = trained(g, ctx)
    if t:
        return t, "the model's trained context"
    if _sane(g.get("cap")):
        return g["cap"], "the measured cap"
    if _sane((g.get("profile") or {}).get("num_ctx")):
        return g["profile"]["num_ctx"], "the profile's window"
    if _sane(sent):
        return sent, "the window the call was sent with"
    w = _sane((g.get("stats") or {}).get("window"))
    return (w, "the window the calls were sent with") if w else (None, "unknown")


def _journal(ctx: dict) -> list:
    if "_journal" not in ctx:
        from halo_harness.ollama_steward.steward import read_journal
        ctx["_journal"] = read_journal(ctx["state_dir"]) if ctx.get("state_dir") else []
    return ctx["_journal"]


def held(g: dict, ctx: dict, *, session=None, cut=None) -> str:
    """Why a num_predict proposal for this host and model is held back now, or ""."""
    from halo_harness.ollama_steward.ledger import parse_at
    now = ctx.get("now") or time.time()
    for r in _journal(ctx):
        if r.get("key") != g["key"] or r.get("field") != "num_predict" or r.get("kind") not in ("apply", "proposal"):
            continue
        nums = (r.get("evidence") or {}).get("numbers") or {}
        if cut and nums.get("cut") == cut:
            return "a reserve was already proposed for this cut"
        if now - (parse_at(r.get("at")) or 0) < HOUR_S:  # any session: the steward's own runs were a new one each
            return "a reserve was proposed for this model less than an hour ago (at most one an hour)"
    return ""


def reserve(g: dict, ctx: dict, *, reply=None, prompt=None, sent=None, session=None,
            cut=None) -> "tuple[Optional[int], str]":
    """(the num_predict to propose, "") or (None, why none)."""
    current = g["profile"].get("num_predict")
    to = target(reply)
    n, source = model_context(g, ctx, sent)
    if n and isinstance(prompt, int) and not isinstance(prompt, bool):
        room = n - prompt
        to = min(to, room // STEP * STEP)
        if to < RESERVE_MIN:
            return None, (f"{source} ({say_n(n)}) minus the prompt ({say_n(prompt)}) leaves {say_n(max(room, 0))}: "
                          "the prompt has to compact, a bigger reserve cannot fit")
    w = _sane((g.get("profile") or {}).get("num_ctx")) or _sane(sent) or _sane((g.get("stats") or {}).get("window"))
    if w and to > w // 2:  # the window in use keeps at least half for the prompt
        to = w // 2 // STEP * STEP
        if to < RESERVE_MIN:
            return None, (f"the window in use ({say_n(w)}) is too small for a reply reserve of {say_n(RESERVE_MIN)}: "
                          "the prompt compacts, or the window grows (num_ctx)")
    if isinstance(current, int) and not isinstance(current, bool) and current >= to:
        return None, f"the reserve is already {say_n(current)} (the cut asks for {say_n(to)})"
    why = held(g, ctx, session=session, cut=cut)
    return (None, why) if why else (to, "")


def _old_would_propose(g: dict) -> Optional[int]:
    """What the rule before 3.3.13.1 proposed (2 x the current value), when it would have proposed at all."""
    current = g["profile"].get("num_predict") or 0
    to = max(RESERVE_MIN, 2 * current)
    window = g["profile"].get("num_ctx") or g["stats"]["window"]
    to = min(to, window // 4) if window and window // 4 >= RESERVE_MIN else to
    return None if current and to <= current else to


def loop_finding(g: dict, ctx: dict, why: str) -> list:
    """`reserve-loop`: the old doubling would have proposed again from the profile's own value; the bound held it."""
    from halo_harness.ollama_steward.rules import finding
    current, old = g["profile"].get("num_predict"), _old_would_propose(g)
    said = ctx.setdefault("_reserve_loop_said", set())
    if not current or old is None or g["key"] in said:
        return []
    said.add(g["key"])
    return [finding("reserve-loop", g, "warn",
                    f"the reply reserve would have grown again, num_predict {say_n(current)} -> {say_n(old)} "
                    f"(the rule before 3.3.13.1 doubled its own value at each cut, a loop); held: {why}",
                    numbers={"num_predict": say_n(current), "would_have_been": say_n(old), "held": why})]
