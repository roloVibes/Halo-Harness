"""tests.test_map_truth -- Halo 3.6.0.2 R19 (with R4, R14-R18, R20-R24, R28-R31, R35, R41, R43, R45, R47 and section 4 of
the design): every sentence a person reads about which map a session runs on, the status line, Agents -> Map's lines and
the words Live / Feed / Map, built once in routes/crew/map/truth.ts and run in node through tests/helpers/node_ts.py (no
browser, no wall clock: every time is a fixed local instant of 2026-01-15, every {t} is matched as clock(t)).

1. each truth state's lines, letter for letter (T1-T12, Empty), Agents -> Map's L1-L4 and every other line of the rules;
2. S13 says "starter (the default)" for the default, and its terminal tail;
3. one locale-aware formatter for every time (matched by pattern, never a fixed format);
4. the order T7, S13, the started line, T5/T6, decided by whether the session is open, never by whether it is busy;
5. the status line: who works (working rows only), on what, waiting for whom, the cost, the hand-offs outside the map;
6. the worst case the truth block reserves at 408 and 360 px;
7. the words in one place (WORDS, WAS), and no banned word in any output.
Run: python -m tests.test_map_truth   (HALO_NODE_TS_TRANSPILE=1 runs it the way a node without TypeScript does)
"""
from __future__ import annotations

import json
import re
import shutil
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from tests.helpers.runner import Ctx, new_registry, print_results, run_all  # noqa: E402

test, TESTS = new_registry()
MAPDIR = Path(__file__).resolve().parent.parent / "halo_harness" / "studio" / "ui" / "src" / "routes" / "crew" / "map"
TIMES = ["00:05", "09:07", "10:24", "11:30", "11:40", "12:30", "12:45", "23:59"]
DEF = "starter (the default)"
BASE = dict(title="fix-login", a="starter", plain=True, b=None, bSince=None, started="@10:24", turns=2, studio=False,
            ended=None, machine=None, unreadable=None, changed=None, workflow=None, busy=False)
STATES = {
    "T1": dict(BASE, a="shop", plain=False, b="shop", bSince="@09:07"),
    "T1 b=a": dict(BASE, a="review-flow", plain=False, b="review-flow", bSince="@11:30"),
    "T2": dict(BASE, a="shop", plain=False, b="review-flow", bSince="@11:30"),
    # the coordinator accepted it (P3 batch 8): T2 when {B} was switched on before this session started
    "T2 switched before": dict(BASE, a="shop", plain=False, b="review-flow", bSince="@09:07"),
    "T3": dict(BASE),
    "T3 with B": dict(BASE, b="review-flow", bSince="@11:30"),
    "T4": dict(BASE, a=None, plain=False),
    "T8": dict(BASE, a="shop", plain=False, ended="@12:45"),
    "T9": dict(BASE, a="review-flow", plain=False, machine="gpu-box"),
    "T10": dict(BASE, studio=True, turns=0, b="review-flow"),
    "T11": dict(BASE, a="shop", plain=False, b="review-flow"),
    "T12": dict(BASE, a="review-flow", plain=False, unreadable="~/maps/review-flow.yaml"),
    "Empty": dict(BASE, none=True, b="review-flow"),
    "Empty unset": dict(BASE, none=True),
    # the coordinator's ruling (P4 batch 10): new sessions with no map (roles off, crew.map unset: the row's map_next_none)
    "T2 no map next": dict(BASE, a="starter", plain=False, bNone=True),
    "T10 no map next": dict(BASE, studio=True, turns=0, bNone=True),
    "Empty no map next": dict(BASE, none=True, bNone=True),
}
S13 = "This session keeps running on {0}, as it started. Start a new session to run on {1}."
NEW = {"act": "new-session", "label": "New session"}
WANT = {
    "T1": ("T1", [("This session runs on shop, as it started at {10:24}. New sessions will too.", None)]),
    "T1 b=a": ("T1", [("This session runs on review-flow, as it started at {10:24}. New sessions will too.", None)]),
    "T2": ("T2", [(S13.format("shop", "review-flow"), NEW),
                  ("It started at {10:24}, before review-flow was switched on at {11:30}.", None)]),
    "T2 switched before": ("T2", [(S13.format("shop", "review-flow"), NEW), ("It started at {10:24}.", None)]),
    "T3": ("T3", [("This session runs on starter (the default), as it started at {10:24}. On starter main chooses who to "
                   "hand work to; the dashed lines show what it chose.", None)]),
    "T3 with B": ("T2", [(S13.format(DEF, "review-flow"), NEW),
                         ("It started at {10:24}, before review-flow was switched on at {11:30}.", None)]),
    "T4": ("T4", [("This session runs with no map, as it started at {10:24}: main does the work and starts its own agents.",
                   None)]),
    "T8": ("T8", [("This session ended at {12:45}. It ran on shop.", None)]),
    "T9": ("T9", [("fix-login runs on review-flow on gpu-box. Its drawing is in that machine's Studio.", None)]),
    "T10": ("T10", [("New session from Studio, no message yet. It will run on review-flow.", None)]),
    "T11": ("T11", [(S13.format("shop", "review-flow"), NEW),
                    ("It started at {10:24}. review-flow was set outside Halo, so when it was switched on is not known.",
                     None)]),
    "T12": ("T12", [("This session runs on review-flow from ~/maps/review-flow.yaml, which Studio cannot read here.", None)]),
    "Empty": ("Empty", [("No session is open here. New sessions will run on review-flow.", NEW)]),
    "Empty unset": ("Empty", [("No session is open here. New sessions will run on starter (the default).", NEW)]),
    "T2 no map next": ("T2", [("This session runs on starter, as it started at {10:24}. New sessions will run with no map.", None)]),
    "T10 no map next": ("T10", [("New session from Studio, no message yet. It will run with no map.", None)]),
    "Empty no map next": ("Empty", [("No session is open here. New sessions will run with no map.", NEW)]),
}
BANNED = re.compile(r"\b(in use|lineup|bio|cast|helpers?|delegating)\b", re.I)
TASK60 = "rewrite the retry loop of the client so it backs off and logs"

