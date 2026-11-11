"""tests.helpers.studio_start -- the Glossary and the Next footer in Studio (Halo 3.1.1.0 R1), driven through real
clicks in headless Chrome on the driver base (tests/helpers/chrome_driver.Driver). tests/test_studio_start.py runs it as
a subprocess with a scrubbed environment (3.4.0.0 B: the guided first run's scenario left with it for the first-run
pack):

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
    term = f"[...{Q}('[data-testid=\"help-term\"]')].find((b) => b.textContent === 'tier')"
    # 3.2.1.0 R5: on Linux (WSL's Chromium: a 757 px tall viewport, wider fonts) the WORDS row sits below the
    # dialog's fold, under its footer, and the click landed on the footer: scroll the word into view first
    c.js(f"{term}.scrollIntoView({{block: 'center'}}); 1")
    c.click_on(term)
    out["opened_on"] = c.wait("document.querySelector('[data-testid=\"glossary-word\"][open] summary')?.textContent", 10)
    out["help_closed"] = c.js("!document.querySelector('[data-testid=\"section-help\"]')")
    c.key("Escape")
    c.wait("!document.querySelector('[data-testid=\"glossary\"]')", 5)
    c.js("document.querySelector('[data-testid=\"start-next-go\"]').scrollIntoView({block: 'center'})")
    c.click_on("document.querySelector('[data-testid=\"start-next-go\"]')")
    sel = "document.querySelector('[data-testid=\"section-tab\"][aria-selected=\"true\"]')?.textContent || ''"
    try:
        c.wait(f"({sel}).startsWith('Agents') && document.querySelector('[data-testid=agents]')?.dataset.view === 'live'"
               " && !!document.querySelector('[data-testid=run-goal-drawer]')", 10)  # 3.4.0.0 D: Live's Run a goal panel
    except TimeoutError:
        pass
    out["went_to"] = c.js(sel)
    out["goal_open"] = c.js("!!document.querySelector('[data-testid=run-goal-drawer]')")
    return out


class StartDriver(Driver):
    """`glossary`: the Glossary and the Next footer. A fresh scratch home."""

    no_chrome = {"skip": "no Chrome found"}

    @contextmanager
    def session(self, c):
        from capture_fresh import fresh_home
        from capture_studio import serve
        os.environ["HALO_START_FAKE"] = "1"  # the driver env scrubs HALO_*: the start runs on the fake model calls
        state = fresh_home()
        srv, url = serve(state)
        url = url.replace("mode=orchestra", "mode=roles")
        try:
            yield ((glossary, (c, url)),)
        finally:
            srv.shutdown()
            srv.server_close()
            import shutil
            shutil.rmtree(state.parent, ignore_errors=True)


if __name__ == "__main__":
    sys.exit(StartDriver(sys.argv[1:]).main())
