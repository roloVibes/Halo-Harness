"""tests.test_auto_name_ui -- Halo 3.6.0.5 (a): Studio knows Auto is one map. `auto`, `starter` and no map set are ONE
map through one UI test (`isAuto` / `onMap` in routes/crew/map/truthWords.ts); the words read "Auto (the default)"; a new
map is never made under a default's name (W16, the same template as crew/store.py DEFAULT_NAME). Run in node through
tests/helpers/node_ts.py (no browser, no wall clock).
Run: python -m tests.test_auto_name_ui
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from tests.helpers.runner import Ctx, new_registry, print_results, run_all  # noqa: E402

test, TESTS = new_registry()
SRC = Path(__file__).resolve().parent.parent / "halo_harness" / "studio" / "ui" / "src" / "routes"
MAPDIR = SRC / "crew" / "map"
W15 = ("This session runs on Auto (the default), as it started at {t}. Main picks who works on each task; each task shows "
       "as a named, coloured group.")


def _u(p: Path) -> str:
    return json.dumps(p.resolve().as_uri())


def node(body: str, **mods) -> dict:
    """Import each `name=path` as `name`, run `body` (which fills `out`), return `out`."""
    from tests.helpers import node_ts
    head = "".join(f"const {k} = await import({_u(p)});\n" for k, p in mods.items())
    return node_ts.run(head + "const out = {};\n" + body + "\nconsole.log(JSON.stringify(out));")


BASE = ("{ title: 'fix-login', a: 'auto', plain: true, b: null, bSince: null, started: 1768469040, turns: 2, studio: false,"
        " ended: null, machine: null, unreadable: null, changed: null, workflow: null, busy: false }")


@test
def test_name_of_the_default_words(ctx: Ctx):
    out = node("out.w = W.nameOfTheDefault('Starter');", W=MAPDIR / "truthWords.ts")
    ctx.check(f"nameOfTheDefault('Starter') is W16, got {out.get('w')!r}",
              out.get("w") == "Starter is a name of the default (Auto); give your map another name.")
    from halo_harness.crew import store
    src = (MAPDIR / "truthWords.ts").read_text(encoding="utf-8")
    m = re.search(r"nameOfTheDefault = \(name: string\): string => `\$\{name\}([^`]*)`", src)
    ctx.check(f"crew/store.py DEFAULT_NAME and truthWords.ts hold one template, got {m and m.group(1)!r}",
              m is not None and "{name}" + m.group(1) == store.DEFAULT_NAME)


@test
def test_auto_session_with_no_map_set_is_t3(ctx: Ctx):
    out = node(f"""const base = {BASE};
out.s1 = T.truthState(base); out.s2 = T.truthState({{ ...base, a: 'starter' }});
out.lines = T.truthLines(base).map((l) => l.text); out.clk = T.clock(base.started);""", T=MAPDIR / "truth.ts")
    ctx.check(f"a session on auto or starter with no map set is T3, got {out.get('s1')} {out.get('s2')}",
              out.get("s1") == "T3" and out.get("s2") == "T3")
    lines = out.get("lines") or []
    ctx.check(f"exactly one map line, W15, got {lines}", lines[:1] == [W15.format(t=out.get("clk"))]
              and not any("keeps running" in x or "Start a new session" in x for x in lines))


@test
def test_old_rows_and_logs_naming_starter_read_as_auto(ctx: Ctx):
    out = node("""out.n = [W.mapName('starter', false), W.mapName('auto', false), W.mapName('starter', true), W.mapName('shop', false)];
out.opt = `fix-login · ${W.mapName('starter', false)}`;""", W=MAPDIR / "truthWords.ts")
    ctx.check(f"mapName: starter / auto read as Auto, shop as itself, got {out.get('n')}",
              out.get("n") == ["Auto (the default)"] * 3 + ["shop"])
    # livePick.ts imports stores that reach lib/motion.tsx, which node cannot load: its optText is read from the source
    # (it writes {map} through mapName), and the label is built here the way optText builds it
    src = (SRC / "agents" / "livePick.ts").read_text(encoding="utf-8")
    ctx.check("livePick's optText writes {map} through mapName",
              'mapName(r.map, !!r.map_plain)' in src and '`${String(r.title || r.session_id.slice(0, 8))} · ${a}`' in src)
    ctx.check(f"the Live picker's option for a row on starter, got {out.get('opt')!r}", out.get("opt") == "fix-login · Auto (the default)")


@test
def test_one_identity(ctx: Ctx):
    out = node("""out.auto = [W.isAuto('auto'), W.isAuto('starter'), W.isAuto('Starter'), W.isAuto('auto', 'starter'),
  W.isAuto('starter', 'starter'), W.isAuto('starter', 'yours'), W.isAuto('starter', 'project'), W.isAuto('shop')];