HEAD = """const T = await import(%s);
const at = (s) => { const [h, m] = s.split(':').map(Number); return new Date(2026, 0, 15, h, m).getTime() / 1000; };
const fx = (o) => JSON.parse(JSON.stringify(o), (k, v) => typeof v === 'string' && v[0] === '@' ? at(v.slice(1)) : v);
const clk = {}; for (const s of %s) clk[s] = T.clock(at(s));
const D = fx(%s); const out = {};
"""
# Every function of truth.ts, called once over the facts the other tests use: the words test scans all of it.
ALL = """
const st = (f) => ({ state: T.truthState(f), lines: T.truthLines(f) });
out.states = Object.fromEntries(Object.entries(D.states).map(([k, f]) => [k, st(f)]));
const t = at('12:30');
out.L = [T.mapLine({ kind: 'L1', session: 'fix-login' }),
  T.mapLine({ kind: 'L2', on: [{ session: 'fix-login', a: 'starter', plain: true }] }),
  T.mapLine({ kind: 'L2', on: [{ session: 'a', a: 'x', plain: false }, { session: 'b', a: 'starter', plain: true },
                               { session: 'c', a: 'y', plain: false }] }),
  T.mapLine({ kind: 'L3', session: 'fix-login', workflow: 'W', a: 'starter', plain: true }),
  T.mapLine({ kind: 'L4', map: 'review-flow', session: 'fix-login', t })];
out.bits = {
  start1: T.startLines('review-flow', { map: 'review-flow', t }), start2: T.startLines(null, { map: 'review-flow', t }),
  start3: T.startLines('review-flow', null),
  head1: T.blockHead('W', 3, 6), head2: T.blockHead('W'),
  steps: ['done', 'working', 'next', 'failed'].map((s) => T.stepRow(3, 'test', 'tester', 'm-small', s)),
  agent: T.agentRow('coder', 'm-code', 'working'), madeUp: T.madeUpRow(D.task, 'working'), more: T.moreRows(4),
  trace1: T.traceHover(1, t, 'fix the retry'), trace3: T.traceHover(3, t, 'fix the retry'), off: T.offHover('coder'),
  ended: T.endedAt(t), openMap: T.openMapAt('coder'), card: T.openInAgents(),
  pick1: T.pickerSuffix(['fix-login']), pick2: T.pickerSuffix(['a', 'b']), pickNext: T.pickerSuffix([], true),
  switch: T.switchLabel(), removed: T.removedAt(t), tag: T.newTag(t), pair: T.pair('starter (the default)', 'review-flow'),
  jbW: T.justBuilt('workflow', { workflow: 'W' }), jbRun: T.justBuilt('running', { t }), jbOther: T.justBuilt('other', { t }),
  jbOtherNext: T.justBuilt('other', { t, map: 'review-flow', next: 'review-flow' }),
  jbOtherNot: T.justBuilt('other', { t, map: 'review-flow', next: 'starter' }),
  hover1: T.hoverLines({ name: 'coder', workflow: null, model: 'm-code', state: 'working', when: 'always', source: 'main',
                         children: ['made up: check it · working'], built: t }),
  hover2: T.hoverLines({ name: 'check', workflow: 'W', model: 'm-small', state: 'next', when: 'always', source: 'main',
                         children: [], built: null }),
  unreached: T.unreachedHead(), workflows: T.workflowsHead(),
};
out.status = D.status.map((s) => T.statusLine(s));
out.s13 = [T.s13(T.mapName('starter', true), 'review-flow'), T.s13(T.mapName('starter', true), 'review-flow', true),
           T.s13(T.mapName('shop', false), 'review-flow')];
out.reserve = T.reserve(D.states.T2, 408);
"""
STATUS = [
    dict(state="working", rows=[dict(name="planner", state="done"), dict(name="coder", state="done"),
                                dict(name="tester", state="working"), dict(name="reviewer", state="next")],
         what="", workflow=dict(name="W", step=3, of=6), waiting="model", cost=2.42, off=0),
    dict(state="working", rows=[dict(name="main", state="working")], what="reading client.py", workflow=None, waiting=None,
         cost=0.12, off=0),
    dict(state="working", rows=[dict(name=n, state="working") for n in ("a", "b", "c")], what="editing files", workflow=None,
         waiting="you", cost=1.5, off=0),
    dict(state="working", rows=[dict(name="coder", state="working"), dict(name="reviewer", state="waiting")],
         what="running tests", workflow=None, waiting="reviewer", cost=0.9, off=0),
    dict(state="idle", rows=[], what="", workflow=None, waiting=None, cost=0.4, off=0),
    dict(state="done", rows=[], what="", workflow=None, waiting=None, cost=1.1, off=0),
]


