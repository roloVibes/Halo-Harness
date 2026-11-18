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
    # batch 3 (A5): openMap takes the scope of his old file; only a map opened with no scope is remembered
    ctx.check("mapStore.ts exports openName and openMap opens and remembers what it gives",
              "export { openName, readOnly" in store_src and "const name = openName(asked, scope);" in store_src
              and "if (!scope) writeLocal(LAST, name);" in store_src)
    ctx.check(f"openName, got {out.get('open')}", out.get("open") == ["auto", "auto", "starter", "shop"])
    ctx.check(f"his old starter file open: a session on starter is not on it (no L1), new sessions not (no L2), got {out.get('mine')}",
              out.get("mine") == [False, False])
    ctx.check(f"Auto open: the session on starter is on it (L1), new sessions too, got {out.get('auto')}", out.get("auto") == [True, True])
    # batch 2 moved quietOf to the pure quietOf.ts (test_map_tab_on_auto_draws_main_and_m1 runs it); its compares and
    # useQuiet's call (mapQuiet.ts, whose stores reach lib/motion.tsx) are read from the two sources
    src = (MAPDIR / "mapQuiet.ts").read_text(encoding="utf-8") + (MAPDIR / "quietOf.ts").read_text(encoding="utf-8")
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


M1 = ("Auto has no plan to edit: main picks who works on each task as it goes, and Live draws each task as a named group. "
      "Main can hand work to: ")
ON = "{ sid: %r, title: %r, a: %r, plain: false, flow: '' }"


@test
def test_map_tab_on_auto_draws_main_and_m1(ctx: Ctx):
    """A11, A14, A22: Auto's Map tab says M1 (twelve names, then "and {n} more"); its quiet row never says L1 or L2 (the
    tab's one Watch button is M1's); Auto is read-only (mapStore's `locked` = his Lock or a read-only map)."""
    on_auto, on_shop = ON % ("s1", "fix-login", "auto"), ON % ("s2", "tidy", "shop")
    out = node(f"""out.head = A.m1Head('abcdefghijklmn'.split('')); out.tail = A.M1_TAIL; out.none = A.NOTHING_ON_AUTO;
out.short = A.m1Head(['planner', 'coder']); out.watch = A.WATCH;
out.qa = Q.quietOf('auto', {{}}, [{on_auto}], null, 'starter').facts;
out.qs = Q.quietOf('shop', {{}}, [{on_shop}], null, 'yours').facts;
out.ro = [A.readOnly('auto', 'starter'), A.readOnly('shop', 'yours'), A.readOnly('starter', 'yours')];""",
               A=MAPDIR / "autoWords.ts", Q=MAPDIR / "quietOf.ts")
    ctx.check(f"m1Head of 14 names: twelve, then 'and 2 more', got {out.get('head')!r}",
              out.get("head") == M1 + "a, b, c, d, e, f, g, h, i, j, k, l and 2 more.")
    ctx.check(f"m1Head of two names, got {out.get('short')!r}", out.get("short") == M1 + "planner, coder.")
    ctx.check(f"M1_TAIL, NOTHING_ON_AUTO, WATCH, got {out.get('tail')!r} {out.get('none')!r} {out.get('watch')!r}",
              out.get("tail") == "· + New map makes a map of your own." and out.get("none") == "Nothing runs on Auto right now."
              and out.get("watch") == "Watch it in Live")
    ctx.check(f"quietOf on Auto with a session on it: no L1, no L2, got {out.get('qa')}", out.get("qa") is None)
    ctx.check(f"quietOf on shop with a session on it: L1, got {out.get('qs')}", (out.get("qs") or {}).get("kind") == "L1")
    ctx.check(f"readOnly: Auto true, shop false, got {out.get('ro')}", (out.get("ro") or [])[:2] == [True, False])
    src = (MAPDIR / "mapStore.ts").read_text(encoding="utf-8")
    ctx.check("mapStore.ts exports readOnly; locked is his Lock or a read-only map, set when a map lands and on toggleLock",
              "export { openName, readOnly }" in src and src.count("handLock || readOnly(") >= 3
              and 'handLock: read(LOCK) === "1"' in src)
    view = (MAPDIR / "MapView.tsx").read_text(encoding="utf-8")
    ctx.check("MapMain draws AutoPlan in place of the canvas, the strip and the cards on Auto",
              "isAuto(name, scope) ? <AutoPlan />" in view)