out.old = [W.isOldDefault('starter', 'yours'), W.isOldDefault('auto', 'starter')];
out.on = [W.onMap('starter', 'auto'), W.onMap('auto', 'starter', 'starter'), W.onMap('starter', 'starter', 'yours')];
out.next = [T.nextMap(null), T.nextMap('starter')];""", W=MAPDIR / "truthWords.ts", T=MAPDIR / "truth.ts")
    ctx.check(f"isAuto, got {out.get('auto')}", out.get("auto") == [True, True, True, True, True, False, False, False])
    ctx.check(f"isOldDefault, got {out.get('old')}", out.get("old") == [True, False])
    ctx.check(f"onMap, got {out.get('on')}", out.get("on") == [True, True, False])
    ctx.check(f"nextMap, got {out.get('next')}", out.get("next") == ["auto", "auto"])


@test
def test_open_name_and_quiet_on_his_old_file(ctx: Ctx):
    out = node("""out.open = [S.openName('starter'), S.openName(' Auto '), S.openName('starter', 'yours'), S.openName('shop')];
// quietOf's three compares (mapQuiet.ts), on his old file named starter (scope yours) and on Auto
out.mine = [W.onMap('starter', 'starter', 'yours'), W.onMap(T.nextMap(null), 'starter', 'yours')];
out.auto = [W.onMap('starter', 'auto', 'starter'), W.onMap(T.nextMap(null), 'auto', 'starter')];""",
               S=MAPDIR / "truthWords.ts", W=MAPDIR / "truthWords.ts", T=MAPDIR / "truth.ts")
    store_src = (MAPDIR / "mapStore.ts").read_text(encoding="utf-8")
    ctx.check("mapStore.ts exports openName and openMap opens and remembers what it gives",
              "export { openName }" in store_src and "const name = openName(asked);" in store_src
              and "writeLocal(LAST, name);" in store_src)
    ctx.check(f"openName, got {out.get('open')}", out.get("open") == ["auto", "auto", "starter", "shop"])
    ctx.check(f"his old starter file open: a session on starter is not on it (no L1), new sessions not (no L2), got {out.get('mine')}",
              out.get("mine") == [False, False])
    ctx.check(f"Auto open: the session on starter is on it (L1), new sessions too, got {out.get('auto')}", out.get("auto") == [True, True])
    # mapQuiet.ts imports stores that reach lib/motion.tsx, which node cannot load: its compares are read from the source
    src = (MAPDIR / "mapQuiet.ts").read_text(encoding="utf-8")
    ctx.check("quietOf compares only through onMap with the open map's scope (L3, L1, L2), and useQuiet passes the scope",
              src.count("onMap(s.a, name, scope)") == 3 and "onMap(nextMap(next), name, scope)" in src
              and "s.a !== name" not in src and "s.a === name" not in src
              and 'useMap((s) => s.detail?.scope || "")' in src and "quietOf(name, flowBoxes(file), on, next, scope)" in src)


@test
def test_a_build_frame_naming_starter_runs_auto(ctx: Ctx):
    """RULINGS 1 (an ordered share): routes/crew/map/built.ts reads a build frame's `this_session`; an old log's
    `starter`, and none, run `auto`; his map `shop` stays `shop`."""
    src = (MAPDIR / "built.ts").read_text(encoding="utf-8")
    ctx.check("built.ts names no literal starter fallback", '"starter"' not in src
              and 'const running = !d.this_session || isAuto(String(d.this_session)) ? "auto" : String(d.this_session);' in src)
    out = node("""const run = (x) => (!x || W.isAuto(String(x)) ? 'auto' : String(x));
out.r = ['starter', null, 'shop'].map(run);""", W=MAPDIR / "truthWords.ts")
    ctx.check(f"starter / none / shop -> auto / auto / shop, got {out.get('r')}", out.get("r") == ["auto", "auto", "shop"])


if __name__ == "__main__":
    ctx = Ctx()
    results, passed, failed, skipped = run_all(TESTS, ctx)
    sys.exit(print_results(results, passed, failed, skipped))
