"""tests.helpers.studio_design -- the Design click checks of
tests/test_studio_ui.py (Halo 3.0.7.0 round R3: a React section now),
driven through real clicks, drags and keys in headless Chrome over the
DevTools protocol (tests/helpers/cdp.py). Run as a subprocess with a
scrubbed environment, like tools/capture_studio.py:

    python -m tests.helpers.studio_design design   # a seeded project's thread and artboards, a turn sent and cancelled
    python -m tests.helpers.studio_design design-rest   # R3b: knobs, text edit, pins, system, 3 directions, device

The last stdout line is a JSON object of what it saw (exit 2: no Chrome).
No model is called: Design's turns run through design_api.RUNNER."""
from __future__ import annotations

import json
import shutil
import sys
import threading
from contextlib import contextmanager
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO))
sys.path.insert(0, str(REPO / "tools"))

from tests.helpers.chrome_driver import Driver  # noqa: E402

Q = "document.querySelectorAll"


def tid(name: str) -> str:
    return f"{Q}('[data-testid=\"{name}\"]')"


def design(c, url: str, state: Path) -> dict:
    from design_demo import seed
    from halo_harness.studio import design_api
    out: dict = {}
    c.go(url)
    out["start"] = c.wait(f"{tid('design-start')}.length", 20)
    p = seed(state)
    c.go("about:blank")
    c.go(url)
    out["turns"] = c.wait(f"{tid('design-turn')}.length >= 2 && {tid('design-turn')}.length", 20)
    out["heading"] = c.js("document.querySelector('[data-testid=\"design-turn\"] .md-h')?.textContent")
    out["code"] = c.js("document.querySelectorAll('[data-testid=\"design-turn\"] pre.md-pre').length")
    out["raw_html"] = c.js("document.querySelectorAll('[data-testid=\"design-thread-list\"] script, [data-testid=\"design-thread-list\"] img').length")
    out["artboards"] = c.js(f"[...{tid('design-artboard')}].map((a) => a.dataset.id)")
    out["sandbox"] = c.js("[...document.querySelectorAll('[data-testid=\"design-artboard\"] iframe')].map((f) => f.getAttribute('sandbox'))")
    # a turn sent with Enter streams in (the live feed), Cancel turn stops it
    gate = threading.Event()

    def runner(cmd, cwd, env, on_line, stdin="", cancel=None):
        on_line(json.dumps({"type": "assistant", "message": {"content": [{"type": "text", "text": "**Working** on it."}, {"type": "tool_use", "name": "Write", "input": {"file_path": "artboards/hero/index.html"}}]}}))
        gate.set()
        return 130 if cancel is not None and cancel.wait(20) else 0
    design_api.RUNNER, design_api.REGISTERED = runner, set()
    c.click_on("document.querySelector('[data-testid=\"design-send-box\"]')")
    c.type_text("Make the hero darker")
    c.key("Enter")
    out["live"] = c.wait("document.querySelector('[data-testid=\"design-turn\"][data-live] [data-testid=\"design-tool\"]')?.textContent", 15)
    out["cancel_button"] = c.wait(f"{tid('design-cancel')}.length", 5)
    c.click_on("document.querySelector('[data-testid=\"design-cancel\"]')")
    out["after_cancel"] = c.wait(f"!{tid('design-cancel')}.length && {tid('design-turn')}.length", 15)
    out["cancelled_logged"] = bool([h for h in p.history() if h.get("cancelled")])
    # rename an artboard through its dialog
    c.click_on("document.querySelector('[data-testid=\"design-artboard\"][data-id=\"hero\"] [data-testid=\"design-rename\"]')")
    c.wait(f"{tid('design-rename-name')}.length", 5)
    c.js("document.querySelector('[data-testid=\"design-rename-name\"]').select()")
    c.type_text("Landing hero")
    c.click_on("document.querySelector('[data-testid=\"design-rename-go\"]')")
    out["renamed"] = c.wait("document.querySelector('[data-testid=\"design-artboard\"][data-id=\"hero\"] .da-title b')?.textContent === 'Landing hero' && 'Landing hero'", 10)
    return out


class DesignDriver(Driver):
    """`design`, `design-rest` over capture_studio's seeded home (no model call: design_api.RUNNER)."""

    no_chrome = {"skip": "no Chrome found"}

    @contextmanager
    def session(self, c):
        from capture_studio import seeded_home, serve
        state = seeded_home()
        mode = self.argv[0] if self.argv else "design"
        srv, url = serve(state, True)
        url = url.replace("mode=orchestra", "mode=design").replace("feed=off", "tour=off")
        try:
            if mode == "design-rest":
                from tests.helpers.studio_design_rest import design_rest
                yield ((design_rest, (c, url, state)),)
            else:
                yield ((design, (c, url, state)),)
        finally:
            srv.shutdown()
            srv.server_close()
            shutil.rmtree(state.parent, ignore_errors=True)


def main(argv: list) -> int:
    return DesignDriver(argv).main()


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
