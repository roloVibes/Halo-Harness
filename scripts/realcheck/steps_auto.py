"""scripts/realcheck/steps_auto.py -- the steps `auto-groups` and `auto-ready-lines` (3.6.0.5 "Auto and groups", design
section 6): Auto drawn as a person lives it. A real Studio (`halo studio`) and a real terminal session (`halo`) in one
scratch home on Auto (the default), the fake provider answering (fakes.AUTOGROUPS_REPLIES, fakes.AUTO_BUILD_CHANGES);
each assert alone, every one reported as '(n) what a person saw' with its evidence.

auto-groups (a fresh home: no workflow of his, no crew.map):
  (1) before any call: the drawer and Agents -> Live draw Auto with main alone and no group, the truth block says W15,
      and no page (Agents' four views, Setup, Session) says "starter"
  (2) `/status` prints W1
  (3) the five replies run (no "Invalid arguments"; every sub-agent was asked) and group 1 holds its three members
      within GROUP_FIRST_S of the first spawn frame reaching the page (the page's own clock)
  (4) four groups, named, in their own colours (never a state's), in start order, group 1 never moved
  (5) each line from main into a group was drawn live while a member worked, then a trace with at least one hand-off
  (6) every member says "Why this model:" where a person reads it: a member of an open group in its hover card, a
      member of a folded group (all done: it folds to its head) in its group's card, its row chosen
  (7) no text under 12 px in the drawer, nothing cut inside a group
  (8) Agents -> Live draws the same four groups right of main; nothing left running after quit

auto-ready-lines (a home holding one workflow of his, tidy, so the session has the Workflow tool):
  (1) the Builder card says A15 and offers no map row and no use row; Enter applies it
  (2) the folded terminal card says P1 in its header (above its status row)
  (3) Studio's head is H1 with [Open in Workflows] and the one line under it; no pair; the drawer still Auto
  (4) `halo config get crew.map` is what it was before the build
  (5) "use it now" draws the workflow as the group "workflow review · step 1 of 2": wholly inside the drawer's visible
      box, or named by the slot and one press puts its head at the top within 1 s; the head and main hold still
  (6) nothing left running after quit

The selectors read here are this check's contract with the packages a, b and t: see briefs v3605 k/moved.md. SKIP when
no browser may be used (--browser none); with no Chrome found, a FAIL that names it (the first thing it does)."""
from __future__ import annotations

import re
import sys
import time

from realcheck import fakes, screen
from realcheck.core import Fail, browser, excerpt, split_url, wait_address
from realcheck.steps_a import _no_leftovers
from realcheck.steps_b import WATCH
from realcheck.steps_map import CARD_HEAD, HOOK, _alone, _answer, _flat, _followed, _off, _say, _started, alt

WIN = sys.platform == "win32"
W1 = "Map: Auto (the default: main picks who works on each task, and a model for each one)"
W15_RE = (r"This session runs on Auto \(the default\), as it started at [^.]+\. Main picks who works on each task; "
          r"each task shows as a named, coloured group\.")
GROUPS = [(1, "compare the three reports", ["researcher", "researcher", "researcher"]),
          (2, "fix the login bug", ["coder", "reviewer"]),
          (3, "summarize the notes", [""]),
          (4, "list the open bugs", [""])]
# groups 3 and 4 are groups of one: a general-purpose helper is drawn by the role Auto picked for its task
# (routes/crew/map/overlayGroups.ts whoOf), so "" asks for one member of any name
WHY = "Why this model:"
# (what a person calls it, the page's query, the test ids that say it has drawn)
PAGES = (("Agents: Live", "mode=agents&view=live", "live-world"),
         ("Agents: Map", "mode=agents&view=map", "map-bar"),
         ("Agents: Agents", "mode=agents&view=crew", "crew-item|crew-none"),
         ("Agents: Workflows", "mode=agents&view=workflows", "flow-item|flow-none"),
         ("Setup", "mode=setup&block=team", "setup-rail-step"),
         ("Session", "mode=session&open=session-map", "session-lit-map"))
GROUP_FIRST_S = 10.0 if WIN else 5.0
TURN_S = 120.0 if WIN else 60.0
SUBWAIT_PROMPTS = sorted(a["prompt"] for reply in fakes.AUTOGROUPS_REPLIES for _n, a, _c in reply)

A15 = "Your review workflow: the workflow review (coder, then checker)."
# 3.6.0.15 U4: the card's checker is put into the running session and the put takes, so ONE line names both
P1 = "Ready in this session now: the workflow review, the agent checker (subagent_type `checker`)."
H1 = "Just built: the workflow review. Ready in this session now, by name."
OPEN_WF = "Open in Workflows"
NO_ROWS = ("Make a new map", "New sessions run on")
USE_HEAD = "workflow review · step 1 of 2"
HEADER, STATUS_OK = "⏺", "✓"  # a tool card's header glyph (tui/dispatch.py) and its status row's (tui/widgets/cards.py)

M = "document.querySelector('[data-testid=session-lit-map]')"
# A wait's expression must give a true value back through returnByValue: an element comes back as {}, which never ends
# the wait. So `!!` covers the whole && chain.
MAIN_DRAWN = f"!!({M} && {M}.querySelector('[data-box=main]'))"
SCROLL_BOX = """(e) => { for (let p = e.parentElement; p; p = p.parentElement) { const o = getComputedStyle(p).overflowY;
    if (o === 'auto' || o === 'scroll') return p; } return null; }"""
TOP_OF = f"""(e) => {{ const b = ({SCROLL_BOX})(e), r = e.getBoundingClientRect();
    return b ? r.top - b.getBoundingClientRect().top + b.scrollTop : r.top + scrollY; }}"""

