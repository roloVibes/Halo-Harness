"""scripts/realcheck/steps_map.py -- the step `session-map` (3.6.0.2 "Session map", design section 11): the owner's
sentence, checked the way he lives it. A real Studio (`halo studio`) and a real terminal session (`halo`) in one
scratch home; in the terminal he asks for a workflow (the fake provider answers with one Builder card,
fakes.BUILD_CHANGES); then, each assert alone, every one reported as '(n) what a person saw' with its evidence:

  (1) the card in the terminal says what it builds, word for word (R37's first row, the create row, the use row with
      the one sentence S13 and the terminal's tail), the use row is ticked, and Enter applies it
      (Tab first while the card waits: the card rules)
  (2) Studio, untouched: the word `new` on Session's Live button within 5 s of the outcome reaching the page (Windows:
      5-10 s logged slow, past 10 fails), in a slot that was there before; no drawer opened, no section changed,
      nothing popped up; which path carried it (the builder_done frame or the status row's `built`) is logged
  (3) pressing Live shows the just-built map drawn down, the new box marked, every text at least 12 px, no box cut,
      and the truth block with the same S13 the card said
  (4) Agents (Alt+2) opens on its fourth view Live, drawing the session's own map starter, nothing amber; its Map view
      shows review-flow with the quiet line L2
  (5) the next question's model request carries the [Halo] facts note naming both maps, the build's request none, and
      the Builder result the model read named both maps, said S13 and offered no restart
  (6) two more turns leave the drawer exactly as it was; no /api call failed, no console error; nothing left running

The selectors read here are this check's contract with the packages that build the feature (P3, P4): see the notes
of the package PA. SKIP when no browser may be used or the machine has none (the first thing it does)."""
from __future__ import annotations

import json
import re
import sys
import time

from realcheck import fakes, screen
from realcheck.core import Fail, Skip, browser, excerpt, split_url, wait_address
from realcheck.steps_a import _no_leftovers
from realcheck.steps_b import WATCH

S13 = "This session keeps running on starter (the default), as it started. Start a new session to run on review-flow."
R37_ROW = "Your review workflow: the workflow review (coder, then reviewer), run from a box on the new map review-flow."
CREATE_ROW = "Make a new map review-flow"
USE_ROW = ("New sessions run on review-flow. " + S13 + " In the terminal: quit, then run halo; /clear keeps starter "
           "(the default).")
L2 = "runs on starter (the default), as it started; new sessions run on this map."
WORD_S, WORD_WINDOWS_S = 5.0, 10.0  # the word `new` after the outcome reached the page (Windows: 5-10 s is slow)

Q = "document.querySelector"
BTN = f"{Q}('[data-testid=viewbar-btn][data-panel=session-map]')"
ROW = f"!!{Q}('[data-testid=viewbar]') && !{Q}('[data-testid=session-start]')"  # Studio has the session's row
OFF = (1279, 799)  # where the pointer rests while a drawing is read (R12 holds while it is over the drawing)

# the Builder's outcome as the page receives it (a `builder_done` frame on the feed, or a status row whose `built`
# says applied), the moment the word `new` shows, and what popped up: installed before the first load, beside WATCH
HOOK = r"""(() => { if (window.__rcb) return; const b = window.__rcb = {frame: 0, row: 0, word: 0, pops: [], followed: []};
  try { performance.setResourceTimingBufferSize(100000); } catch (e) {}  // (6) counts fleet reads past 250 entries
  const now = () => performance.now();
  const applied = (v, d) => { if (!v || typeof v !== 'object' || d > 8) return false;
    if (v.built && typeof v.built === 'object' && v.built.outcome === 'applied') return true;
    for (const k in v) if (applied(v[k], d + 1)) return true; return false; };
  const seen = (text) => { if (b.row) return; try { if (applied(JSON.parse(text), 0)) b.row = now(); } catch (e) {} };
  const ES = window.EventSource;
  if (ES) { const W = function (u, o) { const es = new ES(u, o);
      es.addEventListener('builder_done', () => { b.frame = b.frame || now(); });
      es.addEventListener('sessions', (ev) => { try { const f = JSON.parse(ev.data);
        b.followed = (((f || {}).data || {}).sessions || []).map((r) => r.session_id); } catch (e) {} });
      for (const k of ['live', 'registry']) es.addEventListener(k, (ev) => seen(ev.data));
      return es; };
    W.prototype = ES.prototype; W.CONNECTING = 0; W.OPEN = 1; W.CLOSED = 2; window.EventSource = W; }
  const f = window.fetch;
  window.fetch = function (u, o) { const p = f.apply(this, arguments); const s = String(u && u.url || u).replace(/[?#].*$/, '');
    if (/\/api\/live$/.test(s)) p.then((r) => r.clone().text()).then(seen).catch(() => {}); return p; };
  const look = () => {
    const w = document.querySelector('[data-testid=viewbar-btn][data-panel=session-map] [data-testid=viewbar-word]');
    if (!b.word && w && w.textContent.trim() === 'new') b.word = now();
    for (const e of document.querySelectorAll('[role=dialog], .toast')) if (!e.__rcSeen) { e.__rcSeen = 1;
      b.pops.push(String(e.className || e.getAttribute('role')) + ': ' + String(e.textContent || '').slice(0, 80)); } };
  document.addEventListener('DOMContentLoaded', () => { look(); new MutationObserver(look).observe(document.body,
    {subtree: true, childList: true, characterData: true, attributes: true}); }); })();"""


