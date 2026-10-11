"""halo_harness.remote.bridge_cards -- the phone-side text of the session's
cards (Halo 2.0.9 round 3) and the parsing of the replies to them.

Permission card: reply `1` allow once, `2` allow for the session, `3` always
allow, `4` deny (`4 <reason>` sends the reason back to the model).
Question: lettered options (`b`, or `a,c` when several may be picked); any
other text is the answer itself. Plan review: `approve` or `feedback <text>`.
Approval gate: `accept`, `edit <instruction>` or `stop`.
"""

from __future__ import annotations

import re
from typing import Optional

ONE_LINE = 160
PERMISSION_CHOICES = {"1": ("allow", "once", "Allowed once."), "2": ("allow", "session", "Allowed for this session."),
                      "3": ("allow", "always", "Always allowed."), "4": ("deny", "once", "Denied.")}
_PERM_REPLY = re.compile(r"^([1-4])(?:\s+(.+))?$", re.S)


def one_line(text, limit: int = ONE_LINE) -> str:
    s = " ".join(str(text or "").split())
    return s if len(s) <= limit else s[:limit - 3] + "..."


def describe_input(name: str, data) -> str:
    if not isinstance(data, dict):
        return ""
    for key in ("command", "file_path", "path", "url", "pattern", "query", "prompt", "description"):
        if isinstance(data.get(key), str) and data[key].strip():
            return one_line(data[key])
    for v in data.values():
        if isinstance(v, str) and v.strip():
            return one_line(v)
    return ""


def permission_card(data: dict) -> str:
    name = data.get("name") or "a tool"
    lines = [f"Permission needed: {name}"]
    detail = describe_input(name, data.get("input"))
    if detail:
        lines.append(detail)
    reason = one_line(data.get("reason"))
    if reason:
        lines.append(f"Why: {reason}")
    lines += ["1 allow once", "2 allow for this session", "3 always allow", "4 deny (4 <reason> to explain)"]
    return "\n".join(lines)


def parse_permission_reply(text: str) -> "Optional[tuple]":
    """`(action, scope, message, confirmation)` or None."""
    m = _PERM_REPLY.match(text.strip())
    if not m:
        return None
    action, scope, done = PERMISSION_CHOICES[m.group(1)]
    return action, scope, (m.group(2) or "").strip(), done


def normalize_questions(data: dict) -> list:
    """`[{question, options: [label...], multi}]` from either input shape."""
    inp = data.get("input") if isinstance(data, dict) else None
    inp = inp if isinstance(inp, dict) else {}
    qs = inp.get("questions")
    if not isinstance(qs, list) or not qs:
        qs = [inp] if inp.get("question") else []
    out = []
    for q in qs:
        if not isinstance(q, dict) or not q.get("question"):
            continue
        opts = []
        for o in q.get("options") or []:
            label = o.get("label") if isinstance(o, dict) else o
            if label:
                opts.append(str(label))
        out.append({"question": str(q["question"]), "options": opts, "multi": bool(q.get("multiSelect"))})
    return out


def letter(i: int) -> str:
    return chr(ord("a") + i)


def question_card(q: dict, index: int = 0, total: int = 1) -> str:
    head = f"Question {index + 1}/{total}: " if total > 1 else "Question: "
    lines = [head + q["question"]]
    lines += [f"{letter(i)}. {label}" for i, label in enumerate(q["options"])]
    hint = "reply with letters like a,c" if q["multi"] else "reply with a letter"
    lines.append(f"({hint}, or type your own answer)" if q["options"] else "(type your answer)")
    return "\n".join(lines)


def parse_question_reply(q: dict, text: str) -> str:
    """Letters map to the option labels; anything else is the answer verbatim."""
    t = text.strip()
    picks = [p.strip().lower() for p in re.split(r"[,\s]+", t) if p.strip()]
    n = len(q["options"])
    if picks and n and all(len(p) == 1 and 0 <= ord(p) - 97 < n for p in picks):
        if not q["multi"] and len(picks) > 1:
            return t
        return ", ".join(q["options"][ord(p) - 97] for p in picks)
    return t


def plan_card(data: dict) -> str:
    return "Plan ready for review:\n\n" + str(data.get("plan") or "(empty plan)") + \
        "\n\nReply approve, or feedback <your notes>."


def approval_card(data: dict) -> str:
    who = data.get("position") or "the next step"
    head = f"Approval needed ({who})"
    return head + ":\n" + one_line(data.get("text"), 400) + "\nReply accept, edit <instruction>, or stop."


def status_text(st: dict) -> str:
    ctx, lim = st.get("context_tokens"), st.get("context_limit")
    lines = [f"Session: {st.get('title') or '(untitled)'}",
             f"Phase: {st.get('phase', '?')}{' (running)' if st.get('busy') else ''}",
             f"Model: {st.get('model', '?')}  Mode: {st.get('permission_mode', '?')}  Effort: {st.get('effort') or '-'}"]
    if ctx and lim:
        lines.append(f"Context: {ctx * 100 // lim}%")
    if st.get("cost_usd") is not None:
        lines.append(f"Cost: ${st['cost_usd']:.4f}")
    waiting = sum(len(v) for v in (st.get("pending") or {}).values())
    if waiting:
        lines.append(f"Waiting on you: {waiting} card(s)")
    return "\n".join(lines)


def cost_line(st: dict) -> str:
    bits = ["Done."]
    if st.get("cost_usd") is not None:
        bits.append(f"cost ${st['cost_usd']:.4f}")
    elif st.get("total_input_tokens") is not None:
        bits.append(f"in {st['total_input_tokens']} out {st.get('total_output_tokens') or 0} tokens")
    ctx, lim = st.get("context_tokens"), st.get("context_limit")
    if ctx and lim:
        bits.append(f"context {ctx * 100 // lim}%")
    return " ".join(bits[:1]) + (" " + ", ".join(bits[1:]) if len(bits) > 1 else "")