def _url(name: str, folder: Path = MAPDIR) -> str:
    return json.dumps((folder / name).resolve().as_uri())


def ts(body: str, data: dict | None = None, url: str | None = None):
    from tests.helpers import node_ts
    data = dict(states=STATES, status=STATUS, task=TASK60, **(data or {}))
    js = HEAD % (url or _url("truth.ts"), json.dumps(TIMES), json.dumps(data)) + body + "\nconsole.log(JSON.stringify({clk, out}));"
    r = node_ts.run(js)
    return r["clk"], r["out"]


def X(clk: dict, s: str) -> str:
    return re.sub(r"\{(\d\d:\d\d)\}", lambda m: clk[m[1]], s)


def texts(lines) -> list:
    return [ln.get("text", "") for ln in lines]


def strings(o) -> list:
    if isinstance(o, str):
        return [o]
    if isinstance(o, dict):
        return [s for v in o.values() for s in strings(v)]
    if isinstance(o, list):
        return [s for v in o for s in strings(v)]
    return []


def sources() -> dict:
    return {p.name: p.read_text(encoding="utf-8") for p in sorted(MAPDIR.glob("truth*.ts"))}


@test
def test_truth_each_state(ctx: Ctx):
    clk, out = ts(ALL)
    for k, (state, lines) in WANT.items():
        got = out["states"][k]
        ctx.check(f"{k}: the state is {state}, got {got['state']}", got["state"] == state)
        want = [X(clk, t) for t, _ in lines]
        ctx.check(f"{k}: the lines are the design's, got {texts(got['lines'])}", texts(got["lines"]) == want)
        for i, (_, act) in enumerate(lines):
            g = got["lines"][i] if i < len(got["lines"]) else {}
            ctx.check(f"{k}: line {i} carries {act}, got {g}",
                      (act is None and "act" not in g) or (act is not None and g.get("act") == act["act"] and g.get("label") == act["label"]))
    # Agents -> Map's lines (L1-L4)
    L = out["L"]
    want_l = [("fix-login runs on this map now.", "watch-live", "Watch it in Live"),
              ("fix-login runs on starter (the default), as it started; new sessions run on this map.", "watch-live",
               "Watch it in Live"),
              ("3 sessions run on other maps, as they started; new sessions run on this map.", "watch-live",
               "Watch them in Live"),
              ("fix-login is running the workflow W from this map. It runs on starter (the default), as it started.",
               "watch-live", "Watch it in Live"),
              (X(clk, "review-flow was just built in fix-login at {12:30}."), "open-it", "Open it")]
    for i, (text, act, label) in enumerate(want_l):
        g = L[i]
        ctx.check(f"Agents -> Map line {i}: {text!r} [{label}], got {g}",
                  len(g) == 1 and g[0].get("text") == text and g[0].get("act") == act and g[0].get("label") == label)
        ctx.check(f"L line {i} says none of 'another map', 'not lit', 'in use'",
                  not any(w in g[0].get("text", "") for w in ("another map", "not lit", "in use")))
    # every other line of the rules
    b = out["bits"]
    first = "No session is open here. New sessions will run on review-flow."
    ctx.check(f"R4 start view, B = X, got {b['start1']}",
              texts(b["start1"]) == [first, X(clk, "Your last session built the map review-flow at {12:30}. New sessions run on it.")]
              and b["start1"][-1].get("act") == "new-session" and b["start1"][-1].get("label") == "New session")
    ctx.check(f"R4 start view, B unset: no 'New sessions run on it.', got {texts(b['start2'])}",
              texts(b["start2"]) == ["No session is open here. New sessions will run on starter (the default).",
                                      X(clk, "Your last session built the map review-flow at {12:30}.")])
    ctx.check(f"R4 start view, no build seen: one sentence + [New session], got {b['start3']}",
              texts(b["start3"]) == [first] and b["start3"][0].get("act") == "new-session")
    exact = {
        "head1": "workflow W · step 3 of 6", "head2": "workflow W",
        "steps": [f"3 test · tester · m-small · {s}" for s in ("done", "working", "next", "failed")],
        "agent": "coder · m-code · working", "madeUp": f"made up: {TASK60[:40]} · working", "more": "+4 more",
        "trace1": X(clk, "Carried 1 hand-off; last at {12:30}: fix the retry"),
        "trace3": X(clk, "Carried 3 hand-offs; last at {12:30}: fix the retry"),
        "off": "Not on the map: coder started this itself", "ended": X(clk, "ended at {12:30}"),
        "openMap": "Open the map at coder", "pick1": " · running in fix-login", "pick2": " · running in 2 sessions",
        "pickNext": " · new sessions", "switch": "New sessions run on this",
        "removed": X(clk, "This map was removed at {12:30}."), "tag": X(clk, "new {12:30}"),
        "pair": ["Running: starter (the default)", "Just built: review-flow"],
        "hover1": ["coder", "agent", "m-code", "working", "Starts when: always (from main)", "made up: check it · working",
                   X(clk, "Built {12:30} in this session")],
        "hover2": ["check", "workflow W", "m-small", "next", "Starts when: always (from main)"],
        "unreached": "Not connected yet: no line from main reaches these, so this session never runs them.",
        "workflows": "Workflows are fixed lists of steps. A session runs a map, and a box on a map can run a workflow: see Map.",
    }
    for k, v in exact.items():
        ctx.check(f"{k} = {v!r}, got {b[k]!r}", b[k] == v)
    ctx.check(f"the step-in card's link is [Open in Agents -> Live], got {b['card']}",
              b["card"].get("label") == "Open in Agents -> Live" and b["card"].get("act") == "open-agents-live")
    ctx.check(f"R31 a workflow on no map, got {b['jbW']}",
              b["jbW"].get("text") == "Just built: the workflow W. It is on no map, so no session runs it yet."
              and b["jbW"].get("act") == "open-workflows" and b["jbW"].get("label") == "Open in Workflows")
    ctx.check(f"R31 the running map, got {b['jbRun']}",
              b["jbRun"] == {"text": X(clk, "Changed in this session at {12:30}; this session takes it at its next hand-off.")})
    ctx.check(f"R31 any other map, got {b['jbOther']}",
              b["jbOther"] == {"text": X(clk, "Just built in this session at {12:30}. This session does not run on it.")})
    ctx.check(f"R31 (+ R36's row) another map new sessions now run on, got {b['jbOtherNext']}",
              b["jbOtherNext"] == {"text": X(clk, "Just built in this session at {12:30}. This session does not run on it. "
                                                  "New sessions run on review-flow.")})
    ctx.check(f"R31 another map new sessions do not run on: no use sentence, got {b['jbOtherNot']}",
              b["jbOtherNot"] == b["jbOther"])