def _flat(text: str) -> str:
    """Text with every space and box-drawing character taken out: a redraw or a wrap splits only those."""
    return re.sub(r"[\s─-╿]+", "", text or "")


def alt(c, n: int) -> None:
    """Alt+<n>, the section keys (tests/helpers/studio_session.alt)."""
    for kind in ("keyDown", "keyUp"):
        c.call("Input.dispatchKeyEvent", type=kind, key=str(n), code=f"Digit{n}", windowsVirtualKeyCode=48 + n, modifiers=1)


def _off(c) -> None:
    c.call("Input.dispatchMouseEvent", type="mouseMoved", x=OFF[0], y=OFF[1], button="none", buttons=0)


def _wait(c, expr: str, timeout: float):
    try:
        return c.wait(expr, timeout)
    except TimeoutError:
        return None


def _say(t, text: str) -> int:
    """Type a line into the session and press Enter; the screen's length before it (what came after is the answer)."""
    mark = len(t.plain())
    t.type(text)
    time.sleep(0.3)
    t.write(b"\r")
    return mark


def _alone(n: int, bad: list, fn, *args):
    """One assert: what the checker itself could not do is said as that assert's, never stops the next one."""
    try:
        return fn(*args)
    except Exception as e:
        bad.append(f"({n}) not run: realcheck could not read the page or the screen: {type(e).__name__}: {str(e)[:160]}")
        return None


def session_map(ctx):
    from tests.helpers.chrome_driver import open_chrome
    exe = browser(ctx)  # first: --browser none is a SKIP before any halo starts
    if not exe:
        raise Skip("no Chrome or Chromium on this machine (HALO_CHROME or --browser names one)")
    h = ctx.home("session-map")
    ts = ctx.terminal(h, "studio")
    url, at, meanwhile = wait_address(ctx, h, ts, 60)
    if not url:
        screen.quit_with_ctrl_c(ts)
        ts.cleanup()
        ctx.end_leftovers(h)
        raise Fail(f"`halo studio` printed no address in {at:.0f} s: " + excerpt(ts.plain(), 200),
                   {"while_waiting": meanwhile})
    base, token = split_url(url)
    ev: dict = {"address_s": round(at, 1)}
    bad: list = []
    c = t = None
    try:
        c = open_chrome(1280, 800, exe=exe)
        c.call("Emulation.setDeviceMetricsOverride", width=1280, height=800, deviceScaleFactor=1, mobile=False)
        c.call("Page.enable")
        for src in (WATCH, HOOK):
            c.call("Page.addScriptToEvaluateOnNewDocument", source=src)
        c.go(f"{base}/?mode=session&tour=off#t={token}")  # no `open=`: a fresh profile has the drawer closed
        t = ctx.terminal(h, cols=200, rows=50)  # `halo` in the same home and project, as a person types it
        ev["session_up_s"] = round(screen.tui_ready(t, 60), 1)
        if not ev["session_up_s"]:
            bad.append("(1)-(6) not run: the terminal session never showed its status line in 60 s: "
                       + excerpt(t.plain(), 200))
        else:
            ev["row_seen"] = bool(_wait(c, ROW, 30))
            _followed(c, ev, bad)
            before = c.js(BEFORE) or {}
            ev["before"] = before
            applied = _alone(1, bad, _card, t, ev, bad) or 0.0
            _alone(2, bad, _word, c, before, applied, ev, bad)
            ev["build_reply"] = bool(t.wait_for(lambda s: fakes.MAPBUILD_DONE in s, 30))
            _alone(3, bad, _drawn, c, ev, bad)
            _alone(4, bad, _agents, c, ev, bad)
            _alone(5, bad, _note, ctx, t, ev, bad)
            _alone(6, bad, _turns, ctx, t, c, ev, bad)
            page = c.js("window.__rc ? {failed: window.__rc.failed, errors: window.__rc.errors} : null") or {}
            ev["page"] = page
            if page.get("failed"):
                bad.append(f"(6) failed /api call(s): {page['failed'][:3]}")
            if page.get("errors"):
                bad.append(f"(6) console error {page['errors'][0][:160]!r}")
    finally:
        if c is not None:
            c.close()
        for term in (t, ts):
            if term is not None:
                screen.quit_with_ctrl_c(term)
                term.cleanup()
        try:
            _no_leftovers(ctx, h, "the session and Studio")
        except Fail as e:
            bad.append("(6) left running: " + e.detail)
            ev["left"] = e.evidence.get("left")
        ctx.end_leftovers(h)
    if bad:
        raise Fail("; ".join(bad[:8]) + (f" (+{len(bad) - 8} more)" if len(bad) > 8 else ""), ev)
    w = ev.get("word") or {}
    return (f"the card, the word new in {w.get('lag_ms', 0) / 1000:.1f} s ({w.get('path')}), the drawing down, Agents "
            "on Live, the note, three turns held still"), ev


