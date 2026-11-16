"""tests.helpers.studio_session_built -- the owner's sentence in a browser on the Linux VM, without a model and without
a terminal (Halo 3.6.0.2 "Session map", design section 11, the VM browser test): over this harness's REAL session
(tests/helpers/studio_session_rig.py: open, on the map starter, two agents held mid-work) the workflow `review` and the
new map `review-flow` are written as an applied Builder card writes them, new sessions are switched to review-flow
(config `crew.map`), and the Builder's outcome frame `builder_done` (R25, built by hand from the documented wire shape)
is published through Studio's own bridge. Then, at 1280 x 800, Studio's page is read:

    built    Session loads (no `open=`: the drawer starts closed), the view bar's rects and the word's slot are recorded,
             the page's event feed is open, the frame is sent
    word     (2) the word `new` on Session's Live button within 10 s, no button moved, nothing opened or popped up
    drawn    (3) a press on Live: the pair, the just-built map drawn down, the new box marked, text >= 12 px, no box
             cut, the truth block S13 with New session; S0 kept for (6)
    turns    (6) the rig's turn ends and two more come and go: the drawer stays exactly as S0
    agents   (4) Alt+2 opens Agents on its fourth view Live (starter, nothing amber); 3 · Map shows review-flow with L2

Every step catches its own waits and returns what it saw (no step raises); `verdicts(got)` says, per assert, what a
person would have seen wrong. The words and the page reads are scripts/realcheck/steps_map.py's (one place).

    python -m tests.helpers.studio_session_built        (the last stdout line is the JSON)
"""
from __future__ import annotations

import sys
import time
from contextlib import contextmanager
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO))
sys.path.insert(0, str(REPO / "scripts"))

from tests.helpers.chrome_driver import Driver  # noqa: E402
from realcheck.steps_map import AFTER, BEFORE, BTN, DRAWN, L2, OFF, Q, ROW, S13, SAMPLE, alt  # noqa: E402

FLOW = {"format": "workflow/1", "name": "review", "for": "review",
        "steps": [{"name": "code", "agents": ["coder"]}, {"name": "review", "agents": ["reviewer"]}]}
MAP = """format: map/1
name: review-flow
boxes:
- {id: review, workflow: review}
lines:
- {from: main, to: review, when: always}
"""
TABS = ["1 · Agents", "2 · Workflows", "3 · Map", "4 · Live"]
WORD_S, STEPS_S = 10.0, 60.0  # the word after the frame; the whole run from the frame's publish
LIVE_STATES = ("queued", "running", "waiting")

# the page's event feed: how many EventSource connections have opened (the frame is sent only after one has)
OPEN_HOOK = r"""(() => { if (window.__sbOpen !== undefined) return; window.__sbOpen = 0; const ES = window.EventSource;
  if (!ES) return; const W = function (u, o) { const es = new ES(u, o); es.addEventListener('open', () => { window.__sbOpen += 1; });
  return es; }; W.prototype = ES.prototype; W.CONNECTING = 0; W.OPEN = 1; W.CLOSED = 2; window.EventSource = W; })();"""
POPS = """(() => { const vis = (e) => !!(e.offsetParent || e.getClientRects().length);
  return {dialogs: [...document.querySelectorAll('[role=dialog]')].filter(vis).length,
          toasts: [...document.querySelectorAll('.toast')].filter(vis).length}; })()"""
AGENTS = f"""(() => {{ const a = {Q}('[data-testid=agents]'), live = {Q}('[data-testid=agents-view-live]'),
  root = {Q}('[data-testid=agents-live]');
  return {{view: a ? a.dataset.view : '', live_tab: live ? {{selected: live.getAttribute('aria-selected'), text: live.textContent.trim()}} : null,
          tabs: [...document.querySelectorAll('[data-testid^=agents-view-]')].map((x) => x.textContent.trim()),
          live_map: root ? root.dataset.map : '',
          amber: a ? a.querySelectorAll('.mp-amber, [data-lit=other], [data-testid=map-show-running]').length : 0}}; }})()"""
MAP_VIEW = f"""(() => {{ const s = {Q}('[data-testid=map-switcher]'), top = {Q}('[data-testid=map-topline]');
  return {{map_value: s ? s.value : '', topline: top ? top.innerText.replace(/\\s+/g, ' ') : '',
          watch_button: top ? [...top.querySelectorAll('button')].some((b) => b.textContent.trim() === 'Watch it in Live') : false}}; }})()"""