@test
def test_watch_it_in_live_or_nothing_runs(ctx: Ctx):
    """A14: M1's [Watch it in Live] is the newest session on Auto (openOn's list, newest first); none: ""."""
    rows = ", ".join(ON % x for x in (("s1", "one", "shop"), ("s2", "two", "starter"), ("s3", "three", "auto")))
    out = node(f"out.a = A.autoWatch([{rows}]); out.b = A.autoWatch([{ON % ('s1', 'one', 'shop')}]); out.c = A.autoWatch([]);",
               A=MAPDIR / "autoWords.ts")
    ctx.check(f"the first on Auto (any of its names), else '', got {out.get('a')!r} {out.get('b')!r} {out.get('c')!r}",
              out.get("a") == "s2" and out.get("b") == "" and out.get("c") == "")


@test
def test_switcher_rows_auto_first(ctx: Ctx):
    """A8, A13, W14: Auto (the default) first, his maps, the project's, the shipped ones "(ships with Halo)"; each keeps
    the picker's own facts; never "starter", never "· in use"."""
    rows = ("[{ name: 'ship-it', scope: 'starter' }, { name: 'auto', scope: 'starter' }, { name: 'shop', scope: 'yours' },"
            " { name: 'proj', scope: 'project' }, { name: 'doc-review--review', scope: 'pack' }]")
    out = node(f"""const rows = {rows};
out.a = P.pickerRows(rows, [], null);
out.b = P.pickerRows(rows, [{ON % ('s1', 'fix-login', 'starter')}], null);
out.c = P.pickerRows(rows, [], 'shop');""", P=MAPDIR / "pickerRows.ts")
    a = out.get("a") or []
    ctx.check(f"texts in order, got {[r['text'] for r in a]}", [r["text"] for r in a] == [
        "Auto (the default)", "shop", "doc-review--review", "proj (this project's)", "ship-it (ships with Halo)"])
    ctx.check(f"values, got {[r['value'] for r in a]}", [r["value"] for r in a] == ["auto", "shop", "doc-review--review", "proj", "ship-it"])
    b, c = out.get("b") or [{}], out.get("c") or [{}, {}]
    ctx.check(f"a session on starter: the Auto row runs in it, got {b[0].get('text')!r}",
              b[0].get("text") == "Auto (the default) · running in fix-login")
    ctx.check(f"next shop: shop tagged, Auto not, got {c[0].get('text')!r} {c[1].get('text')!r}",
              c[1].get("text") == "shop · new sessions" and c[0].get("text") == "Auto (the default)")
    texts = " ".join(r.get("text", "") for r in a + b + c)
    ctx.check("no text holds starter or · in use", "starter" not in texts and "· in use" not in texts)
    src = (MAPDIR / "MapBar.tsx").read_text(encoding="utf-8")
    ctx.check("MapBar's Picker draws pickerRows", "pickerRows(rows, on, next)" in src and '" (starter)"' not in src)


SETUP = SRC / "setup"