@test
def test_s13_says_the_default(ctx: Ctx):
    _, out = ts(ALL)
    s = S13.format(DEF, "review-flow")
    ctx.check(f"S13 for a plain session, got {out['s13'][0]!r}", out["s13"][0] == s)
    ctx.check(f"S13 in the terminal adds its tail, got {out['s13'][1]!r}",
              out["s13"][1] == s + " In the terminal: quit and run halo again; /clear keeps starter (the default).")
    ctx.check(f"S13 on its own map 'shop' has no '(the default)', got {out['s13'][2]!r}",
              out["s13"][2] == S13.format("shop", "review-flow"))


@test
def test_times_by_pattern(ctx: Ctx):
    clk, out = ts("""out.pat = Object.fromEntries(Object.entries(clk).map(([k, v]) =>
      [k, /^\\d{1,2}[:.]\\d{2}(\\s?[AaPp]\\.?\\s?[Mm]\\.?)?$/u.test(v)]));
      out.zero = T.clock(0);""")
    for k in ("00:05", "09:07", "12:30", "23:59"):
        ctx.check(f"clock({k}) reads as a time in this locale, got {clk[k]!r}", out["pat"][k])
    ctx.check(f"clock(0) is '', got {out['zero']!r}", out["zero"] == "")
    src = "\n".join(sources().values())
    ctx.check("truth.ts (and any split file) has exactly one toLocaleTimeString", src.count("toLocaleTimeString") == 1)
    ctx.check("no time is built by hand (getHours / getMinutes / padStart)",
              not re.search(r"getHours|getMinutes|getUTCHours|padStart", src))


