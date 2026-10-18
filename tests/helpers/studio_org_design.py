"""tests.helpers.studio_org_design -- the Org and Design click checks of
tests/test_studio_ui.py (Halo 3.0.7.0 round R3: both are React sections
now), driven through real clicks, drags and keys in headless Chrome over the
DevTools protocol (tests/helpers/cdp.py). Run as a subprocess with a
scrubbed environment, like tools/capture_studio.py:

    python -m tests.helpers.studio_org_design org      # Start view without Paperclip, then the chart over FakePaperclip
    python -m tests.helpers.studio_org_design design   # a seeded project's thread and artboards, a turn sent and cancelled
    python -m tests.helpers.studio_org_design design-rest   # R3b: knobs, text edit, pins, system, 3 directions, device

The last stdout line is a JSON object of what it saw (exit 2: no Chrome).
No model is called: Design's turns run through design_api.RUNNER."""
from __future__ import annotations

import json
import shutil
import sys
import threading
import time
from contextlib import contextmanager
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO))
sys.path.insert(0, str(REPO / "tools"))

from tests.helpers.chrome_driver import Driver  # noqa: E402

Q = "document.querySelectorAll"


def tid(name: str) -> str:
    return f"{Q}('[data-testid=\"{name}\"]')"


def org(c, url: str, state: Path) -> dict:
    from halo_harness.paperclip.client import save_config
    from capture_org_design import seed_paperclip
    out: dict = {}
    save_config({"base_url": "http://127.0.0.1:1"}, state)  # no Paperclip answers: the Start view
    c.go(url)
    out["start"] = c.wait(f"{tid('org-start')}.length", 20)
    out["start_buttons"] = c.js(f"[{tid('org-install')}.length, {tid('org-link')}.length]")
    out["start_panels"] = c.js(f"{tid('org-card')}.length + {tid('panel-about')}.length")
    fake, _lead = seed_paperclip(state)
    try:
        c.go("about:blank")
        c.go(url)
        out["cards"] = c.wait(f"{tid('org-card')}.length >= 7 && {tid('org-card')}.length", 20)
        out["groups"] = c.js(f"[...{tid('org-group')}].map((g) => g.querySelector('.oc-group-label').textContent)")
        out["cards_in_boxes"] = c.js(f"""(() => {{ const boxes = [...{tid('org-group')}].map((b) => b.getBoundingClientRect());
          return [...{tid('org-card')}].every((n) => {{ const r = n.getBoundingClientRect();
            return boxes.some((b) => r.left >= b.left - 1 && r.right <= b.right + 1 && r.top >= b.top - 1 && r.bottom <= b.bottom + 1); }}); }})()""")
        out["edges"] = c.js(f"{tid('org-edge')}.length")
        by = {a["name"]: a["id"] for a in fake.agents.values()}
        card = lambda name: f"document.querySelector('[data-testid=\"org-card\"][data-id=\"{by[name]}\"]')"  # noqa: E731
        # a plain move inside its own box: the place goes to the server (PUT layout/pc:<id>) 500 ms later
        x, y, w, h = c.rect(card("release"))
        c.drag(x + w / 2, y + 12, x + w / 2 + 30, y + 40)
        layout = state / "studio" / "layouts" / f"_pc-{fake.company['id']}.json"
        end = time.time() + 6
        while time.time() < end and not layout.is_file():
            time.sleep(0.1)
        saved = json.loads(layout.read_text(encoding="utf-8")) if layout.is_file() else {}
        out["layout_saved"] = by["release"] in saved or by["release"] in (saved.get("nodes") or {})
        # dropped onto another card: Studio asks, then Paperclip gets the new manager
        x, y, w, h = c.rect(card("verify"))
        tx, ty, tw, th = c.rect(card("worker"))
        c.drag(x + w / 2, y + 12, tx + tw / 2, ty + th / 2)
        out["asked"] = c.wait(f"document.querySelector('[data-testid=\"org-reparent\"] .dialog-title')?.textContent", 10)
        c.click_on("document.querySelector('[data-testid=\"org-reparent-yes\"]')")
        end = time.time() + 8
        while time.time() < end and fake.agents[by["verify"]].get("reportsTo") != by["worker"]:
            time.sleep(0.1)
        out["reparented"] = fake.agents[by["verify"]].get("reportsTo") == by["worker"]
        out["new_box"] = c.wait(f"[...{tid('org-group')}].some((g) => /worker|engineer/i.test(g.textContent)) && 'yes'", 10)
        # double-click opens the Inspector on the agent; an issue row opens it on the issue
        c.js(f"{card('research')}.dispatchEvent(new MouseEvent('dblclick', {{bubbles: true}}))")
        out["inspector"] = c.wait("document.querySelector('[data-testid=\"org-inspector-agent\"] .oi-title')?.textContent", 10)
        c.click_on("document.querySelector('[data-testid=\"org-agent-wake\"]')")  # an agent action: POST agents/<id>/wakeup
        end = time.time() + 6
        woke = lambda: any(m == "POST" and q.endswith(f"/agents/{by['research']}/wakeup") for m, q, _b, _h in fake.requests)  # noqa: E731
        while time.time() < end and not woke():
            time.sleep(0.1)
        out["woke"] = woke()
        c.click_on(f"{tid('org-issue')}[0]")
        out["issue"] = c.wait("document.querySelector('[data-testid=\"org-inspector-issue\"] .ow-id')?.textContent", 10)
    finally:
        fake.close()
    return out


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


class OrgDesignDriver(Driver):
    """`org`, `design`, `design-rest` over capture_studio's seeded home (no model call: design_api.RUNNER)."""

    no_chrome = {"skip": "no Chrome found"}

    @contextmanager
    def session(self, c):
        from capture_studio import seeded_home, serve
        state = seeded_home()
        mode = self.argv[0] if self.argv else "org"
        section = "design" if mode.startswith("design") else mode
        srv, url = serve(state, True)
        url = url.replace("mode=orchestra", f"mode={section}").replace("feed=off", "tour=off" if section == "design" else "feed=off&tour=off")
        try:
            if mode == "design-rest":
                from tests.helpers.studio_design_rest import design_rest
                yield ((design_rest, (c, url, state)),)
            else:
                yield ((org if mode == "org" else design, (c, url, state)),)
        finally:
            srv.shutdown()
            srv.server_close()
            shutil.rmtree(state.parent, ignore_errors=True)


def main(argv: list) -> int:
    return OrgDesignDriver(argv).main()


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