FOLLOWED = "window.__rcb && window.__rcb.followed && window.__rcb.followed.length > 0"
FOLLOW_S = 30.0


def _followed(c, ev: dict, bad: list) -> bool:
    """Studio follows the session before he types (its feed's `sessions` frame lists it). Studio's feed attaches a new
    session on its 2-s scan; a person has not typed a request by then, but this rig types at once, and what the
    session sent before the attach (the `builder_done` frame) never reached the page. How long it took is evidence."""
    t0 = time.monotonic()
    ok = bool(_wait(c, FOLLOWED, FOLLOW_S))
    ev["followed_s"] = round(time.monotonic() - t0, 1) if ok else None
    if not ok:
        bad.append(f"(2) Studio never followed the session in {FOLLOW_S:.0f} s (no `sessions` frame on its feed "
                   "listed it)")
    return ok


# -- (1) the card ------------------------------------------------------------------------------------------------------
def _card(t, ev: dict, bad: list) -> float:
    """Type the request, read the card the terminal shows, press Enter (Apply is its first option). The moment of the
    press, or 0 when no card showed."""
    mark = _say(t, fakes.BUILD_PROMPT)
    shown = t.wait_for(lambda s: card_seen(s[mark:])["shown"], 30)
    seen = t.plain()[mark:]
    got = card_seen(seen)
    missing, ticked = got["missing"], got["ticked"]
    ev["card"] = {"screen": seen[-1500:], "missing": missing, "ticked": ticked, "shown": shown}
    if not shown:
        bad.append("(1) no Builder card in 30 s: " + excerpt(seen, 160))
        return 0.0
    if missing or not ticked:
        h = CARD_HEAD_TEXT.search(seen)
        bad.append(f"(1) the card lacks {', '.join(missing) or 'nothing'}"
                   + ("" if ticked else "; the use row is not ticked inside the Apply question")
                   + ": " + excerpt(seen[h.start():] if h else seen, 160))
    ev["card"]["key"] = _answer(t, mark)
    return time.monotonic()


# the line above the box while a card waits (tui/widgets/cards.py WAIT_LINE / WAIT_LINE_SHORT, and the held box's
# placeholder HELD_PLACEHOLDER): "⏸ Question waits ... Tab goes to it", "Tab: go to the waiting card"
CARD_WAITS = re.compile(r"⏸\w+waits|Tab:gotothewaitingcard")  # read in _flat text: a redraw splits only spaces
CARD_SIGN_S = 10.0  # how long the step looks for the wait line: a runner 5-10x slower than the PC redraws late