@test
def test_t7_first_then_s13(ctx: Ctx):
    f = dict(BASE, b="N", bSince="@11:30", workflow="W", changed={"t": "@11:40"})
    clk, out = ts("""out.a = T.truthLines(D.f); out.b = T.truthLines(D.g); out.c = T.truthLines(D.h);
      out.all = Object.values(D.states).flatMap((x) => [T.truthLines(x), T.truthLines({ ...x, workflow: 'W', changed: { t: at('11:40') } }),
        T.truthLines({ ...x, changed: { t: at('11:40'), problem: 'p' } })]);""",
                  dict(f=f, g=dict(f, changed={"t": "@11:40", "problem": "line main -> qa names no box"}),
                       h=dict(BASE, a="N", plain=False, b="N", workflow="W")))
    want = ["This session is running the workflow W from N.", S13.format(DEF, "N"),
            X(clk, "It started at {10:24}, before N was switched on at {11:30}."),
            X(clk, "starter (the default) changed at {11:40}; this session takes it at its next hand-off.")]
    ctx.check(f"T7, S13, the started line, T5 in that order, got {texts(out['a'])}", texts(out["a"]) == want)
    ctx.check(f"S13 carries [New session], got {out['a'][1]}", out["a"][1].get("act") == "new-session")
    t6 = X(clk, "starter (the default) changed at {11:40} but has a problem, so this session keeps the last good version: "
                "line main -> qa names no box.")
    ctx.check(f"with a problem the last line is T6, got {texts(out['b'])}", texts(out["b"]) == want[:3] + [t6])
    ctx.check(f"B = A with W: T7 then T1, got {texts(out['c'])}",
              texts(out["c"]) == ["This session is running the workflow W from N.",
                                  X(clk, "This session runs on N, as it started at {10:24}. New sessions will too.")])
    bad = [s for s in strings(out["all"]) if re.search(r"fallback|went back|another map", s, re.I)]
    ctx.check(f"no line of any state says 'fallback', 'went back' or 'another map', got {bad}", not bad)


@test
def test_open_not_busy_decides(ctx: Ctx):
    _, out = ts("""out.same = Object.fromEntries(Object.entries(D.states).map(([k, f]) => {
        const a = { ...f, busy: false }, b = { ...f, busy: true };
        const t1 = { ...f, turns: f.turns ? 1 : 0 }, t3 = { ...f, turns: f.turns ? 3 : 0 };
        return [k, T.truthState(a) === T.truthState(b) && JSON.stringify(T.truthLines(a)) === JSON.stringify(T.truthLines(b))
                   && T.truthState(t1) === T.truthState(t3) && JSON.stringify(T.truthLines(t1)) === JSON.stringify(T.truthLines(t3))];
      }));
      const term = (o) => T.truthState({ ...D.states.T3, ...o });
      out.term = [term({ turns: 0 }), term({ turns: 0, b: 'review-flow', bSince: at('11:30') }), term({ turns: 0, plain: false, a: 'shop', b: 'shop' })];
      out.studio = [term({ studio: true, turns: 0 }), term({ studio: true, turns: 1 }), term({ studio: true, turns: 1, plain: false, a: 'shop', b: 'shop' })];""")
    for k, same in out["same"].items():
        ctx.check(f"{k}: busy or not, turn 1 or 3: the same state and byte-equal lines", same)
    ctx.check(f"an open terminal session with no turn yet is drawn (T3, T2, T1), got {out['term']}", out["term"] == ["T3", "T2", "T1"])
    ctx.check(f"a Studio session: T10 before its first message, then T3 / T1, got {out['studio']}",
              out["studio"] == ["T10", "T3", "T1"])


