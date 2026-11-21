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
{needs: [pdf]}, {says: [words]}, ask (only when I ask), main-decides. `map_use` on a map whose agents may do more than
the map in use says so, amber, unticked -- and so does one whose MAIN gives the next sessions more (a less careful start
mode, more tools: 3.6.0.1), compared in this folder and outside any project (crew.map is global: jf-mapuse). On a map
not in use a line widens nothing by itself (what an agent may do is in its own file); on the map IN USE a line (or a
When off `ask`) that gives main Agent / Task or an agent doing more is a widening row too (jf-mapuse).

3.6.0.2 R36 R37 R54 -- in a session (ctx `session`): a nameless change goes to the map the session runs on (each row
says it takes it at its next hand-off; a box whose agent may do more than the session's main is a widening row); on the
default map it gets no rows, only map_facts.NAME_THE_MAP. A new name makes the map (one create row). After all of a
card's calls, `card_use_rows` adds "new sessions run on it" for each map created (ticked unless it widens) or edited
(its own question, unticked); every widening check of a use row runs on the map as the card leaves it (`_final`,
compiled with the card's agents and workflows), and `use_recheck` checks it again at Apply when the file changed.
`apply_check` is that Apply-time check for both doors (the session's card and Studio's builder box); it fails closed:
a use row it cannot decide is left out (P2 batch 9).
"""

from __future__ import annotations

from halo_harness.crew import map_when, store
from halo_harness.crew.changes import row
from halo_harness.crew.changes_map import USE_TARGET, apply_map
from halo_harness.crew.formats import LINE_WHEN, MAP, circle, name_problem, when_problem
from halo_harness.crew.map_facts import BACK_TO_AUTO, DEFAULT_WORDS, NEXT_HANDOFF, ROW_BOX, ROW_LINE, ROW_NEW_MAP
from halo_harness.crew.spec import MODES


def _t(name: str) -> str:
    return f"map:{name}"


def _tc(ctx):
    """The team control of the session this card is in (None outside a session or with no map)."""
    tc = getattr(ctx.get("session"), "team_control", None)
    return tc if getattr(tc, "is_map", False) else None


def _plain(tc) -> bool:
    from halo_harness.crew.compile import is_default
    return is_default(getattr(tc, "map", None))


def map_name(args: dict, ctx) -> str:
    """The map a change goes to: `map`, else (3.6.0.2 R36, in a session) the map the session runs on -- "" on the
    default map, which a change must name -- else the map open on the tab, else the map in use, else "" (3.6.0.5:
    never a literal default; `_refused` answers a default's name)."""
    got = str(args.get("map") or (ctx.get("selection") or {}).get("map") or "").strip()
    if got:
        return got
    tc = _tc(ctx)
    if tc is not None:
        return "" if _plain(tc) else str(getattr(tc, "map_name", "") or "")
    from halo_harness.crew.compile import in_use
    return in_use(None, ctx.get("cwd"))[0] or ""


def _refused(name: str, args: dict):
    """3.6.0.5 A6: a map edit never goes to a default's name (so `_view` never copies Auto as his map): W16 echoing the
    name he typed in args.map; with none typed (taken from Studio's open map or the map in use), NAME_A_NEW_MAP.
    None for any other name."""
    if not store.is_auto(name):
        return None
    typed = str(args.get("map") or "").strip()
    if typed:
        return {"text": store.default_name_refusal(typed), "rows": []}
    from halo_harness.crew.map_facts import NAME_A_NEW_MAP
    return {"text": NAME_A_NEW_MAP, "rows": []}


def _unnamed(ctx) -> str:
    from halo_harness.crew.map_facts import name_the_map
    return name_the_map(ctx.get("session"))


def _new(name: str, ctx, first=()) -> bool:
    """The map `name` is made in this card (its create row is in it), not edited."""
    return any(r.get("target") == _t(name) and r["op"].get("op") == "create" for r in [*(ctx.get("made") or []), *first])


def _view(name: str, ctx, create: bool = False) -> "tuple[dict | None, list]":
    """(the map as it would be after this turn's rows so far, the rows a not-yours map needs first). `create`: a name
    that is no map yet starts one (3.6.0.2 R36: its create row, main then the boxes)."""
    mine = store.load("map", name, cwd=ctx.get("cwd"), state_dir=ctx.get("state_dir"), scope="yours")
    body = store.clean(mine) if mine else None
    first: list = []
    made = [r for r in ctx.get("made") or [] if r.get("target") == _t(name)]
    if body is None and not any(r["op"].get("op") in ("create", "copy") for r in made):
        there = store.load("map", name, cwd=ctx.get("cwd"), state_dir=ctx.get("state_dir"))
        if there is None:
            if not create or name_problem(name):
                return None, []
            body = {"format": MAP, "name": name, "main": {"agent": "main"}, "boxes": [], "lines": []}
            return body, [row("create", _t(name), ROW_NEW_MAP.format(B=name), {"op": "create", "body": body})]
        body = store.clean(there)
        first = [row("create", _t(name), f"Copy the map {name} ({store.scope_words(there['_scope'])}) as yours (the changes below go into your copy)",
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
    if not name:
        return {"text": _unnamed(ctx), "rows": []}
    if _refused(name, args):
        return _refused(name, args)
    if kind not in ("agent", "workflow") or name_problem(ref):
        return {"text": "kind: agent or workflow, and ref: its name", "rows": []}
    made = any(r.get("target") == f"{kind}:{ref}" and r["op"].get("op") in ("create", "copy") for r in ctx.get("made") or [])
    if not made and store.load(kind, ref, cwd=ctx.get("cwd"), state_dir=ctx.get("state_dir")) is None:
        return {"text": f"no {kind} named {ref}: make it first ({kind}_make)", "rows": []}
    body, first = _view(name, ctx, create=True)
    if body is None:
        return {"text": f"no map named {name}", "rows": []}
    if _box_of(body, ref):
        return {"text": f"{ref} is on the map {name} already (box {_box_of(body, ref)})", "rows": []}
    ids = {b.get("id") for b in body.get("boxes") or [] if isinstance(b, dict)} | {"main"}
    bid = ref if ref not in ids else next(f"{ref}-{i}" for i in range(2, 99) if f"{ref}-{i}" not in ids)
    op = {"op": "map_box_add", "box": {"id": bid, kind: ref}}
    said = (ROW_BOX.format(x=bid, kind=kind, ref=ref) if _new(name, ctx, first)
            else f"On the map {name}: a box for the {kind} {ref} (not connected yet)")
    rows = first + [row("change", _t(name), said, op)]
    return {"text": f"preview: box {bid} on {name}; connect it with map_line_add", "rows": rows}


def map_box_remove(args: dict, ctx) -> dict:
    name = map_name(args, ctx)
    if not name:
        return {"text": _unnamed(ctx), "rows": []}
    if _refused(name, args):
        return _refused(name, args)
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
    if not name:
        return name, None, [], "", "", _unnamed(ctx)
    if _refused(name, args):
        return name, None, [], "", "", _refused(name, args)["text"]
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
    more = _line_more(name, body, op, ctx)  # jf-mapuse: on the map in use, a line may widen as map_use does
    said = (ROW_LINE.format(a=who, x=_box_line(body, b), words=map_when.words(when)) if _new(name, ctx, first)
            else f"On the map {name}: {who} hands work to {_box_line(body, b)}, {map_when.words(when)}")
    return {"text": f"preview: the line {a} -> {b}", "rows": first + [row("change", _t(name), said + more, op, bool(more))]}


def map_line_change(args: dict, ctx) -> dict:
    name, body, first, a, b, bad = _line_args(args, ctx)
    when = parse_when(args.get("when"))
    bad = bad or when_problem(when, LINE_WHEN)
    if not bad and not any(ln.get("from") == a and ln.get("to") == b for ln in body.get("lines") or []):
        bad = f"no line {a} -> {b} on the map {name}: use map_line_add"
    if bad:
        return {"text": bad, "rows": []}
    op = {"op": "map_line_set", "from": a, "to": b, "when": when}
    more = _line_more(name, body, op, ctx)  # jf-mapuse: `ask` -> main decides lets main hand it work on its own
    return {"text": "preview: the line's When", "rows": first + [row("change", _t(name),
            f"On the map {name}: {a} -> {_box_line(body, b)} now {map_when.words(when)}{more}", op, bool(more))]}


def map_line_remove(args: dict, ctx) -> dict:
    name, body, first, a, b, bad = _line_args(args, ctx)
    if not bad and not any(ln.get("from") == a and ln.get("to") == b for ln in body.get("lines") or []):
        bad = f"no line {a} -> {b} on the map {name}"
    if bad:
        return {"text": bad, "rows": []}
    return {"text": "preview: take the line out", "rows": first + [row("change", _t(name),
            f"On the map {name}: take out the line {a} -> {_box_line(body, b)} ({_box_line(body, b)} waits under Not connected yet)",
            {"op": "map_line_remove", "from": a, "to": b})]}


_RANKS = {"default": 0, "acceptEdits": 1, "auto": 2}


def card_body(kind: str, name: str, ctx) -> "dict | None":
    """`kind:name` as the card's rows so far would leave it (EVERY row, ticked or not: the most it may become), else the
    file the store reads; None when neither (3.6.0.2 R54)."""
    from halo_harness.crew.changes import _apply_op
    rows = [r for r in ctx.get("made") or [] if r.get("target") == f"{kind}:{name}" and r["op"].get("op") != "fill"]
    got = None if any(r["op"].get("op") in ("create", "copy") for r in rows) else \
        store.load(kind, name, cwd=ctx.get("cwd"), state_dir=ctx.get("state_dir"))
    body = store.clean(got) if got else None
    for r in rows:
        body = _apply_op(body, r["op"])
    return body


def _overlay(ctx) -> dict:
    """{(kind, name): body} for every agent and workflow the card makes or changes, as it would leave them (yours)."""
    out: dict = {}
    for r in ctx.get("made") or []:
        kind, _, name = str(r.get("target") or "").partition(":")
        if kind in ("agent", "workflow") and (kind, name) not in out:
            got = card_body(kind, name, ctx)
            if got is not None:
                out[(kind, name)] = {**got, "_scope": "yours"}
    return out


def _touched(name: str, ctx) -> bool:
    return any(r.get("target") == _t(name) for r in ctx.get("made") or [])


def _compiled(name: str, ctx, cwd):
    """The map `name` compiled as this card would leave it, seen from `cwd`: by name when the card does not touch it
    (crew/compile.compile_map, the file new sessions read), else its body after the card's rows -- yours -- with the
    card's agents and workflows (R54: one check, on a body)."""
    from halo_harness.crew.compile import compile_map, compile_raw
    sd = ctx.get("state_dir")
    if not _touched(name, ctx):
        return compile_map(name, cwd=cwd, state_dir=sd)
    body = _view(name, {**ctx, "cwd": cwd})[0] or {}
    c = compile_raw(body, name=name, cwd=cwd, state_dir=sd, extra=_overlay({**ctx, "cwd": cwd}))
    c.scope, c.source = "yours", "config"
    return c


def _powers_of(c, ctx) -> dict:
    """agent -> (its tool kinds, its mode rank) for every agent main can reach on the compiled map `c`."""
    agents = dict(c.agents)
    extra = _overlay(ctx)
    for wf in c.workflows.values():  # a workflow box's agents work for the session too
        for s in wf.get("steps") or []:
            for n in (s.get("agents") or []) if isinstance(s, dict) else []:
                got = agents.get(n) or extra.get(("agent", n)) or store.load("agent", n, cwd=ctx.get("cwd"),
                                                                              state_dir=ctx.get("state_dir"))
                if got:
                    agents[n] = got
    return {n: (set(a.get("uses") or []), _RANKS.get(MODES.get(a.get("careful"), "default"), 0)) for n, a in agents.items()}


def _powers(name: str, ctx) -> dict:
    """`_powers_of` the map `name` as the card would leave it (by name when untouched)."""
    return _powers_of(_compiled(name, ctx, ctx.get("cwd")), ctx)


def _use_words(name: str, ctx) -> str:
    """What new sessions on the map `name` (as this card leaves it) may do beyond the map in use, in words ("" when
    nothing): its agents (here, and outside this project) and its main (the mode, the tools)."""
    from halo_harness.crew.compile import in_use
    now, _src = in_use(None, ctx.get("cwd"))
    more: list = []
    for cwd in dict.fromkeys([ctx.get("cwd"), None]) if now else []:  # jf-mapuse: here, and where no project shadows
        here = {**ctx, "cwd": cwd}
        if cwd is None and store.find("map", now, cwd=None, state_dir=ctx.get("state_dir")) is None:
            continue  # the map in use is this project's only: outside, sessions run as the starter does
        had = _powers(now, {**here, "made": []})
        have_all = set().union(*[u for u, _r in had.values()]) if had else set()
        top = max([r for _u, r in had.values()], default=0)
        more += [n for n, (u, r) in _powers(name, here).items() if ((u - have_all) or r > top) and n not in more]
    extra = f" -- its agents may do more than the map {now}'s ({', '.join(more)})" if more else ""
    return extra + _main_more(name, ctx)  # 3.6.0.1: main too -- the mode next sessions start in, the tools main keeps


def _file_mark(name: str, ctx) -> dict:
    """R54: the file new sessions would read for `name` and the sha256 of its bytes now (None for a map made in the
    card), so Apply can tell whether it changed since the card was shown."""
    import hashlib
    got = store.find("map", name, cwd=ctx.get("cwd"), state_dir=ctx.get("state_dir"))
    path = str(got[0]) if got else None
    try:
        with open(path, "rb") as fh:
            return {"file": path, "sha": hashlib.sha256(fh.read()).hexdigest()}
    except (OSError, TypeError):
        return {"file": None, "sha": None}


def map_use(args: dict, ctx) -> dict:
    from halo_harness.crew.compile import in_use
    name = str(args.get("map") or "").strip()
    if not name or (store.find("map", name, cwd=ctx.get("cwd"), state_dir=ctx.get("state_dir")) is None
                    and not _new(name, ctx)):
        return {"text": f"no map named {name!r}", "rows": []}
    now, _src = in_use(None, ctx.get("cwd"))
    if store.is_auto(name):  # 3.6.0.5 (r/batch05): a name of the default is Auto, never his old file of that name
        from halo_harness.crew.compile import DEFAULT_MAP
        if store.is_auto(now):
            return {"text": f"New sessions run on {DEFAULT_WORDS} already.", "rows": []}
        words = _use_words(DEFAULT_MAP, ctx)  # what Auto's agents may do beyond the map in use: unticked, as for any map
        return {"text": f"preview: new sessions run on {DEFAULT_WORDS}", "rows": [row("change", USE_TARGET,
                f"{BACK_TO_AUTO}{words}.", {"op": "use", "value": DEFAULT_MAP, **_file_mark(DEFAULT_MAP, ctx)},
                bool(words))]}
    if now == name:
        return {"text": f"new sessions run on {name} already", "rows": []}
    words = _use_words(name, ctx)
    return {"text": f"preview: new sessions run on {name}", "rows": [row("change", USE_TARGET,
            f"My sessions use the map {name} (config crew.map; a running session keeps its own){words}",
            {"op": "use", "value": name, **_file_mark(name, ctx)}, bool(words))]}


def _main_more(name: str, ctx) -> str:
    """What the map `name` gives main beyond the map in use, in words ("" when nothing): the mode a new session starts
    in and the tools main keeps, both through crew/map_session.start (the session's own rule, never re-derived)."""
    from halo_harness.crew.map_session import RANK, bases, start, start_on
    gained, bits, seen = set(), [], set()
    for cwd, resolved, where in bases(ctx.get("cwd")):  # jf-mapuse: crew.map is global -- this folder AND outside
        kw = {"cwd": cwd, "state_dir": ctx.get("state_dir"), "resolved": resolved}
        m0, t0 = start(None, **kw)
        m1, t1 = start_on(_compiled(name, ctx, cwd), body=True, **kw) if _touched(name, ctx) else start(name, **kw)
        gained |= t1 - t0
        if RANK.get(m1, 99) > RANK.get(m0, 99) and (m0, m1) not in seen:
            bits.append(f"new sessions{where} start in {m1} mode, as its main says (until now {m0})")
        seen.add((m0, m1))
    words = _tool_words(gained)
    bits += [f"its main may use {', '.join(words)}"] if words else []
    return f" -- {'; '.join(bits)}" if bits else ""


def _tool_words(gained: set) -> list:
    from halo_harness.crew.changes import use_word
    from halo_harness.crew.map_session import KINDS
    words = [use_word(k) for k, tools in KINDS.items() if gained & set(tools)]
    return words + ["Hand work to agents"] * bool(gained & {"Agent", "Task"}) + ["Run workflows"] * ("Workflow" in gained)


def _reach(c, cwd, state_dir) -> dict:
    """agent -> its file, for every agent the session on `c` hands work to on main's own say: main's lines that are
    not `ask` (only when the person asks), a workflow's step agents, and the chains on from there (crew/map_run)."""
    from halo_harness.crew.compile import is_default
    if c is None or is_default(c):
        return {}
    out, todo, done = {}, [h for h in c.handoffs if h.get("when") != "ask"], set()
    while todo:
        h = todo.pop()
        if (h["box"], h["name"]) in done:
            continue
        done.add((h["box"], h["name"]))
        if h["kind"] == "agent":
            names = [h["name"]]
        else:
            steps = (c.workflows.get(h["name"]) or {}).get("steps") or []
            names = [n for s in steps if isinstance(s, dict) for n in s.get("agents") or []]
        for n in names:
            got = c.agents.get(n) or store.load("agent", n, cwd=cwd, state_dir=state_dir)
            if got:
                out[n] = got
        todo += [e for e in c.chains.get(h["box"]) or [] if e.get("when") != "ask"]
    return out


def _line_more(name: str, body: dict, op: dict, ctx) -> str:
    """jf-mapuse: what a line row gives the sessions on the map IN USE, in words ("" when nothing, or the map is not
    the one in use): the tools main gains (Agent / Task once it has an agent to hand to) and the agents main now hands
    work to on its own that may do more than main and the agents it reached before. Compared from the map as a session
    runs it now, here and outside this project (bases), so each row is judged as if applied alone."""
    from halo_harness.crew.compile import compile_raw, for_session, in_use, is_default
    from halo_harness.crew.map_session import _ALL, bases, removed_names
    if in_use(None, ctx.get("cwd"))[0] != name:
        return ""
    after = apply_map(body, op)
    ranks = {"default": 0, "acceptEdits": 1, "auto": 2}

    def power(a: dict) -> tuple:
        return set(a.get("uses") or []), ranks.get(MODES.get(a.get("careful"), "default"), 0)

    gained, more = set(), []
    for cwd, _r, _w in bases(ctx.get("cwd")):
        c0 = for_session(None, cwd=cwd, state_dir=ctx.get("state_dir"))[0]
        if c0 is None or c0.name != name:
            continue  # a map with a problem runs as the starter; this edit does not reach that session's map
        c1 = compile_raw(after, name=name, cwd=cwd, state_dir=ctx.get("state_dir"))
        c1.source, c1.scope = c0.source, "yours"
        if c1.problems:
            continue
        keeps = [set(_ALL) - (set() if is_default(c) else set(removed_names(_ALL, c))) for c in (c0, c1)]  # as start()
        gained |= keeps[1] - keeps[0]
        had = [power(c0.main or {})] + [power(a) for a in _reach(c0, cwd, ctx.get("state_dir")).values()]
        have_all, top = set().union(*[u for u, _r in had]), max(r for _u, r in had)
        more += [n for n, a in _reach(c1, cwd, ctx.get("state_dir")).items()
                 if n not in more and ((power(a)[0] - have_all) or power(a)[1] > top)]
    words = _tool_words(gained)
    bits = ([f"main may now hand work to agents that may do more ({', '.join(more)})"] if more else [])
    bits += [f"main may use {', '.join(words)}"] if words else []
    return f" -- {'; '.join(bits)}" if bits else ""


# ---- 3.6.0.2 R36 R37 R54: the Builder in a session ------------------------------------------------------------------
def _box_agents(op: dict, body: dict, ctx) -> list:
    """The agents a box row (or a line row to a box) puts to work: the box's agent(s), or its workflow's step agents."""
    o = op.get("op")
    if o == "map_box_add":
        box = op.get("box") or {}
    elif o == "map_line_add":
        to = (op.get("line") or {}).get("to")
        box = next((b for b in body.get("boxes") or [] if isinstance(b, dict) and b.get("id") == to), {})
    else:
        return []
    if box.get("workflow"):
        wf = card_body("workflow", str(box["workflow"]), ctx) or {}
        return [n for s in wf.get("steps") or [] if isinstance(s, dict) for n in s.get("agents") or []]
    ref = box.get("agent")
    return [str(n) for n in (ref if isinstance(ref, list) else [ref]) if n]


def _beyond(names: list, c, mode: str, ctx) -> bool:
    """An agent of `names` may use a tool kind the session's main (on its map `c`) does not keep, or works less
    carefully than the session's mode (the session's ceiling, as crew/map_session.start reads main)."""
    from halo_harness.crew.map_session import _ALL, KINDS, RANK, removed_names
    keeps = set(_ALL) - set(removed_names(_ALL, c))
    for n in names:
        a = card_body("agent", n, ctx) or {}
        if any(set(KINDS[u]) - keeps for u in a.get("uses") or [] if u in KINDS):
            return True
        if RANK.get(MODES.get(a.get("careful"), "default"), 0) > RANK.get(mode, 1):
            return True
    return False


def _on_running_map(got: dict, ctx) -> dict:
    """R36: a change to the map this session runs on (its own file, yours: crew/map_control.refresh follows it) says
    the session takes it at its next hand-off; a box (or a line to a box) whose agent may do more than the session's
    main is a widening row. A running map that is not yours (a project's, a starter) gets a copy made yours, which the
    session does not follow (no hand-off words) but new sessions may read: the box check runs all the same, and when
    new sessions run on that name, the copy is checked as map_use is (R54, P2 batch 9) -- widening, it is its own
    question, unticked."""
    tc = _tc(ctx)
    rows = got.get("rows") or []
    if tc is None or _plain(tc) or not rows:
        return got
    run = str(getattr(tc, "map_name", "") or "")
    mine = [r for r in rows if r.get("target") == _t(run)]
    if not mine:
        return got
    made = [r for r in [*(ctx.get("made") or []), *rows]  # the copy row, from this call or an earlier one of the card
            if r.get("target") == _t(run) and r["op"].get("op") in ("create", "copy")]
    follows = getattr(tc.map, "scope", "") == "yours" and not made
    here = {**ctx, "made": [*(ctx.get("made") or []), *rows]}
    body = _view(run, here)[0] or {}
    mode = str(getattr(getattr(ctx.get("session"), "permission_engine", None), "mode", None) or "default")
    for r in mine:
        if r in made:
            continue
        if follows:
            r["summary"] += f" -- {NEXT_HANDOFF}"
        if not r["widen"] and _beyond(_box_agents(r["op"], body, here), tc.map, mode, here):
            r["widen"], r["ticked"] = True, False
    from halo_harness.crew.compile import in_use
    if made and in_use(None, ctx.get("cwd"))[0] == run:
        words = _use_words(run, here)
        for r in made:
            if words and not r["widen"]:
                r["summary"] += words
                r["widen"], r["ticked"] = True, False
    return got


def _in_session(fn):
    def run(args: dict, ctx) -> dict:
        return _on_running_map(fn(args, ctx), ctx)
    run.__name__ = fn.__name__
    return run


def card_use_rows(rows: list, ctx) -> list:
    """After all of a session card's calls (crew/session_tool.preview): the use row of each map CREATED in the card
    ("New sessions run on {B}. " + S13, ticked unless it widens) and of each map EDITED that new sessions do not use
    (its own question, unticked) -- never for the session's own map, none when the card has a map_use row of its own
    (that row is checked again on the card's final body). Every check runs on the map as the card leaves it (R54)."""
    from halo_harness.crew import map_facts
    from halo_harness.crew.compile import DEFAULT_MAP
    session = ctx.get("session")
    if session is None:
        return []
    final = {**ctx, "made": list(rows)}
    asked = [r for r in rows if (r.get("op") or {}).get("op") == "use"]
    for r in asked:
        v = r["op"].get("value")
        words = _use_words(v, final) if v and not r["widen"] else ""
        if words:
            r["summary"] += words
            r["widen"], r["ticked"] = True, False
    if asked:
        return []
    tc = _tc(ctx)
    own = str(getattr(tc, "map_name", "") or "") if tc is not None else ""
    nxt = map_facts.next_map()[0] or DEFAULT_MAP
    out: list = []
    for b in dict.fromkeys(r["target"][4:] for r in rows if str(r.get("target") or "").startswith("map:")):
        new = _new(b, final)
        if b == own or (b == nxt and not new):
            continue
        words = _use_words(b, final)
        said = (map_facts.use_new(session, b) if new else map_facts.use_edited(b)) + words
        r = row("change", USE_TARGET, said, {"op": "use", "value": b, **_file_mark(b, ctx)}, bool(words))
        if not new:
            r["ask"], r["ticked"] = True, False  # section 4: an edited map's question, unticked, No first
        out.append(r)
    return out


def use_recheck(rows: list, ids, ctx) -> dict:
    """R54 at Apply: {id: the line saying why} for each picked use row to leave out -- its map file changed since the
    card was shown and, checked again on the file as it is now with the card's picked rows, lets agents do more; or the
    check cannot decide (fails CLOSED): the file cannot be read, a map with no file that the card does not make, or the
    check raises."""
    import hashlib
    from halo_harness.crew import map_facts
    picked = [r for r in rows if r["id"] in set(ids)]
    made = [x for x in picked if (x.get("op") or {}).get("op") != "use"]
    out: dict = {}
    for r in picked:
        op = r.get("op") or {}
        if op.get("op") != "use":
            continue
        b = str(op.get("value") or "")
        if not op.get("file"):  # a map made in the card: written by this same Apply, checked on the card's body
            if b and not _new(b, {"made": made}):
                out[r["id"]] = map_facts.use_unchecked(b, map_facts.UNCHECKED_UNREAD)
            continue
        try:
            with open(op["file"], "rb") as fh:
                sha = hashlib.sha256(fh.read()).hexdigest()
        except OSError:
            out[r["id"]] = map_facts.use_unchecked(b, map_facts.UNCHECKED_UNREAD)
            continue
        if sha == op.get("sha"):
            continue
        try:
            wide = _use_words(b, {**ctx, "made": made})
        except Exception:
            out[r["id"]] = map_facts.use_unchecked(b, map_facts.UNCHECKED_RAISED)
            continue
        if wide:
            out[r["id"]] = map_facts.use_left(b)
    return out


def apply_check(rows: list, ids, ctx) -> "tuple[list, list]":
    """R54 at Apply, the ONE path of both doors (crew/session_tool.finish, studio/builder_api.post_apply): (the ids to
    write, the lines saying which use rows were left out and why). Fails closed: if the recheck itself breaks, every
    picked use row is left out -- a map the agent wrote grants nothing the person did not tick."""
    from halo_harness.crew import map_facts
    ids = list(ids)
    try:
        left = use_recheck(rows, ids, ctx)
    except Exception:
        left = {r["id"]: map_facts.use_unchecked(str((r.get("op") or {}).get("value") or ""), map_facts.UNCHECKED_RAISED)
                for r in rows if r["id"] in set(ids) and (r.get("op") or {}).get("op") == "use"}
    return [i for i in ids if i not in left], [left[r["id"]] for r in rows if r["id"] in left]


def first_line(rows: list, ctx) -> str:
    """R37: "Your {words} workflow: ..." when the card makes a workflow AND a new map with a box running it (a line,
    not a change: no id, nothing written). A15: in a session on Auto, a card that makes a workflow and creates or edits
    no map says FIRST_WORKFLOW_AUTO."""
    from halo_harness.crew.map_facts import FIRST_WORKFLOW, FIRST_WORKFLOW_AUTO
    from halo_harness.crew.tools_flow import step_who
    made = [r["target"][9:] for r in rows if str(r.get("target")).startswith("workflow:") and r["op"].get("op") == "create"]
    final = {**ctx, "made": list(rows)}

    def steps_of(w: str) -> str:
        steps = [s for s in (card_body("workflow", w, final) or {}).get("steps") or [] if isinstance(s, dict)]
        return ", then ".join(step_who(s) for s in steps)
    for r in rows:
        box = (r["op"].get("box") or {}) if r["op"].get("op") == "map_box_add" else {}
        m = str(r.get("target"))[4:]
        if box.get("workflow") in made and _new(m, final):
            w = str(box["workflow"])
            return FIRST_WORKFLOW.format(words=w, W=w, steps=steps_of(w), M=m)
    if made and _plain(_tc(ctx)) and not any(str(r.get("target")).startswith("map:") for r in rows):
        return FIRST_WORKFLOW_AUTO.format(words=made[0], W=made[0], steps=steps_of(made[0]))
    return ""


TOOLS = {
    "map_box_add": (_in_session(map_box_add), '{"map"?, "kind": agent|workflow, "ref"}  (a box, not connected yet)'),
    "map_box_remove": (_in_session(map_box_remove), '{"map"?, "box"}  (the box and its lines)'),
    "map_line_add": (_in_session(map_line_add), '{"map"?, "from" (main or a box / name), "to", "when"?: always|ask|'
                     'main-decides|{"needs": [pdf|images|audio|video|code|review]}|{"says": [words]}}  (a circle is refused)'),
    "map_line_change": (_in_session(map_line_change), '{"map"?, "from", "to", "when"}'),
    "map_line_remove": (_in_session(map_line_remove), '{"map"?, "from", "to"}'),
    "map_use": (map_use, '{"map"}  (what new sessions run on: config crew.map)'),
}
