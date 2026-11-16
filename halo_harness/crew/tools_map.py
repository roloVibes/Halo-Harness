"""halo_harness.crew.tools_map -- the builder's map tools (Halo 3.6.0.0 R3, the design's tool table).

    map_box_add      {map?, kind: agent | workflow, ref}          a box on the map ("not connected yet" until a line)
    map_box_remove   {map?, box}                                  the box and its lines
    map_line_add     {map?, from, to, when?}                      from / to: a box id or the agent / workflow name
    map_line_change  {map?, from, to, when}
    map_line_remove  {map?, from, to}
    map_use          {map}                                        config `crew.map`: what new sessions run

`map` defaults to the map open on the Map tab, else the map in use, else `starter`. A map that is not yours yet (a
starter, the project's) is copied as yours first: one create line, then the change lines. A line that would make a
circle is refused in one sentence (the file format refuses it too: crew/formats.py). When in words: always,
{needs: [pdf]}, {says: [words]}, ask (only when I ask), main-decides. A map line widens nothing by itself (what an agent
may do is in its own file); `map_use` on a map whose agents may do more than the map in use says so, amber, unticked --
and so does one whose MAIN gives the next sessions more (a less careful start mode, more tools: 3.6.0.1).
"""

from __future__ import annotations

from halo_harness.crew import map_when, store
from halo_harness.crew.changes import row
from halo_harness.crew.changes_map import USE_TARGET, apply_map
from halo_harness.crew.formats import LINE_WHEN, circle, name_problem, when_problem
from halo_harness.crew.spec import MODES


def _t(name: str) -> str:
    return f"map:{name}"


def map_name(args: dict, ctx) -> str:
    got = str(args.get("map") or (ctx.get("selection") or {}).get("map") or "").strip()
    if got:
        return got
    from halo_harness.crew.compile import in_use
    return in_use(None, ctx.get("cwd"))[0] or "starter"


def _view(name: str, ctx) -> "tuple[dict | None, list]":
    """(the map as it would be after this turn's rows so far, the rows a not-yours map needs first)."""
    mine = store.load("map", name, cwd=ctx.get("cwd"), state_dir=ctx.get("state_dir"), scope="yours")
    body = store.clean(mine) if mine else None
    first: list = []
    made = [r for r in ctx.get("made") or [] if r.get("target") == _t(name)]
    if body is None and not any(r["op"].get("op") in ("create", "copy") for r in made):
        there = store.load("map", name, cwd=ctx.get("cwd"), state_dir=ctx.get("state_dir"))
        if there is None:
            return None, []
        body = store.clean(there)
        first = [row("create", _t(name), f"Copy the {there['_scope']} map {name} as yours (the changes below go into your copy)",
                     {"op": "copy", "body": body})]
    for r in made:
        o = r["op"].get("op")
        body = r["op"]["body"] if o in ("create", "copy") else apply_map(body or {}, r["op"])
    return body, first


def _box_of(body: dict, ref: str) -> str:
    """The box id `ref` means: a box id, main, or the agent / workflow a box holds."""
    ref = str(ref or "").strip()
    if ref == "main":
        return "main"
    boxes = [b for b in body.get("boxes") or [] if isinstance(b, dict)]
    for b in boxes:
        if b.get("id") == ref:
            return ref
    for b in boxes:
        held = b.get("agent") if isinstance(b.get("agent"), list) else [b.get("agent")]
        if ref in held or b.get("workflow") == ref:
            return b["id"]
    return ""


def parse_when(w):
    if isinstance(w, str):
        s = w.strip().lower()
        for k in ("needs", "says"):
            if s.startswith(k):
                return {k: [x.strip() for x in s[len(k):].lstrip(": ").split(",") if x.strip()]}
        return {"main decides": "main-decides", "only when i ask": "ask", "": "main-decides"}.get(s, s)
    return w if w is not None else "main-decides"


def _box_line(body: dict, bid: str) -> str:
    b = next((x for x in body.get("boxes") or [] if isinstance(x, dict) and x.get("id") == bid), {})
    return b.get("workflow") or (", ".join(b["agent"]) if isinstance(b.get("agent"), list) else b.get("agent")) or bid


