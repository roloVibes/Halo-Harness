"""halo_harness.crew.tools_flow -- the builder's workflow tools (Halo 3.6.0.0 R2, the design's tool table).

    workflow_make    {name, for, steps: [{name, agents, gets?, hands?, when?, repeat?}], own_copy?, max_usd?}
    workflow_change  {name, fields: {for?, own_copy?, max_usd?}}
    workflow_copy    {name, new_name}
    workflow_remove  {name}                      refused while a map has a box for it (the reply says which)
    step_add         {workflow, step: {...}, index?}     index: 1-based place (the end when left out)
    step_change      {workflow, index, fields: {...}}
    step_move        {workflow, index, to}
    step_remove      {workflow, index}

Each answers {text, rows} like the agent tools (crew/tools.py): a new workflow is a create line holding no steps, then
one line per step, so the person ticks the steps they want. A step naming an agent that is not one of theirs is said
in the text: the builder proposes it with agent_make (a proposal card in the preview, with "make it"). A workflow line
widens nothing by itself: what its agents may use is in each agent's own file, and the agent's own lines say it.
"""

from __future__ import annotations

from halo_harness.crew import store
from halo_harness.crew.changes import row
from halo_harness.crew.formats import WORKFLOW, name_problem, workflow_problems
from halo_harness.crew.store import step_clean

WHEN_WORDS = {"always": "always", "ask": "only when you ask"}


def _t(name: str) -> str:
    return f"workflow:{name}"


def _mine(name: str, ctx):
    return store.load("workflow", name, cwd=ctx.get("cwd"), state_dir=ctx.get("state_dir"), scope="yours")


def _any(name: str, ctx):
    return store.load("workflow", name, cwd=ctx.get("cwd"), state_dir=ctx.get("state_dir"))


def when_words(when) -> str:
    if when in (None, "always", "ask"):
        return WHEN_WORDS[when or "always"]
    if isinstance(when, dict) and when.get("needs"):
        return "only when the task needs " + ", ".join(map(str, when["needs"]))
    if isinstance(when, dict) and when.get("says"):
        return "only when the task says " + ", ".join(map(str, when["says"]))
    return str(when)


def step_line(s: dict) -> str:
    rep = s.get("repeat") if isinstance(s.get("repeat"), dict) else None
    bits = [f"{s.get('name')} ({' + '.join(s.get('agents') or []) or 'no agent'})", when_words(s.get("when"))]
    if s.get("hands"):
        bits.append(f"hands on {s['hands']}")
    if rep:
        bits.append(f"repeat until {rep.get('until')}, at most {rep.get('max', 3)} times")
    return " · ".join(bits)


def _missing(steps: list, ctx) -> list:
    out: list = []
    for s in steps:
        for a in (s.get("agents") or []) if isinstance(s, dict) else []:
            if a not in out and store.load("agent", a, cwd=ctx.get("cwd"), state_dir=ctx.get("state_dir")) is None:
                out.append(a)
    return out


def _step_problem(s) -> str:
    probe = {"format": WORKFLOW, "name": "probe", "for": "x", "steps": [step_clean(s) if isinstance(s, dict) else s]}
    bad = workflow_problems(probe)
    return bad[0].replace("step 1", "the step") if bad else ""


def _note_missing(text: str, steps: list, ctx) -> str:
    miss = _missing(steps, ctx)
    if miss:
        text += (f". Not an agent of theirs yet: {', '.join(miss)} -- propose each with agent_make (a card the person "
                 "can make), or use one of theirs")
    return text


def workflow_make(args: dict, ctx) -> dict:
    name = str(args.get("name") or "").strip()
    if name_problem(name):
        return {"text": name_problem(name), "rows": []}
    if _mine(name, ctx):
        return {"text": f"{name} is one of your workflows already: use step_add / step_change / workflow_change", "rows": []}
    steps = [s for s in args.get("steps") or [] if isinstance(s, dict)]
    if not str(args.get("for") or "").strip():
        return {"text": "for: one line on what the workflow is for is needed", "rows": []}
    for s in steps:
        p = _step_problem(s)
        if p:
            return {"text": p, "rows": []}
    body = {"format": WORKFLOW, "name": name, "for": str(args["for"]).strip(), "steps": []}
    if isinstance(args.get("own_copy"), bool):
        body["own_copy"] = args["own_copy"]
    if isinstance(args.get("max_usd"), (int, float)) and not isinstance(args.get("max_usd"), bool) and args["max_usd"] > 0:
        body["max_usd"] = args["max_usd"]
    rows = [row("create", _t(name), f"Create the workflow {name}: {str(body['for'])[:90]}", {"op": "create", "body": body})]
    for i, s in enumerate(steps, 1):
        rows.append(row("change", _t(name), f"{name}, step {i}: {step_line(s)}", {"op": "step_add", "step": step_clean(s), "index": None}))
    return {"text": _note_missing(f"preview: the workflow {name} with {len(steps)} step(s)", steps, ctx), "rows": rows}


def workflow_change(args: dict, ctx) -> dict:
    name = str(args.get("name") or "").strip()
    now = _mine(name, ctx)
    if now is None:
        why = "a starter: workflow_copy it first" if _any(name, ctx) else "no workflow of yours by that name"
        return {"text": f"{name}: {why}", "rows": []}
    rows = []
    for k, v in (args.get("fields") or {}).items():
        if k not in ("for", "own_copy", "max_usd"):
            return {"text": f"{k}: change steps with step_add / step_change / step_move / step_remove", "rows": []}
        if v != now.get(k):
            rows.append(row("change", _t(name), f"{name}, {k}: {v}", {"op": "step_wf", "field": k, "value": v}))
    return {"text": f"preview: {len(rows)} change(s) to {name}" if rows else f"{name}: nothing would change", "rows": rows}