def seed_built(rig) -> dict:
    """What an applied card writes: the workflow `review`, the map `review-flow`, new sessions on it. The map's body."""
    from halo_harness.crew import store
    from halo_harness.theme import set_config_value
    store.write_text(store.path_for("workflow", "review", state_dir=rig.state), store.dump(FLOW))
    path = store.path_for("map", "review-flow", state_dir=rig.state)
    store.write_text(path, MAP)
    set_config_value("crew.map", "review-flow")
    return store.read(path) or {}


def frame(lv, body: dict) -> dict:
    """The `builder_done` frame an applied card in this session sends (design section 6 / R25), from main."""
    data = {"id": "card-rc-1", "outcome": "applied",
            "wrote": [{"kind": "workflow", "name": "review", "added": True}, {"kind": "map", "name": "review-flow", "added": True}],
            "undo": "u-rc-1", "next": "review-flow", "this_session": "starter", "maps": {"review-flow": body}, "t": time.time()}
    lv.frame("main", "builder_done", data)
    return data


def _wait(c, expr: str, timeout: float):
    try:
        return c.wait(expr, timeout)
    except TimeoutError:
        return None


def _off(c) -> None:
    c.mouse("mouseMoved", *OFF)


def built(c, rig, lv, st) -> dict:
    c.call("Page.enable")  # the hook runs before any page script
    c.call("Page.addScriptToEvaluateOnNewDocument", source=OPEN_HOOK)
    c.go(rig.url("session"))
    reached = bool(_wait(c, ROW, 20))
    feed = bool(_wait(c, "window.__sbOpen > 0", 10))
    before = c.js(BEFORE) or {}
    st["rects"] = before.get("rects") or {}
    st["slot"] = bool(before.get("slot") and before.get("empty"))  # the word's slot is there, empty, before the build
    st["sent"] = time.monotonic()
    frame(lv, st["body"])
    return {"reached": reached, "feed_open": feed, "frame_sent": True,
            "before": {"slot": before.get("slot"), "empty": before.get("empty")}}


def word(c, rig, lv, st) -> dict:
    seen = _wait(c, f"{BTN}?.querySelector('[data-testid=viewbar-word]')?.textContent.trim() === 'new'", WORD_S)
    seconds = round(time.monotonic() - st["sent"], 2) if seen else None
    a, pops = c.js(AFTER) or {}, c.js(POPS) or {}
    moved = [k for k, r in st["rects"].items() if any(abs(x - y) > 0.5 for x, y in zip(r, (a.get("rects") or {}).get(k) or [1e9] * 4))]
    lv.refresh()  # a `sessions` frame: the page reads GET live again, as when a turn ends (R40's facts on the page)
    return {"word": {"seconds": seconds, "name": a.get("name"), "title": a.get("title"), "pressed": a.get("pressed"),
                     "drawer": a.get("drawer"), "sections_shown": a.get("sections_shown"), "dialogs": pops.get("dialogs"),
                     "toasts": pops.get("toasts"), "slot_before": st.get("slot", False),"moved": moved}}


def drawn(c, rig, lv, st) -> dict:
    try:
        c.click_on(BTN)
    except Exception as e:  # what the press could not do is said; the reads below still run
        st["press"] = f"{type(e).__name__}: {e}"[:160]
    _off(c)
    _wait(c, f"!!{Q}('[data-testid=session-lit-map][data-map=review-flow]')", 10)
    _off(c)
    d = c.js(DRAWN) or {}
    d["s0"] = c.js(SAMPLE) or {}
    d["press"] = st.get("press", "")
    return {"drawn": d}


