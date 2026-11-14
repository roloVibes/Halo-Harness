"""halo_harness.crew.runner_text -- the words the step runner sends and reads (Halo 3.6.0.0 R2, crew/runner.py).

    step_prompt(wf, step, i, request, carry, prev, rnd, agent)   what one agent of a step is asked
    hand_on(calls) -> text            each agent's reply under its name: the next step's input
    check_prompt(until, hand, step)   the one yes/no question after a step that repeats
    said_yes(text) -> bool            the check's answer: its first word is yes

Everything the agents and the person wrote (the request, what a step handed on) goes in labelled as what it is.
"""

from __future__ import annotations

import re

_YES = re.compile(r"^\W*(yes|no)\b", re.I)


def short(text, n: int = 160) -> str:
    t = str(text or "").strip()
    return t if len(t) <= n else t[: n - 3] + "..."


def first_line(text) -> str:
    for ln in str(text or "").splitlines():
        if ln.strip():
            return short(ln.strip(), 200)
    return ""


def step_prompt(wf: dict, step: dict, i: int, request: str, carry: str, prev: str, rnd: int, agent: str) -> str:
    others = [a for a in step.get("agents") or [] if a != agent]
    lines = [f"You are {agent}, working on step {i} \"{step.get('name')}\" of the workflow {wf.get('name')}"
             f" ({str(wf.get('for') or '').strip()})."]
    if others:
        lines.append(f"{', '.join(others)} work on this step at the same time as you; do your own part.")
    lines.append(f"The request:\n{request}")
    gets = str(step.get("gets") or "").strip()
    if carry:
        lines.append(f"You get {gets or 'what the step before handed on'}. What the step before handed on:\n{carry}")
    elif gets:
        lines.append(f"You get: {gets} (from the request above).")
    hands = str(step.get("hands") or "").strip()
    if rnd > 1 and prev:
        until = str((step.get("repeat") or {}).get("until") or "")
        lines.append(f"Round {rnd}: after the last round the check \"{until}\" said no. What this step handed on then:\n{prev}\n"
                     "Do the step again and fix what kept the check from saying yes.")
    lines.append(f"Hand on {hands or 'your result'}: end your reply with it, plainly.")
    return "\n\n".join(lines)


def hand_on(calls: list) -> str:
    """`[(name, Call)]` -> one text: each agent's reply under its name (one agent: its reply alone)."""
    good = [(n, c) for n, c in calls if c.ok]
    if len(good) == 1 and len(calls) == 1:
        return str(good[0][1].text or "").strip()
    return "\n\n".join(f"{n}:\n{str(c.text or '').strip()}" for n, c in good)


def check_prompt(until: str, hand: str, step: dict) -> str:
    return (f"A check after the step \"{step.get('name')}\". Change nothing. Is this true now: \"{until}\"?\n"
            "Look if you need to, then answer with one word first -- yes or no -- and one line why.\n\n"
            f"What the step handed on:\n{hand}")


def said_yes(text) -> bool:
    m = _YES.match(str(text or ""))
    return bool(m and m.group(1).lower() == "yes")