# installed before the first load, after WATCH and HOOK: what the page DREW, on its own clock (moved.md question 2)
GROUPS_HOOK = r"""(() => { if (window.__rcg) return; const g = window.__rcg = {lines: [], first: {}, spawn: 0, full: 0, trail: []};
  const now = () => performance.now();
  const has = (v, d) => { if (!v || typeof v !== 'object' || d > 8) return false;
    if (v.spawn && typeof v.spawn === 'object') return true;
    for (const k in v) if (has(v[k], d + 1)) return true; return false; };
  const seen = (text) => { if (g.spawn) return; try { if (has(JSON.parse(text), 0)) g.spawn = now(); } catch (e) {} };
  const ES = window.EventSource;
  if (ES) { const W = function (u, o) { const es = new ES(u, o);
      for (const k of ['agent_state', 'live', 'registry']) es.addEventListener(k, (ev) => seen(ev.data));
      return es; };
    W.prototype = ES.prototype; W.CONNECTING = 0; W.OPEN = 1; W.CLOSED = 2; window.EventSource = W; }
  const f = window.fetch;
  window.fetch = function (u, o) { const p = f.apply(this, arguments); const s = String(u && u.url || u).replace(/[?#].*$/, '');
    if (/\/api\/live$/.test(s)) p.then((r) => r.clone().text()).then(seen).catch(() => {}); return p; };
  const topOf = TOP_OF_JS;
  const last = {};
  const look = () => { const M = document.querySelector('[data-testid=session-lit-map]'); if (!M) return;
    for (const l of M.querySelectorAll('path.mp-line[data-from=main]')) { const to = l.getAttribute('data-to') || '';
      if (!to.startsWith('group:')) continue;
      const r = {to, lit: l.getAttribute('data-lit') || '', hops: Number(l.getAttribute('data-hops') || 0)}, p = last[to];
      if (!p || p.lit !== r.lit || p.hops !== r.hops) { last[to] = r; g.lines.push(r); } }
    for (const e of M.querySelectorAll('[data-testid=session-map-group]')) { const n = e.dataset.group; if (!n || g.first[n]) continue;
      const nm = e.querySelector('[data-testid=map-group-name]');
      g.first[n] = {top: topOf(e), members: e.querySelectorAll('[data-member]').length, name: nm ? nm.textContent : ''}; }
    const one = M.querySelector('[data-testid=session-map-group][data-group="1"]');
    if (!g.full && one && one.querySelectorAll('[data-member]').length === 3) g.full = now();
    if (one && g.trail.length < 30) { const t = Math.round(topOf(one)), mb = M.querySelector('[data-box=main]'),
        mh = mb ? Math.round(mb.getBoundingClientRect().height) : 0, k = one.querySelectorAll('[data-member]').length;
      const p = g.trail[g.trail.length - 1]; if (!p || p.top !== t || p.main !== mh || p.k !== k) g.trail.push({at: Math.round(now()), top: t, main: mh, k, says: mb ? mb.innerText.replace(/\s+/g, ' ').slice(0, 100) : ''}); } };
  new MutationObserver(look).observe(document, {subtree: true, childList: true, attributes: true,
    attributeFilter: ['data-lit', 'data-hops', 'data-group', 'data-member', 'style']}); })();""".replace("TOP_OF_JS", TOP_OF)


def _fold(text: str) -> str:
    return re.sub(r"\s+", " ", text or "").strip()


def _wait(c, expr: str, timeout: float):
    try:
        return c.wait(expr, timeout)
    except TimeoutError:
        return None


def _quit(ctx, h, c, terms, bad: list, ev: dict, n: str) -> None:
    """Chrome closed, every terminal quit with Ctrl+C and cleaned, nothing of the run left (one more assert)."""
    if c is not None:
        try:
            c.close()
        except Exception:
            pass
    for term in terms:
        if term is not None:
            screen.quit_with_ctrl_c(term)
            term.cleanup()
    try:
        _no_leftovers(ctx, h, "the session and Studio")
    except Fail as e:
        bad.append(f"({n}) left running: " + e.detail)
        ev["left"] = e.evidence.get("left")
    ctx.end_leftovers(h)


def _open(ctx, h):
    """`halo studio` in a terminal of its own: (that terminal, base, token, evidence); raises Fail (after ending what
    it started) when Studio printed no address."""
    ts = ctx.terminal(h, "studio")
    url, at, meanwhile = wait_address(ctx, h, ts, 60)
    if not url:
        screen.quit_with_ctrl_c(ts)
        ts.cleanup()
        ctx.end_leftovers(h)
        raise Fail(f"`halo studio` printed no address in {at:.0f} s: " + excerpt(ts.plain(), 200),
                   {"while_waiting": meanwhile})
    base, token = split_url(url)
    return ts, base, token, {"address_s": round(at, 1)}


def _chrome(exe: str, hooks: tuple):
    from tests.helpers.chrome_driver import open_chrome
    c = open_chrome(1280, 800, exe=exe)
    c.call("Emulation.setDeviceMetricsOverride", width=1280, height=800, deviceScaleFactor=1, mobile=False)
    c.call("Page.enable")
    for src in hooks:
        c.call("Page.addScriptToEvaluateOnNewDocument", source=src)
    return c


def _session(ctx, h, c, page: str, ev: dict, bad: list, upto: str):
    """`halo` in a second terminal of the same home and project; Studio on `page` following it. The terminal, or None
    with one bad line when it never came up."""
    c.go(page)
    t = ctx.terminal(h, cols=200, rows=50)  # `halo` in the same home and project, as a person types it
    ev["session_up_s"] = round(screen.tui_ready(t, 60), 1)
    if not ev["session_up_s"]:
        bad.append(f"(1)-({upto}) not run: the terminal session never showed its status line in 60 s: "
                   + excerpt(t.plain(), 200))
        return t, ""
    sid = _started(h)
    _followed(c, ev, bad, sid)
    _off(c)
    return t, sid


def _fail(bad: list, ev: dict) -> None:
    if bad:
        raise Fail("; ".join(bad[:8]) + (f" (+{len(bad) - 8} more)" if len(bad) > 8 else ""), ev)


# == auto-groups =======================================================================================================
def auto_groups(ctx):
    exe = browser(ctx)  # first: --browser none is a SKIP, no Chrome found a FAIL, before any halo starts
    h = ctx.home("auto-groups")
    ts, base, token, ev = _open(ctx, h)
    bad: list = []
    c = t = None
    try:
        c = _chrome(exe, (WATCH, HOOK, GROUPS_HOOK))
        page = f"{base}/?mode=session&open=session-map&tour=off#t={token}"
        t, sid = _session(ctx, h, c, page, ev, bad, "8")
        if ev.get("session_up_s"):
            _alone(1, bad, _before, c, base, token, sid, ev, bad)
            _alone(2, bad, _status, t, ev, bad)
            turned = _alone(3, bad, _turn, ctx, t, c, ev, bad)
            if turned:
                _alone(4, bad, _groups, c, ev, bad)
                _alone(5, bad, _lines, c, ev, bad)
                _alone(6, bad, _why, c, ev, bad)
                _alone(7, bad, _cut, c, ev, bad)
                _alone(8, bad, _live, c, ev, bad)
            else:
                bad.append("(4)-(8) not run: the turn of five replies never drew group 1")
    finally:
        _quit(ctx, h, c, (t, ts), bad, ev, "8")
    _fail(bad, ev)
    return ("four groups named and coloured in Session and Agents -> Live, lines live then traced, W1, nothing left "
            f"(group 1 in {ev.get('first_group_s', 0):.1f} s)"), ev


BEFORE = f"""(() => {{ const D = {M}, T = document.querySelector('[data-testid=session-truth]');
  return {{map: D ? D.dataset.map || '' : null, boxes: D ? [...D.querySelectorAll('[data-box]')].map((e) => e.dataset.box) : [],
    groups: document.querySelectorAll('[data-group]').length, truth: T ? T.innerText : ''}}; }})()"""
