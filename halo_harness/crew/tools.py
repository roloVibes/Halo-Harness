"""halo_harness.crew.tools -- the builder's tools: configuration only (Halo 3.6.0.0 R1, the design's tool table).

R1 has the agent tools; R2 adds `workflow_*` / `step_*` and R3 `map_*` by putting their entries in TOOLS (same shape):

    agent_make                {name, does, instructions?, model?, needs?, uses?, careful?, more?}
    agent_change              {name, fields: {does?, instructions?, model?, needs?, uses?, careful?, more?}}
    agent_copy                {name, new_name}
    agent_remove              {name}
    agent_draft_instructions  {name, does}          one model call; fills the instructions in the preview

Each `run(name, args, ctx)` answers {text, rows}: `text` is what the builder model reads back, `rows` the change set
(crew/changes.py) that a preview draws. Nothing here writes a file, runs a command, reads a project file or reaches
the web; `ctx` = {cwd, state_dir, selection, draft(name, does) -> (text, cost)}.
"""

from __future__ import annotations

from halo_harness.crew import store
from halo_harness.crew.changes import row, use_word, widens
from halo_harness.crew.formats import AGENT, CAREFUL, MORE_KEYS, agent_problems, name_problem, use_ok

CAREFUL_WORDS = {"ask-changes": "asks before it changes anything", "ask-commands": "changes files on its own, asks before commands",
                 "own": "works on its own (your deny rules still hold)"}
FIELDS = ("does", "instructions", "model", "needs", "uses", "careful", "more")


def _target(name: str) -> str:
    return f"agent:{name}"


def _mine(name: str, ctx) -> "dict | None":
    return store.load("agent", name, cwd=ctx.get("cwd"), state_dir=ctx.get("state_dir"), scope="yours")


def _any(name: str, ctx) -> "dict | None":
    return store.load("agent", name, cwd=ctx.get("cwd"), state_dir=ctx.get("state_dir"))


def _short(text, n: int = 90) -> str:
    t = " ".join(str(text or "").split())
    return t if len(t) <= n else t[: n - 1] + "..."


def _more_rows(name: str, more: dict, before: dict) -> list:
    out = []
    for k, v in (more or {}).items():
        if k in MORE_KEYS:
            op = {"op": "more", "field": k, "value": v}
            out.append(row("change", _target(name), f"{name}: more, {k} = {v if v is not None else 'none'}", op, widens(op, before)))
    return out


def _body_rows(name: str, body: dict, verb: str) -> list:
    """A new agent as rows: the file itself with only what never widens (read, asks before changes), then one row per
    tool beyond reading and one for a less careful mode -- each unticked until the person ticks it."""
    uses = [u for u in body.get("uses") or [] if use_ok(u)]
    base = {"format": AGENT, "name": name, "does": body.get("does") or "", "model": body.get("model") or "auto",
            "uses": [u for u in uses if u == "read"], "careful": CAREFUL[0]}
    for k in ("instructions", "needs"):
        if body.get(k):
            base[k] = body[k]
    more = {k: v for k, v in (body.get("more") or {}).items() if k in MORE_KEYS}
    base["more"] = {k: v for k, v in more.items() if k != "offline" or v}
    rows = [row("create", _target(name), f"{verb} the agent {name}: {_short(base['does'])} (model {base['model']}"
                f"{', may use: Read files' if base['uses'] else ''}, asks before it changes anything)", {"op": verb.lower(), "body": base})]
    for u in uses:
        if u != "read":
            op = {"op": "add_use", "use": u}
            rows.append(row("change", _target(name), f"{name} may use: {use_word(u)}", op, widens(op, base)))
    care = body.get("careful")
    if care in CAREFUL and care != CAREFUL[0]:
        op = {"op": "set", "field": "careful", "value": care}
        rows.append(row("change", _target(name), f"{name}, how careful: {CAREFUL_WORDS[care]}", op, widens(op, base)))
    return rows


def _problems_text(body: dict, name: str) -> str:
    probe = {"format": AGENT, "name": name, "does": body.get("does") or "x", "model": body.get("model") or "auto",
             "careful": body.get("careful") or CAREFUL[0], **{k: body[k] for k in ("uses", "needs", "more", "instructions") if k in body}}
    bad = agent_problems(probe, name=name)
    return "; ".join(bad)


def agent_make(args: dict, ctx) -> dict:
    name = str(args.get("name") or "").strip()
    if name_problem(name):
        return {"text": name_problem(name), "rows": []}
    if _mine(name, ctx):
        return {"text": f"{name} is one of yours already: use agent_change", "rows": []}
    if not str(args.get("does") or "").strip():
        return {"text": "does: one line on what the agent does is needed", "rows": []}
    bad = _problems_text(args, name)
    if bad:
        return {"text": bad, "rows": []}
    rows = _body_rows(name, args, "Create")
    return {"text": f"preview: {len(rows)} line(s) for the new agent {name}", "rows": rows}


