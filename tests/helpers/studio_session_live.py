"""tests.helpers.studio_session_live -- Session's Live column (Halo 3.1.5.0
R3) through real clicks, keys and the pointer in headless Chrome on the
driver base (tests/helpers/chrome_driver.Driver), over
tests/helpers/studio_fleet_rig.py with three extra agents and scripted feed
frames (tests/helpers/studio_live_rig.py). tests/test_studio_session_live.py
runs it as a subprocess with a scrubbed environment:

    python -m tests.helpers.studio_session_live live   the default arrangement, two agents' lines interleaved in
                                                       arrival order with their tags, a tool row's clock and its
                                                       result, Follow paused by a scroll up and the pill, a tag
                                                       pinning and Esc unpinning, a hovered line lighting its
                                                       node, an ask landing as a card, a spawn and a hand-back,
                                                       1000 lines and the DOM cap; 3.1.7.0 R1: Fleet's time and
                                                       KIND columns, the narrow layout, a tool row's whole result
                                                       (tests/helpers/studio_session_insight.py)

The last stdout line is a JSON object of what it saw (exit 2: no Chrome).
No model is called."""
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


def lines(c) -> list:
    return c.js(f"{LINES}.map((l) => [l.dataset.key, l.dataset.kind, l.querySelector('.slv-name').textContent, "
                "(l.querySelector('.slv-text, .slv-tool, .slv-ask, .slv-out') || l).textContent])") or []


def arrangement(c) -> dict:
    """The default grid: each panel's [x, y, w, h] from its grid-area, and whether it is a strip."""
    js = ("Object.fromEntries([...document.querySelectorAll('[data-section=\"session\"] .ws-cell')].map((p) => {"
          " const m = (p.getAttribute('style') || '').match(/grid-area: (\\d+) \\/ (\\d+) \\/ span (\\d+) \\/ span (\\d+)/);"
          " return [p.dataset.panel, m ? [+m[2] - 1, +m[1] - 1, +m[4], +m[3], !!p.querySelector('[data-collapsed]')] : null]; }))")
    return c.js(js) or {}


def live(c, rig) -> dict:
    from tests.helpers.studio_live_rig import Live
    lv = Live(rig)
    out: dict = {}
    c.go(rig.url("session"))
    c.wait(f"!!{COL} && document.querySelectorAll('[data-testid=\"session-map\"] [data-testid=\"fleet-node\"]').length >= 6", 40)
    time.sleep(0.8)
    out["arrangement"] = arrangement(c)
    out["follow_default"] = c.js(f"{COL}.dataset.follow === 'true'")
    impl, res = lv.key("implementer"), lv.key("researcher")
    out["res_key"] = res
    lv.say("implementer", "ALPHA reads basket.py first. ")
    c.wait(f"{LINES}.some((l) => l.textContent.includes('ALPHA'))", 10)
    lv.say("researcher", "BRAVO checks the pricing notes. ")
    c.wait(f"{LINES}.some((l) => l.textContent.includes('BRAVO'))", 10)
    lv.tool("implementer", "Bash", "live-t1", "git status --short")
    c.wait(f"{LINES}.some((l) => l.dataset.kind === 'tool' && l.dataset.key === '{impl}')", 10)
    lv.say("researcher", " CHARLIE: the notes agree.")
    c.wait(f"{LINES}.some((l) => l.textContent.includes('CHARLIE'))", 10)
    got = [x for x in lines(c) if any(w in x[3] for w in ("ALPHA", "BRAVO", "git status --short"))]
    out["order"] = [[k == impl and "impl" or k == res and "res" or k, kind, name] for k, kind, name, _ in got]
    out["joined"] = any("BRAVO" in t and "CHARLIE" in t for *_, t in got)
    tool = f"{LINES}.find((l) => l.dataset.kind === 'tool' && l.textContent.includes('git status --short'))"
    out["tool_target"] = c.js(f"{tool}.querySelector('.slv-target')?.textContent || ''")
    e0 = c.js(f"{tool}.querySelector('[data-testid=\"session-live-elapsed\"]').textContent")
    time.sleep(2.3)
    e1 = c.js(f"{tool}.querySelector('[data-testid=\"session-live-elapsed\"]').textContent")
    out["elapsed"] = [e0, e1]
    out["node_clock"] = c.js(f"document.querySelector('[data-testid=\"fleet-node\"][data-key=\"{impl}\"] [data-testid=\"fleet-node-tool\"] .fm-tool-text')?.textContent || ''")
    lv.result("implementer", "live-t1", "M basket.py\n?? notes.md")
    out["result"] = c.wait(f"{tool}.querySelector('[data-testid=\"session-live-result\"]')?.textContent", 10)
    from tests.helpers.studio_session_insight import columns  # 3.1.7.0 R1: Fleet's columns, the narrow layout, the whole result
    out.update(columns(c, lv, tool))
    out.update(follow(c, lv))
    out.update(pin_and_hover(c, lv, res))
    lv.ask("reviewer", "permission_request")
    out["ask"] = c.wait(f"{LINES}.filter((l) => l.dataset.kind === 'ask').map((l) => [l.querySelector('.slv-name').textContent, "
                        f"l.querySelectorAll('[data-testid=\"session-live-key\"]').length, l.querySelector('.slv-ask-what').textContent])[0]", 10)
    lv.spawn("s9a1w2n3", "linter", "linter", "or:mock/qwen3-coder", "Lint: the basket module")
    out["spawn_line"] = c.wait(f"{LINES}.filter((l) => l.dataset.kind === 'spawn' && l.querySelector('.slv-name').textContent === 'linter')"
                               ".map((l) => [l.querySelector('.slv-name').textContent, l.textContent]).pop()", 10)
    lv.state("docs", state="done", last_text="CHANGES.md: the discount applies before tax")
    out["output_line"] = c.wait(f"{LINES}.filter((l) => l.dataset.kind === 'output' && l.querySelector('.slv-name').textContent === 'docs').map((l) => [l.querySelector('.slv-name').textContent, "
                                "l.querySelector('.slv-out-text').textContent]).pop()", 10)
    out.update(flood(c, lv))
    return out