STARTER = r"""(() => { const t = document.body.innerText || '', out = [], re = /\bstarters?\b/gi; let m;
  while ((m = re.exec(t)) && out.length < 5) out.push(t.slice(Math.max(0, m.index - 30), m.index + 30)); return out; })()"""
LIVE_BEFORE = """(() => { const w = document.querySelector('[data-testid=live-world]');
  return w ? {map: w.dataset.map || '', groups: w.querySelectorAll('[data-group]').length} : null; })()"""


def _drawn_expr(ids: str) -> str:
    return " || ".join(f"!!document.querySelector('[data-testid={i}]')" for i in ids.split("|"))


def _before(c, base: str, token: str, sid: str, ev: dict, bad: list) -> None:
    """(1) before any call: the drawer, then each page by its URL, the drawer page last (Session's own text)."""
    _wait(c, MAIN_DRAWN, 30)
    _wait(c, "!!document.querySelector('[data-testid=session-truth]')", 10)
    read = c.js(BEFORE) or {}
    pages = []
    for name, query, ids in PAGES:
        c.go(f"{base}/?{query}&tour=off#t={token}")
        got = {"page": name, "drawn": bool(_wait(c, _drawn_expr(ids), 10))}
        if name == "Agents: Live":
            _wait(c, "document.querySelector('[data-testid=live-world]')?.dataset.map === 'auto'", 10)
            got["live"] = c.js(LIVE_BEFORE)
        if name == "Session":
            _followed(c, {}, [], sid)
            _wait(c, MAIN_DRAWN, 30)
        got["starter"] = c.js(STARTER) or []
        pages.append(got)
    read["pages"] = pages
    ev["before"] = {k: v for k, v in read.items() if k != "truth"}
    ev["before"]["truth"] = _fold(read.get("truth"))[:200]
    _followed(c, ev, bad, sid)  # the drawer page loaded again: Studio follows the session before he types
    _off(c)
    bad.extend(judge_before(read))


def judge_before(read: dict) -> list:
    """(1) in words a person would say, from the drawer's read and each page's."""
    out = []
    if read.get("map") != "auto":
        out.append(f"(1) before any call the drawer draws the map {read.get('map')!r}, not auto")
    if read.get("boxes") != ["main"]:
        out.append(f"(1) before any call the drawer holds the boxes {read.get('boxes')}, not main alone")
    if read.get("groups"):
        out.append(f"(1) before any call the page draws {read['groups']} group(s)")
    if not re.search(W15_RE, _fold(read.get("truth"))):
        out.append("(1) the truth block does not say W15: " + excerpt(_fold(read.get("truth")), 160))
    for p in read.get("pages") or []:
        if not p.get("drawn"):
            out.append(f"(1) {p['page']} did not draw in 10 s")
        for s in p.get("starter") or []:
            out.append(f"(1) {p['page']} says starter: ...{_fold(s)}...")
        if "live" in p:
            live = p.get("live") or {}
            if live.get("map") != "auto":
                out.append(f"(1) before any call Agents -> Live draws the map {live.get('map')!r}, not auto")
            if live.get("groups"):
                out.append(f"(1) before any call Agents -> Live draws {live['groups']} group(s)")
    return out


def _status(t, ev: dict, bad: list) -> None:
    """(2) `/status` prints W1."""
    mark = _say(t, "/status")
    ok = t.wait_for(lambda s: _flat(W1) in _flat(s[mark:]), 15)
    ev["status"] = excerpt(t.plain()[mark:], 300)
    if not ok:
        bad.append("(2) /status does not print W1: " + excerpt(t.plain()[mark:], 200))


def _turn(ctx, t, c, ev: dict, bad: list) -> bool:
    """(3) the five replies: group 1 full within GROUP_FIRST_S of the first spawn frame, the turn's end, every
    sub-agent asked, no "Invalid arguments". True when group 1 was drawn full."""
    ctx.provider.rearm()
    mark = _say(t, fakes.AUTOGROUPS_PROMPT)
    full = bool(_wait(c, "!!(window.__rcg && window.__rcg.full)", TURN_S))
    rec = c.js("window.__rcg ? {spawn: window.__rcg.spawn, full: window.__rcg.full, first: window.__rcg.first, "
               "lines: window.__rcg.lines.length} : null")
    ev["recorder"] = rec
    if rec and rec.get("spawn") and rec.get("full"):
        ev["first_group_s"] = round((rec["full"] - rec["spawn"]) / 1000, 2)
    done = t.wait_for(lambda s: fakes.AUTOGROUPS_DONE in s[mark:], TURN_S)
    seen = t.plain()[mark:]
    ev["turn"] = {"done": done, "screen": seen[-1500:]}
    sent = sorted(p for p in SUBWAIT_PROMPTS if ctx.provider.requests_with(p))
    ev["subagents_asked"] = len(sent)
    bad.extend(judge_record(rec))
    if not done:
        bad.append(f"(3) the turn never ended in {TURN_S:.0f} s: " + excerpt(seen, 200))
    if "Invalid arguments" in seen:
        i = seen.find("Invalid arguments")
        bad.append("(3) a call was refused: " + excerpt(seen[max(0, i - 80):i + 80], 160))
    if sent != SUBWAIT_PROMPTS:
        bad.append(f"(3) the sub-agents asked were {len(sent)} of 7; never asked: "
                   f"{[p for p in SUBWAIT_PROMPTS if p not in sent]}")
    return full


def judge_record(rec) -> list:
    """(3) what the page's recorder saw: never a pass on an empty record; group 1 full in time."""
    if not rec:
        return ["(3) the page's recorder saw nothing of the turn (no __rcg on the page)"]
    out = []
    if not rec.get("spawn"):
        out.append("(3) the page's recorder saw nothing of the first spawn frame")
    if not rec.get("full"):
        out.append("(3) the page's recorder saw nothing of group 1 holding its three members")
    if not (rec.get("first") or {}).get("1"):
        out.append("(3) the page's recorder saw nothing of group 1 being drawn")
    if not rec.get("lines"):
        out.append("(3) the page's recorder saw nothing of a line from main into a group")
    if rec.get("spawn") and rec.get("full"):
        s = (rec["full"] - rec["spawn"]) / 1000
        if s > GROUP_FIRST_S:
            out.append(f"(3) group 1 held its three members {s:.1f} s after the first spawn frame reached the page "
                       f"(at most {GROUP_FIRST_S:.0f} s)")
    return out