def _answer(t, mark: int) -> str:
    """Apply the card the way a person does under the card rules (tui/card_focus.py): a card shown within
    CARD_WAIT_S of a key into the box WAITS (its line above the box says so) and Enter in the box never answers it,
    so he presses Tab, then the card's key; a card that took the focus answers its key at once. A card answers no key
    in its first CARD_FRESH_S on screen, so the key comes after that. Which way it went is returned for the evidence."""
    from halo_harness.tui.keys import CARD_FRESH_S
    seen_at = time.monotonic()
    # the focus is decided right after the card shows (card_focus.decide, through call_later) and its wait line is
    # drawn in a later redraw: looked for a slow runner's while; a card that took the focus shows no sign in plain
    # text, so Enter goes only once the look is over (CARD_SIGN_S: the rare path pays the time, never a lost Apply)
    waited = t.wait_for(lambda s: CARD_WAITS.search(_flat(s[mark:])) is not None, CARD_SIGN_S)
    rest = CARD_FRESH_S + 0.2 - (time.monotonic() - seen_at)
    if rest > 0:  # the card's first moments (a rule's time, not a redraw): a key now would answer nothing
        time.sleep(rest)
    if not waited:
        t.write(b"\r")
        return "Enter: the card had the focus"
    at = len(t.plain())
    t.write(b"\t")
    # the Tab turns to the card (K7): the wait line is taken down in a redraw; the key goes after that redraw
    turned = t.wait_for(lambda s: len(s) > at, 5)
    t.write(b"\r")
    return "Tab, then Enter: the card waited (its line was above the box)" + ("" if turned else
                                                                              "; no redraw after the Tab in 5 s")


# the card's question, in _flat text: section 4 "Builder: apply these {n} changes?" (the base: "Apply these N ...")
CARD_HEAD = re.compile("applythese", re.I)
CARD_HEAD_TEXT = re.compile(r"apply\s+these", re.I)


def card_seen(seen: str) -> dict:
    """What the terminal shows of the Builder card: its question (shown), the rows it lacks (missing), and whether the
    use row is ticked (it lies inside the question: no "Line <k>" question before it, no "not ticked" after it)."""
    flat = _flat(seen)
    want = {"R37 row": R37_ROW, "create row": CREATE_ROW, "use row": USE_ROW}
    missing = [k for k, v in want.items() if _flat(v) not in flat]
    h, use = CARD_HEAD.search(flat), _flat(USE_ROW)
    i0, iu = (h.start() if h else -1), flat.find(use)
    ticked = (0 <= i0 < iu and not re.search(r"Line\d", flat[i0:iu], re.I)
              and not re.search("notticked", flat[iu + len(use):iu + len(use) + 40], re.I))
    return {"shown": h is not None, "missing": missing, "ticked": ticked}


# -- (2) the word new --------------------------------------------------------------------------------------------------
BEFORE = f"""(() => {{ const b = {BTN}; const rects = {{}};
  for (const e of document.querySelectorAll('[data-testid=viewbar-btn]')) {{ const r = e.getBoundingClientRect();
    rects[e.dataset.panel] = [r.left, r.top, r.width, r.height]; }}
  const w = b && b.querySelector('[data-testid=viewbar-word]');
  return {{slot: !!w, empty: !!w && !w.textContent.trim(), rects, pops: (window.__rcb || {{}}).pops?.length || 0}}; }})()"""

AFTER = f"""(() => {{ const b = {BTN}; const rects = {{}};
  for (const e of document.querySelectorAll('[data-testid=viewbar-btn]')) {{ const r = e.getBoundingClientRect();
    rects[e.dataset.panel] = [r.left, r.top, r.width, r.height]; }}
  const shown = [...document.querySelectorAll('.section-view')].filter((s) => s.offsetParent).map((s) => s.dataset.section);
  const w = b && b.querySelector('[data-testid=viewbar-word]');
  return {{name: b ? (b.querySelector('.viewbar-name') || {{}}).textContent || '' : 'no button', title: b ? b.title : '',
          pressed: b ? b.getAttribute('aria-pressed') : '', word: w ? w.textContent.trim() : null,
          drawer: !!document.querySelector('.stage-drawer[data-panel-in=session-map]'), sections_shown: shown, rects,
          rcb: window.__rcb || null}}; }})()"""


