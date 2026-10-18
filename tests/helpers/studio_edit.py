"""tests.helpers.studio_edit -- Studio as the one editor of bios and lineups
(Halo 3.1.1.0 R3), driven through real clicks and typing in headless Chrome on
the driver base (tests/helpers/chrome_driver.Driver). tests/test_studio_edit_route.py
runs it as a subprocess with a scrubbed environment:

    python -m tests.helpers.studio_edit bio     `?edit=bio:coder` opens Roles on coder's bio form: the fields the
                                                terminal view shows, field_help.py's lines, the YAML toggle; typed
                                                edits saved through the form land in ~/.halo/agents/coder.yaml
    python -m tests.helpers.studio_edit focus   a page is open; `open_edit` (what `halo studio --edit` runs) on the
                                                running Studio focuses it: lineup:halo-dev-cycle opens its inspector's
                                                Lineup tab (a section edited and saved through it), team the Team
                                                section, bio:reviewer the bio form; no browser tab is opened

The last stdout line is a JSON object of what it saw (exit 2: no Chrome).
No model is called."""
from __future__ import annotations

import json
import shutil
import sys
import threading
import time
from contextlib import contextmanager
from pathlib import Path

import yaml

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO))
sys.path.insert(0, str(REPO / "tools"))

from tests.helpers.chrome_driver import Driver  # noqa: E402

FORM = "document.querySelector('[data-testid=\"bio-form\"]')"


def q(testid: str) -> str:
    return f"document.querySelector('[data-testid=\"{testid}\"]')"


def fill(c, testid: str, text: str) -> None:
    """Type `text` into the field (its old text selected first), then leave it: the form commits on blur."""
    c.js(f"{q(testid)}.scrollIntoView({{block: 'center'}}); 1")
    c.click_on(q(testid))
    c.js(f"{q(testid)}.select(); 1")
    c.type_text(text)
    c.js(f"{q(testid)}.blur(); 1")


def press(c, testid: str) -> None:
    """Scroll the control into view, then click it."""
    c.js(f"{q(testid)}.scrollIntoView({{block: 'center'}}); 1")
    time.sleep(0.1)
    c.click_on(q(testid))


def pick(c, expr: str, value: str) -> None:
    """Choose `value` in the <select> `expr` the way a user's change does."""
    c.js(f"""(() => {{ const el = {expr}; const set = Object.getOwnPropertyDescriptor(HTMLSelectElement.prototype, 'value').set;
      set.call(el, {json.dumps(value)}); el.dispatchEvent(new Event('change', {{bubbles: true}})); return 1; }})()""")


def section_tab(c) -> str:
    return c.js("document.querySelector('[data-testid=\"section-tab\"][aria-selected=\"true\"]')?.textContent || ''")


def bio(c, url: str, state: Path) -> dict:
    from halo_harness import field_help
    out: dict = {}
    c.go(url)
    out["form"] = c.wait(f"{FORM}?.dataset.bio", 30)
    out["section"] = section_tab(c)
    out["overlays"] = c.js("document.querySelectorAll('[data-testid=\"start-here\"], [data-testid=\"section-help\"]').length")
    ids = ["bio-description", "bio-kind", "bio-tags", "bio-fallback", "bio-effort", "bio-context-budget", "bio-tools-allow",
           "bio-tools-deny", "bio-rules", "bio-context-files", "bio-memory", "bio-prompt-notes", "bio-max-iterations",
           "bio-max-budget", "bio-worktree", "bio-offline", "bio-accept-prompt", "bio-schedule-cron", "bio-schedule-every",
           "bio-schedule-prompt", "bio-triggers", "roles-scope-project", "bio-yaml-toggle"]
    c.wait(f"{FORM}.querySelectorAll('.field-hint').length > 10", 10)
    out["missing"] = c.js(f"{json.dumps(ids)}.filter((t) => !{FORM}.querySelector(`[data-testid=\"${{t}}\"]`))")
    hints = c.js(f"[...{FORM}.querySelectorAll('.field-hint')].map((h) => h.textContent)")
    want = [field_help.BIO[k] for k in ("models.preference", "tools.rules", "context.files", "schedule.cron", "environment.offline")]
    out["help_from_source"] = [w in hints for w in want] + [field_help.IDENTITY["tags"] in hints]
    out["efforts"] = c.js(f"[...{q('bio-effort')}.options].map((o) => o.value)")
    fill(c, "bio-tags", "alpha, beta")
    fill(c, "bio-context-files", "CLAUDE.md, plans/STATUS.md")
    fill(c, "bio-accept-prompt", "say ok")
    fill(c, "bio-schedule-every", "30m")
    fill(c, "bio-schedule-prompt", "check the inbox")
    press(c, "bio-offline")
    press(c, "bio-yaml-toggle")
    out["yaml"] = c.wait(f"{q('bio-yaml-text')}?.value.includes('every: 30m') && {q('bio-yaml-text')}.value", 10)
    press(c, "bio-yaml-toggle")
    c.wait(f"!!{q('bio-tags')}", 5)
    press(c, "bio-save")
    path = state / "agents" / "coder.yaml"
    end = time.time() + 15
    while time.time() < end and not path.exists():
        time.sleep(0.1)
    time.sleep(0.3)
    saved = yaml.safe_load(path.read_text(encoding="utf-8")) if path.exists() else {}
    out["saved"] = {"tags": saved.get("tags"), "files": (saved.get("context") or {}).get("files"),
                    "accept": (saved.get("acceptance") or {}).get("prompt"), "schedule": saved.get("schedule"),
                    "offline": (saved.get("environment") or {}).get("offline")}
    out["problems"] = c.js(f"{q('bio-problems')}?.textContent || ''")
    return out


