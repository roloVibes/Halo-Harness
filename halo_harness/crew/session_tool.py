"""halo_harness.crew.session_tool -- the builder's tools, offered to main in a session (Halo 3.6.0.0 R3, the design's
"In a session"; docs/STUDIO-builder.md).

One implementation: crew/tools.py. The session's `Builder` tool (tools/builder_tool.py) wraps it: main sends
`{tool, args}` or `{changes: [{tool, args}, ...]}` (one card for several), every tool runs as the builder's does (rows,
nothing written), and the person answers ONE approval card:

    question 1   "Apply these N changes? ..." (the lines that let no agent do more)      Apply them / Leave them
    one more per widening line, each its own choice, "No" first                          No / Yes, this line too
    (3.6.0.2 R36: an edited map's "Run new sessions on it instead?" is its own question too, unticked, No first)

3.6.0.2 R36 R37 R54 R21: after the calls, crew/tools_map.card_use_rows adds the "new sessions run on it" row of each
map the card makes (ticked unless it widens) or edits; a card that makes a workflow and a new map running it opens
with R37's line; at Apply a use row whose map file changed is checked again (tools_map.use_recheck); the result ends
with what was written and the sentence main repeats word for word (crew/map_facts.result_tail: S13, or T1).

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
from pathlib import Path

APPLY, LEAVE, NO, YES = "Apply them", "Leave them", "No (leave this line out)", "Yes, this line too"


def _ctx(session, made: list) -> dict:
    return {"cwd": getattr(session, "cwd", None), "state_dir": None, "selection": {}, "made": made, "publish": None,
            "draft": lambda name, does: ("", 0.0), "session": session}  # session: studio_show's facts line (R39)


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
    first = ""
    if rows:
        from halo_harness.crew import tools_map
        try:  # a bug here is a card without these lines, never a crash of the turn
            rows += tools_map.card_use_rows(rows, _ctx(session, rows))
            first = tools_map.first_line(rows, _ctx(session, rows))
        except Exception:
            first = ""
    out = {"rows": rows, "text": "\n".join(([first] if first else []) + texts)}
    if rows:
        out["card"] = card(rows, first)
    return out


def _own(r: dict) -> bool:
    """A line asked on its own, "No" first: a widening line, or an edited map's use row (3.6.0.2 R36)."""
    return bool(r["widen"] or r.get("ask"))


def card(rows: list, first: str = "") -> dict:
    plain = [r for r in rows if not _own(r)]
    wide = [r for r in rows if _own(r)]
    qs = []
    if plain:
        body = "\n".join(([first] if first else []) + [f"  {i}. {r['summary']}" for i, r in enumerate(plain, 1)])
        qs.append({"question": f"Apply these {len(plain)} change{'s' if len(plain) > 1 else ''}? (none lets an agent do more)\n{body}",
                   "header": "Builder", "options": [{"label": APPLY}, {"label": LEAVE}]})
    for k, r in enumerate(wide, len(plain) + 1):
        more = " -- this lets the agent do more; not ticked for you" if r["widen"] else ""
        qs.append({"question": f"{k}. {r['summary']}{more}", "header": f"Line {k}", "options": [{"label": NO}, {"label": YES}]})
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
    plain = [r for r in rows if not _own(r)]
    wide = {k: r for k, r in enumerate([r for r in rows if _own(r)], len(plain) + 1)}
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


def _outcome(outcome: str, wrote=(), undo=None) -> dict:
    return {"outcome": outcome, "wrote": list(wrote), "undo": undo or None}


def _same_path(p) -> str:
    """A path as the system names it: one file through a link (macOS /var is /private/var), another drive-letter case
    or other slashes (Windows) is the same string (P8 batch 2)."""
    import os
    return os.path.normcase(os.path.realpath(str(p)))


def _items(paths, had=frozenset(), removed: bool = False) -> list:
    """3.6.0.2 R25: `[{kind, name, added}]` for the crew files written (config.json, map_use's, is no crew file)."""
    from halo_harness.crew.store import KINDS
    kinds = {v: k for k, v in KINDS.items()}
    known = {_same_path(h) for h in had}
    out = []
    for p in paths or []:
        p = Path(p)
        if p.parent.name in kinds:
            out.append({"kind": kinds[p.parent.name], "name": p.stem, "added": _same_path(p) not in known and not removed,
                        **({"removed": True} if removed else {})})
    return out