def _word(c, before: dict, applied: float, ev: dict, bad: list) -> None:
    got = _wait(c, "window.__rcb && (window.__rcb.frame || window.__rcb.row)", 30) if applied else None
    ev["apply_to_page_s"] = round(time.monotonic() - applied, 1) if got else None  # evidence: the key to the page
    rcb = c.js("window.__rcb") or {}
    t0 = min([x for x in (rcb.get("frame"), rcb.get("row")) if x] or [0])
    path = "none" if not got else ("frame" if t0 == rcb.get("frame") else "row")
    if t0:
        _wait(c, "window.__rcb.word", 10)
    a = c.js(AFTER) or {}
    rcb = a.get("rcb") or {}
    lag = (rcb.get("word") or 0) - t0 if t0 and rcb.get("word") else -1
    moved = [k for k, r in (before.get("rects") or {}).items()
             if any(abs(x - y) > 0.5 for x, y in zip(r, (a.get("rects") or {}).get(k) or [1e9] * 4))]
    pops = (rcb.get("pops") or [])[before.get("pops") or 0:]
    slow = lag > WORD_S * 1000
    ev["word"] = {"frame_ms": rcb.get("frame"), "row_ms": rcb.get("row"), "word_ms": rcb.get("word"), "lag_ms": lag,
                  "path": path, "slow": slow, "name": a.get("name"), "title": a.get("title"), "pressed": a.get("pressed"),
                  "drawer": a.get("drawer"), "sections_shown": a.get("sections_shown"), "pops": pops, "moved": moved,
                  "slot_before": before.get("slot"), "slot_empty_before": before.get("empty")}
    says = []
    if not applied:
        says.append("not run: the card was never applied")
    elif not t0:
        says.append("the Builder's outcome never reached the page in 30 s")
    if a.get("word") != "new":
        says.append(f"no word new on the Live button (it reads {a.get('name')})")
    elif lag > WORD_WINDOWS_S * 1000 or (slow and sys.platform != "win32"):
        says.append(f"the word new came {lag / 1000:.1f} s after the outcome reached the page (budget "
                    f"{WORD_WINDOWS_S if sys.platform == 'win32' else WORD_S:.0f} s)")
    if not before.get("slot") or not before.get("empty"):
        says.append("no empty slot for the word before the build")
    if a.get("name") != "Live" or "(was Map)" not in (a.get("title") or ""):
        says.append(f"the button reads {a.get('name')!r}, its hover {a.get('title', '')[:60]!r}")
    if a.get("pressed") != "false" or a.get("drawer"):
        says.append("the drawer opened by itself")
    if a.get("sections_shown") != ["session"]:
        says.append(f"the section changed: {a.get('sections_shown')}")
    if pops:
        says.append(f"something popped up: {pops[0]}")
    if moved:
        says.append(f"view-bar buttons moved: {moved}")
    if says:
        bad.append("(2) " + "; ".join(says))


# -- (3) the drawing -----------------------------------------------------------------------------------------------------
DRAWN = """(() => { const q = (s, r) => (r || document).querySelector(s), qa = (s, r) => [...(r || document).querySelectorAll(s)];
  const R = (e) => { const r = e.getBoundingClientRect(); return {x: r.left, y: r.top, w: r.width, h: r.height}; };
  const drawer = q('.stage-drawer[data-panel-in=session-map]');
  const pair = q('[data-testid=session-map-pair]'), built = pair && q('[data-which=built]', pair);
  const m = q('[data-testid=session-lit-map]'), sc = m && q('.mp-mini-scroll', m), world = m && q('.mp-mini-world', m);
  const zoom = world ? parseFloat(world.dataset.zoom || '1') : 0;
  const boxes = m ? qa('[data-testid=session-lit-box]', m).map((b) => ({box: b.dataset.box, ...R(b),
    new: b.hasAttribute('data-new'), text: (b.innerText || '').replace(/\\s+/g, ' ').slice(0, 60),
    all: (b.innerText || '').replace(/\\s+/g, ' ')})) : [];
  const texts = m ? qa('.mp-name, .mp-lit-row, .mp-step', m) : [];
  const small = texts.filter((e) => parseFloat(getComputedStyle(e).fontSize) * zoom < 11.99).map((e) => e.textContent.slice(0, 40));
  const ellipsis = texts.filter((e) => getComputedStyle(e).textOverflow === 'ellipsis' && e.scrollWidth > e.clientWidth)
    .map((e) => e.textContent.slice(0, 40));
  const truth = q('[data-testid=session-truth]'), more = m && q('[data-testid=map-more-below]', m);
  return {drawer: drawer ? drawer.innerText.replace(/\\s+/g, ' ').slice(0, 160) : 'no drawer',
          pair: pair ? pair.innerText.replace(/\\s+/g, ' ') : '', built_pressed: built ? built.getAttribute('aria-pressed') : '',
          map: m ? m.dataset.map : '', dir: m ? (m.dataset.dir || '') : '', zoom, boxes, small_px: small, ellipsis,
          scroll: sc ? R(sc) : null, more_below: more ? more.textContent.trim() : '',
          truth: truth ? truth.innerText.replace(/\\s+/g, ' ') : '',
          new_session: truth ? qa('button', truth).some((x) => x.textContent.trim() === 'New session') : false}; })()"""