def focus(c, url: str, state: Path, srv) -> dict:
    from halo_harness.studio import launch
    from halo_harness.studio.edit_open import open_edit
    from halo_harness.studio.edit_target import parse
    from halo_harness.studio.events import bridge_for
    out: dict = {}
    opened: list = []
    launch._open = lambda u: opened.append(u) or True  # a focused page needs no new tab; record any
    c.go(url)
    c.wait(f"document.querySelectorAll('[data-testid=\"section-tab\"]').length === 7", 30)
    end = time.time() + 15
    while time.time() < end and bridge_for(srv).listeners() < 1:
        time.sleep(0.1)
    out["listeners"] = bridge_for(srv).listeners()
    cwd = state.parent / "project"
    r = open_edit(parse("lineup:halo-dev-cycle")[0], cwd=cwd, state_dir=state)
    out["lineup_how"], out["lineup_pages"] = r["how"], r["pages"]
    out["lineup_tab"] = c.wait(f"{q('roles-lineup-tab')}?.dataset.lineup", 20)
    out["lineup_selected"] = c.js(f"{q('roles-tab-lineup')}?.getAttribute('aria-selected')")
    press(c, "roles-block-delegation")
    c.wait(f"!!{q('roles-section-delegation')}", 5)
    out["about"] = c.js(f"{q('roles-about-delegation')}?.textContent || ''")
    pick(c, f"{q('roles-section-delegation')}.querySelector('select')", "round-robin")
    c.wait(f"!{q('roles-save')}.disabled", 10)
    press(c, "roles-save")
    path = state / "teams" / "halo-dev-cycle.yaml"
    end = time.time() + 15
    mode = None
    while time.time() < end and mode != "round-robin":
        time.sleep(0.2)
        mode = ((yaml.safe_load(path.read_text(encoding="utf-8")) or {}).get("delegation") or {}).get("mode")
    out["delegation_saved"] = mode
    r = open_edit(parse("team")[0], cwd=cwd, state_dir=state)
    out["team_how"] = r["how"]
    end = time.time() + 10
    while time.time() < end and not section_tab(c).startswith("Team"):
        time.sleep(0.1)
    out["team_section"] = section_tab(c)
    r = open_edit(parse("bio:reviewer")[0], cwd=cwd, state_dir=state)
    out["bio_how"] = r["how"]
    out["bio_form"] = c.wait(f"{FORM}?.dataset.bio === 'reviewer' && {FORM}.dataset.bio", 20)
    out["bio_section"] = section_tab(c)
    out["tabs_opened"] = len(opened)
    out["url"] = r["url"].split("#")[0]
    return out


class EditDriver(Driver):
    """`bio`: a page opened with `?edit=bio:coder`; `focus`: a running Studio focused by open_edit."""

    no_chrome = {"skip": "no Chrome found"}

    @contextmanager
    def session(self, c):
        from capture_studio import seeded_home
        from halo_harness.privateio import write_private_atomic
        from halo_harness.studio.server import start_server, studio_info_path, url_for
        state = seeded_home()
        proj = state.parent / "project"
        proj.mkdir(exist_ok=True)
        srv = start_server(port=0, cwd=proj, state_dir=state)
        threading.Thread(target=srv.serve_forever, daemon=True).start()
        write_private_atomic(studio_info_path(state), json.dumps({"pid": 0, "port": srv.server_address[1], "token": srv.token}))
        try:
            if self.argv[:1] == ["focus"]:
                yield ((focus, (c, url_for(srv, "roles").replace("?mode=roles", "?mode=roles&tour=off"), state, srv)),)
            else:
                yield ((bio, (c, url_for(srv, None, "bio:coder"), state)),)
        finally:
            srv.shutdown()
            srv.server_close()
            shutil.rmtree(state.parent, ignore_errors=True)


if __name__ == "__main__":
    sys.exit(EditDriver(sys.argv[1:]).main())