@test
def test_own_map_while_none_is_set_is_not_t1(ctx: Ctx):
    """P1 batch 2's checker: a session started on its own map (`--map mine`) while no map is set for new sessions is NOT
    T1 ("New sessions will too." is false: they run on starter). The two maps are compared by identity (unset = starter),
    and it reads S13 with {B} = "starter (the default)"."""
    own = dict(BASE, a="mine", plain=False, b=None, bSince=None)
    clk, out = ts("""out.none = T.truthLines(D.own); out.st = T.truthState(D.own);
      out.unset = T.truthLines({ ...D.own, bSince: at('11:30') }); out.unsetSt = T.truthState({ ...D.own, bSince: at('11:30') });
      out.before = T.truthLines({ ...D.own, b: 'review-flow', bSince: at('09:07') });
      out.starter = T.truthState({ ...D.own, a: 'starter' }); out.plain = T.truthState({ ...D.own, a: 'starter', plain: true });
      out.res = T.reserve(D.own, 408).lines;""", dict(own=own))
    ctx.check(f"own map, none set: not T1, got {out['st']}", out["st"] != "T1" and out["st"] == "T2")
    ctx.check(f"own map, none set: S13 with the default, then when it started (no false 'switched on'), got {texts(out['none'])}",
              texts(out["none"]) == [S13.format("mine", DEF), X(clk, "It started at {10:24}.")]
              and out["none"][0].get("act") == "new-session")
    ctx.check(f"own map, the default switched back on at 11:30 through Halo: T2 with that time, got {out['unsetSt']} {texts(out['unset'])}",
              out["unsetSt"] == "T2" and texts(out["unset"]) == [S13.format("mine", DEF),
                                                                X(clk, "It started at {10:24}, before starter (the default) was switched on at {11:30}.")])
    ctx.check(f"B switched on before this session started: no false 'before', got {texts(out['before'])}",
              texts(out["before"]) == [S13.format("mine", "review-flow"), X(clk, "It started at {10:24}.")])
    ctx.check(f"started on starter by name, none set: the same map (T1); taken by default: T3, got {out['starter']} {out['plain']}",
              out["starter"] == "T1" and out["plain"] == "T3")
    ctx.check(f"the reserve holds S13 for the default too, got {texts(out['res'])}", S13.format("mine", DEF) in texts(out["res"]))


@test
def test_status_line_each_state(ctx: Ctx):
    _, out = ts(ALL)
    want = ["tester working on the workflow W, step 3 of 6 · waiting for a model reply · $2.42",
            "main working on reading client.py · $0.12",
            "3 agents working on editing files · waiting for you · $1.50",
            "coder working on running tests · waiting for reviewer · $0.90",
            "Waiting for you · $0.40", "Done · $1.10"]
    for got, w in zip(out["status"], want):
        ctx.check(f"{w!r}, got {got!r}", got == w)
    bad = [s for s in out["status"] if re.search(r"delegating|helpers|models|thinking in|waiting on:", s)]
    ctx.check(f"no 'delegating', 'helpers', 'models', 'thinking in', 'waiting on:', got {bad}", not bad)


@test
def test_hand_offs_plural_by_count(ctx: Ctx):
    data = dict(offs=[dict(s, off=n) for s in (STATUS[1], STATUS[4], STATUS[5]) for n in (0, 1, 2, 12)])
    _, out = ts("out.offs = D.offs.map((s) => T.statusLine(s));", data)
    base = ["main working on reading client.py · $0.12", "Waiting for you · $0.40", "Done · $1.10"]
    tails = ["", " · 1 hand-off outside the map", " · 2 hand-offs outside the map", " · 12 hand-offs outside the map"]
    got = out["offs"]
    for i, b in enumerate(base):
        for j, tail in enumerate(tails):
            ctx.check(f"{b!r} + {tail!r}, got {got[i * 4 + j]!r}", got[i * 4 + j] == b + tail)


@test
def test_worst_case_reserve_at_408_and_360(ctx: Ctx):
    f = dict(BASE, b="review-flow", workflow="review")
    long = "m" * 120
    _, out = ts("""const f = D.f, s = f.started;
      const cands = [];
      for (const v of [{ b: f.a }, { b: null }, { b: f.b, bSince: at('11:30') }, { b: f.b, bSince: null }])
        for (const workflow of [f.workflow, null]) for (const changed of [{ t: s }, null])
          cands.push(T.truthLines({ ...f, ...v, workflow, changed }));
      cands.push(T.truthLines({ ...f, ended: at('12:45') }));
      out.r408 = T.reserve(f, 408); out.r360 = T.reserve(f, 360);
      out.want = T.truthLines({ ...f, changed: { t: s } });
      out.over = [408, 360].flatMap((w) => cands.map((c) => [T.est(c, w), T.reserve(f, w).est]));
      out.est408 = T.est(out.r408.lines, 408);
      out.long = T.reserve({ ...f, b: D.long }, 408).est;""", dict(f=f, long=long))
    ctx.check(f"at 408 the reserve is T7 + S13 + the started line + T5, got {texts(out['r408']['lines'])}",
              texts(out["r408"]["lines"]) == texts(out["want"]) and len(out["want"]) == 4)
    ctx.check("its est is est() of its lines", out["est408"] == out["r408"]["est"])
    bad = [p for p in out["over"] if p[0] > p[1]]
    ctx.check(f"every candidate state fits the reserve at 408 and 360, over: {bad}", not bad)
    ctx.check(f"360 reserves at least what 408 does: {out['r360']['est']} >= {out['r408']['est']}",
              out["r360"]["est"] >= out["r408"]["est"])
    ctx.check(f"a 120-character B grows it, never clamped: {out['long']} > {out['r408']['est']}", out["long"] > out["r408"]["est"])