def map_box_add(args: dict, ctx) -> dict:
    name, kind, ref = map_name(args, ctx), str(args.get("kind") or "agent"), str(args.get("ref") or "").strip()
    if kind not in ("agent", "workflow") or name_problem(ref):
        return {"text": "kind: agent or workflow, and ref: its name", "rows": []}
    made = any(r.get("target") == f"{kind}:{ref}" and r["op"].get("op") in ("create", "copy") for r in ctx.get("made") or [])
    if not made and store.load(kind, ref, cwd=ctx.get("cwd"), state_dir=ctx.get("state_dir")) is None:
        return {"text": f"no {kind} named {ref}: make it first ({kind}_make)", "rows": []}
    body, first = _view(name, ctx)
    if body is None:
        return {"text": f"no map named {name}", "rows": []}
    if _box_of(body, ref):
        return {"text": f"{ref} is on the map {name} already (box {_box_of(body, ref)})", "rows": []}
    ids = {b.get("id") for b in body.get("boxes") or [] if isinstance(b, dict)} | {"main"}
    bid = ref if ref not in ids else next(f"{ref}-{i}" for i in range(2, 99) if f"{ref}-{i}" not in ids)
    op = {"op": "map_box_add", "box": {"id": bid, kind: ref}}
    rows = first + [row("change", _t(name), f"On the map {name}: a box for the {kind} {ref} (not connected yet)", op)]
    return {"text": f"preview: box {bid} on {name}; connect it with map_line_add", "rows": rows}


def map_box_remove(args: dict, ctx) -> dict:
    name = map_name(args, ctx)
    body, first = _view(name, ctx)
    bid = _box_of(body or {}, str(args.get("box") or args.get("ref") or ""))
    if body is None or not bid or bid == "main":
        return {"text": "no such box on the map (main stays)", "rows": []}
    gone = [f"{ln['from']} -> {ln['to']}" for ln in body.get("lines") or [] if bid in (ln.get("from"), ln.get("to"))]
    words = f" and its line{'s' if len(gone) > 1 else ''} {', '.join(gone)}" if gone else ""
    return {"text": "preview: take the box out", "rows": first + [row("change", _t(name),
            f"On the map {name}: take out {_box_line(body, bid)}{words}", {"op": "map_box_remove", "id": bid})]}


def _line_args(args: dict, ctx):
    name = map_name(args, ctx)
    body, first = _view(name, ctx)
    if body is None:
        return name, None, first, "", "", f"no map named {name}"
    a, b = _box_of(body, args.get("from") or "main"), _box_of(body, args.get("to"))
    if not a or not b:
        return name, body, first, a, b, f"both ends are boxes on the map {name} (add one with map_box_add first)"
    return name, body, first, a, b, ""


def map_line_add(args: dict, ctx) -> dict:
    name, body, first, a, b, bad = _line_args(args, ctx)
    when = parse_when(args.get("when"))
    bad = bad or ("nothing hands work to main" if b == "main" else "") or when_problem(when, LINE_WHEN)
    if bad:
        return {"text": bad, "rows": []}
    if any(ln.get("from") == a and ln.get("to") == b for ln in body.get("lines") or []):
        return {"text": f"{a} -> {b} is there already: use map_line_change", "rows": []}
    loop = circle([ln for ln in body.get("lines") or [] if isinstance(ln, dict)] + [{"from": a, "to": b}])
    if loop:
        return {"text": f"Refused: {a} -> {b} would make a circle ({' -> '.join(loop)}); a loop lives inside a workflow as repeat until.", "rows": []}
    op = {"op": "map_line_add", "line": {"from": a, "to": b, "when": when}}
    who = "main" if a == "main" else _box_line(body, a)
    return {"text": f"preview: the line {a} -> {b}", "rows": first + [row("change", _t(name),
            f"On the map {name}: {who} hands work to {_box_line(body, b)}, {map_when.words(when)}", op)]}


def map_line_change(args: dict, ctx) -> dict:
    name, body, first, a, b, bad = _line_args(args, ctx)
    when = parse_when(args.get("when"))
    bad = bad or when_problem(when, LINE_WHEN)
    if not bad and not any(ln.get("from") == a and ln.get("to") == b for ln in body.get("lines") or []):
        bad = f"no line {a} -> {b} on the map {name}: use map_line_add"
    if bad:
        return {"text": bad, "rows": []}
    op = {"op": "map_line_set", "from": a, "to": b, "when": when}
    return {"text": "preview: the line's When", "rows": first + [row("change", _t(name),
            f"On the map {name}: {a} -> {_box_line(body, b)} now {map_when.words(when)}", op)]}


