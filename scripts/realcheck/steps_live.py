"""scripts/realcheck/steps_live.py -- the step `live-scene` (3.6.0.14 K1): the drawing of a running session on Auto as a
person sees it. A real Studio (`halo studio`) and a real terminal session (`halo`) in one scratch home on Auto, the fake
provider handing out seven helpers in one message (fakes.LIVE_CALLS: four lone Agent calls and a batch of three; Halo
runs four at once, so two of the batch wait queued), headless Chrome at
1440 x 900 on Agents -> Live. Each assert alone, every one reported as '(n) what a person saw' with its evidence:

  (1) NOW: each member says what it does now, letter for letter ("done in {span}", "waiting for you · {s}",
      "Bash · {s}", "waiting for a model reply · {s}" twice, "queued · {s}" twice), main "Agent · {s}"
  (2) each group's counts line is the product's rule over its members' raw states; main's TURN counts the helpers started
      ((1)-(3) wait for the writer's all-done group to fold to its head first, so every run reads one layout)
  (3) the slot names the group that waits on you, by where the page drew it (one message cannot start the lone helpers
      in a fixed order): below the view the down form, else, the drawing scrolled to its end, above it the up form; its
      tail; one press brings its member into view
  (4) Session's drawer at its narrowest, the member scrolled into the page and the pointer resting ON it (the point is
      read on the drawing, with the root's `data-held`, at the rest, before the let-go and after) while two helpers end
      and two start: no box moves (0.5 px) and the box under the pointer does not ring
  (5) the long tool (42 characters) reads "a tool · {s}" while held, its whole name once the pointer left: one growth,
      no second, no other member's height changed; the chart's helper was given the tool at once (alwaysLoad) with
      ToolSearch in its first request, and the tool ran ("slept 30.0s")
  (6) every ring of the no-preference parts: in view, not under the pointer, not under the open box, at most four in one
      frame, never main's box
  (7) the box opens in place in Agents -> Live: it unfolds from its box, its corner at its box (or the view's clamp),
      nothing else moves, its NOW waits on you, Pause holds still through its seconds, Pause and Resume; Escape closes it
 (7c) in Session's drawer the box opened on the lowest working member of the open group drawn directly above the
      testers', over a tester: the tester ends under it and does not ring
  (8) reduced motion: the box opens and closes with no transition and no animation, and a helper that ends does not ring
  (9) nothing left running after quit

The pointer is moved OFF the drawing by `_away` (steps_map.py: the rail in Agents, the page's last pixel in Session), and a read whose
pointer was found over the drawing is a named failure, never a pass. Every wait names the state it waits for and ends
only on a true value. The judges are pure functions of a read (tests/test_realcheck.py judges them with no browser).
SKIP when no browser may be used (--browser none); with no Chrome found, a FAIL that names it (the first thing it does)."""
from __future__ import annotations

import json
import re
import sys
import time
from types import SimpleNamespace

from realcheck import fakes, screen  # noqa: F401  (screen: the terminal helpers the step's imports share)
from realcheck.core import Fail, browser  # noqa: F401
from realcheck.steps_b import WATCH
from realcheck.steps_map import BTN, HOOK, WIDE, _alone, _away, _say, _wide_chrome, alt
from realcheck.steps_auto import _fail, _open, _quit, _session

WIN = sys.platform == "win32"
LIVE_WAIT_S = 30.0 if WIN else 15.0
TURN_WAIT_S = 120.0 if WIN else 60.0  # the seven drawn: a real session's first turn on Auto
W, H = WIDE
DRAWER = "!!document.querySelector('[data-testid=session-lit-map]')"
OPEN = "!!document.querySelector('[data-testid=map-step-in][data-open]')"
GONE = "!document.querySelector('.mp-step-in')"
SHEET = "document.querySelector('[data-testid=map-step-in][data-open]')"
PAUSE = f"{SHEET}?.querySelector('[data-testid=map-step-in-pause]')"
ASK_GROUP = "review the money module"
DESC = {k: what for k, (_a, _t, _m, what) in zip(("writer", "tool", "ask", "long", "t1", "t2", "t3"), fakes.LIVE_HELPERS)}
TESTS = ("t1", "t2", "t3")  # the batch "run the tests": one runs, two wait queued
SCENE_RAWS = sorted(["done", "running", "running", "running", "waiting", "queued", "queued"])

# the words, as the product writes them (routes/crew/live/waits.ts secsWords, groupWords.ts span with a no-break space)
SECS = r"(?:\d+ s|\d+ min \d\d s)"
SPAN = "\\d+\u00a0(?:s|min)"
FORMS = {"done": (rf"done in {SPAN}", "done in {span}"), "waiting": (rf"waiting for you · {SECS}", "waiting for you · {s}"),
         "queued": (rf"queued · {SECS}", "queued · {s}"), "bash": (rf"Bash · {SECS}", "Bash · {s}"),
         "model": (rf"waiting for a model reply · {SECS}", "waiting for a model reply · {s}")}
COST = r"<?\$\d+\.\d{2,4}"  # a group's cost as the page writes it (F5: "$0.0024", "<$0.0001"; "$0.00")
MAIN_NOW = rf"Agent · {SECS}"
HELD = rf"a tool · {SECS}"
WHOLE = rf"{re.escape(fakes.LIVE_TOOL)} · {SECS}"
_JS_SECS = r"(\d+ s|\d+ min \d\d s)"
HELD_JS = rf"^a tool · {_JS_SECS}$"
WHOLE_JS = rf"^{re.escape(fakes.LIVE_TOOL)} · {_JS_SECS}$"

# state that stays, read after the fact: a frame counter, the pointer, every transition that ran, every ring (with what
# lay under the pointer and the open box at that moment), every sheet's life (unfold, open, fold, place, side)
LIVE_HOOK = r"""(() => { if (window.__rcl) return; const L = window.__rcl = {frame: 0, x: -1, y: -1, rings: [], sheets: [], runs: []};
  const tick = () => { L.frame += 1; requestAnimationFrame(tick); }; requestAnimationFrame(tick);
  addEventListener('pointermove', (e) => { L.x = e.clientX; L.y = e.clientY; }, true);
  const R = (e) => { if (!e) return null; const r = e.getBoundingClientRect(); return [r.left, r.top, r.width, r.height]; };
  const id = (e) => (e && e.dataset ? e.dataset.member || e.dataset.box || '' : '');
  const box = (e) => (e && e.closest ? e.closest('[data-member], [data-box]') : null);
  const groupOf = (e) => (e && e.dataset && e.dataset.member ? box(e.parentElement) : null);
  const reduced = () => matchMedia('(prefers-reduced-motion: reduce)').matches;
  const ring = (e) => { const sc = e.closest('[data-testid=live-scroll], .mp-mini-scroll'), at = L.x >= 0 ? document.elementFromPoint(L.x, L.y) : null;
    const ub = box(at), k = document.querySelector('.mp-step-in[data-open]'); let view = null;
    if (sc) { const v = sc.getBoundingClientRect(); view = [v.left + sc.clientLeft, v.top + sc.clientTop, sc.clientWidth, sc.clientHeight]; }
    L.rings.push({id: id(e), group: id(groupOf(e)), root: e.closest('[data-testid=agents-live]') ? 'live' : e.closest('[data-testid=session-lit-map]') ? 'session' : '',
      frame: L.frame, rect: R(e), view, under: id(ub), underGroup: id(ub && ub.dataset.member ? groupOf(ub) : ub), sheet: R(k), reduced: reduced(), rang: e.dataset.rang || ''}); };
  const rows = new WeakMap();
  const sheet = (k, set) => { let s = rows.get(k);
    if (!s) { s = {n: L.sheets.length, first: L.frame, unfold: 0, fold: 0, open: 0, place: '', side: '', target: '', places: []}; rows.set(k, s); L.sheets.push(s); }
    const p = k.dataset.place || ''; if (p) { s.place = p; if (!s.places.includes(p)) s.places.push(p); }
    for (const a of ['unfold', 'fold', 'open']) if ((set === 'data-' + a || k.hasAttribute('data-' + a)) && !s[a]) s[a] = L.frame || 1;
    s.side = k.dataset.side || s.side; s.target = k.dataset.target || s.target; s.reduced = reduced(); };
  const each = (n) => { if (!n || n.nodeType !== 1) return; if (n.classList.contains('mp-step-in')) sheet(n); for (const k of n.querySelectorAll('.mp-step-in')) sheet(k); };
  document.addEventListener('transitionrun', (e) => { const t = e.target; L.runs.push({sheet: !!(t.closest && t.closest('.mp-step-in')),
    id: (t.dataset && t.dataset.testid) || String(t.className || ''), prop: e.propertyName, frame: L.frame, reduced: reduced()}); }, true);
  const look = (muts) => { for (const m of muts) { const t = m.target;
    if (m.type === 'attributes') { if (m.attributeName === 'data-rang') ring(t);
      if (t.classList && t.classList.contains('mp-step-in')) sheet(t, m.oldValue === null ? m.attributeName : ''); }
    else for (const n of m.addedNodes) each(n); } };
  const start = () => new MutationObserver(look).observe(document.documentElement, {subtree: true, childList: true, attributes: true,
    attributeOldValue: true, attributeFilter: ['data-rang', 'data-unfold', 'data-fold', 'data-open', 'data-place']});
  if (document.documentElement) start(); else document.addEventListener('DOMContentLoaded', start); })();"""