@test
def test_reserve_holds_only_the_names_it_has(ctx: Ctx):
    """R20 with the coordinator's ruling of P4 batch 11 (it replaces P3 batch 8's 'longest name allowed' reserve, which
    cost the drawing 36 px for everyone; this test was test_reserve_is_for_the_longest_name_allowed, rewritten to the
    truth): the truth block reserves NOTHING for a name it does not have. In T1 ({B} is {A}, no workflow) the reserve's
    lines name only {A}; the states it can reach with its own names (T1, T1 + T5) fit it; a {B} switched on later or a {W}
    that starts later is a real change: the reserve taken with that name holds it (the block measures again, once)."""
    f = dict(BASE, a="shop", plain=False, b="shop", bSince="@09:07")  # T1: {B} is {A}, no workflow yet
    _, out = ts("""const f = D.f, s = f.started;
      out.t1 = T.reserve(f, 408).lines; out.n = T.LONGEST_NAME === undefined;
      out.own = [408, 360].flatMap((w) => [null, { t: s }].map((changed) => [T.est(T.truthLines({ ...f, changed }), w), T.reserve(f, w).est]));
      out.later = [];
      for (const w of [408, 360]) for (const b of ['shop', D.b48]) for (const workflow of [null, D.b48]) {
        const g = { ...f, b, bSince: s + 60, workflow }, r = T.reserve(g, w).est;
        for (const changed of [null, { t: s }]) { const e = T.est(T.truthLines({ ...g, changed }), w); if (e > r) out.later.push([w, b, workflow, e, r]); } }""",
            dict(f=f, b48="mw" * 24))
    said = " ".join(texts(out["t1"]))
    ctx.check(f"T1's reserve names only shop (no stand-in name), got {texts(out['t1'])}",
              "shop" in said and not re.search(r"name-|flow-|running the workflow|Start a new session", said))
    ctx.check(f"no LONGEST_NAME stand-in is exported any more, got {out.get('n')}", out.get("n") is True)
    ctx.check(f"T1 and T1 + T5 fit T1's reserve at 408 and 360, got {out['own']}", all(e <= r for e, r in out["own"]))
    ctx.check(f"with a real 48-character {{B}} or {{W}} the reserve taken then holds every state of it, over: {out['later']}",
              out["later"] == [])


@test
def test_status_room_holds_the_sentences_this_run_can_show(ctx: Ctx):
    """R23 with the coordinator's ruling of P4 batch 11: the status line's twin holds the sentences this run can show with
    its REAL names (its rows, the workflows it knows, a model reply or him, a hand-off outside the map unless it runs on the
    default map), so the line takes the tallest from its first draw and a later sentence moves nothing."""
    w40 = "code-review-and-tests-for-every-change-m"
    now = dict(state="done", rows=[], what="", workflow=None, waiting=None, cost=0.8, off=0)
    _, out = ts("""out.own = T.statusRoom(D.now, ['main', 'planner', 'tester'], [{ name: D.w40, of: 2 }], false);
      out.plain = T.statusRoom(D.now, ['main', 'tester'], [{ name: D.w40, of: 2 }], true);""", dict(now=now, w40=w40))
    own, plain = out["own"], out["plain"]
    want = f"tester working on the workflow {w40}, step 2 of 2 · waiting for a model reply · $0.80 · 1 hand-off outside the map"
    ctx.check(f"the sentence it shows now is one of them, got {own[:2]}", "Done · $0.80" in own)
    ctx.check(f"the long working sentence with its real names is held, got {len(own)} sentences", want in own)
    ctx.check(f"every sentence names only names it has, got {[s for s in own if re.search(r'name-|flow-|reviewer', s)]}",
              not any(re.search(r"name-|flow-|reviewer", s) for s in own))
    ctx.check(f"on the default map no hand-off tail is held, got {[s for s in plain if 'outside the map' in s]}",
              not any("outside the map" in s for s in plain) and want.replace(" · 1 hand-off outside the map", "") in plain)


