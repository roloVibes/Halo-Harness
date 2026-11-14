"""halo_harness.crew.session_tool -- the builder's tools, offered to main in a session (Halo 3.6.0.0 R3, the design's
"In a session"; docs/STUDIO-builder.md).

One implementation: crew/tools.py. The session's `Builder` tool (tools/builder_tool.py) wraps it: main sends
`{tool, args}` or `{changes: [{tool, args}, ...]}` (one card for several), every tool runs as the builder's does (rows,
nothing written), and the person answers ONE approval card:

    question 1   "Apply these N changes? ..." (the lines that let no agent do more)      Apply them / Leave them
    one more per widening line, each its own choice, "No" first                          No / Yes, this line too

In the terminal it is the question card (the AskUserQuestion round trip, agent/loop.py); in Studio the same lines show
in the session's ask card. Only what the person picked is written (crew/changes.py apply: the format checked first,
the before-image kept, the undo id said back); `{undo: <id>}` puts a change back through the same card. With no one to
answer (print mode) nothing is written and the reply says so. `studio_show` answers at once: it changes nothing.

    preview(session, input) -> {rows, text, card?}     card: the questions; None when nothing would change
    finish(preview, answer, session) -> str             what was written (or left), for main's tool result
"""

from __future__ import annotations

import json
import re

APPLY, LEAVE, NO, YES = "Apply them", "Leave them", "No (leave this line out)", "Yes, this line too"


def _ctx(session, made: list) -> dict:
    return {"cwd": getattr(session, "cwd", None), "state_dir": None, "selection": {}, "made": made, "publish": None,
            "draft": lambda name, does: ("", 0.0)}


def preview(session, input: dict) -> dict:
    from halo_harness.crew import tools
    input = input if isinstance(input, dict) else {}
    if input.get("undo"):
        uid = str(input["undo"])
        return {"rows": [], "text": f"undo {uid}", "undo": uid,
                "card": {"questions": [{"question": f"Put back the change {uid} (every file as it was before)?",
                                        "header": "Undo", "options": [{"label": APPLY}, {"label": LEAVE}]}]}}
    calls = input.get("changes") if isinstance(input.get("changes"), list) else [{"tool": input.get("tool"), "args": input.get("args")}]
    rows: list = []
    texts: list = []
    for call in calls[:12]:
        call = call if isinstance(call, dict) else {}
        if call.get("tool") in ("try_agent", "try_workflow"):
            texts.append(f"{call.get('tool')}: Try it runs from Studio's Agents and Workflows tabs, not from a session")
            continue
        got = tools.run(call.get("tool"), call.get("args"), _ctx(session, rows))
        rows += got.get("rows") or []
        texts.append(f"{call.get('tool')}: {got.get('text')}")
    out = {"rows": rows, "text": "\n".join(texts)}
    if rows:
        out["card"] = card(rows)
    return out


def card(rows: list) -> dict:
    plain = [r for r in rows if not r["widen"]]
    wide = [r for r in rows if r["widen"]]
    qs = []
    if plain:
        body = "\n".join(f"  {i}. {r['summary']}" for i, r in enumerate(plain, 1))
        qs.append({"question": f"Apply these {len(plain)} change{'s' if len(plain) > 1 else ''}? (none lets an agent do more)\n{body}",
                   "header": "Builder", "options": [{"label": APPLY}, {"label": LEAVE}]})
    for k, r in enumerate(wide, len(plain) + 1):
        qs.append({"question": f"{k}. {r['summary']} -- this lets the agent do more; not ticked for you",
                   "header": f"Line {k}", "options": [{"label": NO}, {"label": YES}]})
    return {"questions": qs}


def _said(answer) -> list:
    """Every (question, answer) pair in the card's answer (a dict, a list, or plain words)."""
    if isinstance(answer, str):
        try:
            answer = json.loads(answer)
        except ValueError:
            return [("", answer)]
    if isinstance(answer, dict):
        return [(str(k), str(v)) for k, v in answer.items()]
    if isinstance(answer, list):
        return [("", str(a)) for a in answer]
    return [("", str(answer or ""))]


def chosen(rows: list, answer) -> list:
    """The ids the person picked: the plain lines when they said Apply, a widening line only when its own answer says
    Yes (in plain words: "yes 3" / "line 3")."""
    plain = [r for r in rows if not r["widen"]]
    wide = {k: r for k, r in enumerate([r for r in rows if r["widen"]], len(plain) + 1)}
    ids: list = []
    for q, a in _said(answer):
        low = a.strip().lower()
        if q.startswith("Apply these") or (not q and low.startswith(("apply", "yes"))):
            if low.startswith(("apply", "yes")):
                ids += [r["id"] for r in plain]
        m = re.match(r"^(\d+)\. ", q)
        if m and int(m.group(1)) in wide and low.startswith("yes"):
            ids.append(wide[int(m.group(1))]["id"])
        if not q:
            for n in re.findall(r"(?:yes|line)\s+(\d+)", low):
                if int(n) in wide:
                    ids.append(wide[int(n)]["id"])
    return list(dict.fromkeys(ids))


def finish(pv: dict, answer, session) -> str:
    from halo_harness.crew import changes
    if pv.get("undo"):
        if not any(a.strip().lower().startswith(("apply", "yes")) for _q, a in _said(answer)):
            return f"Left as it is: the change {pv['undo']} was not undone."
        got = changes.undo(pv["undo"])
        return f"Undone: {len(got.get('restored') or [])} file(s) put back." if got.get("ok") else str(got.get("error"))
    ids = chosen(pv["rows"], answer)
    if not ids:
        return pv["text"] + "\nThe person left every line: nothing was written."
    got = changes.apply(pv["rows"], ids, cwd=getattr(session, "cwd", None))
    if not got["ok"]:
        return pv["text"] + "\nNothing was written: " + "; ".join(got["problems"])
    left = len(pv["rows"]) - len(ids)
    return (pv["text"] + f"\nApplied {len(ids)} line(s){f', left {left}' if left else ''}: wrote "
            f"{', '.join(got['wrote'] + got['removed']) or 'nothing'}. Undo id {got['undo_id']} (Builder {{\"undo\": \"{got['undo_id']}\"}}, "
            "or Undo in Studio). Studio follows the files." + ("".join(f"\nskipped: {s}" for s in got["skipped"])))


def no_one_to_ask(pv: dict) -> str:
    return pv["text"] + ("\nNot applied: this session has no one to answer the approval card (print mode). Ask in the "
                         "terminal or in Studio's builder box; nothing was written." if pv.get("rows") else "")