RECT = "(e) => { if (!e) return null; const r = e.getBoundingClientRect(); return [r.left, r.top, r.width, r.height]; }"
# every box's rect in a drawing: main, groups, members
RECTS = f"""((root) => {{ const R = {RECT}; return root ? Object.fromEntries([...root.querySelectorAll('[data-box], [data-member]')]
  .map((e) => [e.dataset.member ? 'member:' + e.dataset.member : 'box:' + e.dataset.box, R(e)])) : {{}}; }})"""
LINES = """((root) => root ? Object.fromEntries([...root.querySelectorAll('[data-member]')].map((m) => [m.dataset.member,
  m.querySelector('[data-testid=map-member-line]')?.textContent || ''])) : {})"""
NOWS = "((root) => root ? [...root.querySelectorAll('[data-testid=map-member-now]')].map((e) => e.textContent).join('|') : '')"


# == the wait expressions: each gives true only (an element through returnByValue is {}, which never ends a wait) ======
def member(root: str, aid: str) -> str:
    return f"({root})?.querySelector('[data-member={json.dumps(aid)}]')"


def members_wait(root: str) -> str:
    return (f"((r) => !!r && [...r.querySelectorAll('[data-member]')].map((m) => m.dataset.raw).sort().join() === "
            f"{json.dumps(','.join(SCENE_RAWS))})({root})")


def now_wait(root: str, aid: str, pattern: str) -> str:
    return (f"new RegExp({json.dumps(pattern)}).test({member(root, aid)}"
            "?.querySelector(':scope > [data-testid=map-member-now]')?.textContent || '')")


def raw_wait(root: str, aid: str, raw: str) -> str:
    return f"{member(root, aid)}?.dataset.raw === {json.dumps(raw)}"


def seen_wait(root: str, scroll: str, aid: str) -> str:
    """The member wholly inside its drawing's scroll box, and no box open."""
    return (f"((m, s) => {{ if (!m || !s || document.querySelector('.mp-step-in')) return false; const r = m.getBoundingClientRect(),"
            " v = s.getBoundingClientRect(), top = v.top + s.clientTop, left = v.left + s.clientLeft;"
            " return r.height > 0 && r.top >= top - 0.5 && r.bottom <= top + s.clientHeight + 0.5 && r.left >= left - 0.5"
            f" && r.right <= left + s.clientWidth + 0.5; }})({member(root, aid)}, {scroll})")


def done_now_wait(root: str) -> str:
    """(1) every done member's NOW drawn as "done in {span}" (its time may reach the page a poll after its done state)."""
    return (f"((r) => {{ const d = r ? [...r.querySelectorAll('[data-member]')].filter((m) => m.dataset.raw === 'done') : [];"
            " return d.length > 0 && d.every((m) => /^done in \\d/.test(m.querySelector(':scope > [data-testid=map-member-now]')"
            f"?.textContent || '')); }})({root})")


def pause_wait(word: str) -> str:
    return f"({PAUSE}?.textContent || '').trim() === {json.dumps(word)}"


def live_wait(root: str) -> str:
    return f"!!({root})?.querySelector('[data-member]')"


def folded_wait(root: str, aid: str) -> str:
    """3.6.0.15 K2 (a): the member's group folded to its head (GroupBlock.tsx `data-folded`; its members stay mounted)."""
    return f"!!{member(root, aid)}?.closest('[data-box]')?.hasAttribute('data-folded')"


def waits(root: str = "document.querySelector('#root')", scroll: str = "document.querySelector('#scroll')") -> dict:
    """Every wait expression of the step (tests/test_realcheck.py evaluates each against a page stand-in)."""
    return {"drawn": members_wait(root), "done_now": done_now_wait(root), "live": live_wait(root), "drawer": DRAWER, "open": OPEN, "gone": GONE,
            "folded": folded_wait(root, "a1"), "held": now_wait(root, "a1", HELD_JS), "whole": now_wait(root, "a1", WHOLE_JS),
            "raw": raw_wait(root, "a1", "done"), "seen": seen_wait(root, scroll, "a1"), "resume": pause_wait("Resume"),
            "pause": pause_wait("Pause")}


# == the judges: pure functions of a read; each returns what a person saw ([] when right) ============================
def _over(away) -> bool:
    return bool(away and away.get("over"))


def _over_line(n, away) -> str:
    return f"({n}) not judged: the pointer at ({away.get('x')}, {away.get('y')}) is over the drawing"


def _who(read: dict, aid: str) -> str:
    return ((read or {}).get("lines") or {}).get(aid) or aid


def judge_live_now(read: dict, away=None) -> list:
    """(1) every member's NOW by its raw state, and main's NOW."""
    if _over(away):
        return [_over_line(1, away)]
    ms = (read or {}).get("members") or {}
    raws = sorted(m.get("raw", "") for m in ms.values())
    bad = [] if raws == SCENE_RAWS else [f"(1) the members' states are {raws}, the script gives {SCENE_RAWS}"]
    running, wrong = {"bash": 0, "model": 0}, False
    for aid, m in ms.items():
        raw, now, kind, who = m.get("raw", ""), m.get("now", ""), m.get("kind", ""), _who(read, aid)
        if raw == "running":
            form = next((f for f in ("bash", "model") if re.fullmatch(FORMS[f][0], now)), "")
            if not form or (form == "bash" and kind != "tool"):
                wrong = True
                bad.append(f"(1) {who} (running): NOW reads {now!r} (kind {kind!r}), not {FORMS['bash'][1]!r} (a tool) "
                           f"or {FORMS['model'][1]!r}")
            else:
                running[form] += 1
        elif raw in FORMS:
            if not re.fullmatch(FORMS[raw][0], now) or (raw == "waiting" and kind != "wait"):
                bad.append(f"(1) {who} ({raw}): NOW reads {now!r} (kind {kind!r}), not {FORMS[raw][1]!r}")
            elif raw == "queued" and not re.fullmatch(r"(?:.+ · )?queued", m.get("state", "")):
                bad.append(f"(1) {who} (queued): its state line reads {m.get('state')!r}, not '{{model}} · queued'")
    if raws == SCENE_RAWS and not wrong and running != {"bash": 1, "model": 2}:
        bad.append(f"(1) the running helpers say 'Bash · {{s}}' {running['bash']} times and 'waiting for a model reply · "
                   f"{{s}}' {running['model']} times, the script gives once and twice")
    main = (read or {}).get("main") or {}
    if not re.fullmatch(MAIN_NOW, main.get("now", "")):
        bad.append(f"(1) main's NOW reads {main.get('now', '')!r}, not 'Agent · {{s}}'")
    return bad