GROUPS_READ = f"""(() => {{ const D = {M}, topOf = {TOP_OF};
  const probe = (v) => {{ const s = document.createElement('span'); s.style.color = `var(${{v}})`; D.appendChild(s);
    const c = getComputedStyle(s).color; s.remove(); return c; }};
  const groups = [...D.querySelectorAll('[data-testid=session-map-group]')].map((g) => {{ const top = topOf(g);
    return {{n: g.dataset.group || '', colour: g.dataset.colour || '', top, bottom: top + g.getBoundingClientRect().height,
      name: g.querySelector('[data-testid=map-group-name]')?.textContent || '', border: getComputedStyle(g).borderTopColor,
      own: probe(`--group-${{g.dataset.colour}}`),
      members: [...g.querySelectorAll('[data-member]')].map((m) => (m.querySelector('[data-testid=map-member-line]') || m).innerText.split('\\n')[0])}}; }});
  return {{groups, probes: Object.fromEntries(['--accent', '--warn', '--ok', '--bad'].map((v) => [v, probe(v)]))}}; }})()"""


def _groups(c, ev: dict, bad: list) -> None:
    """(4) the four groups, read once the turn is done."""
    read = c.js(GROUPS_READ) or {}
    first = (c.js("window.__rcg ? window.__rcg.first : {}") or {}).get("1")
    ev["groups"] = read
    ev["group1_trail"] = c.js("window.__rcg ? window.__rcg.trail : []")  # group 1's top, main's height, its members
    bad.extend(judge_groups(read, first))


def _who(line: str) -> str:
    """A member's agent name: the text before the first ':' of its first line, the whole line when it has none."""
    return (line or "").split(":", 1)[0].strip()


def judge_groups(read: dict, first) -> list:
    """(4) four groups 1-4 in top order and colour, GROUPS' names and members, each in its own colour (never a state's),
    group 2 under group 1, group 1 where it was first drawn."""
    out = []
    gs = sorted(read.get("groups") or [], key=lambda g: g.get("top", 0))
    probes = read.get("probes") or {}
    if [g.get("n") for g in gs] != ["1", "2", "3", "4"]:
        out.append(f"(4) the drawer holds the groups {[g.get('n') for g in gs]} in top order, not 1, 2, 3, 4")
    by_n = {g.get("n"): g for g in gs}
    for n, name, agents in GROUPS:
        g = by_n.get(str(n))
        if not g:
            continue
        if g.get("colour") != str(n):
            out.append(f"(4) group {n} has the colour {g.get('colour')!r}, not {n}")
        if _fold(g.get("name")) != name:
            out.append(f"(4) group {n} is named {_fold(g.get('name'))!r}, not {name!r}")
        who = [_who(m) for m in g.get("members") or []]
        if len(who) != len(agents) or any(a and a != w for a, w in zip(agents, who)):
            out.append(f"(4) group {n} holds {who}, not {[a or 'one helper' for a in agents]}")
        if not g.get("border") or g.get("border") != g.get("own"):
            out.append(f"(4) group {n}'s border is {g.get('border')}, not its colour --group-{g.get('colour')} "
                       f"({g.get('own')})")
        same = [v for v, col in probes.items() if col == g.get("border")]
        if same:
            out.append(f"(4) group {n}'s border is the colour of {', '.join(same)} (a state's colour)")
    one, two = by_n.get("1"), by_n.get("2")
    if one and two and two.get("top", 0) < one.get("bottom", 0):
        out.append(f"(4) group 2's top ({two['top']:.0f}) is above group 1's bottom ({one['bottom']:.0f})")
    if one and first and abs(one.get("top", 0) - first.get("top", 0)) >= 0.5:
        out.append(f"(4) group 1 moved: its top was {first['top']:.1f}, now {one['top']:.1f}")
    if one and not first:
        out.append("(4) the page's recorder never saw group 1's first top")
    return out


LINES_NOW = f"""(() => Object.fromEntries([...{M}.querySelectorAll('path.mp-line[data-from=main]')]
  .filter((l) => (l.getAttribute('data-to') || '').startsWith('group:'))
  .map((l) => [l.getAttribute('data-to'), {{lit: l.getAttribute('data-lit') || '', hops: Number(l.getAttribute('data-hops') || 0)}}])))()"""


def _lines(c, ev: dict, bad: list) -> None:
    """(5) the lines from main into each group: live while a member worked (the recorder), then a trace."""
    _wait(c, f"(() => {{ const l = {LINES_NOW}; return [1, 2, 3, 4].every((n) => (l['group:' + n] || {{}}).lit === 'trace'); }})()",
          30 if WIN else 15)
    last = c.js(LINES_NOW) or {}
    records = c.js("window.__rcg ? window.__rcg.lines : []") or []
    ev["lines"] = {"last": last, "records": records[:40]}
    for n in (1, 2, 3, 4):
        bad.extend(judge_lines(records, last, n))


def judge_lines(records: list, last: dict, n: int) -> list:
    """(5) group n's line: a record of it live, and its last state on the page a trace with at least one hand-off."""
    to = f"group:{n}"
    out = []
    if not any(r.get("to") == to and r.get("lit") == "live" for r in records or []):
        out.append(f"(5) the line from main into group {n} was never drawn live")
    now = (last or {}).get(to)
    if not now:
        out.append(f"(5) no line from main into group {n} at the end")
    elif now.get("lit") != "trace" or (now.get("hops") or 0) < 1:
        out.append(f"(5) the line from main into group {n} ends as {now.get('lit') or 'unlit'!r} with "
                   f"{now.get('hops') or 0} hand-off(s), not a trace with at least one")
    return out


# 3.6.0.15 K4 (a): a group whose members are all done folds to its head 10 s after its last end (LW, foldRule.ts; its
# boxes hidden, never unfolded), so (6) reads a folded group's members in the group's card (OP4: a row per member)
CARD = "document.querySelector('[data-testid=map-step-in][data-open]')"
CARD_OPEN = f"!!{CARD}"
CARD_GONE = "!document.querySelector('.mp-step-in')"
CARD_WAIT_S = 10.0 if WIN else 5.0  # the card opens when its one GET answers, at the latest 1 s after the click
CARD_LINES = f"[...({CARD}?.querySelectorAll('.mp-step-in-head p') || [])].map((p) => p.innerText)"
MEMBERS = f"""[...{M}.querySelectorAll('[data-member]')].map((m) => {{ const g = m.closest('[data-testid=session-map-group]');
  return {{aid: m.dataset.member, n: g ? g.dataset.group || '' : '', folded: !!g && g.hasAttribute('data-folded')}}; }})"""


def group_of(n: str) -> str:
    return f"{M}.querySelector('[data-testid=session-map-group][data-group=\"{n}\"]')"


def row_of(aid: str) -> str:
    """The card's row of the helper `aid` (its key is the fleet key `hid|sid|aid`)."""
    return (f"[...({CARD}?.querySelectorAll('[data-testid=map-step-in-row]') || [])]"
            f".find((r) => (r.dataset.key || '').endsWith('|{aid}'))")


def group_folded(n: str) -> str:
    return f"!!({group_of(n)})?.hasAttribute('data-folded')"


def row_chosen(aid: str) -> str:
    return f"!!({row_of(aid)})?.hasAttribute('data-chosen')"