@test
def test_status_room_holds_ten_hand_offs_and_every_sentence(ctx: Ctx):
    """P4 batch 12 (the checker's follow-up): the twin is given EVERY sentence this run can show, each measured, not the
    four longest by letters (a short sentence can wrap taller than a long one), and the hand-off tail at 10 or more is held
    from the first draw (a two-digit count makes a longer sentence than "1 hand-off")."""
    import re as _re
    now = dict(state="done", rows=[], what="", workflow=None, waiting=None, cost=0.8, off=0)
    _, out = ts("out.own = T.statusRoom(D.now, ['main', 'tester'], [], false);", dict(now=now))
    own = out["own"]
    ctx.check(f"10 hand-offs and 100 hand-offs are held, got {[s for s in own if 'hand-offs' in s][:3]}",
              any("10 hand-offs outside the map" in s for s in own) and any("100 hand-offs outside the map" in s for s in own))
    shortest = min(own, key=len)
    ctx.check(f"more than four sentences, the shortest among them ({shortest!r}), got {len(own)}", len(own) > 4 and "Done · $0.80" in own)
    block = (MAPDIR.parent.parent / "session" / "TruthBlock.tsx").read_text(encoding="utf-8")
    ctx.check("TruthBlock gives the twin every sentence (no cut to the longest few by letters)",
              not _re.search(r"statusRoom\([^;]*\.slice\(0, 4\)", block, _re.S))


@test
def test_words_in_one_place(ctx: Ctx):
    _, out = ts("out.words = T.WORDS; out.was = T.WAS;" + ALL)
    ctx.check(f"WORDS = Live / Feed / Map, got {out['words']}", out["words"] == {"live": "Live", "feed": "Feed", "map": "Map"})
    ctx.check(f"WAS = (was Map) / (was Live), got {out['was']}", out["was"] == {"live": "(was Map)", "feed": "(was Live)"})
    bad = [s for s in strings({k: v for k, v in out.items() if k not in ("words", "was")}) if BANNED.search(s)]
    ctx.check(f"no output says 'in use', 'lineup', 'bio', 'Cast', 'helper', 'delegating', got {bad}", not bad)
    src = sources()
    for name, text in src.items():
        body = re.sub(r"export const (WORDS|WAS) = \{[^}]*\}", "", text)
        lits = re.findall(r"\"[^\"\n]*\b(?:Live|Feed)\b[^\"\n]*\"|`[^`]*\b(?:Live|Feed)\b[^`]*`|'[^'\n]*\b(?:Live|Feed)\b[^'\n]*'",
                          "\n".join(ln for ln in body.splitlines() if not ln.lstrip().startswith(("//", "*", "/*"))))
        ctx.check(f"{name}: the words Live and Feed are written only inside WORDS / WAS, also in: {lits}", not lits)
    # the same module with other words: every output follows WORDS, none keeps the old ones
    with tempfile.TemporaryDirectory(prefix="halo-truth-") as d:
        for name, text in src.items():
            text = re.sub(r'live: "Live", feed: "Feed", map: "Map"', 'live: "Run", feed: "Talk", map: "Plan"', text)
            (Path(d) / name).write_text(text, encoding="utf-8")
        _, o2 = ts("out.words = T.WORDS;" + ALL, url=_url("truth.ts", Path(d)))
        shutil.rmtree(d, ignore_errors=True)
    ctx.check(f"the copy's WORDS are Run / Talk / Plan, got {o2['words']}", o2["words"] == {"live": "Run", "feed": "Talk", "map": "Plan"})
    ctx.check(f"L1-L3's buttons follow, got {[ln[0].get('label') for ln in o2['L'][:4]]}",
              [ln[0].get("label") for ln in o2["L"][:4]] == ["Watch it in Run", "Watch it in Run", "Watch them in Run", "Watch it in Run"])
    ctx.check(f"the card's link follows, got {o2['bits']['card']}", o2["bits"]["card"].get("label") == "Open in Agents -> Run")
    ctx.check(f"the Workflows head follows, got {o2['bits']['workflows']!r}", o2["bits"]["workflows"].endswith("see Plan."))
    old = [s for s in strings({k: v for k, v in o2.items() if k != "words"}) if re.search(r"Live|Feed| Map", s)]
    ctx.check(f"no output of the copy says Live, Feed or Map any more, got {old}", not old)


if __name__ == "__main__":
    ctx = Ctx()
    results, passed, failed, skipped = run_all(TESTS, ctx)
    sys.exit(print_results(results, passed, failed, skipped))