def _agents(n: int) -> str:
    return f"{n} {'agent' if n == 1 else 'agents'}"


def counts_line(raws: list) -> str:
    """groupWords.ts countParts over raw states (no cost part: the fake model costs nothing)."""
    n = lambda *r: sum(1 for x in raws if x in r)  # noqa: E731
    parts = [_agents(len(raws))]
    for k, word in ((n("running", "paused"), "working"), (n("queued"), "queued"), (n("waiting"), "waiting on you"),
                    (n("done"), "done"), (n("stopped"), "stopped"), (n("failed"), "failed")):
        if k:
            parts.append(f"{k} {word}")
    return " · ".join(parts)


def judge_live_heads(read: dict, away=None) -> list:
    """(2) each group's counts line from its members' raw states; main's TURN from the helpers that started."""
    if _over(away):
        return [_over_line(2, away)]
    ms, gs = (read or {}).get("members") or {}, (read or {}).get("groups") or {}
    bad = []
    for gid, g in gs.items():
        raws = [m.get("raw", "") for m in ms.values() if m.get("group") == gid]
        got = g.get("counts", "")
        if raws and all(r == "done" for r in raws):
            ok, want = bool(re.fullmatch(rf"{_agents(len(raws))} · all done · {COST} · {SPAN}", got)), \
                f"{_agents(len(raws))} · all done · ${{cost}} · {{time}}"
        else:
            want = counts_line(raws)  # + its cost when above 0 (the page does not show the raw cost: "$0.00" may stand)
            ok = got == want or bool(re.fullmatch(re.escape(want) + rf" · {COST}", got))
        if not ok:
            bad.append(f"(2) the group {g.get('name', gid)!r} reads {got!r} over its members' states {raws}, want {want!r}")
    started = sum(1 for m in ms.values() if m.get("raw") != "queued")
    want = f"This turn: started {started} {'helper' if started == 1 else 'helpers'}"
    got = ((read or {}).get("main") or {}).get("turn", "")
    if got != want:
        bad.append(f"(2) main's TURN reads {got!r}, want {want!r} (the helpers not queued; main used no tool itself)")
    return bad


def slot_words(name: str, more: int, arrow: str = "down") -> str:
    """groupWords.ts slotWords, the waiting forms: down (below the view) and up (above it)."""
    head = f"{'↑' if arrow == 'up' else '↓'} {name} · waits on you"
    return f"{head} · and {more} more {'group' if more == 1 else 'groups'} below" if more > 0 else head


def _gn(gid: str) -> int:
    try:
        return int(str(gid).split(":")[-1])
    except ValueError:
        return 0


def order_of(read: dict) -> list:
    """The groups' names in the order the page drew them (their `group:<n>`)."""
    gs = (read or {}).get("groups") or {}
    return [gs[g].get("name", g) for g in sorted(gs, key=_gn)]


def judge_live_slot(read: dict, pressed=None, away=None) -> list:
    """(3) the slot names the asking group with its arrow, by where the page drew it (the lone helpers' order is the
    order their workers took the lock: 3.6.0.15 K2 (a)): wholly below the view the down form, wholly above it the up
    form, each with the tail of the other groups wholly below (downFit.ts groupsBelow: a folded group's box counts);
    `pressed` ({seen, sheet}) after one press. The asking group in the view is the entry's named failure."""
    if _over(away):
        return [_over_line(3, away)]
    gs, view, slot = (read or {}).get("groups") or {}, (read or {}).get("view"), (read or {}).get("slot") or {}
    if not view:
        return ["(3) not judged: the drawing's scroll box was not read"]
    top, foot = view[1], view[1] + view[3]
    below = {gid for gid, g in gs.items() if g.get("rect") and g["rect"][1] >= foot - 0.5}
    above = {gid for gid, g in gs.items() if g.get("rect") and g["rect"][1] + g["rect"][3] <= top + 0.5}
    ask = next((gid for gid, g in gs.items() if g.get("name") == ASK_GROUP), None)
    arrow = "down" if ask in below else "up" if ask in above else ""
    # the slot's own input is the WAITING member (downFit.ts waitSlot): out of sight when not wholly in the view (partly
    # counts), its arrow by its top; read when the read has its rect (Agents scrolled to its end may leave a middle
    # group partly above the view, its waiting member wholly above it)
    m = next((x for x in ((read or {}).get("members") or {}).values() if x.get("group") == ask and x.get("raw") == "waiting"
              and x.get("rect") and x["rect"][3] > 0), None)
    if m and not arrow:
        r = m["rect"]
        arrow = "" if r[1] >= top - 0.5 and r[1] + r[3] <= foot + 0.5 else "up" if r[1] < top - 0.5 else "down"
    if ask is None:
        return [f"(3) not judged: the group {ASK_GROUP!r} was not drawn ({order_of(read)})"]
    if not arrow:
        return [f"(3) not judged: the group {ASK_GROUP!r} lies in the view at {W} x {H} ({order_of(read)})"]
    want = slot_words(ASK_GROUP, len(below - {ask}), arrow)
    bad = []
    if slot.get("text") != want:
        bad.append(f"(3) the slot reads {slot.get('text')!r}, want {want!r}")
    if slot.get("arrow") != arrow:
        bad.append(f"(3) the slot's arrow is {slot.get('arrow')!r}, not {arrow!r}")
    if pressed is not None and not pressed.get("seen"):
        bad.append("(3) one press on the slot did not bring the asking member wholly into view")
    if pressed is not None and pressed.get("sheet"):
        bad.append("(3) a box was open after the press on the slot")
    return bad


def _moved(a, b) -> float:
    if not a or not b:
        return float("inf")
    return max(abs(x - y) for x, y in zip(a, b))


def judge_live_rest(before: dict, after: dict, rang=("", "")) -> list:
    """(4) no box moved (0.5 px) while the pointer rested on the drawing; the box under it did not ring."""
    bad = []
    for k, r in (before or {}).items():
        d = _moved(r, (after or {}).get(k))
        if d > 0.5:
            bad.append(f"(4) {k} moved by {d:.1f} px under a resting pointer" if d != float("inf")
                       else f"(4) {k} was gone under a resting pointer")
    if (rang or ("", ""))[0] != (rang or ("", ""))[1]:
        bad.append("(4) the box under the resting pointer rang")
    return bad


