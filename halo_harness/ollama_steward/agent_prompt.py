"""halo_harness.ollama_steward.agent_prompt -- Halo 3.3.4.0 R4: what the
steward's model reads.

`guide()` is the system text: how to write the note, the proposals block,
the one rule ("a smaller window is the answer to a spill, never to an
outgrown conversation", taken from knowledge/symptoms.md's own words) and
every alert kind's meaning (its severity, symptom, cause, Halo-side change
and server-side recommendation from symptoms.md's table, the `[S<n>]` tags
left out). It is built once per process from the knowledge files, so it
never drifts from them, and held under GUIDE_TOKENS (`estimate_tokens`):
the cells are shortened to their first clause, the symptom and the cause
first, until it fits.

`context(ctx, done, events)` is the user text: the hardware card of each host
involved, the ledger's rollups per model, the last 20 events, the findings
(`rules.format_finding`), the fit plans (`fit.format_plan`), the changes
this run made and the machines that called.
"""

from __future__ import annotations

import re
from typing import Optional

GUIDE_TOKENS = 2000
EVENTS = 20
_GUIDE: dict = {}

HEAD = """You are Halo's Ollama steward. Halo records every call to the local model servers (Ollama, llama-server, \
mlx_lm.server, LM Studio) and reads the servers' own logs; you turn what it found into a short note for the person \
who runs them.

Write at most 6 lines in plain words, no headings. Line 1 stands alone in a status line: what went wrong and on \
which machine, or what changed. Then explain the chain: what holds the card, what spilled, which call then was cut, \
trimmed or timed out, and on which machine. Then say what the steward changed (the changes below) or what the \
person should run: copy a server-side line exactly as a finding gives it, with what it costs. Use only the numbers \
you are given.

After the note you may propose a profile change the rules did not make, as one fenced block:
```proposals
[{"key": "<host>|<model>", "field": "num_ctx", "to": 32768, "why": "one short reason"}]
```
The fields: num_ctx, num_predict, keep_alive, tools_max, host_for, compact_at. Each proposal is checked against \
the measured cap and the card's fit before it lands; leave the block out when the rules' changes cover it."""


def _strip(text: str) -> str:
    return re.sub(r"\s*\[S\d+\]", "", str(text or "")).strip()


def first_clause(text: str) -> str:
    """`text` up to its first "; " outside parentheses."""
    depth = 0
    for i, ch in enumerate(text):
        depth += (ch == "(") - (ch == ")")
        if depth == 0 and text.startswith("; ", i):
            return text[:i]
    return text


def _rule_sentence() -> str:
    from halo_harness.ollama_steward.explain import _read
    for para in _read("symptoms").split("\n\n"):
        for sentence in re.split(r"(?<=[.])\s+", _strip(para)):
            if "outgrew" in sentence and "smaller window" in sentence:
                return sentence
    return ""


def _kind_lines(short: "tuple[str, ...]") -> "list[str]":
    from halo_harness.ollama_steward.explain import symptom_rows
    from halo_harness.ollama_steward.server_rules import SEVERITY
    out = []
    for kind, row in symptom_rows().items():
        cell = {k: (first_clause(_strip(v)) if k in short else _strip(v)) for k, v in row.items()}
        sev = f" ({SEVERITY[kind]})" if kind in SEVERITY else ""
        out.append(f"- {kind}{sev}: {cell['symptom']} -> {cell['cause']}. Halo: {cell['Halo-side change']}. "
                   f"Server: {cell['server-side recommendation']}")
    return out


def tokens(text: str) -> int:
    from halo_harness.providers.config import estimate_tokens
    return estimate_tokens(text)


def guide(*, budget: int = GUIDE_TOKENS) -> str:
    """The system text, built once from the knowledge files (under `budget` tokens)."""
    if budget in _GUIDE:
        return _GUIDE[budget]
    rule = _rule_sentence()
    order = ((), ("symptom",), ("symptom", "cause"), ("symptom", "cause", "server-side recommendation"),
             ("symptom", "cause", "server-side recommendation", "Halo-side change"))
    text = ""
    for short in order:
        text = "\n".join([HEAD, "", f"The rule: {rule}", "",
                          "The alert kinds (an event's severity): symptom -> cause. Halo-side change. Server-side change:"]
                         + _kind_lines(short))
        if tokens(text) <= budget:
            break
    _GUIDE[budget] = text
    return text


def _hosts_in(ctx: dict, found: list) -> "list[str]":
    names = []
    for x in [g["host"] for g in ctx.get("groups") or []] + [f.get("host") for f in found]:
        if x and x not in names:
            names.append(x)
    return names


def context(ctx: dict, done: dict, *, events: Optional[list] = None, changes: Optional[list] = None) -> str:
    """The user text for one note."""
    from halo_harness.ollama_steward.fit import format_plan
    from halo_harness.ollama_steward.hardware import format_card
    from halo_harness.ollama_steward.rules import format_finding
    from halo_harness.ollama_steward.server_events import format_event
    from halo_harness.ollama_steward.traffic import format_row, rollup
    found = list(done.get("findings") or [])
    out = [f"Mode: {done.get('mode')} (auto applies changes, review proposes them, off reports only)", "",
           "Hardware cards:"]
    for name in _hosts_in(ctx, found):
        card = (ctx.get("cards") or {}).get(name)
        lines = format_card(card, host_name=name) if card else [f"'{name}': no card read"]
        out += [f"  {x}" for x in lines[:8]]
    rows = rollup(ctx.get("lines") or [], ctx.get("hosts") or [])
    out += ["", "Calls per model (the ledger's window):"] + ([f"  {r['host']} {format_row(r).strip()}" for r in rows]
                                                             or ["  none"])
    machines: dict = {}
    for r in rows:
        for who, n in (r.get("machines") or {}).items():
            machines[who] = machines.get(who, 0) + n
    out += ["", "Machines that called: " + (", ".join(f"{k} {v}" for k, v in machines.items()) or "none")]
    evs = list(events if events is not None else ctx.get("events") or [])[-EVENTS:]
    out += ["", f"The last {len(evs)} server events:"] + ([f"  {format_event(e)}" for e in evs] or ["  none"])
    out += ["", "Findings:"] + ([f"  {x}" for f in found for x in format_finding(f)] or ["  none"])
    plans = [f["plan"] for f in found if isinstance(f.get("plan"), dict)]
    if plans:
        out += ["", "Fit plans:"] + [f"  {x}" for p in plans for x in format_plan(p)]
    said = [c.get("say") or "" for c in (changes if changes is not None else
                                         (done.get("rolled_back") or []) + (done.get("applied") or []))]
    said += [f"proposed (review): {p.get('field')} {p.get('from')} -> {p.get('to')} for {p.get('key')}"
             for p in done.get("proposed") or []]
    out += ["", "Changes this run:"] + ([f"  {x}" for x in said if x] or ["  none"])
    return "\n".join(out)
