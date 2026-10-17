"""tests.helpers.studio_clarity -- the Studio clarity checks (Halo 3.0.4.0
round R6b) driven through real clicks and keys in headless Chrome over the
DevTools protocol (tests/helpers/cdp.py). tests/test_studio_ui.py runs it as
a subprocess with a scrubbed environment, like tools/capture_studio.py:

    python -m tests.helpers.studio_clarity panel    # Orchestra: click to focus, ?, the ... menu, the Inspector, the section help

The last stdout line is a JSON object of what it saw (exit 2: no Chrome)."""
from __future__ import annotations

import json
import shutil
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO))
sys.path.insert(0, str(REPO / "tools"))


def panel(c, url: str) -> dict:
    out = {}
    c.go(url.replace("feed=off", "feed=off&tour=off"))
    c.wait("document.querySelectorAll('[data-testid=\"report-check\"]').length === 8")
    out["about"] = c.js("document.querySelectorAll('[data-testid=\"panel-about\"]').length")
    body = "document.querySelector('[data-panel=\"report\"] .panel-body')"
    x, y, w, h = c.rect(body)
    c.click(x + 20, y + h - 8)  # the body's padding: nothing to press there, the panel itself takes it
    out["active"] = c.wait("document.querySelector('[data-panel=\"report\"] .panel').hasAttribute('data-active')", 5)
    out["focused"] = c.js("document.activeElement === document.querySelector('[data-panel=\"report\"] .panel')")
    out["others_active"] = c.js("document.querySelectorAll('.panel[data-active]').length")
    c.click_on("document.querySelector('[data-panel=\"graph\"] .panel-title')")  # a click on a title bar focuses, moves nothing
    out["title_click"] = c.wait("document.querySelector('[data-panel=\"graph\"] .panel').hasAttribute('data-active') && 'graph'", 5)
    out["layout_after_click"] = c.js("document.querySelector('.hud-strip').textContent.includes('layout default') ? 'default' : 'yours'")
    x, y, w, h = c.rect(body)
    c.click(x + 20, y + h - 8)
    c.key("?")
    c.wait("!!document.querySelector('[data-testid=\"panel-help\"]')", 5)
    out["help_title"] = c.js("document.querySelector('.panel-help-title').textContent")
    out["help_lines"] = c.js("document.querySelectorAll('.panel-help-lines li').length")
    c.key("Escape")
    out["help_closed"] = c.wait("!document.querySelector('[data-testid=\"panel-help\"]')", 5)
    c.click_on("document.querySelector('[data-panel=\"lanes\"] [data-testid=\"panel-menu-btn\"]')")
    c.wait("!!document.querySelector('[data-testid=\"panel-menu\"]')", 5)
    out["menu"] = c.js("[...document.querySelectorAll('[data-testid=\"panel-menu\"] [role=menuitem]')].map((b) => b.dataset.item)")
    c.click_on("document.querySelector('[data-testid=\"panel-menu\"] [data-item=\"settings\"]')")
    out["inspector"] = c.wait("document.querySelector('.inspector-title')?.textContent", 5)
    x, y, w, h = c.rect(body)
    c.click(x + 20, y + h - 8)
    out["inspector_follows"] = c.wait("document.querySelector('.inspector-title')?.textContent === 'Report' && 'Report'", 5)
    c.click_on("document.querySelector('[data-panel=\"report\"] [data-testid=\"panel-compact\"]')")
    out["compact"] = c.wait("document.querySelector('[data-panel=\"report\"] .panel').dataset.face === 'glance' && 'glance'", 5)
    c.click_on("document.querySelector('[data-testid=\"section-help-btn\"]')")
    c.wait("!!document.querySelector('[data-testid=\"section-help\"]')", 5)
    out["section_title"] = c.js("document.querySelector('[data-testid=\"section-help\"] .dialog-title').textContent")
    out["section_steps"] = c.js("document.querySelectorAll('[data-testid=\"section-help\"] .section-help-steps li').length")
    out["section_panels"] = c.js("document.querySelectorAll('[data-testid=\"section-help\"] section[aria-label=Panels] li').length")
    c.click_on("document.querySelector('[data-testid=\"section-help-ok\"]')")
    out["section_closed"] = c.wait("!document.querySelector('[data-testid=\"section-help\"]')", 5)
    out["seen"] = c.js("localStorage.getItem('halo.studio.seen.orchestra')")
    return out


def main(argv: list) -> int:
    from capture_studio import find_chrome, seeded_home, serve
    from tests.helpers.cdp import Chrome
    exe = find_chrome()
    if not exe:
        print(json.dumps({"skip": "no Chrome found"}))
        return 2
    state = seeded_home()
    repo = None
    if argv[:1] == ["panel"]:
        from tests.helpers.orchestra_studio_rig import finished_run
        repo, _run = finished_run()
    srv, url = serve(state, True, repo)
    c = Chrome(exe)
    try:
        got = panel(c, url)  # 3.0.7.0 R2: the Roles checks are tests/helpers/studio_roles.py
        print(json.dumps(got))
        return 0
    finally:
        c.close()
        srv.shutdown()
        srv.server_close()
        if repo is not None:
            from tests.helpers.orchestra_studio_rig import cleanup
            cleanup(repo)
        shutil.rmtree(state.parent, ignore_errors=True)


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