TRUTH_SAYS_S13 = (f"(({Q}('[data-testid=session-truth]') || {{}}).innerText || '').replace(/\\s+/g, ' ')"
                  f".includes({json.dumps(S13)})")


def _drawn(c, ev: dict, bad: list) -> None:
    c.click_on(BTN)
    _off(c)
    _wait(c, f"!!{Q}('[data-testid=session-lit-map][data-map=review-flow]')", 10)
    _off(c)
    # the truth block reads the status row (R28), which reaches the page a moment after the frame (0.3 s on the VM)
    t0 = time.monotonic()
    said = _wait(c, TRUTH_SAYS_S13, WORD_S)
    truth_s = round(time.monotonic() - t0, 2) if said else None
    d = c.js(DRAWN) or {}
    boxes, sc = d.get("boxes") or [], d.get("scroll")
    main = next((b for b in boxes if b["box"] == "main"), None)
    rows: dict = {}
    for b in boxes:
        rows.setdefault(round(b["y"] / 2), []).append(b["box"])
    cut, below = [], []
    for b in boxes if sc else []:
        top, bottom = b["y"], b["y"] + b["h"]
        inside = (top >= sc["y"] - 0.5 and bottom <= sc["y"] + sc["h"] + 0.5 and b["x"] >= sc["x"] - 0.5
                  and b["x"] + b["w"] <= sc["x"] + sc["w"] + 0.5)
        if top >= sc["y"] + sc["h"] - 0.5:
            below.append(b["box"])
        elif not inside:
            cut.append(b["box"])
    review = next((b for b in boxes if b["box"] == "review"), {})
    ev["drawn"] = {k: d.get(k) for k in ("pair", "built_pressed", "map", "dir", "zoom", "small_px", "ellipsis",
                                         "more_below", "truth", "new_session", "drawer")}
    ev["drawn"].update(truth_s=truth_s)
    ev["drawn"].update(boxes=[{k: v for k, v in b.items() if k != "all"} for b in boxes], cut=cut, below=below,
                       rows_per_line=max((len(v) for v in rows.values()), default=0))
    if d.get("map") != "review-flow":
        bad.append(f"(3) the drawer shows {d.get('drawer', '')[:100]!r}, not the map review-flow")
        return
    says = []
    if "Running: starter" not in d.get("pair", "") or "Just built: review-flow" not in d.get("pair", "") \
            or d.get("built_pressed") != "true":
        says.append(f"no Running / Just built pair with Just built chosen ({d.get('pair', '')[:80]!r})")
    if d.get("dir") != "down":
        says.append(f"drawn {d.get('dir') or 'left to right'}, not down")
    if not main or any(b["y"] < main["y"] + main["h"] - 0.5 for b in boxes if b is not main):
        says.append("a box is not below main")
    if ev["drawn"]["rows_per_line"] > 2:
        says.append(f"{ev['drawn']['rows_per_line']} boxes in one row")
    if not all(w in review.get("all", "") for w in ("workflow review", "coder", "reviewer")) or not review.get("new"):
        says.append(f"the box review is not its marked workflow block ({review.get('text', 'no box')!r})")
    if any(w in b["all"] for b in boxes for w in ("helper", "made up", "Save as an agent")):
        says.append("a box says helper / made up")
    if (d.get("zoom") or 0) < 1.0 or d.get("small_px") or d.get("ellipsis"):
        says.append(f"text under 12 px or cut short (zoom {d.get('zoom')}, {(d.get('small_px') or d.get('ellipsis'))[:2]})")
    if cut or (below and d.get("more_below") != f"↓ {len(below)} more below"):
        says.append(f"boxes cut {cut} / below without the line ({d.get('more_below')!r})")
    if S13 not in d.get("truth", "") or not d.get("new_session") or "In the terminal" in d.get("truth", ""):
        says.append(f"the truth block does not say S13 with [New session] ({d.get('truth', '')[:80]!r})")
    if says:
        bad.append("(3) " + "; ".join(says))


# -- (4) Agents opens on Live ------------------------------------------------------------------------------------------
AGENTS = f"{Q}('[data-testid=agents]')"