def turns(c, rig, lv, st) -> dict:
    samples: list = []

    def sample(when: str) -> None:
        _off(c)
        s = c.js(SAMPLE) or {}
        s["when"] = when
        samples.append(s)
    rig.release("a")
    rig.release("b")
    t0, ended = time.monotonic(), False
    while time.monotonic() - t0 < 30:
        try:
            ended = not any(a.get("state") in LIVE_STATES for a in rig.agents())
        except Exception:
            ended = False
        if ended:
            break
        time.sleep(0.25)
    lv.refresh()
    time.sleep(1.5)
    sample("idle after the rig's turn")
    for n in (2, 3):
        lv.refresh(busy=True)
        lv.say("main", f"turn {n}")
        time.sleep(1.5)
        sample(f"during {n}")
        lv.refresh(busy=False)
        time.sleep(1.5)
        sample(f"after {n}")
    return {"turns": samples, "rig_turn": {"ended": ended, "seconds": round(time.monotonic() - t0, 1)}}


def agents(c, rig, lv, st) -> dict:
    alt(c, 2)
    _wait(c, f"{Q}('[data-testid=agents]')?.dataset.view === 'live'", 10)
    a = c.js(AGENTS) or {}
    try:
        c.click_on(f"{Q}('[data-testid=agents-view-map]')")
        _wait(c, f"{Q}('[data-testid=map-switcher]')?.value === 'review-flow' && "
                 f"({Q}('[data-testid=map-topline]')?.innerText || '').includes({L2!r})", 10)
        a.update(c.js(MAP_VIEW) or {})
    except Exception as e:
        a["map_error"] = f"{type(e).__name__}: {e}"[:160]
    return {"agents": a, "steps_s": round(time.monotonic() - st["sent"], 1)}


# -- what a person would have seen wrong, per assert (pure: tests/test_studio_session_built.py feeds it) ---------------
def _word_says(w: dict) -> list:
    says = []
    if not w.get("slot_before"):
        says.append("no empty slot for the word before the build")
    if w.get("seconds") is None or w["seconds"] > WORD_S:
        says.append(f"no word new on the Live button within {WORD_S:.0f} s of the frame")
    if w.get("name") != "Live" or "(was Map)" not in (w.get("title") or ""):
        says.append(f"the button reads {w.get('name')!r}, its hover {(w.get('title') or '')[:60]!r}")
    if w.get("pressed") != "false" or w.get("drawer"):
        says.append("the drawer opened by itself")
    if w.get("sections_shown") != ["session"]:
        says.append(f"the section changed: {w.get('sections_shown')}")
    if w.get("dialogs") or w.get("toasts"):
        says.append(f"something popped up ({w.get('dialogs')} dialogs, {w.get('toasts')} toasts)")
    if w.get("moved"):
        says.append(f"view-bar buttons moved: {w['moved']}")
    return says


def _drawn_says(d: dict) -> list:
    says = []
    pair = d.get("pair") or ""
    if "Running: starter" not in pair or "Just built: review-flow" not in pair or d.get("built_pressed") != "true":
        says.append(f"no Running / Just built pair with Just built chosen ({pair[:80]!r})")
    if d.get("map") != "review-flow":
        says.append(f"the drawer shows {(d.get('drawer') or '')[:100]!r} (data-map {d.get('map')!r}), not the map review-flow")
    else:
        boxes, sc = d.get("boxes") or [], d.get("scroll")
        main = next((b for b in boxes if b.get("box") == "main"), None)
        if d.get("dir") != "down":
            says.append(f"drawn {d.get('dir') or 'left to right'}, not down")
        if not main or any(b["y"] < main["y"] + main["h"] - 0.5 for b in boxes if b is not main):
            says.append("a box is not below main")
        rows: dict = {}
        for b in boxes:
            rows.setdefault(round(b["y"] / 2), []).append(b["box"])
        if max((len(v) for v in rows.values()), default=0) > 2:
            says.append("more than two boxes in one row")
        review = next((b for b in boxes if b.get("box") == "review"), {})
        if not all(w in review.get("all", "") for w in ("workflow review", "coder", "reviewer")) or not review.get("new"):
            says.append(f"the box review is not its marked workflow block ({review.get('text', 'no box')!r})")
        if any(w in b.get("all", "") for b in boxes for w in ("helper", "made up", "Save as an agent")):
            says.append("a box says helper / made up")
        if (d.get("zoom") or 0) < 1.0 or d.get("small_px") or d.get("ellipsis"):
            says.append(f"text under 12 px or cut short (zoom {d.get('zoom')}, {(d.get('small_px') or d.get('ellipsis') or [])[:2]})")
        cut, below = [], []
        for b in boxes if sc else []:
            inside = (b["y"] >= sc["y"] - 0.5 and b["y"] + b["h"] <= sc["y"] + sc["h"] + 0.5 and b["x"] >= sc["x"] - 0.5
                      and b["x"] + b["w"] <= sc["x"] + sc["w"] + 0.5)
            if b["y"] >= sc["y"] + sc["h"] - 0.5:
                below.append(b["box"])
            elif not inside:
                cut.append(b["box"])
        if cut or (below and d.get("more_below") != f"↓ {len(below)} more below"):
            says.append(f"boxes cut {cut} / below without the line ({d.get('more_below')!r})")
    truth = d.get("truth") or ""
    if S13 not in truth or not d.get("new_session") or "In the terminal" in truth:
        says.append(f"the truth block does not say S13 with [New session] ({truth[:80]!r})")
    return says