def why_waits() -> dict:
    """Every wait (6) makes, by the state it names (tests/test_realcheck.py evaluates each against a page stand-in)."""
    return {"folded": group_folded("1"), "open": CARD_OPEN, "chosen": row_chosen("a1"), "gone": CARD_GONE}


def _hover(c, aid: str) -> str:
    """A member's hover card (G4), the pointer moved onto the member for real."""
    el = f"{M}.querySelector('[data-member=\"{aid}\"]')"
    c.js(f"{el}.scrollIntoView({{block: 'center'}}); 1")
    time.sleep(0.2)
    x, y, w, hh = c.rect(el)
    for dx in (0, 2, 4):  # a real move onto it (the hover starts on the first move, then rests)
        c.call("Input.dispatchMouseEvent", type="mouseMoved", x=x + w / 2 + dx, y=y + hh / 2, button="none", buttons=0)
        time.sleep(0.05)
    card = ("(() => { const h = document.getElementById('halo-hover-card'); return h && h.getClientRects().length "
            f"&& (h.dataset.for || '').endsWith(':{aid}') ? h.innerText : ''; }})()")
    _wait(c, f"({card}).includes({WHY!r})", 2)
    text = c.js(card) or ""
    _off(c)
    time.sleep(0.2)
    return text


def _card(c, n: str, aids: list) -> dict:
    """The folded group `n`'s card, as a person opens it: a click on the group's head, then each member's row chosen
    and the card head's lines read; the card closed (×) and gone before the next group. {aid: {"card": [lines]} or
    {"card_note": what did not happen}}."""
    out: dict = {}
    _off(c)
    c.click_on(f"{group_of(n)}.querySelector('[data-testid=map-group-head]')")
    if not _wait(c, CARD_OPEN, CARD_WAIT_S):
        return {aid: {"card_note": f"no card opened in {CARD_WAIT_S:.0f} s at a click on the group's head"} for aid in aids}
    for aid in aids:
        if not c.js(f"!!({row_of(aid)})"):
            out[aid] = {"card_note": "the group's card has no row for it", "rows": c.js(
                f"[...({CARD}?.querySelectorAll('[data-testid=map-step-in-row]') || [])].map((r) => r.dataset.key || '')") or []}
            continue
        if not c.js(row_chosen(aid)):
            c.click_on(f"({row_of(aid)}).querySelector('[data-testid=map-step-in-row-text]')")
        if not _wait(c, row_chosen(aid), CARD_WAIT_S):
            out[aid] = {"card_note": f"its row was not chosen in {CARD_WAIT_S:.0f} s"}
            continue
        out[aid] = {"card": c.js(CARD_LINES) or []}
    c.click_on(f"{CARD}.querySelector('[data-testid=map-step-in-close]')")
    if not _wait(c, CARD_GONE, CARD_WAIT_S):
        for v in out.values():
            v["left_open"] = True
    _off(c)
    return out


def _why(c, ev: dict, bad: list) -> None:
    """(6) "Why this model:" where a person reads it now: a member of an OPEN group in its hover (G4), a member of a
    FOLDED group in its group's card, its row chosen. A group that folds while its members are hovered is read in its
    card too, so the step never races the fold's 10 s."""
    members = c.js(MEMBERS) or []
    seen = {m.get("aid", ""): {"group": m.get("n", "")} for m in members}
    for n in dict.fromkeys(m.get("n", "") for m in members):
        aids = [m.get("aid", "") for m in members if m.get("n") == n]
        if not c.js(group_folded(n)):
            for aid in aids:
                seen[aid]["hover"] = _hover(c, aid)
        left = [a for a in aids if WHY not in seen[a].get("hover", "")]
        if left and n and c.js(group_folded(n)):
            for aid, read in _card(c, n, left).items():
                seen[aid].update(read)
    ev["why"] = {aid: {"where": why_where(v), "group": v.get("group"), "hover": _fold(v.get("hover", ""))[:120],
                       **{k: v[k] for k in ("card", "card_note", "rows", "left_open") if k in v}} for aid, v in seen.items()}
    bad.extend(judge_why(seen))


def why_where(read) -> str:
    """Where a member's "Why this model:" was read: "hover", "card" (a line of its group's card head that starts with
    it, its row chosen), or "" (nowhere). A plain string is a hover's text."""
    v = {"hover": read} if isinstance(read, str) else (read or {})
    if WHY in (v.get("hover") or ""):
        return "hover"
    if any(_fold(x).startswith(WHY) for x in v.get("card") or []):
        return "card"
    return ""


def judge_why(seen: dict) -> list:
    """(6) seven members, each read where a person reads it: its hover (an open group), else its group's card (a
    folded group); a member read nowhere is named with what was read."""
    out = []
    if len(seen) != 7:
        out.append(f"(6) the drawer holds {len(seen)} member(s), not 7")
    for aid, read in (seen or {}).items():
        if why_where(read):
            continue
        v = {"hover": read} if isinstance(read, str) else (read or {})
        if "card" in v or "card_note" in v:
            said = v.get("card_note") or "its head reads " + excerpt(" | ".join(_fold(x) for x in v.get("card") or []), 160)
            out.append(f"(6) the member {aid} of the folded group {v.get('group')}: its group's card, its row chosen, has "
                       f"no line {WHY!r} ({said})")
        else:
            out.append(f"(6) the hover of the member {aid} does not say {WHY!r}: " + excerpt(_fold(v.get("hover")), 80))
    return out


CUT = f"""(() => {{ const D = {M}, all = [...D.querySelectorAll('*')];
  const small = all.filter((e) => [...e.childNodes].some((n) => n.nodeType === 3 && n.textContent.trim())
    && parseFloat(getComputedStyle(e).fontSize) < 12).map((e) => [e.className && e.className.baseVal !== undefined ? e.className.baseVal : e.className || e.tagName, parseFloat(getComputedStyle(e).fontSize)]);
  const cut = [];
  for (const g of D.querySelectorAll('[data-testid=session-map-group]')) for (const e of [g, ...g.querySelectorAll('*')])
    if (e.scrollHeight > e.clientHeight + 1 || e.scrollWidth > e.clientWidth + 1)
      cut.push([String(e.className || e.tagName), e.scrollHeight, e.clientHeight, e.scrollWidth, e.clientWidth]);
  return {{small, cut}}; }})()"""


def _cut(c, ev: dict, bad: list) -> None:
    """(7) no text under 12 px in the drawer, nothing cut inside a group."""
    read = c.js(CUT) or {}
    ev["cut"] = read
    bad.extend(judge_cut(read))


def judge_cut(read: dict) -> list:
    out = []
    for cls, px in (read.get("small") or [])[:3]:
        out.append(f"(7) a text of {px} px in the drawer ({cls}): under 12 px")
    for cls, sh, ch, sw, cw in (read.get("cut") or [])[:3]:
        out.append(f"(7) {cls} inside a group is cut (scroll {sh}x{sw} over its box {ch}x{cw})")
    return out