def map_line_remove(args: dict, ctx) -> dict:
    name, body, first, a, b, bad = _line_args(args, ctx)
    if not bad and not any(ln.get("from") == a and ln.get("to") == b for ln in body.get("lines") or []):
        bad = f"no line {a} -> {b} on the map {name}"
    if bad:
        return {"text": bad, "rows": []}
    return {"text": "preview: take the line out", "rows": first + [row("change", _t(name),
            f"On the map {name}: take out the line {a} -> {_box_line(body, b)} ({_box_line(body, b)} waits under Not connected yet)",
            {"op": "map_line_remove", "from": a, "to": b})]}


def _powers(name: str, ctx) -> dict:
    """agent -> (its tool kinds, its mode rank) for every agent main can reach on the map `name`."""
    from halo_harness.crew.compile import compile_map
    c = compile_map(name, cwd=ctx.get("cwd"), state_dir=ctx.get("state_dir"))
    ranks = {"default": 0, "acceptEdits": 1, "auto": 2}
    agents = dict(c.agents)
    for wf in c.workflows.values():  # a workflow box's agents work for the session too
        for s in wf.get("steps") or []:
            for n in (s.get("agents") or []) if isinstance(s, dict) else []:
                got = agents.get(n) or store.load("agent", n, cwd=ctx.get("cwd"), state_dir=ctx.get("state_dir"))
                if got:
                    agents[n] = got
    return {n: (set(a.get("uses") or []), ranks.get(MODES.get(a.get("careful"), "default"), 0)) for n, a in agents.items()}


def map_use(args: dict, ctx) -> dict:
    from halo_harness.crew.compile import in_use
    name = str(args.get("map") or "").strip()
    if not name or store.find("map", name, cwd=ctx.get("cwd"), state_dir=ctx.get("state_dir")) is None:
        return {"text": f"no map named {name!r}", "rows": []}
    now, _src = in_use(None, ctx.get("cwd"))
    if now == name:
        return {"text": f"new sessions run on {name} already", "rows": []}
    had = _powers(now, ctx) if now else {}
    have_all = set().union(*[u for u, _r in had.values()]) if had else set()
    top = max([r for _u, r in had.values()], default=0)
    more = [n for n, (u, r) in _powers(name, ctx).items() if (u - have_all) or r > top] if now else []
    extra = f" -- its agents may do more than the map {now}'s ({', '.join(more)})" if more else ""
    main_more = _main_more(name, ctx)  # 3.6.0.1: main too -- the mode next sessions start in, the tools main keeps
    return {"text": f"preview: new sessions run on {name}", "rows": [row("change", USE_TARGET,
            f"My sessions use the map {name} (config crew.map; a running session keeps its own){extra}{main_more}",
            {"op": "use", "value": name}, bool(more or main_more))]}


def _main_more(name: str, ctx) -> str:
    """What the map `name` gives main beyond the map in use, in words ("" when nothing): the mode a new session starts
    in and the tools main keeps, both through crew/map_session.start (the session's own rule, never re-derived)."""
    from halo_harness.crew.changes import use_word
    from halo_harness.crew.map_session import KINDS, RANK, configured_mode, start
    kw = {"cwd": ctx.get("cwd"), "state_dir": ctx.get("state_dir"), "resolved": configured_mode(ctx.get("cwd"))}
    (m0, t0), (m1, t1) = start(None, **kw), start(name, **kw)
    gained = t1 - t0
    words = [use_word(k) for k, tools in KINDS.items() if gained & set(tools)]
    words += ["Hand work to agents"] * bool(gained & {"Agent", "Task"}) + ["Run workflows"] * ("Workflow" in gained)
    bits = ([f"new sessions start in {m1} mode, as its main says (until now {m0})"] if RANK.get(m1, 99) > RANK.get(m0, 99) else [])
    bits += [f"its main may use {', '.join(words)}"] if words else []
    return f" -- {'; '.join(bits)}" if bits else ""


TOOLS = {
    "map_box_add": (map_box_add, '{"map"?, "kind": agent|workflow, "ref"}  (a box, not connected yet)'),
    "map_box_remove": (map_box_remove, '{"map"?, "box"}  (the box and its lines)'),
    "map_line_add": (map_line_add, '{"map"?, "from" (main or a box / name), "to", "when"?: always|ask|main-decides|'
                     '{"needs": [pdf|images|audio|video|code|review]}|{"says": [words]}}  (a circle is refused)'),
    "map_line_change": (map_line_change, '{"map"?, "from", "to", "when"}'),
    "map_line_remove": (map_line_remove, '{"map"?, "from", "to"}'),
    "map_use": (map_use, '{"map"}  (what new sessions run on: config crew.map)'),
}