def _had(rows: list, ids, cwd) -> set:
    """The ticked rows' crew files that are there before the write (what is changed, not added)."""
    from halo_harness.crew.store import KINDS, path_for
    out = set()
    for r in rows:
        kind, _, name = str(r.get("target") or "").partition(":")
        if r["id"] in ids and kind in KINDS and name:
            path = path_for(kind, name, cwd=cwd)
            if path.is_file():
                out.add(str(path))
    return out


def finish(pv: dict, answer, session) -> str:
    """The card's answer -> what is written, as text; the outcome (`applied | left | failed`, what was written, the
    undo id) is left on `pv["outcome"]` for the `builder_done` frame (3.6.0.2 R25). A raise leaves `failed`."""
    from halo_harness.crew import changes
    pv["outcome"] = _outcome("failed")
    if pv.get("undo"):
        if not any(a.strip().lower().startswith(("apply", "yes")) for _q, a in _said(answer)):
            pv["outcome"] = _outcome("left")
            return f"Left as it is: the change {pv['undo']} was not undone."
        got = changes.undo(pv["undo"])
        if got.get("ok"):  # R25: nothing an undo touches is new -- a body put back, or a file the card made removed
            gone = set(got.get("removed") or [])
            back = [p for p in got.get("restored") or [] if p not in gone]
            pv["outcome"] = _outcome("applied", _items(back, set(back)) + _items(sorted(gone), removed=True))
        return f"Undone: {len(got.get('restored') or [])} file(s) put back." if got.get("ok") else str(got.get("error"))
    ids = chosen(pv["rows"], answer)
    from halo_harness.crew import map_facts
    # 3.6.0.2 R54: a use row whose map changed since the card and now widens -- or whose recheck cannot decide -- is
    # left out (fails closed; the same function as Studio's builder/apply)
    from halo_harness.crew.tools_map import apply_check
    ids, lines = apply_check(pv["rows"], ids, _ctx(session, []))
    left_out = "".join("\n" + line for line in lines)
    if not ids:
        pv["outcome"] = _outcome("left")
        return pv["text"] + left_out + "\nThe person left every line: nothing was written."
    cwd = getattr(session, "cwd", None)
    had = _had(pv["rows"], set(ids), cwd)
    import time
    before = time.time() - 0.001  # crew.map_since's `at` is rounded to 3 decimals
    got = changes.apply(pv["rows"], ids, cwd=cwd)
    if not got["ok"]:
        return pv["text"] + "\nNothing was written: " + "; ".join(got["problems"])
    for r in pv["rows"]:  # 3.6.0.2 R38: the facts note says ", by this session" for a switch this card wrote
        if r["id"] in ids and (r.get("op") or {}).get("op") == "use":
            try:
                session._map_switched_by_me = {"map": (r["op"].get("value") or None), "from": before,
                                               "to": time.time() + 0.001}
            except Exception:
                pass
    pv["outcome"] = _outcome("applied" if got["wrote"] or got["removed"] else "left",
                             _items(got["wrote"], had) + _items(got["removed"], had, removed=True), got["undo_id"])
    left = len(pv["rows"]) - len(ids)
    try:  # 3.6.0.2 R21 + section 4: what was written and the sentence main repeats (S13, or T1)
        used = any(r["id"] in ids and (r.get("op") or {}).get("op") == "use" for r in pv["rows"])
        tail = map_facts.result_tail(session, pv["outcome"]["wrote"], got["undo_id"], used)
    except Exception:
        tail = ""
    return (pv["text"] + f"\nApplied {len(ids)} line(s){f', left {left}' if left else ''}: wrote "
            f"{', '.join(got['wrote'] + got['removed']) or 'nothing'}. Undo id {got['undo_id']} (Builder {{\"undo\": \"{got['undo_id']}\"}}, "
            f"or Undo in Studio). {tail}" + left_out + ("".join(f"\nskipped: {s}" for s in got["skipped"])))


def no_one_to_ask(pv: dict) -> str:
    return pv["text"] + ("\nNot applied: this session has no one to answer the approval card (print mode). Ask in the "
                         "terminal or in Studio's builder box; nothing was written." if pv.get("rows") else "")