def judge_live_rest_point(points: list) -> list:
    """(4) 3.6.0.15 K2 (c): the resting point, read at the rest, just before the long tool is let go and with the second
    rects ({x, y, w, h, on, held}): off the page or not on the drawing is the STEP's failure (then nothing of (4) is
    judged); on it while the drawing's root does not say `data-held` "1" at the rest or before the let-go is the
    product's, with both readings."""
    if not points:
        return ["(4) not judged: the resting point was not read"]
    for p in points:
        p = p or {}
        x, y, w, h = p.get("x"), p.get("y"), p.get("w") or 0, p.get("h") or 0
        inside = isinstance(x, (int, float)) and isinstance(y, (int, float)) and 0 <= x < w and 0 <= y < h
        if not (inside and p.get("on")):
            return [f"(4) not judged: the resting point ({x}, {y}) is not on the drawing (page {w} x {h})"]
    a, b = (points[0] or {}).get("held", ""), ((points[1] if len(points) > 1 else points[0]) or {}).get("held", "")
    if a != "1" or b != "1":
        return [f"(4) the drawing was not held under a pointer resting on it (data-held {a!r} at the rest, {b!r} before "
                "the long tool was let go)"]
    return []


def live_mcp(requests: list) -> dict:
    """(5) what the provider got from the chart's helper: the tool names of its FIRST request and the long tool's result
    text it sent back (the last of its requests with a tool result)."""
    tools, result = None, ""
    for r in requests or []:
        body = (r or {}).get("body") or {}
        msgs = [m for m in body.get("messages") or [] if isinstance(m, dict)]
        if _marker(msgs) != "RC-LIVELONG":
            continue
        if tools is None:
            tools = [(t.get("function") or {}).get("name") or t.get("name") or "" for t in body.get("tools") or []
                     if isinstance(t, dict)]
        said = [fakes._text(m.get("content")) for m in msgs if m.get("role") == "tool"]
        if said:
            result = said[-1]
    return {"tools": tools or [], "result": result}


def judge_live_mcp(m: dict) -> list:
    """(5) 3.6.0.15 K2 (e): the chart's helper was given the server's tool at once (alwaysLoad) with ToolSearch in its
    first request (F2), and the long tool ran (the fake server's slow_tool takes `seconds: float`: "slept 30.0s")."""
    m = m or {}
    tools, result = m.get("tools") or [], m.get("result") or ""
    bad = []
    if fakes.LIVE_TOOL not in tools or "ToolSearch" not in tools:
        bad.append(f"(5) the chart's helper was not given {fakes.LIVE_TOOL} at once (alwaysLoad) with ToolSearch: {tools}")
    if not re.search(rf"\bslept {fakes.LIVE_LONG_S}(?:\.0)?s\b", result):
        bad.append(f"(5) the long tool did not run: its result reads {result!r}, not \"slept {fakes.LIVE_LONG_S}.0s\"")
    return bad


def judge_live_held(h: dict) -> list:
    """(5) the long tool's held form while the pointer rested, its whole name and ONE growth after it left, no second, and
    no other member's height changed."""
    h = h or {}
    if h.get("not_given"):
        return [f"(5) not judged: the chart's helper was not given the MCP server's tool ({h['not_given']})"]
    if h.get("ended_early"):
        return ["(5) not judged: the long tool ended before the pointer left"]
    bad = []
    if not re.fullmatch(HELD, h.get("held", "")):
        bad.append(f"(5) while the pointer rested the long tool read {h.get('held', '')!r}, not 'a tool · {{s}}'")
    if not re.fullmatch(WHOLE, h.get("whole", "")):
        bad.append(f"(5) after the pointer left the long tool read {h.get('whole', '')!r}, not its whole name")
    elif not (h.get("h1", 0) > h.get("h0", 0) + 0.5):
        bad.append(f"(5) the long tool's box did not grow after the pointer left (height {h.get('h0')} then {h.get('h1')})")
    if abs(h.get("h2", 0) - h.get("h1", 0)) > 0.5:
        bad.append(f"(5) the long tool's box grew a second time (height {h.get('h1')} then {h.get('h2')})")
    for k, v in (h.get("others0") or {}).items():
        now = (h.get("others2") or {}).get(k)
        if now is None or abs(now - v) > 0.5:
            bad.append(f"(5) {k}'s height changed from {v} to {now}")
    return bad


def _meets(a, b) -> bool:
    return bool(a and b) and a[0] < b[0] + b[2] and b[0] < a[0] + a[2] and a[1] < b[1] + b[3] and b[1] < a[1] + a[3]


def _inside(r, v) -> bool:
    return bool(r and v) and r[0] >= v[0] - 0.5 and r[1] >= v[1] - 0.5 and r[0] + r[2] <= v[0] + v[2] + 0.5 \
        and r[1] + r[3] <= v[1] + v[3] + 0.5


def judge_live_rings(rows: list) -> list:
    """(6) every ring with no reduced motion: wholly in its scroll box, not the box (or the group of the member) under the
    pointer, not meeting the open box, at most four in one frame, never main's box."""
    bad, frames = [], {}
    for r in rows or []:
        if r.get("reduced"):
            continue
        frames[r.get("frame")] = frames.get(r.get("frame"), 0) + 1
        i = r.get("id", "")
        if i == "main":
            bad.append("(6) main's box rang")
        elif not _inside(r.get("rect"), r.get("view")):
            bad.append(f"(6) {i} rang out of view")
        elif i and i in (r.get("under"), r.get("underGroup")):
            bad.append(f"(6) {i} rang under the pointer")
        elif _meets(r.get("rect"), r.get("sheet")):
            bad.append(f"(6) {i} rang under the open box")
    for f, n in frames.items():
        if n > 4:
            bad.append(f"(6) {n} rings in one frame (at most 4)")
    return bad


def _corner(rect, geo) -> bool:
    """sheetPlace.ts as built: the corner `data-side` names at its box's, or the clamp 8 px inside the view."""
    a, v, side = (geo or {}).get("anchor"), (geo or {}).get("view"), (geo or {}).get("side")
    if not (rect and a and v):
        return False
    near = lambda x, y: abs(x - y) <= 1.0  # noqa: E731
    left, top, w, h = rect
    vl, vt, vr, vb = v[0], v[1], v[0] + v[2], v[1] + v[3]
    x = (near(left + w, a[0] + a[2]) or near(left + w, vr - 8)) if side == "right" else near(left, a[0])
    return (x or near(left, vl + 8)) and (near(top, a[1]) or near(top + h, vb - 8) or near(top, vt + 8))


def judge_live_sheet(s: dict) -> list:
    """(7) the box from its box: unfolded before usable, `data-place` sheet, its corner by the built rule, no other box
    moved, its NOW waits on you, Pause still through its seconds and Pause -> Resume -> Pause, Escape closes it."""
    s = s or {}
    if not s.get("open"):
        return ["(7) a click on the asking member opened no usable box"]
    bad = []
    if not s.get("unfold") or (s.get("opened") and s["unfold"] > s["opened"]):
        bad.append("(7) the box did not unfold from its box before it was usable")
    if s.get("place") != "sheet":
        bad.append(f"(7) the box's place is {s.get('place')!r}, not 'sheet'")
    if not _corner(s.get("rect"), s.get("geo")):
        bad.append(f"(7) the box's corner is off its box: rect {s.get('rect')}, {s.get('geo')}")
    for k, d in (s.get("moved") or {}).items():
        if d > 0.5:
            bad.append(f"(7) {k} moved by {d:.1f} px when the box opened")
    if not re.fullmatch(FORMS["waiting"][0], s.get("now", "")):
        bad.append(f"(7) the box's NOW reads {s.get('now', '')!r}, not 'waiting for you · {{s}}'")
    ps = s.get("pause") or []
    for i, (when, r) in enumerate(zip(("after its seconds changed", "after Pause", "after Resume"), ps[1:])):
        if _moved(ps[0], r) > 0.5:
            bad.append(f"(7) Pause moved {when}: {ps[0]} then {r}")
    if (s.get("texts") or []) != ["Resume", "Pause"]:
        bad.append(f"(7) Pause then Resume read {s.get('texts')}, want ['Resume', 'Pause']")
    if not s.get("gone"):
        bad.append("(7) Escape did not close the box")
    for k, d in (s.get("moved_after") or {}).items():
        if d > 0.5:
            bad.append(f"(7) {k} moved by {d:.1f} px when the box closed")
    return bad