LIVE_READ = """(() => { const w = document.querySelector('[data-testid=live-world]'); if (!w) return null;
  const main = w.querySelector('[data-map-box=main], [data-box=main]'), r = main ? main.getBoundingClientRect() : null;
  return {map: w.dataset.map || '', main: r ? r.right : null,
    groups: [...w.querySelectorAll('[data-testid=live-group]')].map((g) => ({n: g.dataset.group || '',
      name: g.querySelector('[data-testid=map-group-name]')?.textContent || '', left: g.getBoundingClientRect().left}))}; })()"""


def _live(c, ev: dict, bad: list) -> None:
    """(8) Agents (Alt+2) on 4 · Live: the same four groups, each right of main."""
    alt(c, 2)
    _wait(c, "document.querySelector('[data-testid=live-world]')?.dataset.map === 'auto' && "
             "document.querySelectorAll('[data-testid=live-world] [data-testid=live-group]').length === 4", 10)
    time.sleep(0.5)
    read = c.js(LIVE_READ)
    ev["live"] = read
    bad.extend(judge_live(read))


def judge_live(read) -> list:
    if not read:
        return ["(8) Agents -> Live drew no drawing in 10 s"]
    out = []
    if read.get("map") != "auto":
        out.append(f"(8) Agents -> Live draws the map {read.get('map')!r}, not auto")
    gs = read.get("groups") or []
    if sorted(g.get("n") for g in gs) != ["1", "2", "3", "4"]:
        out.append(f"(8) Agents -> Live holds the groups {[g.get('n') for g in gs]}, not 1, 2, 3, 4")
    names = {str(n): name for n, name, _a in GROUPS}
    for g in gs:
        if g.get("n") in names and _fold(g.get("name")) != names[g["n"]]:
            out.append(f"(8) Agents -> Live names group {g['n']} {_fold(g.get('name'))!r}, not {names[g['n']]!r}")
        if read.get("main") is None:
            continue
        if (g.get("left") or 0) < read["main"]:
            out.append(f"(8) in Agents -> Live group {g.get('n')}'s left ({g.get('left'):.0f}) is left of main's right "
                       f"({read['main']:.0f})")
    if read.get("main") is None:
        out.append("(8) Agents -> Live draws no main box")
    return out


# == auto-ready-lines ==================================================================================================
def auto_ready_lines(ctx):
    exe = browser(ctx)  # first: --browser none is a SKIP, no Chrome found a FAIL, before any halo starts
    h = ctx.home("auto-ready-lines")
    r = ctx.run(h, "workflows", "copy", "plan", "--as", "tidy", timeout=60)
    tidy = h.state / "crew" / "workflows" / "tidy.yaml"
    if r.code != 0 or not tidy.exists():
        ctx.end_leftovers(h)
        raise Fail("could not give the home its workflow tidy: " + excerpt(r.out + r.err, 200), {"code": r.code})
    before_map = ctx.run(h, "config", "get", "crew.map", timeout=60).out.strip()
    ts, base, token, ev = _open(ctx, h)
    ev["crew_map_before"] = before_map
    bad: list = []
    c = t = None
    try:
        c = _chrome(exe, (WATCH, HOOK))
        page = f"{base}/?mode=session&open=session-map&tour=off#t={token}"
        t, _sid = _session(ctx, h, c, page, ev, bad, "6")
        if ev.get("session_up_s"):
            ctx.provider.rearm()
            mark = _alone(1, bad, _build_card, t, ev, bad)
            if mark is not None:
                _alone(2, bad, _folded, t, mark, ev, bad)
                _alone(3, bad, _head, c, ev, bad)
            else:
                bad.append("(2)-(3) not run: no Builder card to apply")
            _alone(4, bad, _same_map, ctx, h, before_map, ev, bad)
            _alone(5, bad, _use, ctx, t, c, ev, bad)
    finally:
        ctx.provider.release()  # always, before ending anything: no held call outlives the step
        _quit(ctx, h, c, (t, ts), bad, ev, "6")
    _fail(bad, ev)
    return ("the card made no map, the folded card and Studio's head said the workflow and the agent are ready now, "
            "crew.map unchanged, the workflow ran as a group, nothing left"), ev


def _build_card(t, ev: dict, bad: list):
    """(1) the card says A15 and no map row; Enter applies it. The screen's mark, or None when no card showed."""
    mark = _say(t, fakes.AUTOBUILD_PROMPT)
    shown = t.wait_for(lambda s: CARD_HEAD.search(_flat(s[mark:])) is not None, 30)
    if shown:  # the card is drawn over several frames: judge the WHOLE card
        t.wait_for(lambda s: _flat(A15) in _flat(s[mark:]), 15)
    seen = t.plain()[mark:]
    ev["card"] = {"shown": shown, "screen": seen[-1500:]}
    if not shown:
        bad.append("(1) no Builder card in 30 s: " + excerpt(seen, 160))
        return None
    bad.extend(judge_card(seen))
    ev["card"]["key"] = _answer(t, mark)
    return mark


def judge_card(seen: str) -> list:
    """(1) A15 on the card, neither a map row nor a use row."""
    flat, out = _flat(seen), []
    if _flat(A15) not in flat:
        out.append(f"(1) the card does not say {A15!r}: " + excerpt(seen, 160))
    for row in NO_ROWS:
        if _flat(row) in flat:
            out.append(f"(1) the card offers a row {row!r} (on Auto a card makes no map)")
    return out


def _folded(t, mark: int, ev: dict, bad: list) -> None:
    """(2) the folded card's header says P1; then the turn ends. 3.6.0.21 T2: the waits are the turn's budget on a slow
    runner (TURN_S), and a turn still running when it runs out is said as that alone: the card's words are judged only
    once they stand or the turn has ended."""
    def ended(s: str) -> bool:
        return fakes.AUTOBUILD_DONE in s[mark:]
    t.wait_for(lambda s: not judge_ready_lines(s[mark:]) or ended(s), TURN_S)
    if ended(t.plain()):  # the card is drawn over several frames: its words get the step's own 15 s to stand
        t.wait_for(lambda s: not judge_ready_lines(s[mark:]), 15)
    seen = t.plain()[mark:]
    ev["folded"] = seen[-2000:]
    lines = judge_ready_lines(seen)
    if lines and not ended(t.plain()):
        bad.append(f"(2) the build's turn never ended in {TURN_S:.0f} s (the folded card's words not judged): "
                   + excerpt(t.plain()[mark:], 160))
        return
    bad.extend(lines)
    if not t.wait_for(ended, TURN_S):
        bad.append(f"(2) the build's turn never ended in {TURN_S:.0f} s: " + excerpt(t.plain()[mark:], 160))


