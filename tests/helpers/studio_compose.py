"""tests.helpers.studio_compose -- composing blocks on Agents -> Cast (Halo 3.3.16.3 part 2, the owner: "drag and drop
those entire use cases ... add this workflow in there when this situation happens") in headless Chrome on the driver
base, the real pointer moved through CDP, over a scratch home: the auto lineup with the shipped `media`, `plan` and
`review` squares on its board, review's rule `off` (config `workflows.when`). tests/test_studio_compose.py runs it:

    python -m tests.helpers.studio_compose compose [--shots DIR]
        load     nothing opens on load; main's lines go to media and plan, each with its when label; review is dashed,
                 its footer says it is not connected, and Problems lists it
        when     a click on media's label opens its When page; pdf only, Save: the label says "needs pdf" and the line
                 says what was written; Undo puts the covers back
        connect  main's edge handle dragged onto review raises the connect card; Connect draws its line; Undo takes it off
        library  `+ Library` on Cast: the three kinds; the search filters all three
        (the drags, the keys and the density: tests/helpers/studio_compose_drags.py)

The last stdout line is a JSON object of what it saw (exit 2: no Chrome). No model is called."""
from __future__ import annotations

import sys
from contextlib import contextmanager
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO))
sys.path.insert(0, str(REPO / "tools"))

from tests.helpers.chrome_driver import Driver  # noqa: E402
from tests.helpers.studio_blocks import go  # noqa: E402
from tests.helpers.studio_compose_bits import Q, asked, named, block, do_it, drag, note, see, sel, undo  # noqa: E402
from tests.helpers.studio_hover_read import seen_for  # noqa: E402

BLOCKS = "document.querySelectorAll('[data-testid=\"block\"]').length"
LABEL = "Object.fromEntries([...document.querySelectorAll('[data-testid=\"block-when\"]')].map((l) => [l.dataset.to, l.textContent]))"


def label(ref: str) -> str:
    return f"({sel('block-when', to=ref)}?.textContent || '')"


def load(c, page) -> dict:
    c.call("Emulation.setDeviceMetricsOverride", width=1800, height=1100, deviceScaleFactor=1, mobile=False)
    go(c, page)
    c.wait(f"{BLOCKS} === 3 && document.querySelectorAll('[data-testid=\"block-when\"]').length === 2", 40)
    seen = seen_for(c, 1.0)
    out = {"quiet": seen is None, "seen": seen, "open": c.js(
        "['blk-confirm', 'wf-library', 'blk-note', 'block-menu', 'wf-page-when', 'blk-move', 'blk-ghost']"
        ".filter((t) => document.querySelector(`[data-testid=\"${t}\"]`))")}
    out["edges"] = c.js("[...document.querySelectorAll('[data-testid=\"block-edge\"]')].map((e) => e.dataset.to)")
    out["labels"] = c.js(LABEL)
    out["review"] = c.js(f"[!!{block('review')}.dataset.connected, getComputedStyle({block('review')}).borderTopStyle,"
                         f" {block('review')}.querySelector('[data-testid=\"block-foot\"]').textContent]")
    strip = f"{Q}('.section-view:not([hidden]) [data-testid=\"viewbar-btn\"][data-panel=\"roles-problems\"]')"  # 3.6.0.0 R0a: its button in the view bar
    c.click_on(strip)
    out["problems"] = c.wait("[...document.querySelectorAll('[data-testid=\"roles-problem-block\"]')].map((b) => b.dataset.block)", 15)
    c.click_on(strip)
    return out


def when(c, page) -> dict:
    see(c, sel("block-when", to="media"))
    c.click_on(sel("block-when", to="media"))
    out = {"page": c.wait(f"{sel('wf-page-when')} && [...document.querySelectorAll('[data-testid=\"wf-when-need\"]')].filter((b) => b.checked).map((b) => b.dataset.need)", 15)}
    for need in ("vision", "audio", "video"):
        see(c, sel("wf-when-need", need=need))
        c.click_on(sel("wf-when-need", need=need))
        c.wait(f"!{sel('wf-when-need', need=need)}.checked", 5)
    out["writes"] = c.js(f"{Q}('.blk-when-writes').textContent")
    see(c, sel("wf-when-save"))
    c.click_on(sel("wf-when-save"))
    out["saved"] = c.wait(f"{label('media')} === 'needs pdf' && {label('media')}", 15)
    out["note"] = note(c)
    undo(c)
    out["undone"] = c.wait(f"{label('media')}.startsWith('needs pdf, images') && {label('media')}", 15)
    return out


def connect(c, page) -> dict:
    see(c, block("review"))
    handle = sel("block-handle")
    x, y, w, h = c.rect(block("review"))
    drag(c, handle, (x + w * 0.5, y + h * 0.6))
    out = {"card": asked(c, "connect")}
    do_it(c)
    out["drawn"] = c.wait(f"!!{sel('block-edge', to='review')} && {block('review')}.dataset.connected && {label('review')}", 15)
    out["note"] = note(c)
    undo(c)
    out["undone"] = c.wait(f"!{sel('block-edge', to='review')} && !{block('review')}.dataset.connected && 'off again'", 15)
    return out


def library(c, page) -> dict:
    c.click_on(sel("wf-library-plus"))
    c.wait(f"!!{sel('wf-library')}", 10)
    kinds = "[...document.querySelectorAll('.lib-kind')].map((k) => [k.dataset.kind, k.querySelectorAll('li').length])"
    out = {"kinds": c.wait(f"document.querySelectorAll('[data-testid=\"lib-template\"]').length === 4 && document.querySelectorAll('[data-testid=\"lib-bio\"]').length > 3 && {kinds}", 20)}
    c.click_on(sel("wf-search"))
    c.type_text("review")
    out["search"] = c.wait(f"{sel('wf-search')}.value === 'review' && {kinds}", 10)
    c.js(f"{sel('wf-search')}.select(); 1")
    c.call("Input.dispatchKeyEvent", type="keyDown", key="Backspace", code="Backspace", windowsVirtualKeyCode=8)
    c.call("Input.dispatchKeyEvent", type="keyUp", key="Backspace", code="Backspace", windowsVirtualKeyCode=8)
    c.wait(f"{sel('wf-search')}.value === '' && document.querySelectorAll('[data-testid=\"lib-template\"]').length === 4", 10)
    c.js("document.activeElement?.blur(); 1")
    return out


class ComposeDriver(Driver):
    no_chrome = {"skip": "no Chrome found"}

    @contextmanager
    def session(self, c):
        from capture_studio import serve
        from halo_harness.config.paths import bridge_home
        from halo_harness.studio.server import url_for
        from halo_harness.theme import set_config_value
        from tests.helpers.studio_compose_drags import steps
        state = bridge_home()
        state.mkdir(parents=True, exist_ok=True)
        set_config_value("workflows.enabled", ["media", "plan", "review"])
        set_config_value("workflows.when", {"review": {"mode": "off"}})
        srv, _url = serve(state)
        base = url_for(srv)
        folder = self.argv[self.argv.index("--shots") + 1] if "--shots" in self.argv else ""

        def page(query: str) -> str:
            return base.replace("/#t=", f"/?{query}&feed=off&tour=off#t=")
        try:
            yield ((named(load), (c, page)), (named(when), (c, page)), (named(connect), (c, page)), (named(library), (c, page)),
                   *steps(c, page, state, folder))
        finally:
            srv.shutdown()
            srv.server_close()


if __name__ == "__main__":
    sys.exit(ComposeDriver(sys.argv[1:]).main())