def _same(a: dict, b: dict) -> bool:
    if a.get("truth") != b.get("truth") or a.get("map") != b.get("map"):
        return False
    return all((a.get(k) is None) == (b.get(k) is None) and (a.get(k) is None or abs(a[k] - b[k]) <= 0.5)
               for k in ("truth_h", "top", "main_top"))


def _turns_says(got: dict) -> list:
    s0, samples = (got.get("drawn") or {}).get("s0") or {}, got.get("turns") or []
    says = [] if (got.get("rig_turn") or {}).get("ended") else ["the rig's turn did not end in 30 s"]
    if not samples:
        return says + ["the turns were not sampled"]
    for s in samples:
        if not _same(s0, s):
            says.append(f"{s.get('when')}: the drawer shows {(s.get('shows') or '')[:100]!r}" if s.get("map") is None else
                        f"{s.get('when')}: the drawer changed (map {s0.get('map')!r} -> {s.get('map')!r}, truth or top)")
            break
    if s0.get("map") != "review-flow" or s0.get("truth") is None:
        says.append(f"before the turns the drawer drew {s0.get('map')!r} with no truth block" if s0.get("truth") is None
                    else f"before the turns the drawer drew {s0.get('map')!r}")
    return says


def _agents_says(a: dict) -> list:
    says = []
    if a.get("view") != "live" or (a.get("live_tab") or {}).get("selected") != "true":
        says.append(f"Agents opened on {a.get('view') or 'nothing'}" + ("" if "4 · Live" in (a.get("tabs") or []) else ", it has no Live view"))
    if a.get("tabs") != TABS or (a.get("live_tab") or {}).get("text") != "4 · Live":
        says.append(f"the views read {a.get('tabs')}")
    if a.get("view") == "live" and a.get("live_map") != "starter":
        says.append(f"Live draws {a.get('live_map')!r}, not starter")
    if a.get("amber"):
        says.append("an amber line shows")
    if a.get("map_value") != "review-flow" or L2 not in (a.get("topline") or "") or not a.get("watch_button"):
        says.append(f"3 · Map shows {a.get('map_value')!r} with {(a.get('topline') or a.get('map_error') or '')[:90]!r}, "
                    "not review-flow with L2 and Watch it in Live")
    return says


def verdicts(got: dict) -> list:
    """One line per assert that a person would have seen wrong: '(2) ...', '(3) ...', '(6) ...', '(4) ...'."""
    out = []
    for n, says in ((2, _word_says(got.get("word") or {})), (3, _drawn_says(got.get("drawn") or {})),
                    (6, _turns_says(got)), (4, _agents_says(got.get("agents") or {}))):
        if says:
            out.append(f"({n}) " + "; ".join(says))
    return out


class BuiltDriver(Driver):
    no_chrome = {"skip": "no Chrome found"}
    width, height = 1280, 800

    @contextmanager
    def session(self, c):
        from tests.helpers.studio_live_rig import Live
        from tests.helpers.studio_session_rig import StudioSessionRig
        with StudioSessionRig() as rig:
            rig.full = False  # no `open=all`: the drawer must start closed
            lv = Live(rig, extra=())
            lv.refresh(map="starter")  # this session started on the default
            st = {"body": seed_built(rig)}
            yield tuple((fn, (c, rig, lv, st)) for fn in (built, word, drawn, turns, agents))


if __name__ == "__main__":
    sys.exit(BuiltDriver(sys.argv[1:]).main())