@test
def test_setup_strip_words(ctx: Ctx):
    """A8 / W14 and the decisions' theme should: the strip's map cell and Setup's glance say "Auto (the default)"; the
    theme cell says "Follow the system" for the theme `auto`, never a bare "auto"."""
    out = node("""out.m = [S.mapWord({ team: { active: 'auto', source: 'default' } }), S.mapWord({ team: { active: 'shop', source: 'config' } }),
  S.mapWord({ team: { active: 'starter', source: 'default' } })];
out.t = [S.themeWord({ theme: 'auto' }), S.themeWord({ theme: 'paper' }), S.themeWord({ theme: '', theme_default: 'instrument' })];""",
               S=SETUP / "words.ts")
    ctx.check(f"mapWord, got {out.get('m')}", out.get("m") == ["Auto (the default)", "shop", "Auto (the default)"])
    ctx.check(f"themeWord, got {out.get('t')}", out.get("t") == ["Follow the system", "paper", "instrument (default)"])
    rail = (SETUP / "SetupRail.tsx").read_text(encoding="utf-8")
    pages = (SETUP / "pages.ts").read_text(encoding="utf-8")
    team = (SETUP / "Team.tsx").read_text(encoding="utf-8")
    ctx.check("the strip's theme cell is themeWord(d), its map cell mapWord(d); pages.ts re-exports both from words.ts",
              '["theme", "Theme", themeWord(d)]' in rail and '["lineup", "Map", mapWord(d)]' in rail
              and 'export { mapWord, themeWord } from "./words";' in pages)
    w10 = ("Auto (the default): main picks who works on each task, and a model for each one. A map of yours: main hands "
           "work along its lines. One model for everything: every job on your model, with no map.")
    ctx.check("Setup's lead is W10 word for word; the glance is mapWord's; no \" (default)\" span, no raw scope chip",
              w10 in " ".join(team.split()) and "mapWord(" in team and '<span className="muted"> (default)</span>' not in team
              and "{r.scope}</span>" not in team and "starter (the default)" not in team)
    ctx.check("the Auto row has no Edit on the Map; its preview head reads Auto (the default)",
              "PREVIEW · {head}" in team and "!isAuto(shown) &&" in team)


@test
def test_his_starter_copy_has_no_use_control(ctx: Ctx):
    """A5: his own old file named starter (scope yours) is a picker row of its own, "starter · your copy from before",
    opened and copied by its scope; read-only, no switch, no sentence that a session runs on it; the copy is my-map
    (my-map-2, my-map-3 when taken)."""
    rows = ("[{ name: 'auto', scope: 'starter' }, { name: 'shop', scope: 'yours' }, { name: 'starter', scope: 'yours' },"
            " { name: 'ship-it', scope: 'starter' }]")
    out = node(f"""out.rows = P.pickerRows({rows}, [], null);
out.ro = [A.readOnly('starter', 'yours'), A.readOnly('auto', 'starter'), A.readOnly('shop', 'yours')];
out.slot = [P.usesSlot('starter', 'yours', null, false), P.usesSlot('auto', 'starter', null, false), P.usesSlot('auto', 'starter', 'shop', false),
  P.usesSlot('auto', 'starter', null, true), P.usesSlot('shop', 'yours', null, false)];
out.copy = [P.copyName([]), P.copyName(['my-map']), P.copyName(['my-map', 'my-map-2'])];
out.url = [P.mapUrl('starter', 'yours'), P.mapUrl('auto')];
out.val = [P.pickerValue('starter', 'yours'), P.pickerValue('auto', '')];
out.q = Q.quietOf('starter', {{}}, [{ON % ('s1', 'fix-login', 'starter')}], null, 'yours').facts;""",
               P=MAPDIR / "pickerRows.ts", A=MAPDIR / "autoWords.ts", Q=MAPDIR / "quietOf.ts")
    ctx.check(f"pickerRows: his old file is its own row among his, got {out.get('rows')}", out.get("rows") == [
        {"value": "auto", "text": "Auto (the default)"}, {"value": "shop", "text": "shop"},
        {"value": "yours:starter", "text": "starter · your copy from before"}, {"value": "ship-it", "text": "ship-it (ships with Halo)"}])
    ctx.check(f"readOnly: his old file and Auto, not shop, got {out.get('ro')}", out.get("ro") == [True, True, False])
    ctx.check(f"usesSlot, got {out.get('slot')}", out.get("slot") == ["old", "default", "", "none", "switch"])
    ctx.check(f"copyName, got {out.get('copy')}", out.get("copy") == ["my-map", "my-map-2", "my-map-3"])
    ctx.check(f"mapUrl, got {out.get('url')}", out.get("url") == ["crew/map/starter?scope=yours", "crew/map/auto"])
    ctx.check(f"pickerValue, got {out.get('val')}", out.get("val") == ["yours:starter", "auto"])
    ctx.check(f"quietOf on his old file with a session on starter: no L1, no L2, got {out.get('q')}",
              (out.get("q") or {}).get("kind") not in ("L1", "L2"))
    store = (MAPDIR / "mapStore.ts").read_text(encoding="utf-8")
    copy = (MAPDIR / "oldCopy.ts").read_text(encoding="utf-8") if (MAPDIR / "oldCopy.ts").is_file() else ""
    bar = (MAPDIR / "MapBar.tsx").read_text(encoding="utf-8")
    team = (SETUP / "Team.tsx").read_text(encoding="utf-8")
    ctx.check("mapStore opens and re-reads by scope (mapUrl), remembers only a map opened with no scope",
              "api.get<MapDetail>(mapUrl(name, scope))" in store and "if (!scope) writeLocal(LAST, name);" in store
              and "mapUrl(name, s.name === name ? s.scope : \"\")" in store and "export { mapUrl, pickerValue" in store)
    ctx.check("oldCopy.ts: copyOld reads his file by its scope, PUTs the copy under copyName, opens it on the Map",
              "export async function copyOld(name: string, scope: string): Promise<boolean>" in copy
              and "mapUrl(name, scope)" in copy and "copyName(" in copy and 'goSection("agents", "map")' in copy)
    ctx.check("MapBar: the switcher's value is pickerValue, the slot is usesSlot, the old file's words and Copy button",
              "value={pickerValue(name, scope)}" in bar and "usesSlot(" in bar and 'data-testid="map-old-words"' in bar
              and 'data-testid="map-old-copy"' in bar)
    ctx.check("Setup's old row: no radio, the name opens it on the Map by scope, Copy as {copyName}",
              'data-testid="setup-map-old"' in team and 'data-testid="map-old-copy"' in team and "openMap(r.name, r.scope)" in team)