def follow(c, lv) -> dict:
    """Enough lines to scroll; a scroll up pauses Follow, new lines show on the pill, the pill resumes."""
    out: dict = {}
    for i in range(40):
        lv.tool(("tester", "docs")[i % 2], "Read", f"fill-{i}")
    c.wait(f"{LINES}.filter((l) => l.dataset.kind === 'tool').length >= 41", 15)
    time.sleep(0.4)
    out["at_bottom"] = c.js(f"{SCROLL}.scrollHeight - {SCROLL}.scrollTop - {SCROLL}.clientHeight < 30")
    c.js(f"{SCROLL}.scrollTop = 0; 1")
    out["paused"] = c.wait(f"!{COL}.dataset.follow && 'paused'", 5) or False
    for i in range(3):
        lv.say("docs" if i % 2 else "tester", f"while you read {i}")
        lv.tool("tester", "Grep", f"new-{i}")
    out["pill"] = c.wait("document.querySelector('[data-testid=\"live-follow\"]')?.textContent", 10)
    out["stayed_up"] = c.js(f"{SCROLL}.scrollTop < 40")
    c.click_on("document.querySelector('[data-testid=\"live-follow\"]')")
    resumed = f"{COL}.dataset.follow === 'true' && !document.querySelector('[data-testid=\"live-follow\"]') && 'resumed'"
    try:
        out["resumed"] = c.wait(resumed, 5) or False
    except TimeoutError:
        # the Linux runner lost the pill click once (0e6e290): scrolling to the bottom is the other way Follow
        # comes back (onScroll: at the bottom -> follow), so take it and say so
        c.js(f"{SCROLL}.scrollTop = {SCROLL}.scrollHeight; 1")
        out["resumed"] = c.wait(resumed, 15) or False
        out["resumed_by"] = "scroll"
    time.sleep(0.3)
    out["back_bottom"] = c.js(f"{SCROLL}.scrollHeight - {SCROLL}.scrollTop - {SCROLL}.clientHeight < 30")
    return out


def pin_and_hover(c, lv, res: str) -> dict:
    out: dict = {}
    tag = f"{LINES}.filter((l) => l.dataset.key === '{res}').pop().querySelector('[data-testid=\"session-live-tag\"]')"
    c.js(f"{tag}.scrollIntoView({{block: 'center'}}); 1")
    c.click_on(tag)
    out["pinned"] = c.wait(f"{COL}.dataset.pinned", 5)
    out["pinned_only"] = c.js(f"{LINES}.length > 0 && {LINES}.every((l) => l.dataset.key === '{res}')")
    out["pinned_steer"] = c.js(f"!!{COL}.querySelector('[data-testid=\"fleet-steer\"]')")
    c.key("Escape")
    out["unpinned"] = c.wait(f"!{COL}.dataset.pinned && 'everyone'", 5) or False
    out["everyone_back"] = c.js(f"new Set({LINES}.map((l) => l.dataset.key)).size")
    line = f"{LINES}.filter((l) => l.dataset.key === '{res}').pop()"
    c.js(f"{line}.scrollIntoView({{block: 'center'}}); 1")
    x, y, w, h = c.rect(line)
    c.mouse("mouseMoved", x + w * 0.7, y + h / 2)
    out["hover_node"] = c.wait("document.querySelector('[data-testid=\"fleet-node\"][data-hover]')?.dataset.key", 5)
    c.mouse("mouseMoved", 5, 5)
    out["hover_off"] = c.wait("!document.querySelector('[data-testid=\"fleet-node\"][data-hover]') && 'off'", 5) or False
    return out


def flood(c, lv) -> dict:
    """1000 more lines from six agents: the DOM keeps the newest 500, the rest are named in one line."""
    who = ("implementer", "researcher", "tester", "docs", "reviewer", "main")
    count = "+(document.querySelector('[data-testid=\"session-live-counts\"]').textContent.match(/([0-9]+) line/) || [0, 0])[1]"
    before = c.js(count) or 0
    t0 = time.time()
    for i in range(1000):
        lv.tool(who[i % len(who)], "Read", f"flood-{i}")
        if i % 200 == 199:
            c.wait(f"{count} >= {before + i + 1}", 20)
    c.wait(f"{count} >= {before + 1000}", 30)
    return {"flood_s": round(time.time() - t0, 1), "dom_lines": c.js(f"{LINES}.length"), "total_lines": c.js(count),
            "older": c.js("document.querySelector('[data-testid=\"session-live-older\"]')?.textContent || ''")}


class LiveDriver(Driver):
    no_chrome = {"skip": "no Chrome found"}

    @contextmanager
    def session(self, c):
        from tests.helpers.studio_fleet_rig import StudioFleetRig
        with StudioFleetRig() as rig:
            yield ((live, (c, rig)),)


if __name__ == "__main__":
    sys.exit(LiveDriver(sys.argv[1:]).main())
