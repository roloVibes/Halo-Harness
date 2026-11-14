"""tests.helpers.studio_session_think -- Session's Live column, 3.3.16.2 "thinking you can see, agents talking", in
headless Chrome on the driver base (tests/helpers/chrome_driver.Driver) over tests/helpers/studio_session_rig.py with
scripted feed frames (tests/helpers/studio_live_rig.py `think` / `talk`):

    python -m tests.helpers.studio_session_think think   a THINK row streams with its caret, stays ONE row, clamps at
                                                         four lines, shows all, ends with its length and tokens; its
                                                         chip says what it led to; why? on the Edit row opens that
                                                         thought; the Thinking view narrows the feed; the timeline lane
                                                         has a thinking segment and its click scrolls to the row
    python -m tests.helpers.studio_session_think talk    (tests/helpers/studio_session_talk.py)

The last stdout line is a JSON object of what it saw (exit 2: no Chrome). No model is called."""
from __future__ import annotations

import sys
import time
from contextlib import contextmanager
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO))

from tests.helpers.chrome_driver import Driver  # noqa: E402

COL = "document.querySelector('[data-testid=\"session-live-detail\"]')"
LINES = "[...document.querySelectorAll('[data-testid=\"session-live-line\"]')]"
SCROLL = "document.querySelector('[data-testid=\"session-live-scroll\"]')"
BODY = "l.querySelector('[data-testid=\"live-row\"]')"


def of_kind(kind: str, key: str = "") -> str:
    """The rows whose body says `kind` (think, talk, tool ...), of agent `key` when given."""
    k = f" && l.dataset.key === '{key}'" if key else ""
    return f"{LINES}.filter((l) => {BODY}?.dataset.kind === '{kind}'{k})"


def opened(c, rig) -> dict:
    c.go(rig.url("session"))
    c.wait(f"!!{COL} && document.querySelectorAll('[data-testid=\"session-map\"] [data-testid=\"roles-live-node\"]').length >= 6", 40)
    time.sleep(0.6)
    return {}


def overflow(c, kind: str) -> list:
    """Rows of `kind` whose body is wider than its box (text pushed out of the column)."""
    return c.js(f"{of_kind(kind)}.filter((l) => {BODY}.scrollWidth > {BODY}.clientWidth + 1).map((l) => l.dataset.n)") or []


def think(c, rig, lv) -> dict:
    out: dict = {}
    impl = lv.key("implementer")
    row = f"{of_kind('think', impl)}[0]"
    text = f"{row}.querySelector('[data-testid=\"live-think-text\"]')"
    lv.think("implementer", "tA", "The basket total is off by a cent. ")
    c.wait(f"!!{row}", 10)
    out["kind_label"] = c.js(f"{row}.querySelector('[data-testid=\"session-live-kind\"]').textContent")
    out["streaming"] = c.js(f"{text}.dataset.typing === 'true'")
    for i in range(7):
        lv.think("implementer", "tA", f"Step {i}: rounding happens before tax, so the discount has to apply first or the cent goes missing.\n")
    c.wait(f"{text}.textContent.includes('Step 6')", 10)
    out["one_row"] = c.js(f"{of_kind('think', impl)}.length")
    out["clamped"] = c.js(f"[{text}.scrollHeight > {text}.clientHeight + 4, Math.round({text}.clientHeight / parseFloat(getComputedStyle({text}).lineHeight))]")
    more = f"{row}.querySelector('[data-testid=\"live-show-all\"]')"
    out["show_all"] = c.wait(f"{more}?.textContent", 5)
    lv.think("implementer", "tA", "", end=True, ms=4200, tokens=812)
    out["took"] = c.wait(f"{row}.querySelector('[data-testid=\"live-think-took\"]')?.textContent", 10)
    out["caret_after"] = c.js(f"{text}.dataset.typing === 'true'")
    lv.tool("implementer", "Edit", "th-e1", "basket.py")
    out["led"] = c.wait(f"{row}.querySelector('[data-testid=\"live-think-led\"]')?.textContent", 10)
    h0 = c.js(f"{row}.getBoundingClientRect().height")
    c.js(f"{more}.scrollIntoView({{block: 'center'}}); 1")
    c.click_on(more)
    c.wait(f"{more}.textContent === 'show less'", 5)
    out["expanded"] = c.js(f"[{text}.scrollHeight <= {text}.clientHeight + 1, {row}.getBoundingClientRect().height > {h0}]")
    out.update(why(c, lv, impl))
    return out