def agent_change(args: dict, ctx) -> dict:
    name = str(args.get("name") or "").strip()
    now = _mine(name, ctx)
    if now is None:
        there = _any(name, ctx)
        why = "a starter: agent_copy it first, then change the copy" if there else "no agent of yours by that name"
        return {"text": f"{name}: {why}", "rows": []}
    fields = args.get("fields") if isinstance(args.get("fields"), dict) else {}
    bad = _problems_text({**{k: now.get(k) for k in FIELDS if now.get(k) is not None}, **fields}, name)
    if bad:
        return {"text": bad, "rows": []}
    rows = []
    for k, v in fields.items():
        if k == "uses":
            had = list(now.get("uses") or [])
            for u in [u for u in v if u not in had]:
                op = {"op": "add_use", "use": u}
                rows.append(row("change", _target(name), f"{name} may use: {use_word(u)}", op, widens(op, now)))
            for u in [u for u in had if u not in v]:
                rows.append(row("change", _target(name), f"{name} no longer uses: {use_word(u)}", {"op": "drop_use", "use": u}))
        elif k == "more":
            rows += _more_rows(name, v, now)
        elif k in FIELDS and v != now.get(k):
            op = {"op": "set", "field": k, "value": v}
            words = CAREFUL_WORDS.get(v, "") if k == "careful" else _short(v)
            rows.append(row("change", _target(name), f"{name}, {'what it does' if k == 'does' else k}: {words}", op, widens(op, now)))
    return {"text": f"preview: {len(rows)} change(s) to {name}" if rows else f"{name}: nothing would change", "rows": rows}


def agent_copy(args: dict, ctx) -> dict:
    src, new = str(args.get("name") or "").strip(), str(args.get("new_name") or "").strip()
    body = _any(src, ctx)
    if body is None:
        return {"text": f"no agent named {src}", "rows": []}
    if name_problem(new) or _mine(new, ctx):
        return {"text": name_problem(new) or f"{new} is one of yours already", "rows": []}
    rows = _body_rows(new, {k: body.get(k) for k in FIELDS if body.get(k) is not None}, "Copy")
    rows[0]["summary"] = f"Copy {src} as {new}: " + rows[0]["summary"].split(": ", 1)[1]
    return {"text": f"preview: {new}, a copy of {src}", "rows": rows}


def agent_remove(args: dict, ctx) -> dict:
    name = str(args.get("name") or "").strip()
    if _mine(name, ctx) is None:
        return {"text": f"{name}: no agent of yours by that name", "rows": []}
    uses = store.used_by(name, cwd=ctx.get("cwd"), state_dir=ctx.get("state_dir"))
    if uses:
        return {"text": f"{name} is used by {', '.join(uses)}: take it out there first", "rows": []}
    return {"text": f"preview: delete {name}", "rows": [row("remove", _target(name), f"Delete the agent {name}", {"op": "remove"})]}


def agent_draft_instructions(args: dict, ctx) -> dict:
    name = str(args.get("name") or "").strip()
    does = str(args.get("does") or "").strip()
    unsaved = (ctx.get("selection") or {}).get("unsaved") or {}
    now = _mine(name, ctx)
    does = does or str((now or {}).get("does") or unsaved.get("does") or "")
    if name_problem(name) or not does:
        return {"text": "name and does are needed to draft instructions", "rows": []}
    text, _cost = ctx["draft"](name, does)
    if not text:
        return {"text": "the draft came back empty", "rows": []}
    if now is not None and not unsaved:
        op = {"op": "set", "field": "instructions", "value": text}
        return {"text": "preview: the drafted instructions", "rows": [row("change", _target(name), f"{name}, instructions: {_short(text, 120)}", op)]}
    op = {"op": "fill", "field": "instructions", "value": text}
    return {"text": "preview: the drafted instructions, put into the form", "rows": [row("fill", _target(name), f"Put the drafted instructions into {name}'s form: {_short(text, 100)}", op)]}


TOOLS = {
    "agent_make": (agent_make, '{"name", "does", "instructions"?, "model"? (a catalog ref or auto), "needs"?, "uses"? '
                   '[read|edit|bash|web|skill:<n>|mcp:<server>], "careful"? ask-changes|ask-commands|own, "more"?}'),
    "agent_change": (agent_change, '{"name", "fields": {any of does, instructions, model, needs, uses, careful, more}}'),
    "agent_copy": (agent_copy, '{"name", "new_name"}'),
    "agent_remove": (agent_remove, '{"name"}  (deletes the file, once no workflow or map uses it)'),
    "agent_draft_instructions": (agent_draft_instructions, '{"name", "does"}  (drafts the instructions it gets)'),
}


def run(name: str, args, ctx) -> dict:
    got = TOOLS.get(str(name))
    if got is None:
        return {"text": f"no tool {name!r}; the tools are {', '.join(TOOLS)}", "rows": []}
    try:
        return got[0](args if isinstance(args, dict) else {}, ctx)
    except Exception as e:  # a tool bug is a line the model reads, never a crash of the turn
        return {"text": f"{name} failed: {type(e).__name__}: {str(e)[:160]}", "rows": []}