def judge_live_covered(cv: dict) -> list:
    """(7c) the box open in Session's drawer over the tester: the tester ends under it and does not ring."""
    cv = cv or {}
    if "on" in cv and not cv["on"]:  # 3.6.0.15 K2 (b): no member to open: never a click on an empty id
        return [f"(7c) not run: the member to open was not found in Session's drawer ({cv.get('lines') or {}})"]
    if not cv.get("pre"):
        return ["(7c) not judged: the sheet does not cover the tester"]
    bad = []
    if cv.get("place") != "drawer":
        bad.append(f"(7c) the box's place is {cv.get('place')!r}, not 'drawer'")
    if cv.get("raw") != "done":
        bad.append(f"(7c) the covered tester did not end under the open box (its state {cv.get('raw')!r})")
    if cv.get("rang0") != cv.get("rang1") or cv.get("rows"):
        bad.append("(7c) the covered tester rang under the open box")
    return bad


def judge_live_reduced(r: dict) -> list:
    """(8) reduced motion, judged on the state that stays: the box usable with every transition-duration 0s and no
    animation, no transition ran on it, Escape closes it; a helper that ends does not ring and no member animates.
    `data-unfold` / `data-fold` are not judged here (the sheet sets them on every open and fold)."""
    r = r or {}
    if not r.get("open"):
        return ["(8) a click on the asking member opened no usable box under reduced motion"]
    bad = []
    if r.get("runs"):
        bad.append(f"(8) a transition ran on the box under reduced motion: {r['runs'][:3]}")
    durs = [d for d in r.get("durations") or [] if d != "0s"]
    if durs:
        bad.append(f"(8) the box's transition-duration is {durs} under reduced motion")
    if r.get("anims"):
        bad.append(f"(8) the box animated under reduced motion: {r['anims'][:3]}")
    if not r.get("gone"):
        bad.append("(8) Escape did not close the box under reduced motion")
    if r.get("raw") != "done":
        bad.append(f"(8) the chart's helper did not end (its state {r.get('raw')!r})")
    if r.get("rings") or r.get("rang0") != r.get("rang1"):
        bad.append(f"(8) a box rang under reduced motion: {[x.get('id') for x in r.get('rings') or []] or r.get('rang1')}")
    if r.get("member_anims"):
        bad.append(f"(8) a member animated under reduced motion: {r['member_anims'][:3]}")
    return bad


# == the browser ======================================================================================================
def _views():
    from tests.helpers.studio_auto_groups_draw import LMORE, LSCROLL, LW, MORE
    from tests.helpers.studio_live_now_steps import ANIMS, MSCROLL, READ, SLOT_READ, frames, narrow, rest_on
    from tests.helpers.studio_session_run import M
    from tests.helpers.studio_session_step_in import SHEET_GEO
    return SimpleNamespace(LMORE=LMORE, LSCROLL=LSCROLL, LW=LW, MORE=MORE, ANIMS=ANIMS, MSCROLL=MSCROLL, READ=READ,
                           SLOT_READ=SLOT_READ, frames=frames, narrow=narrow, rest_on=rest_on, M=M, SHEET_GEO=SHEET_GEO,
                           root={"live": LW, "session": M}, scroll={"live": LSCROLL, "session": MSCROLL},
                           slot={"live": LMORE, "session": MORE})


def _wait(c, expr: str, timeout: float = LIVE_WAIT_S):
    try:
        return c.wait(expr, timeout)
    except TimeoutError:
        return None


def _read(c, V, view: str) -> dict:
    root, sc = V.root[view], V.scroll[view]
    got = c.js(f"({V.READ})({root}, {sc})") or {}
    got["slot"] = c.js(f"({V.SLOT_READ})({V.slot[view]})")
    got["lines"] = c.js(f"({LINES})({root})") or {}
    got["folded"] = c.js(f"((r) => r ? [...r.querySelectorAll('[data-box][data-folded]')].map((g) => g.dataset.box) : [])({root})") or []
    return got


def _aid(c, V, view: str, what: str) -> str:
    lines = c.js(f"({LINES})({V.root[view]})") or {}
    one = re.compile(rf"(?:.+: )?{re.escape(what)}(?: \(\d+/\d+\))?")  # a batch child's description ends " (i/n)"
    return next((a for a, line in lines.items() if one.fullmatch(line)), "")


def _into_view(c, V, view: str, aid: str, top: bool = False) -> None:
    """The member wholly inside its drawing's scroll box (its top 8 px under the box's top with `top`)."""
    c.js(f"""((m, s) => {{ if (!m || !s) return 0; const r = m.getBoundingClientRect(), v = s.getBoundingClientRect(),
      t = v.top + s.clientTop, b = t + s.clientHeight;
      if ({'true' if top else 'false'} || r.top < t) s.scrollTop += r.top - t - 8; else if (r.bottom > b) s.scrollTop += r.bottom - b + 8; return 1; }})
      ({member(V.root[view], aid)}, {V.scroll[view]})""")
    V.frames(c, 3)


def _ticks(c, expr: str, n: int = 3) -> int:
    """Wait until the text `expr` reads (the drawing's NOW words, a box's NOW) changed `n` times: the page's own clock
    stepped, never a wait in milliseconds."""
    end, k, seen = time.monotonic() + LIVE_WAIT_S, 0, c.js(expr)
    while k < n and time.monotonic() < end:
        time.sleep(0.2)
        got = c.js(expr)
        if got != seen:
            k, seen = k + 1, got
    return k


def _hook(c, key: str) -> list:
    return c.js(f"window.__rcl ? window.__rcl.{key} : []") or []


def _height(c, V, view: str, aid: str):
    r = c.js(f"({RECT})({member(V.root[view], aid)})")
    return r[3] if r else None


def _now(c, V, view: str, aid: str) -> list:
    return c.js(f"((m) => {{ const n = m?.querySelector(':scope > [data-testid=map-member-now]'); return [n?.textContent || '', "
                f"n?.dataset.now || '']; }})({member(V.root[view], aid)})") or ["", ""]


# == the scene ========================================================================================================
def _home(ctx, h) -> None:
    """The scratch home allows the shell's `sleep` and the long tool, and names the suite's fake MCP server under the
    long server name (loaded at the start, as steps_close._mcp_home) with `alwaysLoad`, as a person's config may: an MCP
    tool is otherwise deferred (agent/catalog.py), main's catalog does not hold it, and a helper is given only the tools
    main's catalog holds (agent/subagent.py: `parent.session_catalog.names`)."""
    (h.home / ".claude").mkdir(parents=True, exist_ok=True)
    (h.home / ".claude" / "settings.json").write_text(json.dumps({"permissions": {"allow": ["Bash(sleep:*)", fakes.LIVE_TOOL]}}),
                                                      encoding="utf-8")
    server = {"type": "stdio", "command": sys.executable, "args": ["-m", "tests.helpers.fake_mcp_server"],
              "env": {"PYTHONPATH": str(ctx.repo)}, "mcpLazy": False, "alwaysLoad": True}
    (h.home / ".claude.json").write_text(json.dumps({"mcpServers": {fakes.LIVE_SERVER: server}}), encoding="utf-8")


