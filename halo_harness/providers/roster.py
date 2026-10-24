"""halo_harness.providers.roster -- the model roster (Halo 3.1.9.0 R1): what
each model in this Halo's catalog is good at, as one short block the main
agent reads, so it can pick a model for a sub-task on purpose (the Agent
tool's `model`).

`roster_block(state_dir, rows)` -> at most `MAX_LINES` lines: a heading, the
strongest and the cheapest model per kind (`capabilities.KINDS`), then one
line per model -- ref, price in/out per 1M tokens, context, what it takes
in, tools, reasoning, the kinds it is best at, and what this host measured
-- the session's own model first, then every model the per-kind lines name,
then the local ones, then the rest by how many kinds they cover. Names
only: model refs, never a key, a host URL or a path. 3.1.9.0 R3: a model
that keeps failing a task kind here leaves that kind's leaders, and one
line after them says so with its numbers (outcomes/learn.py).

The agent loop appends it as a user-role snapshot of kind `roster` through
`roster_snapshot_text` at the three snapshot sites (a new session, `/clear`,
after compaction), main session only, so the system prompt itself stays
byte-stable. Config `models.roster` (default true) turns it off;
`HALO_MODELS_ROSTER=0/1` overrides the config (the test suite's default is
0, the Governor's pattern).
"""

from __future__ import annotations

import os
from typing import Optional

MAX_LINES = 40
HEADING = ("# Model roster (what each model in this Halo's catalog is good at; prices are USD per 1M tokens "
           "in/out; name one with the Agent tool's `model` when a sub-task needs it)")
_IN = (("text", "text"), ("image", "image"), ("audio", "audio"), ("video", "video"), ("pdf", "pdf"))
# 3.1.9.0 R3: a task kind (outcomes/kinds.py) -> the roster kinds whose leaders a model dropped for it leaves;
# the other task kinds (plan, review, writing, check, other) have no per-kind line, only the drop line
DROP_KINDS = {"code": ("code",), "research": ("research",), "media": ("visual", "audio", "video")}


def roster_enabled() -> bool:
    flag = (os.environ.get("HALO_MODELS_ROSTER") or "").strip().lower()
    if flag in ("0", "false", "no", "off"):
        return False
    if flag in ("1", "true", "yes", "on"):
        return True
    try:
        from halo_harness.theme import get_config_value
        return bool(get_config_value("models.roster", default=True))
    except Exception:
        return True


def _money(v) -> str:
    if not isinstance(v, (int, float)) or isinstance(v, bool):
        return "?"
    if v <= 0:
        return "$0"
    return f"${v:.2f}" if v < 100 else f"${v:.0f}"


def _ctx(v) -> str:
    from halo_harness.model_display import format_token_count
    return (format_token_count(v) or "?") + " ctx"


def _measured_words(m) -> str:
    if not isinstance(m, dict):
        return ""
    parts = []
    gym = m.get("gym") if isinstance(m.get("gym"), dict) else None
    if gym and isinstance(gym.get("score"), (int, float)):
        parts.append(f"gym {gym['score']:.2f}")
    if isinstance(m.get("tokens_per_second"), (int, float)):
        parts.append(f"{m['tokens_per_second']:.0f} tok/s")
    if isinstance(m.get("ttft_s"), (int, float)):
        parts.append(f"{m['ttft_s']:.1f}s first token")
    if m.get("tools_probe") is not None:
        parts.append("tool probe " + ("ok" if m["tools_probe"] else "failed"))
    if m.get("tools_rejected"):
        parts.append("rejects tools")
    canary = m.get("canary") if isinstance(m.get("canary"), dict) else None
    if canary:
        parts.append("canary " + ("ok" if canary.get("ok") else "failed"))
    from halo_harness.outcomes.measured import row_words  # 3.1.8.0 R3: checked tasks per kind, "code 4/5"
    if row_words(m.get("outcomes")):
        parts.append(row_words(m.get("outcomes")))
    return ", ".join(parts)