def _agents(c, ev: dict, bad: list) -> None:
    alt(c, 2)
    view = _wait(c, f"(() => {{ const a = {AGENTS}; if (!a || !{Q}('[data-testid=agents-view-crew]')) return null; "
                    f"if (a.dataset.view === 'live') return 'live'; "
                    f"return {Q}('[data-testid=agents-view-live]') ? null : 'no live view: ' + a.dataset.view; }})()", 10)
    a = c.js(f"""(() => {{ const a = {AGENTS}, live = {Q}('[data-testid=agents-view-live]'), root = {Q}('[data-testid=agents-live]');
      return {{view: a ? a.dataset.view : '', tabs: [...document.querySelectorAll('[data-testid^=agents-view-]')].map((x) => x.textContent.trim()),
              selected: live ? live.getAttribute('aria-selected') : '', live_map: root ? root.dataset.map : '',
              amber: !!(a && a.querySelector('.mp-amber, [data-lit=other], [data-testid=map-show-running]'))}}; }})()""") or {}
    ev["agents"] = a
    says = []
    if a.get("view") != "live" or a.get("selected") != "true":
        says.append(f"Agents opened on {a.get('view') or 'nothing'}" + ("" if "4 · Live" in (a.get("tabs") or [])
                                                                       else ", it has no Live view"))
    elif a.get("tabs") != ["1 · Agents", "2 · Workflows", "3 · Map", "4 · Live"]:
        says.append(f"the views read {a.get('tabs')}")
    if a.get("view") == "live" and a.get("live_map") != "starter":
        says.append(f"Live draws {a.get('live_map')!r}, not starter")
    if a.get("amber"):
        says.append("an amber line shows")
    ev["agents"]["waited"] = view
    try:
        c.click_on(f"{Q}('[data-testid=agents-view-map]')")
        _wait(c, f"{Q}('[data-testid=map-switcher]')?.value === 'review-flow' && "
                 f"({Q}('[data-testid=map-topline]')?.innerText || '').includes({L2!r})", 10)
        m = c.js(f"""(() => {{ const s = {Q}('[data-testid=map-switcher]'), top = {Q}('[data-testid=map-topline]');
          return {{map_value: s ? s.value : '', topline: top ? top.innerText.replace(/\\s+/g, ' ') : '',
                  watch: top ? [...top.querySelectorAll('button')].some((b) => b.textContent.trim() === 'Watch it in Live') : false,
                  amber: !!{Q}('.mp-amber')}}; }})()""") or {}
    except Exception as e:
        m = {"error": f"{type(e).__name__}: {e}"[:200]}
    ev["agents"].update(map=m)
    if m.get("map_value") != "review-flow" or L2 not in (m.get("topline") or "") or not m.get("watch") or m.get("amber"):
        says.append(f"3 · Map shows {m.get('map_value')!r} with {(m.get('topline') or m.get('error') or '')[:90]!r}, "
                    "not review-flow with L2 and Watch it in Live")
    alt(c, 1)
    if says:
        bad.append("(4) " + "; ".join(says))


# -- (5) the facts note -------------------------------------------------------------------------------------------------
def _users(req: dict) -> list:
    return [fakes._text(m.get("content")) for m in (req.get("body") or {}).get("messages") or []
            if isinstance(m, dict) and m.get("role") == "user"]


def _note(ctx, t, ev: dict, bad: list) -> None:
    _say(t, fakes.ASK_PROMPT)
    answered = t.wait_for(lambda s: fakes.MAPASK_DONE in s, 30)
    p = ctx.provider
    ask, build = (p.requests_with("RC-MAPASK") or [{}])[0], (p.requests_with("RC-MAPBUILD") or [{}])[0]
    notes = [u[u.find("[Halo]"):] for u in _users(ask) if "[Halo]" in u]
    note = next((n for n in notes if "review-flow" in n and "starter" in n), notes[0] if notes else "")
    build_note = next((u for u in _users(build) if "[Halo]" in u), "")
    result = ""
    for r in p.requests_with("RC-MAPBUILD"):
        tools = [fakes._text(m.get("content")) for m in (r.get("body") or {}).get("messages") or []
                 if isinstance(m, dict) and m.get("role") == "tool"]
        if tools:
            result = tools[0]
            break
    ev["note"] = {"mapask_note": note[:600], "mapbuild_note": build_note[:300], "builder_result": result[:600],
                  "answered": answered,
                  "screen_answer": _flat(fakes.MAPBUILD_DONE + " " + S13) in _flat(t.plain())}
    says = []
    if not answered:
        says.append("no answer to RC-MAPASK in 30 s")
    if not note or "review-flow" not in note or "starter" not in note:
        says.append("the RC-MAPASK request carries no [Halo] note naming both maps")
    if build_note:
        says.append("the RC-MAPBUILD request carried a note")
    lacks = [k for k, w in (("review-flow", "review-flow"), ("starter (the default)", "starter (the default)"),
                            ("S13", S13)) if w not in result]
    if lacks:
        says.append("the Builder result names neither " + " nor ".join(lacks) if len(lacks) > 1
                    else f"the Builder result lacks {lacks[0]}")
    if re.search("restart", result, re.I):
        says.append("the Builder result offers a restart")
    # what the person reads in the terminal: the agent's reply to the build, and in it the one sentence S13
    if not ev.get("build_reply"):
        says.append(f"the terminal never showed the agent's reply {fakes.MAPBUILD_DONE} in 30 s")
    elif not ev["note"]["screen_answer"]:
        says.append(f"the terminal's reply {fakes.MAPBUILD_DONE} does not say S13")
    if says:
        bad.append("(5) " + "; ".join(says))