def live_scene(ctx):
    exe = browser(ctx)  # first: --browser none is a SKIP, no Chrome found a FAIL, before any halo starts
    h = ctx.home("live-scene")
    _home(ctx, h)
    p = ctx.provider
    p.rearm()
    bad: list = []
    c = t = ts = None
    ev: dict = {}
    try:
        ts, base, token, ev = _open(ctx, h)
        c = _wide_chrome(exe, (WATCH, HOOK, LIVE_HOOK))
        t, _sid = _session(ctx, h, c, f"{base}/?mode=agents&view=live&tour=off#t={token}", ev, bad, "9")
        if ev.get("session_up_s"):
            _scene(ctx, c, t, ev, bad)
    finally:
        for go in (p.release, p.release_late, p.release_last):  # no held call outlives the step
            go()
        if ts is not None:
            _quit(ctx, h, c, (t, ts), bad, ev, "9")
        else:
            ctx.end_leftovers(h)
    _fail(bad, ev)
    return ("seven helpers of a real session on Auto: NOW, the heads and TURN, the slot, nothing moves under the pointer, "
            "the held tool and its one growth, the rings, the box in place, reduced motion; nothing left"), ev


def _scene(ctx, c, t, ev: dict, bad: list) -> None:
    V = _views()
    _away(c, "live")
    _say(t, fakes.LIVESCENE_PROMPT)
    t0 = time.monotonic()
    if not _wait(c, members_wait(V.LW), TURN_WAIT_S):
        r = _read(c, V, "live")
        ev["drawn"] = {_who(r, a): m.get("raw") for a, m in (r.get("members") or {}).items()}
        ev["results"] = _results(ctx.provider)
        bad.append(f"(1)-(8) not run: Agents -> Live never drew the seven helpers in {TURN_WAIT_S:.0f} s with the states "
                   f"the script gives ({ev['drawn']})")
        return
    ev["drawn_s"] = round(time.monotonic() - t0, 1)
    # the done member's time may reach the page a poll after its done state: (1) waits for it (never drawn: (1) says so)
    ev["done_now_drawn"] = bool(_wait(c, done_now_wait(V.LW)))
    aids ={k: _aid(c, V, "live", what) for k, what in DESC.items()}
    ev["aids"] = aids
    # 3.6.0.15 K2 (a): the writer's all-done group folds to its head 10 s after its end (LW); (1)-(3) read one layout
    _away(c, "live")
    ev["folded"] = bool(aids["writer"]) and bool(_wait(c, folded_wait(V.LW, aids["writer"])))
    ev["order"] = order_of(_read(c, V, "live"))  # the order the page drew (one message: no fixed start order)
    if ev["folded"]:
        _alone(1, bad, _one, c, V, ev, bad, 1, judge_live_now)
        _alone(2, bad, _one, c, V, ev, bad, 2, judge_live_heads)
        _alone(3, bad, _slot, c, V, aids, ev, bad)
    else:
        bad.append(f"(1)-(3) not run: the writer's all-done group did not fold in {LIVE_WAIT_S:.0f} s")
    held = _alone(4, bad, _rest, ctx, c, V, aids, ev, bad)
    if held:
        _alone(5, bad, _held, ctx, c, V, aids, held, ev, bad)
    else:
        bad.append("(5) not run: (4) never rested the pointer on the drawing")
    _alone(7, bad, _sheet, c, V, aids, ev, bad)
    _alone(7, bad, _covered, ctx, c, V, aids, ev, bad)
    _alone(8, bad, _reduced, ctx, c, V, aids, ev, bad)
    ev["results"] = _results(ctx.provider)
    ev["mcp"] = live_mcp(ctx.provider.mock.requests)  # the long tool's result reached the provider once it ended
    bad.extend(judge_live_mcp(ev["mcp"]))
    rows = _hook(c, "rings")
    ev["rings"] = [[r.get("id"), r.get("root"), r.get("frame"), r.get("reduced")] for r in rows]
    bad.extend(judge_live_rings(rows))


def _marker(msgs: list) -> str:
    """Whose request this is: the scene's marker in its user messages (main's first)."""
    users = " ".join(fakes._text(m.get("content")) for m in msgs if m.get("role") == "user")
    return next((k for k in ("RC-LIVESCENE", "RC-LIVETOOL", "RC-LIVEASK", "RC-LIVELONG", "RC-LIVETEST", "RC-LIVEDONE")
                 if k in users), "")


def _results(p) -> dict:
    """Evidence: the tool results the fake model was sent back, per marker of the scene (what a helper's tool said)."""
    out: dict = {}
    for r in p.mock.requests:
        msgs = [m for m in (r.get("body") or {}).get("messages") or [] if isinstance(m, dict)]
        marker = _marker(msgs)
        tools = [fakes._text(m.get("content"))[:300] for m in msgs if m.get("role") == "tool"]
        if marker and tools:
            out[marker] = tools[-3:]
    return out


def _one(c, V, ev: dict, bad: list, n: int, judge) -> None:
    away = _away(c, "live")
    r = _read(c, V, "live")
    ev[f"read{n}"] = {_who(r, a): [m.get("raw"), m.get("now"), m.get("state")] for a, m in (r.get("members") or {}).items()}
    ev[f"read{n}"].update(main=r.get("main", {}).get("now") if n == 1 else r.get("main", {}).get("turn"),
                          heads={g.get("name"): g.get("counts") for g in (r.get("groups") or {}).values()})
    bad.extend(judge(r, away))


def _slot(c, V, aids: dict, ev: dict, bad: list) -> None:
    away = _away(c, "live")
    r = _read(c, V, "live")
    first = judge_live_slot(r, None, away)
    if first and "lies in the view" in first[0]:
        # 3.6.0.15 K2 (a): the asking group drawn high: the drawing scrolled to its end, where it lies wholly above
        c.js(f"((s) => {{ if (s) s.scrollTop = s.scrollHeight; return 1; }})({V.LSCROLL})")
        V.frames(c, 3)
        away = _away(c, "live")
        _wait(c, f"({V.LMORE})?.dataset.arrow === 'up'")  # the slot answers a scroll at its next frame; else judged as read
        r = _read(c, V, "live")
        first = judge_live_slot(r, None, away)
    ev["slot"] = {"slot": r.get("slot"), "view": r.get("view"), "order": order_of(r),
                  "groups": {g.get("name"): g.get("rect") for g in (r.get("groups") or {}).values()},
                  "folded": [((r.get("groups") or {}).get(g) or {}).get("name", g) for g in r.get("folded") or []]}
    if first and "not judged" in first[0]:
        bad.extend(first)
        return
    c.click_on(V.LMORE)
    _away(c, "live")
    seen = bool(_wait(c, seen_wait(V.LW, V.LSCROLL, aids["ask"])))
    pressed = {"seen": seen, "sheet": bool(c.js("!!document.querySelector('.mp-step-in')"))}
    ev["slot"]["pressed"] = pressed
    bad.extend(judge_live_slot(r, pressed, away))


POINT = """((x, y) => { const root = document.querySelector('[data-testid=session-lit-map]'), e = document.elementFromPoint(x, y);
  const sc = root?.querySelector('.mp-mini-scroll');
  return {x, y, w: innerWidth, h: innerHeight, on: !!(root && e && root.contains(e)), held: root?.dataset.held || '',
    scroll: sc ? [sc.scrollTop, sc.scrollHeight, sc.clientHeight, sc.getBoundingClientRect().top] : null, page: scrollY,
    head: root?.querySelector('.mp-down-head')?.getBoundingClientRect().height ?? null,
    words: (root?.querySelector('.mp-down-head')?.innerText || '').slice(0, 300),
    built: root?.querySelector('.mp-down-room')?.firstElementChild?.getBoundingClientRect().height ?? null}; })"""