def judge_ready_lines(seen: str) -> list:
    """(2) P1 alone in the Builder card's HEADER: after its last header glyph before P1, with no status row between
    the glyph and P1, the status row after P1 and no other ready line between them (a folded card draws its body only
    below its status row)."""
    flat, p1 = _flat(seen), _flat(P1)
    i1 = flat.find(p1)
    if i1 < 0:
        return [f"(2) the folded card does not say {P1!r}"]
    h = flat.rfind(HEADER, 0, i1)
    end = i1 + len(p1)
    st = flat.find(STATUS_OK, end)
    out = []
    if h < 0 or STATUS_OK in flat[h:i1]:
        out.append("(2) the line stands in the card's body, not its header (a status row comes before it)")
    elif st < 0:
        out.append("(2) no status row follows the line")
    elif any(_flat(w) in flat[end:st] for w in ("Ready in this session now:", "Saved for your next session:",
                                                "Not run under its name:")):
        out.append("(2) another ready line follows P1 in the header: " + excerpt(flat[end:st], 160))
    return out


HEAD_READ = f"""(() => {{ const hd = document.querySelector('[data-testid=session-built-head]'), D = {M};
  return {{head: hd ? hd.querySelector('[data-testid=session-built-text]')?.textContent || '' : null,
    buttons: hd ? [...hd.querySelectorAll('button')].map((b) => b.textContent.trim()) : [],
    lines: [...document.querySelectorAll('[data-testid=session-ready-line] [data-testid=session-ready-text]')].map((e) => e.textContent),
    pair: !!document.querySelector('[data-testid=session-map-pair]'), map: D ? D.dataset.map || '' : null}}; }})()"""


def _head(c, ev: dict, bad: list) -> None:
    """(3) Studio's head over the drawing."""
    _wait(c, "document.querySelectorAll('[data-testid=session-ready-line]').length >= 1", 10)
    read = c.js(HEAD_READ) or {}
    ev["head"] = read
    bad.extend(judge_head(read))


def judge_head(read: dict) -> list:
    out = []
    if read.get("head") is None:
        return ["(3) Studio shows no head over the drawing in 10 s"]
    if _fold(read["head"]) != H1:
        out.append(f"(3) Studio's head says {_fold(read['head'])!r}, not {H1!r}")
    if OPEN_WF not in (read.get("buttons") or []):
        out.append(f"(3) the head has no button {OPEN_WF!r} (got {read.get('buttons')})")
    lines = [_fold(x) for x in read.get("lines") or []]
    if lines != [P1]:
        out.append(f"(3) the lines under the head are {lines}, not P1 alone")
    if read.get("pair"):
        out.append("(3) a pair Running | Just built is shown for a build that made no map")
    if read.get("map") != "auto":
        out.append(f"(3) the drawer draws the map {read.get('map')!r}, not auto")
    return out


def _same_map(ctx, h, before: str, ev: dict, bad: list) -> None:
    """(4) new sessions' map unchanged."""
    now = ctx.run(h, "config", "get", "crew.map", timeout=60).out.strip()
    ev["crew_map_after"] = now
    if now != before:
        bad.append(f"(4) crew.map was {before!r} before the build and is {now!r} after")


# k/batch02 entry 3: "use it now" asserts what the judged design rules when the group does not fit under the head (B26
# the slot names it, B27 one press lands with its head at the top) and puts the room on record.
USE_NAME = "workflow review"  # B5: a workflow's group is named "workflow {W}"; the slot names it by that name
RECT_OF = "(e) => { if (!e) return null; const r = e.getBoundingClientRect(); return [r.left, r.top, r.right, r.bottom]; }"
MORE = f"{M}?.querySelector('[data-testid=map-more-below]')"
# what must not move: the head over the drawing and main's box in the page, and main in the drawing's own coordinates
STILL_READ = f"""(() => {{ const D = {M}, m = D && D.querySelector('[data-box=main]'), rect = {RECT_OF};
  return {{head: rect(document.querySelector('[data-testid=session-built-head]')), main: rect(m),
    draw: m ? [m.style.left, m.style.top, m.style.width, m.style.height].map(parseFloat) : null}}; }})()"""
USE_READ = f"""(() => {{ const D = {M}, box = {SCROLL_BOX}, rect = {RECT_OF};
  const name = (e) => (e.querySelector('[data-testid=map-group-name]')?.textContent || '').replace(/\\s+/g, ' ').trim();
  const gs = [...(D ? D.querySelectorAll('[data-testid=session-map-group]') : [])];
  const g = gs.find((e) => e.dataset.workflow === 'review') || gs.find((e) => name(e) === {USE_HEAD!r});
  if (!g) return {{found: false, map: D ? D.dataset.map || '' : null, names: gs.map(name)}};
  const b = box(g), s = b ? b.getBoundingClientRect() : {{left: 0, top: 0, right: innerWidth, bottom: innerHeight}};
  const more = {MORE};
  return {{found: true, map: D.dataset.map || '', name: name(g), group: g.dataset.group || '', rect: rect(g),
    visible: [Math.max(0, s.left), Math.max(0, s.top), Math.min(innerWidth, s.right), Math.min(innerHeight, s.bottom)],
    slot: more ? {{text: more.textContent || '', group: more.dataset.group || ''}} : null}}; }})()"""
USE_SHOWN = f"(() => {{ const u = {USE_READ}; return !!u.found && u.name === {USE_HEAD!r}; }})()"
# from just before the press, in the page: when group n's top first stands at its scroll box's top (B27, as Session's
# slot press lands it), and how far from it it was last
PRESS = f"""((n) => {{ const w = window.__rcpress = {{t0: performance.now(), top: null, d: null}};
  const tick = () => {{ const D = {M}, g = D && D.querySelector(`[data-testid=session-map-group][data-group="${{n}}"]`);
    const s = g && ({SCROLL_BOX})(g), t = performance.now() - w.t0;
    if (g && s) {{ w.d = g.getBoundingClientRect().top - s.getBoundingClientRect().top - s.clientTop; if (w.top == null && Math.abs(w.d) <= 1) w.top = t; }}
    if (w.top == null && t < 3000) requestAnimationFrame(tick); }};
  requestAnimationFrame(tick); return 1; }})"""
PRESS_DONE = "(() => { const w = window.__rcpress; return !!w && (w.top != null || performance.now() - w.t0 > 3000) && w; })()"
# r/batch02 entry 1: the checks of "use it now" poll a fact, never sleep: between two reads the page draws its next frame
# (or 100 ms pass, if no frame comes); the bound is the step's other waits' bound
USE_WAIT_S = 10
NEXT_FRAME = "new Promise((r) => { requestAnimationFrame(() => r(1)); setTimeout(() => r(1), 100); })"