# -- (6) turns hold the drawer ------------------------------------------------------------------------------------------
# the page's reads of the fleet (tests/helpers/studio_session_map_down.FLEET_READS): "after a turn" is after the next one
FLEET_READS = "performance.getEntriesByType('resource').filter((e) => /\\/api\\/live(\\?|$)/.test(e.name)).length"
SAMPLE = f"""(() => {{ const truth = {Q}('[data-testid=session-truth]'), m = {Q}('[data-testid=session-lit-map]');
  const sc = m && m.querySelector('.mp-mini-scroll'), main = m && m.querySelector('[data-testid=session-lit-box][data-box=main]');
  const d = {Q}('.stage-drawer[data-panel-in=session-map]');
  return {{truth: truth ? truth.innerText.replace(/\\s+/g, ' ') : null, truth_h: truth ? truth.offsetHeight : null,
          map: m ? m.dataset.map : null, top: sc ? sc.getBoundingClientRect().top : null,
          main_top: main ? main.getBoundingClientRect().top : null,
          shows: d ? d.innerText.replace(/\\s+/g, ' ').slice(0, 160) : 'no drawer'}}; }})()"""


def _same(a: dict, b: dict) -> bool:
    if a.get("truth") is None or a.get("map") is None or a.get("truth") != b.get("truth") or a.get("map") != b.get("map"):
        return False
    return all(a.get(k) is not None and b.get(k) is not None and abs(a[k] - b[k]) <= 0.5
               for k in ("truth_h", "top", "main_top"))


def _turns(ctx, t, c, ev: dict, bad: list) -> None:
    def sample(when: str) -> dict:
        _off(c)
        s = c.js(SAMPLE) or {}
        s["when"] = when
        ev["turns"].append(s)
        return s
    ev["turns"] = []
    if not c.js(f"!!{Q}('.stage-drawer[data-panel-in=session-map]')"):  # (4) went to Agents and back: open it again
        c.click_on(BTN)
        _wait(c, f"!!{Q}('.stage-drawer[data-panel-in=session-map]')", 5)
        ev["turns_reopened"] = True
    s0 = sample("before")
    first_bad = None if s0.get("map") and s0.get("truth") is not None else s0
    for n, words in ((2, "RC-ASK turn two"), (3, "RC-ASK turn three")):
        mark = _say(t, words)
        # while the turn runs: its request has reached the provider (the event, not a fixed sleep)
        t.wait_for(lambda s: len(ctx.provider.requests_with(words)) > 0, 30)
        during = sample(f"during {n}")
        t.wait_for(lambda s: fakes.ANSWER in s[mark:], 30)
        reads = c.js(FLEET_READS) or 0
        ev.setdefault("fleet_read_after", []).append(_wait(c, f"{FLEET_READS} > {reads}", 15))  # a fleet read lands
        after = sample(f"after {n}")
        for s in (during, after):
            if first_bad is None and not _same(s0, s):
                first_bad = s
    if first_bad is not None:
        what = ("the drawer shows " + repr(first_bad.get("shows", "")[:100])) if first_bad.get("map") is None \
            or first_bad.get("truth") is None else "the drawer changed (truth block, map or top)"
        bad.append(f"(6) {first_bad['when'].replace('during', 'while turn').replace('after', 'after turn')}: {what}")