def workflow_copy(args: dict, ctx) -> dict:
    src, new = str(args.get("name") or "").strip(), str(args.get("new_name") or "").strip()
    body = _any(src, ctx)
    if body is None:
        return {"text": f"no workflow named {src}", "rows": []}
    if name_problem(new) or _mine(new, ctx):
        return {"text": name_problem(new) or f"{new} is one of yours already", "rows": []}
    copy = {**store.clean(body), "name": new}
    return {"text": f"preview: {new}, a copy of {src}",
            "rows": [row("create", _t(new), f"Copy the workflow {src} as {new} ({len(copy.get('steps') or [])} steps)", {"op": "copy", "body": copy})]}


def workflow_remove(args: dict, ctx) -> dict:
    name = str(args.get("name") or "").strip()
    if _mine(name, ctx) is None:
        return {"text": f"{name}: no workflow of yours by that name", "rows": []}
    maps = store.maps_with(name, cwd=ctx.get("cwd"), state_dir=ctx.get("state_dir"))
    if maps:
        return {"text": f"{name} is on the map {', '.join(maps)}: take it off there first", "rows": []}
    return {"text": f"preview: delete {name}", "rows": [row("remove", _t(name), f"Delete the workflow {name}", {"op": "remove"})]}


def _target(args: dict, ctx):
    name = str(args.get("workflow") or args.get("name") or "").strip()
    now = _mine(name, ctx)
    if now is None and not any(r.get("target") == _t(name) for r in ctx.get("made") or []):
        why = "a starter: workflow_copy it first" if _any(name, ctx) else "no workflow of yours by that name (workflow_make makes one)"
        return name, None, f"{name}: {why}"
    return name, now or {"steps": []}, ""


def step_add(args: dict, ctx) -> dict:
    name, now, err = _target(args, ctx)
    if err:
        return {"text": err, "rows": []}
    s = args.get("step") if isinstance(args.get("step"), dict) else {}
    p = _step_problem(s)
    if p:
        return {"text": p, "rows": []}
    at = args.get("index") if isinstance(args.get("index"), int) else None
    where = f"as step {at}" if at else "at the end"
    r = row("change", _t(name), f"{name}, a new step {where}: {step_line(s)}", {"op": "step_add", "step": step_clean(s), "index": at})
    return {"text": _note_missing(f"preview: a new step in {name}", [s], ctx), "rows": [r]}


def _index(args, now, key="index"):
    i = args.get(key)
    n = len(now.get("steps") or [])
    return i if isinstance(i, int) and not isinstance(i, bool) and 1 <= i <= n else None


def step_change(args: dict, ctx) -> dict:
    name, now, err = _target(args, ctx)
    i = None if err else _index(args, now)
    if err or i is None:
        return {"text": err or f"{name}: index is a step number 1-{len(now.get('steps') or [])}", "rows": []}
    fields = {k: v for k, v in (args.get("fields") or {}).items()}
    probe = step_clean({**now["steps"][i - 1], **fields})
    p = _step_problem({k: v for k, v in probe.items() if v not in (None, "", [], {})})
    if p:
        return {"text": p, "rows": []}
    words = ", ".join(f"{k} {when_words(v) if k == 'when' else v}" for k, v in fields.items())
    r = row("change", _t(name), f"{name}, step {i} ({now['steps'][i - 1].get('name')}): {words}", {"op": "step_set", "index": i, "fields": fields})
    return {"text": _note_missing(f"preview: step {i} of {name}", [probe], ctx), "rows": [r]}


def step_move(args: dict, ctx) -> dict:
    name, now, err = _target(args, ctx)
    i, to = (None, None) if err else (_index(args, now), _index(args, now, "to"))
    if err or i is None or to is None:
        return {"text": err or f"{name}: index and to are step numbers 1-{len(now.get('steps') or [])}", "rows": []}
    s = now["steps"][i - 1]
    return {"text": f"preview: move step {i} of {name}",
            "rows": [row("change", _t(name), f"{name}: move step {i} ({s.get('name')}) to step {to}", {"op": "step_move", "index": i, "to": to})]}


def step_remove(args: dict, ctx) -> dict:
    name, now, err = _target(args, ctx)
    i = None if err else _index(args, now)
    if err or i is None:
        return {"text": err or f"{name}: index is a step number", "rows": []}
    s = now["steps"][i - 1]
    return {"text": f"preview: take step {i} out of {name}",
            "rows": [row("remove", _t(name), f"{name}: take out step {i} ({s.get('name')})", {"op": "step_remove", "index": i})]}


_STEP = '{"name", "agents": [names: several work at the same time], "gets"?, "hands"?, "when"? always|ask|{"needs": [pdf|images|audio|video|code|review]}|{"says": [words]}, "repeat"? {"until": words, "max": 1-10}}'
TOOLS = {
    "workflow_make": (workflow_make, '{"name", "for", "steps": [' + _STEP + '], "own_copy"?, "max_usd"?}'),
    "workflow_change": (workflow_change, '{"name", "fields": {any of for, own_copy, max_usd}}'),
    "workflow_copy": (workflow_copy, '{"name", "new_name"}'),
    "workflow_remove": (workflow_remove, '{"name"}  (deletes the file, once no map has it)'),
    "step_add": (step_add, '{"workflow", "step": ' + _STEP + ', "index"? (1-based place; the end when left out)}'),
    "step_change": (step_change, '{"workflow", "index" (1-based), "fields": {any step field; null takes it out}}'),
    "step_move": (step_move, '{"workflow", "index", "to"}'),
    "step_remove": (step_remove, '{"workflow", "index"}'),
}
