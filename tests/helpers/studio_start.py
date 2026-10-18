"""tests.helpers.studio_start -- the first ten minutes in Studio (Halo 3.1.1.0
R1), driven through real clicks in headless Chrome on the driver base
(tests/helpers/chrome_driver.Driver). tests/test_studio_start.py runs it as
a subprocess with a scrubbed environment:

    python -m tests.helpers.studio_start run [PNG]  a fresh home: Start here, Run the ten-minute start (HALO_START_FAKE=1),
                                                    the seven steps done, `start` frames on the feed, no overlay on reload
    python -m tests.helpers.studio_start glossary   the ? menu's Glossary, a section help's word link, the Next footer

The last stdout line is a JSON object of what it saw (exit 2: no Chrome)."""
from __future__ import annotations

import os
import sys
from contextlib import contextmanager
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO))
sys.path.insert(0, str(REPO / "tools"))

from tests.helpers.chrome_driver import Driver  # noqa: E402

Q = "document.querySelectorAll"
STEP = "[data-testid=\"start-step\"]"


def run_start(c, url: str, frames: list, shot: str = "") -> dict:
    out = {}
    c.go(url)
    out["offer"] = c.wait(f"{Q}('[data-testid=\"start-here-run\"]').length", 30)
    out["welcome_with_offer"] = c.js(f"{Q}('[data-testid=\"section-help\"]').length")
    c.click_on("document.querySelector('[data-testid=\"start-here-run\"]')")
    c.wait(f"{Q}('{STEP}').length === 7", 20)
    c.wait("!!document.querySelector('[data-testid=\"start-here-done\"]')", 120)
    out["steps"] = c.js(f"[...{Q}('{STEP}')].map((li) => li.dataset.key + ':' + li.dataset.state)")
    out["done_ok"] = c.js("document.querySelector('[data-testid=\"start-here-done\"]').dataset.ok")
    out["done_text"] = c.js("document.querySelector('[data-testid=\"start-here-done\"]').textContent")
    if shot:
        c.shot(shot)
    out["frames"] = len(frames)
    out["frame_keys"] = sorted({str((f.get("data") or {}).get("key")) for f in frames})
    out["frame_session"] = sorted({str(f.get("session_id"))[:6] for f in frames})
    c.go("about:blank")
    c.go(url)
    c.wait(f"{Q}('[data-testid=\"section-tab\"]').length === 7", 30)
    import time
    time.sleep(2.5)  # GET /api/start has answered by now: a home with a lineup of its own and a start is not fresh
    out["roles_start_after"] = c.js(f"{Q}('[data-testid=\"roles-start\"]').length")
    out["overlay_after_reload"] = c.js(f"{Q}('[data-testid=\"start-here\"]').length")
    return out


def glossary(c, url: str) -> dict:
    out = {}
    c.go(url.replace("feed=off", "feed=off&tour=off"))
    c.wait(f"{Q}('[data-testid=\"start-next\"]').length", 30)
    out["next"] = c.js("document.querySelector('[data-testid=\"start-next\"]').dataset.next")
    out["overlay_quiet"] = c.js(f"{Q}('[data-testid=\"start-here\"]').length")
    c.click_on("document.querySelector('[data-testid=\"section-help-btn\"]')")
    c.wait("!!document.querySelector('[data-testid=\"help-menu\"]')", 5)
    c.click_on("document.querySelector('[data-testid=\"glossary-item\"]')")
    out["words"] = c.wait(f"{Q}('[data-testid=\"glossary-word\"]').length", 10)
    out["first"] = c.js("document.querySelector('[data-testid=\"glossary-word\"] summary').textContent")
    c.key("Escape")
    c.wait("!document.querySelector('[data-testid=\"glossary\"]')", 5)
    c.click_on("document.querySelector('[data-testid=\"section-help-btn\"]')")
    c.wait("!!document.querySelector('[data-testid=\"section-help-item\"]')", 5)
    c.click_on("document.querySelector('[data-testid=\"section-help-item\"]')")
    c.wait("!!document.querySelector('[data-testid=\"section-help\"]')", 5)
    out["terms"] = c.js(f"[...{Q}('[data-testid=\"help-term\"]')].map((b) => b.textContent)")
    c.click_on(f"[...{Q}('[data-testid=\"help-term\"]')].find((b) => b.textContent === 'tier')")
    out["opened_on"] = c.wait("document.querySelector('[data-testid=\"glossary-word\"][open] summary')?.textContent", 10)
    out["help_closed"] = c.js("!document.querySelector('[data-testid=\"section-help\"]')")
    c.key("Escape")
    c.wait("!document.querySelector('[data-testid=\"glossary\"]')", 5)
    c.js("document.querySelector('[data-testid=\"start-next-go\"]').scrollIntoView({block: 'center'})")
    c.click_on("document.querySelector('[data-testid=\"start-next-go\"]')")
    sel = "document.querySelector('[data-testid=\"section-tab\"][aria-selected=\"true\"]')?.textContent || ''"
    try:
        c.wait(f"({sel}).startsWith('Orchestra')", 10)
    except TimeoutError:
        pass
    out["went_to"] = c.js(sel)
    return out


class StartDriver(Driver):
    """`run`: the fake start from the overlay; `glossary`: the Glossary and the Next footer. A fresh scratch home."""

    no_chrome = {"skip": "no Chrome found"}

    @contextmanager
    def session(self, c):
        from capture_start import fresh_home
        from capture_studio import serve
        os.environ["HALO_START_FAKE"] = "1"  # the driver env scrubs HALO_*: the start runs on the fake model calls
        state = fresh_home()
        srv, url = serve(state)
        url = url.replace("mode=orchestra", "mode=roles")
        frames: list = []
        from halo_harness.studio.events import bridge_for
        bridge_for(srv).taps.append(lambda f: frames.append(f) if f.get("event") == "start" else None)
        try:
            if self.argv[:1] == ["glossary"]:
                yield ((glossary, (c, url)),)
            else:
                yield ((run_start, (c, url.replace("&feed=off", ""), frames, (self.argv[1:2] or [""])[0])),)
        finally:
            srv.shutdown()
            srv.server_close()
            import shutil
            shutil.rmtree(state.parent, ignore_errors=True)


if __name__ == "__main__":
    sys.exit(StartDriver(sys.argv[1:]).main())