def _point(c, x: float, y: float) -> dict:
    """The resting point: on the drawing, and whether the drawing's root says it is held."""
    return c.js(f"({POINT})({x}, {y})") or {"x": x, "y": y}


def _rest(ctx, c, V, aids: dict, ev: dict, bad: list):
    alt(c, 1)
    if not _wait(c, DRAWER):
        c.click_on(BTN)
        if not _wait(c, DRAWER):
            bad.append("(4) not run: Session's Live drawer never drew")
            return None
    ev["drawer"] = V.narrow(c)
    _away(c, "session")
    s = {k: _aid(c, V, "session", what) for k, what in DESC.items()}
    ev["session_aids"] = s
    on = next((s[k] for k in TESTS if s[k] and c.js(raw_wait(V.M, s[k], "running"))), s["tool"])  # it ends under the pointer
    if not on:
        ctx.provider.release()  # the scene goes on: the running tester ends, the chart's helper runs its long tool
        bad.append(f"(4) not run: the member to rest on was not found in Session's drawer ({s})")
        return None
    _into_view(c, V, "session", on)
    # 3.6.0.15 K2 (c): the member in the PAGE too (the drawer's scroll box alone left it at y 1838 on a 900 px page)
    c.js(f"(({member(V.M, on)})?.scrollIntoView({{block: 'center', inline: 'nearest'}}), 1)")
    V.frames(c, 3)
    x, y, w, h = c.rect(member(V.M, on))
    spot = (round(x + w / 2 + 4, 1), round(y + h / 2, 1))  # where V.rest_on ends: the centre + 4 px
    V.rest_on(c, member(V.M, on))
    V.frames(c, 3)
    points = [_point(c, *spot)]
    rects0 = c.js(f"({RECTS})({V.M})") or {}
    rang = f"{member(V.M, on)}?.dataset.rang || ''"
    rang0 = c.js(rang)
    points.append(_point(c, *spot))
    ctx.provider.release()  # the running tester ends and a queued one starts; the chart's helper runs its long tool
    held = bool(_wait(c, now_wait(V.M, s["long"], HELD_JS)))
    ticks = _ticks(c, f"({NOWS})({V.M})")
    rects1 = c.js(f"({RECTS})({V.M})") or {}
    points.append(_point(c, *spot))
    rang1 = c.js(rang)
    now = _now(c, V, "session", s["long"])
    ev["rest"] = {"held_seen": held, "ticks": ticks, "now": now, "boxes": len(rects0), "on": on, "points": points}
    first = judge_live_rest_point(points)
    bad.extend(first)
    if first and "not judged" in first[0]:
        return None  # (5): "(4) never rested the pointer on the drawing"
    bad.extend(judge_live_rest(rects0, rects1, (rang0, rang1)))
    heights = {k: r[3] for k, r in rects0.items() if k.startswith("member:") and r}
    return {"held": now[0], "kind": now[1], "h0": heights.get("member:" + s["long"]), "heights": heights, "aids": s,
            "t": time.monotonic()}


def _held(ctx, c, V, aids: dict, held: dict, ev: dict, bad: list) -> None:
    s = held["aids"]
    was = _now(c, V, "session", s["long"])
    away = _away(c, "session")
    if _over(away):
        bad.append(_over_line(5, away))
        return
    ended = not (re.fullmatch(HELD, was[0]) or re.fullmatch(WHOLE, was[0]))
    _wait(c, now_wait(V.M, s["long"], WHOLE_JS))
    whole = _now(c, V, "session", s["long"])[0]
    h1 = _height(c, V, "session", s["long"])
    _ticks(c, f"({NOWS})({V.M})")
    rects = c.js(f"({RECTS})({V.M})") or {}
    h2 = (rects.get("member:" + s["long"]) or [0, 0, 0, 0])[3]
    key = "member:" + s["long"]
    others0 = {k: v for k, v in held["heights"].items() if k != key}
    others2 = {k: (rects.get(k) or [0, 0, 0, None])[3] for k in others0}
    said = " ".join(_results(ctx.provider).get("RC-LIVELONG") or [])
    gone = re.search(r"not found: [\w-]+|Unknown tool '[\w-]+'", said)
    h = {"not_given": gone.group(0) if gone else "", "ended_early": ended, "held": held["held"], "whole": whole, "h0": held["h0"] or 0, "h1": h1 or 0, "h2": h2 or 0,
         "others0": others0, "others2": others2}
    ev["held"] = {k: v for k, v in h.items() if k not in ("others0", "others2")}
    if ended:
        ev["held"]["at_leave"] = was[0]
        ev["held"]["since_held_s"] = round(time.monotonic() - held["t"], 1)
    bad.extend(judge_live_held(h))


def _open_on(c, V, view: str, aid: str) -> bool:
    x, y, w, h = c.rect(member(V.root[view], aid))
    c.click(x + w / 2, y + h / 2)
    return bool(_wait(c, OPEN))


def _sheet(c, V, aids: dict, ev: dict, bad: list) -> None:
    alt(c, 2)
    if not _wait(c, live_wait(V.LW)):
        bad.append("(7) not run: Agents -> Live was not drawn")
        return
    away = _away(c, "live")
    if _over(away):
        bad.append(_over_line(7, away))
        return
    _into_view(c, V, "live", aids["ask"])
    rects0 = c.js(f"({RECTS})({V.LW})") or {}
    mark = len(_hook(c, "sheets"))
    s: dict = {"open": _open_on(c, V, "live", aids["ask"])}
    if s["open"]:
        k = c.js(f"((k) => k ? {{rect: ({RECT})(k), geo: ({V.SHEET_GEO})(k), place: k.dataset.place || '',"
                 f" now: k.querySelector('[data-testid=map-step-in-now]')?.textContent || '', pause: ({RECT})(k.querySelector("
                 f"'[data-testid=map-step-in-pause]'))}} : null)({SHEET})") or {}
        rects1 = c.js(f"({RECTS})({V.LW})") or {}
        row = next((r for r in _hook(c, "sheets")[mark:] if "sheet" in (r.get("places") or [])), {})
        s.update(k, unfold=row.get("unfold", 0), opened=row.get("open", 0),
                 moved={i: _moved(r, rects1.get(i)) for i, r in rects0.items()})
        pause = [k.get("pause")]
        _ticks(c, f"{SHEET}?.querySelector('[data-testid=map-step-in-now]')?.textContent || ''")
        pause.append(c.rect(PAUSE))
        texts = []
        for word in ("Resume", "Pause"):
            c.click_on(PAUSE)
            _wait(c, pause_wait(word))
            texts.append((c.js(f"({PAUSE}?.textContent || '').trim()") or ""))
            pause.append(c.rect(PAUSE))
        s.update(pause=pause, texts=texts)
        c.key("Escape")
        s["gone"] = bool(_wait(c, GONE))
        rects2 = c.js(f"({RECTS})({V.LW})") or {}
        s["moved_after"] = {i: _moved(r, rects2.get(i)) for i, r in rects0.items()}
    ev["sheet"] = {k: v for k, v in s.items() if k not in ("moved", "moved_after")}
    bad.extend(judge_live_sheet(s))


MEETS = """((k, m) => { if (!k || !m) return false; const a = k.getBoundingClientRect(), b = m.getBoundingClientRect();
  return a.left < b.right && b.left < a.right && a.top < b.bottom && b.top < a.bottom; })"""