# A19 (decisions' last part, J2 M3): the four exceptions, and only these. Media keeps ComfyUI's word ("Keeps the word").
MEDIA_KEEPS = ("media/MediaPanels.tsx", "media/commands.ts", "media/store.ts")
HELP_KEEPS = ("help.ts", "Halo's starters and your saved ones")
SCAN = r"""import { createRequire } from 'node:module';
import fs from 'node:fs';
const ts = createRequire(import.meta.url)(TSC);
const S = ts.SyntaxKind;
const KINDS = new Set([S.StringLiteral, S.NoSubstitutionTemplateLiteral, S.TemplateHead, S.TemplateMiddle, S.TemplateTail, S.JsxText]);
const COMPARE = new Set([S.EqualsEqualsEqualsToken, S.ExclamationEqualsEqualsToken, S.EqualsEqualsToken, S.ExclamationEqualsToken]);
function testid(n) {
  let p = n.parent;
  if (p && p.kind === S.JsxExpression) p = p.parent;
  return !!p && p.kind === S.JsxAttribute && p.name.getText() === 'data-testid';
}
function code(n) {
  if (n.kind !== S.StringLiteral && n.kind !== S.NoSubstitutionTemplateLiteral) return false;
  if (n.text !== 'starter') return false;
  const p = n.parent;
  if (p.kind === S.BinaryExpression) return COMPARE.has(p.operatorToken.kind);
  if (p.kind === S.CallExpression) return p.arguments.includes(n);
  if (p.kind === S.PropertyAssignment) return p.initializer === n && p.name.getText() === 'scope';
  return p.kind === S.LiteralType;
}
function scan(rel, text) {
  if (MEDIA.includes(rel)) return [];
  const sf = ts.createSourceFile(rel, text, ts.ScriptTarget.ES2022, true, rel.endsWith('.tsx') ? ts.ScriptKind.TSX : ts.ScriptKind.TS);
  const bad = [];
  const visit = (n) => {
    if (KINDS.has(n.kind) && /starter/i.test(n.text) && !code(n) && !testid(n)
        && !(rel === HELP[0] && n.text.includes(HELP[1]))) {
      const line = sf.getLineAndCharacterOfPosition(n.getStart(sf)).line + 1;
      bad.push(`${rel}:${line}: ${JSON.stringify(n.text.trim())}`);
    }
    ts.forEachChild(n, visit);
  };
  visit(sf);
  return bad;
}
out.bad = []; out.files = 0;
for (const f of fs.readdirSync(ROOT, { recursive: true }).map(String).sort()) {
  const rel = f.split('\\').join('/');
  if (!/\.tsx?$/.test(rel) || !fs.statSync(ROOT + '/' + rel).isFile()) continue;
  out.files += 1; out.bad.push(...scan(rel, fs.readFileSync(ROOT + '/' + rel, 'utf8')));
}
out.fix = Object.fromEntries(Object.entries(FIXTURES).map(([k, src]) => [k, scan('fixture.tsx', src).length]));
"""
FIXTURES = {
    "default": 'const x = a || "starter";', "element": 'const y = ["starter"];', "jsx": "const z = <b>starter</b>;",
    "template": "const t = `on starter now`;", "title": '<i title="starter" />;',
    "compare": 'if (s.scope === "starter") go();', "argument": 'f("starter");', "scope": 'const o = {scope: "starter"};',
    "type": 'type S = "starter";', "testid": '<i data-testid="crew-starter" />;', "comment": "// starter here\n/* starter */ const c = 1;",
}
MUST_FAIL = {"default", "element", "jsx", "template", "title"}