def why(c, lv, impl: str) -> dict:
    out: dict = {}
    tool = f"{of_kind('tool', impl)}.find((l) => l.textContent.includes('basket.py'))"
    chip = f"{tool}.querySelector('[data-testid=\"session-live-why\"]')"
    c.wait(f"!!{chip}", 10)
    out["why_linked"] = c.js(f"!!{chip}.dataset.thought")
    c.js(f"{chip}.scrollIntoView({{block: 'center'}}); 1")
    c.click_on(chip)
    out["why_opens"] = c.wait(f"{tool}.querySelector('[data-testid=\"live-why\"]')?.textContent", 5)
    lv.think("implementer", "tB", "Now read the test to see what it expects.", end=True, ms=900)
    lv.tool("implementer", "Read", "th-r1", "test_basket.py")
    lv.say("researcher", "BRAVO checks the pricing notes. ")
    lv.tool("researcher", "Grep", "th-g1", "discount")
    c.wait(f"{of_kind('tool', impl)}.length >= 2 && {LINES}.some((l) => l.textContent.includes('BRAVO'))", 10)
    return out


def view(c, lv) -> dict:
    """The Thinking view: only thoughts and what each led to; off again, every row."""
    out: dict = {}
    impl, res = lv.key("implementer"), lv.key("researcher")
    btn = "document.querySelector('[data-testid=\"live-think-view\"]')"
    out["view_off"] = c.js(f"{btn}.getAttribute('aria-pressed')")
    before = c.js(f"{LINES}.length")
    c.click_on(btn)
    c.wait(f"{COL}.dataset.think === 'true'", 5)
    time.sleep(0.3)
    out["view_rows"] = c.js(f"{LINES}.map((l) => [{BODY}.dataset.kind, l.dataset.key === '{impl}' ? 'impl' : l.dataset.key === '{res}' ? 'res' : 'other'])")
    out["view_fewer"] = c.js(f"{LINES}.length") < before
    c.click_on(btn)
    c.wait(f"!{COL}.dataset.think", 5)
    return out


def timeline(c, lv) -> dict:
    """The lane in phases; a thinking segment's click scrolls the column to that thought."""
    out: dict = {}
    impl = lv.key("implementer")
    lane = f"document.querySelector('[data-testid=\"session-live-timeline\"] [data-testid=\"fleet-lane\"][data-key=\"{impl}\"]')"
    c.wait(f"!!{lane}?.querySelector('[data-phase=\"thinking\"]')", 10)
    out["phases"] = c.js(f"[...new Set([...{lane}.querySelectorAll('[data-testid=\"live-phase\"]')].map((s) => s.dataset.phase))].sort()")
    n = c.js(f"{of_kind('think', impl)}[0].dataset.n")
    for i in range(40):
        lv.tool(("tester", "docs")[i % 2], "Read", f"th-fill-{i}")
    c.wait(f"{of_kind('tool')}.length >= 44", 15)
    c.js(f"{SCROLL}.scrollTop = {SCROLL}.scrollHeight; 1")
    time.sleep(0.4)
    target = f"document.querySelector('[data-testid=\"session-live-scroll\"] [data-n=\"{n}\"]')"
    vis = (f"(() => {{ const r = {target}.getBoundingClientRect(), s = {SCROLL}.getBoundingClientRect(); "
           "return r.bottom > s.top && r.top < s.bottom; })()")
    out["away"] = not c.js(vis)
    seg = f"{lane}.querySelector('[data-phase=\"thinking\"][data-n=\"{n}\"]')"
    x, y, w, h = c.rect(seg)
    later = c.js(f"[...{lane}.querySelectorAll('[data-phase=\"thinking\"]')].map((e) => e.getBoundingClientRect().left).filter((v) => v > {x}).sort((a, b) => a - b)[0] || 0")
    px, py = (x + min(x + w, later or x + w)) / 2, y + h / 2  # inside its own segment, left of the next thought's (drawn on top)
    c.mouse("mouseMoved", px, py)
    out["tip"] = c.wait("document.querySelector('[data-testid=\"fleet-timeline-tip\"]')?.textContent", 5)
    out["hit"] = c.js(f"(() => {{ const e = document.elementFromPoint({px}, {py}); return e?.dataset?.phase === 'thinking' && e.dataset.n === '{n}' ? 'thinking' : e?.outerHTML?.slice(0, 120) || ''; }})()")
    c.click(px, py)
    out["paused"] = c.wait(f"!{COL}.dataset.follow && 'paused'", 5)
    out["scrolled_to"] = c.wait(vis, 5)
    out["overflow"] = overflow(c, "think")
    return out


class ThinkDriver(Driver):
    no_chrome = {"skip": "no Chrome found"}

    @contextmanager
    def session(self, c):
        from tests.helpers.studio_session_rig import StudioSessionRig
        from tests.helpers.studio_live_rig import Live
        with StudioSessionRig() as rig:
            lv = Live(rig)
            if (self.argv or ["think"])[0] == "talk":
                from tests.helpers.studio_session_talk import conversations, talk
                yield ((opened, (c, rig)), (talk, (c, lv)), (conversations, (c, lv)))
            else:
                yield ((opened, (c, rig)), (think, (c, rig, lv)), (view, (c, lv)), (timeline, (c, lv)))


if __name__ == "__main__":
    sys.exit(ThinkDriver(sys.argv[1:]).main())