def model_line(ref: str, entry: dict) -> str:
    f = entry.get("facts") or {}
    price = "free (local)" if f.get("local") else f"{_money(f.get('price_in_per_m'))}/{_money(f.get('price_out_per_m'))}"
    mi = f.get("modalities_in")
    ins = "+".join(name for key, name in _IN if key in mi) if isinstance(mi, list) and mi else "?"
    tools = {True: "tools", False: "no tools"}.get(f.get("tools"), "tools ?")
    r = f.get("reasoning") if isinstance(f.get("reasoning"), dict) else None
    reasoning = "reasoning" if r and r.get("kind") in ("native", "openai") else ("no reasoning" if r else "reasoning ?")
    kinds = ",".join(entry.get("kinds") or []) or "-"
    line = f"- {ref}  {price}  {_ctx(f.get('context_tokens'))}  in {ins}  {tools}  {reasoning}  best at {kinds}"
    measured = _measured_words(f.get("measured"))
    return line + (f"  measured: {measured}" if measured else "")


def _order(entries: dict, best: dict, current_ref: str) -> list:
    named = [current_ref] if current_ref in entries else []
    for pick in best.values():
        for ref in (pick.get("strongest"), pick.get("cheapest")):
            if ref and ref not in named:
                named.append(ref)
    local = sorted(ref for ref, e in entries.items() if (e.get("facts") or {}).get("local") and ref not in named)
    rest = sorted((ref for ref in entries if ref not in named and ref not in local),
                  key=lambda ref: (-len(entries[ref].get("kinds") or []), ref))
    return named + local + rest


def _drops(state_dir, entries: dict) -> list:
    """3.1.9.0 R3: `[(kind, model, stat)]` of this catalog's models dropped for a task kind (outcomes/learn.py)."""
    try:
        from halo_harness.outcomes.learn import dropped, numbers, settings
        cfg = settings()
        return dropped(numbers(state_dir, cfg), cfg, refs=set(entries)) if cfg["enabled"] else []
    except Exception:
        return []


def _without(entries: dict, best: dict, drops: list) -> dict:
    """The per-kind leaders with each dropped model out of the kinds its task kind maps to (`DROP_KINDS`)."""
    from halo_harness.models_best_at import best_per_kind
    gone: dict = {}
    for task_kind, ref, _s in drops:
        for kind in DROP_KINDS.get(task_kind, ()):
            gone.setdefault(kind, set()).add(ref)
    out = dict(best)
    for kind, refs in gone.items():
        if kind in out and {out[kind].get("strongest"), out[kind].get("cheapest")} & refs:
            again = best_per_kind({ref: e for ref, e in entries.items() if ref not in refs}).get(kind)
            if again:
                out[kind] = again
            else:  # no other model is good at the kind: its line goes, the drop line says why
                del out[kind]
    return out


def roster_block(state_dir, rows: Optional[list] = None, *, current_ref: str = "", stale_ok: bool = False) -> str:
    """The roster text ("" when the catalog has no model). `rows`: the
    catalog rows to describe (default: the best-at cache's own, the catalog
    as `halo models` lists it); `stale_ok`: see `models_best_at.index`.
    3.1.9.0 R3: a model dropped for a task kind (outcomes/learn.py) leaves
    that kind's leaders, and one line names it with its numbers."""
    from halo_harness.models_best_at import best_per_kind, index
    cache = index(state_dir, rows, stale_ok=stale_ok)
    entries = cache.get("rows") or {}
    if rows is not None:
        wanted = {r.get("ref") for r in rows if r.get("ref")}
        entries = {ref: e for ref, e in entries.items() if ref in wanted}
    if not entries:
        return ""
    drops = _drops(state_dir, entries)
    best = _without(entries, best_per_kind(entries), drops) if drops else best_per_kind(entries)
    lines = [HEADING, "Per kind, the strongest (and the cheapest when it differs):"]
    for kind, pick in best.items():
        cheap = pick.get("cheapest")
        lines.append(f"- {kind}: {pick['strongest']}" + (f"; cheapest {cheap}" if cheap and cheap != pick["strongest"] else ""))
    if drops:
        from halo_harness.outcomes.learn import drop_line
        lines.append(drop_line(drops))
    lines.append("Models:")
    order = _order(entries, best, current_ref)
    room = MAX_LINES - len(lines) - (1 if len(order) > MAX_LINES - len(lines) else 0)
    lines += [model_line(ref, entries[ref]) for ref in order[:max(0, room)]]
    if len(order) > room:
        lines.append(f"- (+{len(order) - room} more: `halo models analyze` lists every model)")
    return "\n".join(lines[:MAX_LINES])


def roster_snapshot_text(state_dir, *, current_ref: str = "") -> str:
    """The `roster` snapshot's text, "" when it is off or nothing is listed."""
    if state_dir is None or not roster_enabled():
        return ""
    try:
        return roster_block(state_dir, current_ref=current_ref, stale_ok=True)
    except Exception:
        return ""
