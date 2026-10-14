"""tests.helpers.studio_clarity -- the Studio clarity checks (Halo 3.0.4.0
round R6b) driven through real clicks and keys in headless Chrome over the
DevTools protocol (tests/helpers/cdp.py). tests/test_studio_ui.py runs it as
a subprocess with a scrubbed environment, like tools/capture_studio.py:

    python -m tests.helpers.studio_clarity panel    # Orchestra: click to focus, ?, the ... menu, the Inspector, the section help
    python -m tests.helpers.studio_clarity legacy   # Roles: one header, the status line, the groups, a drop into a box

The last stdout line is a JSON object of what it saw (exit 2: no Chrome)."""
from __future__ import annotations

import json
import shutil
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO))
sys.path.insert(0, str(REPO / "tools"))

FRAME = "document.querySelector('iframe.legacy-frame')"
DOC = f"{FRAME}.contentDocument"


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


def legacy(c, url: str, legacy_url: str) -> dict:
    out = {}
    c.go(url.replace("mode=orchestra", "mode=roles").replace("feed=off", "feed=off&tour=off"))
    out["groups"] = c.wait(f"{DOC}?.querySelectorAll('[data-testid=\"canvas-group\"]').length >= 4 && {DOC}.querySelectorAll('[data-testid=\"canvas-group\"]').length")
    out["labels"] = c.js(f"[...{DOC}.querySelectorAll('.group-label')].map((t) => t.textContent)")
    out["toolbar"] = c.js(f"!!{DOC}.querySelector('#top[data-testid=\"legacy-toolbar\"]')")
    out["brand"] = c.js(f"!!{DOC}.querySelector('#top .brand')")
    out["mode_buttons"] = c.js(f"{DOC}.querySelectorAll('#top [data-mode]').length")
    out["footer_shown"] = c.js(f"getComputedStyle({DOC}.getElementById('status')).display !== 'none'")
    out["toolbar_height"] = c.js(f"{DOC}.getElementById('top').getBoundingClientRect().height")
    out["status"] = c.wait("document.querySelector('[data-testid=\"legacy-status\"]')?.textContent", 10)
    # every card sits inside a box (screen rects, the frame's own coordinates)
    out["cards_in_boxes"] = c.js(f"""(() => {{ const d = {DOC}; const boxes = [...d.querySelectorAll('.group-box')].map((b) => b.getBoundingClientRect());
      return [...d.querySelectorAll('.node')].every((n) => {{ const r = n.querySelector('.card').getBoundingClientRect();
        return boxes.some((b) => r.left >= b.left - 1 && r.right <= b.right + 1 && r.top >= b.top - 1 && r.bottom <= b.bottom + 1); }}); }})()""")
    fx, fy, _w, _h = c.rect(FRAME)
    # drop the verify card (a custom role) into the Reviewers box: it becomes a reviewer
    card = c.rect(f"{DOC}.querySelector('.node[data-id=\"verify#3\"] .card')")
    box = c.rect(f"{DOC}.querySelector('.group[data-key=\"r:reviewer\"] .group-box')")
    c.drag(fx + card[0] + card[2] / 2, fy + card[1] + 12, fx + box[0] + 8, fy + box[1] + 12)
    out["joined"] = c.wait(f"(({FRAME}.contentWindow.app.current.raw.agents.find((a) => a.as === 'verify') || {{}}).role === 'reviewer') && 'reviewer'", 10)
    out["reviewers"] = c.wait(f"{DOC}.querySelector('.group[data-key=\"r:reviewer\"] .group-count')?.textContent === '2' && 2", 10)
    # the catalog is empty on a bare home: every model dropdown says so and offers Refresh (3.0.4.0)
    c.js(f"{FRAME}.contentWindow.app.canvas.select(['verify#3'])")
    out["models_notice"] = c.wait(f"{DOC}.querySelectorAll('[data-testid=\"models-empty\"] button').length", 10)
    btn = c.rect(f"{DOC}.getElementById('btn-groups')")
    c.click(fx + btn[0] + btn[2] / 2, fy + btn[1] + btn[3] / 2)
    out["groups_off"] = c.wait(f"{DOC}.querySelectorAll('[data-testid=\"canvas-group\"]').length === 0 && 'off'", 5)
    c.click(fx + btn[0] + btn[2] / 2, fy + btn[1] + btn[3] / 2)
    out["groups_on"] = c.wait(f"{DOC}.querySelectorAll('[data-testid=\"canvas-group\"]').length", 5)
    c.key("o")  # the focus is in the frame (the toolbar button): O switches the SHELL to Org, not the frame
    out["section_after_o"] = c.wait("document.querySelector('[data-testid=\"section-tab\"][aria-selected=\"true\"] .tab-label')?.textContent === 'Org' && 'Org'", 10)
    c.js(f"{FRAME}.contentWindow.app.dirty = false")  # the role change is unsaved: no "leave the page?" prompt
    c.go(legacy_url)  # the classic page on its own keeps its full header and footer
    c.wait("!!document.querySelector('.node')", 15)
    out["standalone_brand"] = c.js("!!document.querySelector('#top .brand')")
    out["standalone_modes"] = c.js("document.querySelectorAll('#top [data-mode]').length")
    out["standalone_footer"] = c.js("getComputedStyle(document.getElementById('status')).display !== 'none'")
    return out


def main(argv: list) -> int:
    from capture_studio import find_chrome, seeded_home, serve
    from halo_harness.studio.server import url_for
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
        if argv[:1] == ["panel"]:
            got = panel(c, url)
        else:
            got = legacy(c, url, url_for(srv, "roles", legacy=True).replace("?mode=roles", "?mode=roles&tour=off"))
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