def _use(ctx, t, c, ev: dict, bad: list) -> None:
    """(5) "use it now": the workflow's run is a group, in view or named by the slot and brought up by one press, while
    its first step is held; nothing else moved; then the turn ends."""
    ctx.provider.rearm()
    before = c.js(STILL_READ) or {}
    mark = _say(t, fakes.AUTOUSE_PROMPT)
    _wait(c, USE_SHOWN, USE_WAIT_S)
    read = use_now(c, before)
    ev["use"] = read
    bad.extend(judge_use(read))
    ctx.provider.release()  # the first step's child was held at the gate so "step 1 of 2" stood for the read
    if not t.wait_for(lambda s: fakes.AUTOUSE_DONE in s[mark:], TURN_S):
        bad.append(f"(5) the turn never ended in {TURN_S:.0f} s: " + excerpt(t.plain()[mark:], 160))


def _settled(read: dict) -> bool:
    return bool(read.get("found")) and (use_inside(read) or _names_it(read))


def use_now(c, before: dict, wait_s: float = USE_WAIT_S) -> dict:
    """What "use it now" drew (USE_READ), polled frame by frame for up to `wait_s` until ONE of two facts holds: the group
    is wholly inside the drawing's visible box, or the slot names it (the last read either way: the judge says which
    fact never came); what stood still (`before`, after); when the group is out of sight and the slot names it, ONE
    press on the slot (its landing timed in the page) and what stood still a frame after it landed; the room on record.
    Shared with the Linux VM's browser test (tests/helpers/studio_auto.py)."""
    deadline = time.monotonic() + wait_s
    read = c.js(USE_READ) or {}
    while not _settled(read) and time.monotonic() < deadline:
        c.js(NEXT_FRAME)
        read = c.js(USE_READ) or {}
    read["waited_s"] = wait_s
    read["before"], read["after"] = before, c.js(STILL_READ) or {}
    if read.get("found") and not use_inside(read) and _names_it(read):
        c.js(f"{PRESS}({read.get('group')!r})")
        c.click_on(MORE)
        read["press"] = _wait(c, PRESS_DONE, 6) or c.js("window.__rcpress || null")
        c.js(NEXT_FRAME)
        read["pressed"] = c.js(STILL_READ) or {}
    if read.get("found"):
        read["room"] = use_room(read)
    return read


def use_room(read: dict) -> dict:
    """The room on record: the drawing's visible box's height and the group's height, in px."""
    v, r = read.get("visible") or [0, 0, 0, 0], read.get("rect") or [0, 0, 0, 0]
    return {"visible_h": round(v[3] - v[1]), "group_h": round(r[3] - r[1])}


def use_inside(read: dict) -> bool:
    (lf, tp, rt, bt), (vl, vt, vr, vb) = read.get("rect") or [0, 0, 0, 0], read.get("visible") or [0, 0, 0, 0]
    return not (lf < vl - 0.5 or tp < vt - 0.5 or rt > vr + 0.5 or bt > vb + 0.5)


def _names_it(read: dict) -> bool:
    slot = read.get("slot") or {}
    return (str(slot.get("group") or "") == str(read.get("group") or "-")
            and " ".join(str(slot.get("text") or "").split()).startswith(f"↓ {USE_NAME} · "))


def still_now(c, wait_s: float = USE_WAIT_S) -> dict:
    """STILL_READ once the head and main read the same over two frames in a row (or `wait_s` passed): what stood before
    "use it now", read when the drawing has settled, not after a fixed sleep (r/batch02 entry 1)."""
    def eq(x, y) -> bool:  # settling only: a part missing in every read stands as still as one that is there
        return (x is None and y is None) or _same(x, y)
    deadline, reads = time.monotonic() + wait_s, [c.js(STILL_READ) or {}]
    while time.monotonic() < deadline and not (len(reads) >= 3 and all(
            eq(reads[-1].get(k), r.get(k)) for r in reads[-3:-1] for k in ("head", "main", "draw"))):
        c.js(NEXT_FRAME)
        reads.append(c.js(STILL_READ) or {})
    return reads[-1]


def _same(a, b) -> bool:
    """A rect that is missing is never the same as anything, another missing one included (r/batch02 entry 1)."""
    if a is None or b is None:
        return False
    return len(a) == len(b) and all(abs(float(x) - float(y)) <= 0.5 for x, y in zip(a, b))


def _when_gone(b, a) -> str:
    return "before and after" if b is None and a is None else ("before" if b is None else "after")


def judge_use(read: dict) -> list:
    """(5) (a) the group with its name and step line word for word; (b) wholly inside the visible box, OR named by the
    slot and ONE press puts its head at the top within 1 s; (c) the head and main's box did not move (nor main in the
    drawing with the press). A failure out of sight says the room."""
    if not read.get("found"):
        return [f"(5) no group {USE_HEAD!r} in the drawer in 10 s (groups: {read.get('names')})"]
    out, room = [], use_room(read)
    if " ".join(str(read.get("name") or "").split()) != USE_HEAD:
        out.append(f"(5) the workflow's group is named {read.get('name')!r}, not {USE_HEAD!r}")
    if read.get("map") != "auto":
        out.append(f"(5) the drawer draws the map {read.get('map')!r}, not auto")
    if not use_inside(read):
        where = (f"the drawing's visible box {room['visible_h']} px tall, the group {room['group_h']} px "
                 f"({[round(x) for x in read.get('rect') or []]} outside {[round(x) for x in read.get('visible') or []]})")
        press = read.get("press") or {}
        if not _names_it(read):
            slot = read.get("slot")
            last = (f"{' '.join(str(slot.get('text') or '').split())!r} for group {slot.get('group')!r}" if slot
                    else "no slot")
            waited = f"in {read['waited_s']:g} s " if read.get("waited_s") is not None else ""
            out.append(f"(5) {waited}neither the group wholly inside the drawing's visible box nor the slot naming it: the "
                       f"group is out of sight and the slot does not name it ({where}; the slot read last: {last})")
        elif press.get("top") is None or float(press["top"]) > 1000:
            out.append(f"(5) one press on the slot did not put the group's head at the top of the visible box within 1 s "
                       f"({where}; at the top after {press.get('top')} ms, {press.get('d')} px from it last)")
    before, after = read.get("before") or {}, read.get("after") or {}
    for key, what, gone in (("head", "the head over the drawing", "the head"), ("main", "main's box", "main's box")):
        b, a = before.get(key), after.get(key)
        if b is None or a is None:
            out.append(f"(5) {gone} was not found {_when_gone(b, a)} 'use it now', so it cannot be shown to stand still")
        elif not _same(b, a):
            out.append(f"(5) {what} moved with 'use it now': {b} -> {a}")
    if read.get("press") is not None:
        pressed = read.get("pressed") or {}
        for key, moved, gone in (("draw", "main moved in the drawing with the press", "main in the drawing"),
                                 ("head", "the head over the drawing moved with the press", "the head")):
            b, a = before.get(key), pressed.get(key)
            if b is None or a is None:
                out.append(f"(5) {gone} was not found {_when_gone(b, a)} the press, so it cannot be shown to stand still")
            elif not _same(b, a):
                out.append(f"(5) {moved}: {b} -> {a}")
    return out
