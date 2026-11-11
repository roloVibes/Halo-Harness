"""tests.helpers.studio_clarity -- the Studio clarity checks (Halo 3.0.4.0
round R6b) driven through real clicks and keys in headless Chrome over the
DevTools protocol (tests/helpers/cdp.py). tests/test_studio_ui.py runs it as
a subprocess with a scrubbed environment, like tools/capture_studio.py:

    python -m tests.helpers.studio_clarity panel    # Agents' Cast panels: click to focus, ?, the ... menu, the Inspector, the section help

The last stdout line is a JSON object of what it saw (exit 2: no Chrome)."""
from __future__ import annotations

import shutil
import sys
from contextlib import contextmanager
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO))
sys.path.insert(0, str(REPO / "tools"))

from tests.helpers.chrome_driver import Driver  # noqa: E402
from tests.helpers.studio_full import toggle_face  # noqa: E402


P = "document.querySelector('[data-panel=\"{}\"] {}')"


def panel(c, url: str) -> dict:
    """3.4.0.0 D: on Agents' Cast workspace (Runs' Orchestra panels, where this ran before, went with the runs fold)."""
    out = {}
    c.go(url.replace("feed=off", "feed=off&tour=off&mode=agents&view=cast").replace("mode=orchestra&", ""))
    c.wait("document.querySelectorAll('[data-testid=\"roles-card\"]').length >= 7 && document.querySelectorAll('[data-testid=\"panel-title\"]').length === 6", 30)
    out["about"] = c.js("document.querySelectorAll('[data-testid=\"panel-title\"][title]:not([title=\"\"])').length")  # 3.3.2.0 R3: the about line is the title's tooltip and the ?'s first line
    body = P.format("roles-models", ".panel-body")
    x, y, w, h = c.rect(body)
    c.click(x + 20, y + h - 8)  # the body's padding: nothing to press there, the panel itself takes it
    out["active"] = c.wait(P.format("roles-models", ".panel") + ".hasAttribute('data-active')", 5)
    out["focused"] = c.js("document.activeElement === " + P.format("roles-models", ".panel"))
    out["others_active"] = c.js("document.querySelectorAll('.panel[data-active]').length")
    c.click_on(P.format("roles-lineups", ".panel-title"))  # a click on a title bar focuses, moves nothing
    out["title_click"] = c.wait(P.format("roles-lineups", ".panel") + ".hasAttribute('data-active') && 'roles-lineups'", 5)
    out["layout_after_click"] = c.js("document.querySelector('.hud-strip').textContent.includes('layout default') ? 'default' : 'yours'")
    x, y, w, h = c.rect(body)
    c.click(x + 20, y + h - 8)
    c.wait(P.format("roles-models", ".panel") + ".hasAttribute('data-active')", 5)
    c.key("?")
    c.wait("!!document.querySelector('[data-testid=\"panel-help\"]')", 5)
    out["help_title"] = c.js("document.querySelector('.panel-help-title').textContent")
    out["help_lines"] = c.js("document.querySelectorAll('.panel-help-lines li').length")
    c.key("Escape")
    out["help_closed"] = c.wait("!document.querySelector('[data-testid=\"panel-help\"]')", 5)
    c.click_on(P.format("roles-bios", "[data-testid=\"panel-menu-btn\"]"))
    c.wait("!!document.querySelector('[data-testid=\"panel-menu\"]')", 5)
    out["menu"] = c.js("[...document.querySelectorAll('[data-testid=\"panel-menu\"] [role=menuitem]')].map((b) => b.dataset.item)")
    c.click_on("document.querySelector('[data-testid=\"panel-menu\"] [data-item=\"settings\"]')")
    out["inspector"] = c.wait("document.querySelector('.inspector-title')?.textContent", 5)
    x, y, w, h = c.rect(body)
    c.click(x + 20, y + h - 8)
    out["inspector_follows"] = c.wait("document.querySelector('.inspector-title')?.textContent === 'Models' && 'Models'", 5)
    toggle_face(c, '[data-panel="roles-models"]')  # 3.3.2.0 R3: Compact is a row of the ... menu
    out["compact"] = c.wait(P.format("roles-models", ".panel") + ".dataset.face === 'glance' && 'glance'", 5)
    c.click_on("document.querySelector('[data-testid=\"section-help-btn\"]')")
    c.wait("!!document.querySelector('[data-testid=\"help-menu\"]')", 5)  # 3.1.1.0 R1: the ? menu
    out["help_menu"] = c.js("[...document.querySelectorAll('[data-testid=\"help-menu\"] [role=menuitem]')].map((b) => b.dataset.testid)")
    c.click_on("document.querySelector('[data-testid=\"section-help-item\"]')")
    c.wait("!!document.querySelector('[data-testid=\"section-help\"]')", 5)
    out["section_title"] = c.js("document.querySelector('[data-testid=\"section-help\"] .dialog-title').textContent")
    out["section_steps"] = c.js("document.querySelectorAll('[data-testid=\"section-help\"] .section-help-steps li').length")
    out["section_panels"] = c.js("document.querySelectorAll('[data-testid=\"section-help\"] section[aria-label=Panels] li').length")
    out["section_text"] = c.js("document.querySelector('[data-testid=\"section-help\"]').innerText.slice(0, 4000)")
    c.click_on("document.querySelector('[data-testid=\"section-help-ok\"]')")
    out["section_closed"] = c.wait("!document.querySelector('[data-testid=\"section-help\"]')", 5)
    out["seen"] = c.js("Object.keys(localStorage).filter((k) => k.startsWith('halo.studio.seen.')).length")  # 3.3.2.0 R1: no welcome, nothing to remember
    c.click_on("document.querySelector('[data-testid=panels-add]')")  # 3.4.0.0 D: Agents' "+" menu has its panels and no RUNS group
    c.wait("!!document.querySelector('[data-testid=panels-menu]')", 5)
    out["menu_runs"] = c.js("document.querySelectorAll('[data-testid=orchestra-menu-run], [data-testid=orchestra-new-run]').length")
    out["menu_text"] = c.js("document.querySelector('[data-testid=panels-menu]').innerText")
    c.key("Escape")
    return out


class ClarityDriver(Driver):
    """`panel`: the panel checks on Agents' Cast (3.4.0.0 D; Orchestra's before), Studio over capture_studio's seeded home."""

    no_chrome = {"skip": "no Chrome found"}

    @contextmanager
    def session(self, c):
        from capture_studio import seeded_home, serve
        state = seeded_home()
        repo = None
        srv, url = serve(state, True, repo)
        from tests.helpers.studio_full import full
        url = full(url)  # 3.3.2.0 R3: every panel open, the arrangement this driver works in
        try:
            yield ((panel, (c, url)),)  # 3.0.7.0 R2: the Roles checks are tests/helpers/studio_roles.py
        finally:
            srv.shutdown()
            srv.server_close()
            if repo is not None:
                from tests.helpers.orchestra_studio_rig import cleanup
                cleanup(repo)
            shutil.rmtree(state.parent, ignore_errors=True)


def main(argv: list) -> int:
    return ClarityDriver(argv).main()


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