@test
def test_starter_absent_from_ui_words(ctx: Ctx):
    """A19 / J2 M3: every string, template and JSX text under routes/ that holds "starter" (any case; comments never
    count) fails, except a literal exactly "starter" that is compared, passed as an argument, a `scope` value or a type;
    a `data-testid` value; the media files; help.ts's "Halo's starters and your saved ones". A `||` default, an array
    element and text he sees always fail. The scan proves itself on fixtures first."""
    from tests.helpers import node_ts
    if not (node_ts.TSC / "package.json").is_file():
        raise node_ts._cannot(f"{node_ts.TSC} is not there: `npm ci` under halo_harness/studio/ui")
    files = sorted(p for p in SRC.rglob("*") if p.suffix in (".ts", ".tsx") and p.is_file())
    pairs = [p.relative_to(SRC).as_posix() for p in files]
    js = (SCAN.replace("TSC)", json.dumps(str(node_ts.TSC)) + ")", 1)
          .replace("MEDIA.", json.dumps(list(MEDIA_KEEPS)) + ".", 1).replace("HELP[0]", json.dumps(HELP_KEEPS[0]), 1)
          .replace("HELP[1]", json.dumps(HELP_KEEPS[1]), 1).replace("ROOT", json.dumps(SRC.as_posix()))
          .replace("entries(FIXTURES)", "entries(" + json.dumps(FIXTURES) + ")", 1))
    out = node_ts.run("const out = {};\n" + js + "\nconsole.log(JSON.stringify(out));")
    fix = out.get("fix") or {}
    ctx.check(f"the scan proves itself (fails: {sorted(MUST_FAIL)}; passes: the rest), got {fix}",
              fix and all((fix.get(k, 0) > 0) == (k in MUST_FAIL) for k in FIXTURES))
    ctx.check(f"it read every .ts/.tsx under routes/ ({len(pairs)}), got {out.get('files')}",
              out.get("files") == len(pairs) and len(pairs) > 100)
    for keep in MEDIA_KEEPS:
        ctx.check(f"the media file {keep} is there (the keep-list cannot go stale)", (SRC / keep).is_file())
    ctx.check("help.ts still holds the kept phrase (the keep-list cannot go stale)",
              HELP_KEEPS[1] in (SRC / HELP_KEEPS[0]).read_text(encoding="utf-8"))
    bad = out.get("bad") or []
    ctx.check(f"no text he reads under routes/ says starter: {len(bad)} found:\n  " + "\n  ".join(bad), not bad)


if __name__ == "__main__":
    ctx = Ctx()
    results, passed, failed, skipped = run_all(TESTS, ctx)
    sys.exit(print_results(results, passed, failed, skipped))