def above_tests(read: dict, tests: list) -> tuple:
    """(7c) the member to open: of the open (not folded) group drawn directly above the testers' group (the greatest top
    above its top), its lowest running or waiting member; ("", "") when there is none."""
    ms, gs, folded = (read or {}).get("members") or {}, (read or {}).get("groups") or {}, set((read or {}).get("folded") or [])
    tg = next((ms[a].get("group") for a in tests if a in ms), "")
    t_rect = (gs.get(tg) or {}).get("rect")
    if not tg or not t_rect:
        return "", ""
    over = [(g["rect"][1], gid) for gid, g in gs.items()
            if gid != tg and gid not in folded and g.get("rect") and g["rect"][1] < t_rect[1] - 0.5]
    if not over:
        return "", ""
    gid = max(over)[1]
    live = [(m["rect"][1], a) for a, m in ms.items() if m.get("group") == gid and m.get("raw") in ("running", "waiting")
            and m.get("rect") and m["rect"][3] > 0]
    return (max(live)[1], (gs.get(gid) or {}).get("name", gid)) if live else ("", "")


def _under_sheet(c, V, tests: list) -> dict:
    """(7c) with the box open, the drawing scrolled (as a person scrolls it, the sheet staying where it opened) till the
    first tester lies under the middle of the sheet, when no tester lies under it yet: at the drawer's narrowest a box is
    taller than the room above or below it, so the sheet opens at the drawer's own place (sheetPlace.ts drawerPlace)."""
    js = f"""((k, s, ts) => {{ if (!k || !s) return null; const r = k.getBoundingClientRect(), es = ts.filter(Boolean);
      const t = es.length ? Math.min(...es.map((e) => e.getBoundingClientRect().top)) : null;
      return {{sheet: [r.top, r.bottom], t, scroll: s.scrollTop}}; }})({SHEET}, {V.MSCROLL}, [{', '.join(member(V.M, a) for a in tests)}])"""
    g = c.js(js) or {}
    if g.get("t") is None or any(c.js(f"({MEETS})({SHEET}, {member(V.M, a)})") for a in tests):
        return g
    by = round(g["t"] - (g["sheet"][0] + g["sheet"][1]) / 2 + 24)
    c.js(f"((s) => {{ if (s) s.scrollTop += {by}; return 1; }})({V.MSCROLL})")
    V.frames(c, 3)
    return {**g, "by": by, "after": c.js(js), "still_open": bool(c.js(OPEN))}


def _covered(ctx, c, V, aids: dict, ev: dict, bad: list) -> None:
    """(7c) the box opened in Session's drawer on the lowest running or waiting member of the open group drawn directly
    above the testers' group (3.6.0.15 K2 (a): by the rects, the order the page drew), covering a tester that then ends:
    it must not ring. No member to open is its own named line (never a click on an empty id); the sheet not over a
    tester is the entry's named failure."""
    alt(c, 1)
    if not _wait(c, DRAWER):
        bad.append("(7c) not run: Session's Live drawer was not drawn")
        return
    _away(c, "session")
    s = {k: _aid(c, V, "session", what) for k, what in DESC.items()}
    tests = [s[k] for k in TESTS if s[k]]
    r = _read(c, V, "session")
    on, on_group = above_tests(r, tests)
    if not on:
        cv0 = {"on": "", "lines": r.get("lines") or {}, "order": order_of(r)}
        ev["covered"] = cv0
        bad.extend(judge_live_covered(cv0))
        return
    _into_view(c, V, "session", on)
    cv: dict = {"on": on, "on_group": on_group, "open": _open_on(c, V, "session", on)}
    if cv["open"]:
        cv["place"] = c.js(f"{SHEET}?.dataset.place || ''")
        cv["at"] = _under_sheet(c, V, tests)
        covered = [a for a in tests if c.js(f"({MEETS})({SHEET}, {member(V.M, a)})")]
        cv["pre"] = bool(covered)
        cv["rects"] = {"sheet": c.js(f"({RECT})({SHEET})"), "on": c.js(f"({RECT})({member(V.M, on)})"),
                       **{a: c.js(f"({RECT})({member(V.M, a)})") for a in tests}}
        away = _away(c, "session")
        if covered and _over(away):
            bad.append(_over_line("7c", away))
            cv["pre"] = None
        if cv["pre"]:
            def rangs() -> dict:
                return {a: c.js(f"{member(V.M, a)}?.dataset.rang || ''") for a in covered}
            cv["rang0"], mark = rangs(), len(_hook(c, "rings"))
            ctx.provider.release_late()  # the testers end, the covered one under the open box
            _wait(c, " && ".join(f"({raw_wait(V.M, a, 'done')})" for a in tests))
            raws = {a: c.js(f"{member(V.M, a)}?.dataset.raw || ''") for a in covered}
            cv["raw"] = "done" if all(v == "done" for v in raws.values()) else raws
            cv["rang1"] = rangs()
            cv["rows"] = [r for r in _hook(c, "rings")[mark:] if r.get("id") in covered]
            cv["covered"] = covered
        c.key("Escape")
        _wait(c, GONE)
    ev["covered"] = {k: v for k, v in cv.items() if k != "rows"}
    if not cv["open"]:
        bad.append(f"(7c) a click on {_who(r, on)} (the group {on_group!r}) opened no box in Session's drawer")
    elif cv.get("pre") is not None:  # None: the pointer was over the drawing, said above
        bad.extend(judge_live_covered(cv))


def _reduced(ctx, c, V, aids: dict, ev: dict, bad: list) -> None:
    from tests.helpers.chrome_driver import emulate_motion
    emulate_motion(c, "reduce")  # it holds without a reload
    alt(c, 2)
    if not _wait(c, live_wait(V.LW)):
        bad.append("(8) not run: Agents -> Live was not drawn")
        return
    away = _away(c, "live")
    if _over(away):
        bad.append(_over_line(8, away))
        return
    runs0, rings0 = len(_hook(c, "runs")), len(_hook(c, "rings"))
    _into_view(c, V, "live", aids["ask"])
    r: dict = {"open": _open_on(c, V, "live", aids["ask"])}
    if r["open"]:
        got = c.js(f"((k) => k ? {{d: getComputedStyle(k).transitionDuration.split(',').map((x) => x.trim()),"
                   f" a: k.getAnimations().map((x) => x.animationName || x.transitionProperty || 'an animation')}} : null)({SHEET})") or {}
        r.update(durations=got.get("d") or [], anims=got.get("a") or [])
        c.key("Escape")
        r["gone"] = bool(_wait(c, GONE))
        r["runs"] = [x for x in _hook(c, "runs")[runs0:] if x.get("sheet")]
        _into_view(c, V, "live", aids["long"])
        _away(c, "live")
        rang = f"{member(V.LW, aids['long'])}?.dataset.rang || ''"
        r["rang0"] = c.js(rang)
        ctx.provider.release_last()  # the chart's helper ends with reduced motion
        # its long tool runs LIVE_LONG_S from (4)'s let-go: the wait covers what is left of it (3.6.0.15 K2)
        _wait(c, raw_wait(V.LW, aids["long"], "done"), fakes.LIVE_LONG_S + LIVE_WAIT_S)
        r["raw"] = c.js(f"{member(V.LW, aids['long'])}?.dataset.raw || ''")
        r["rang1"] = c.js(rang)
        r["rings"] = _hook(c, "rings")[rings0:]
        r["member_anims"] = c.js(V.ANIMS) or []
    ev["reduced"] = {k: v for k, v in r.items() if k != "rings"}
    bad.extend(judge_live_reduced(r))
