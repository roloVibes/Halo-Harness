"""tests.helpers.studio_packs -- the Studio-contributions checks of
tests/test_packs_studio_ui.py (Halo 3.2.0.0 R3), real keys and clicks in
headless Chrome through the driver base, over a scratch home with the
doc-review fixture pack (enabled) and studio-bundle (enabled, studio-script
not granted); this process serves Studio in a thread with the live feed on
(no provider, no model call):

1. the packs' sections after Orchestra behind a "packs" divider, Alt+7 opens
   Docs review: the markdown, the table, the links, the Settings form; the
   panel's source line and its help; the rail's PACKS group;
2. Session holds the pack's Reviews panel as a strip;
3. the palette's pack action opens the checks panel;
4. the form writes packs.settings.doc-review;
5. the bundle panel shows the grant line, then (granted here) "hello from";
6. a review.done frame: the pack's line in Fleet's Activity, Session's Live
   column and the Reviews panel; an undeclared kind keeps the generic line;
7. a row file: the attention row with the pack's label and keys, A answers it;
8. doc-review disabled: its tab, its Session panel, its palette action and
   its rows are gone without a reload, and its lines fall back to generic.

The last stdout line is the JSON of what it saw (exit 2: no Chrome)."""
from __future__ import annotations

import json
import shutil
import sys
import time
from contextlib import contextmanager
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO))
sys.path.insert(0, str(REPO / "tools"))

from tests.helpers.chrome_driver import Driver  # noqa: E402
from tests.helpers.studio_packs_steps import (CUR, TABS, alt, attention, disabled, events, mod_key, pa, panel,  # noqa: E402
                                              press, q, qa)



def sections(c, url, ctx) -> dict:
    out: dict = {}
    c.go(url)
    c.wait(f"{TABS}.some((t) => t.textContent.startsWith('Docs review'))", 40)
    out["tabs"] = c.js(f"{TABS}.map((t) => t.querySelector('.tab-label').textContent)")
    out["kbds"] = c.js(f"{TABS}.map((t) => t.querySelector('.tab-kbd')?.textContent || '')")
    out["divider"] = c.js(f"(() => {{ const d = {q('[data-testid=tab-divider]')}; return d ? [d.textContent, d.nextElementSibling?.querySelector('.tab-label')?.textContent] : null; }})()")
    alt(c, 7)
    out["alt7"] = c.wait(f"{CUR}.startsWith('Docs review') && {CUR}", 10)
    out["markdown"] = c.wait(f"{panel('doc-review--notes', '[data-testid=pack-markdown]')}?.textContent", 15)
    out["table_rows"] = c.wait(pa("doc-review--checks", "[data-testid=pack-table-row]") + ".length", 15)
    out["table_head"] = c.js(pa("doc-review--checks", "th") + ".map((t) => t.textContent)")
    out["links"] = c.js(pa("doc-review--links", "[data-testid=pack-link]") + ".map((a) => a.textContent)")
    out["about"] = c.js(f"{panel('doc-review--notes', '[data-testid=panel-about]')}?.textContent")
    out["form_fields"] = c.wait(pa("doc-review--settings", "[data-testid=pack-form-input]") + ".map((i) => i.dataset.key)", 15)
    press(c, panel("doc-review--notes", ".panel-title"))
    c.key("?")
    out["help"] = c.wait(f"{q('[data-testid=panel-help]')}?.textContent", 10)
    c.key("Escape")
    out["rail"] = c.js(f"{qa('[data-testid=rail-pack-section]')}.map((b) => b.textContent)")
    return out


def session_panel(c, url, ctx) -> dict:
    alt(c, 1)
    c.wait(f"{CUR}.startsWith('Session')", 10)
    p = panel("doc-review--reviews", ".panel")
    c.wait(f"!!{p}", 20)
    return {"session_panel": [c.js(f"{p}.dataset.collapsed === 'true'"), c.js(f"{p}.querySelector('.panel-title').textContent"),
                              c.js(f"{p}.querySelector('[data-testid=panel-about]').textContent")]}


def palette(c, url, ctx) -> dict:
    mod_key(c, "KeyK", 75, 2, "k")
    c.wait(f"!!{q('[data-testid=palette]')}", 10)
    groups = c.js(f"{qa('.palette-group')}.map((g) => g.getAttribute('aria-label'))")
    c.wait("document.activeElement?.classList.contains('palette-input')", 10)
    c.type_text("Open the review checks")
    try:
        c.wait(f"{q('.palette-item.on .palette-label')}?.textContent === 'Open the review checks'", 10)
    except TimeoutError:
        raise TimeoutError(f"the palette shows {c.js(qa('.palette-label') + '.slice(0, 6).map((l) => l.textContent)')}")
    c.key("Enter")
    c.wait(f"{CUR}.startsWith('Docs review')", 10)
    active = c.wait(f"{panel('doc-review--checks', '.panel')}?.dataset.active === 'true'", 10)
    return {"palette_groups": groups, "palette_ran": bool(active)}


def form(c, url, ctx) -> dict:
    sel = panel("doc-review--settings", 'select[data-key="style"]')
    c.wait(f"!!{sel}", 10)
    c.js(f"(() => {{ const s = {sel}; const set = Object.getOwnPropertyDescriptor(HTMLSelectElement.prototype, 'value').set; "
         f"set.call(s, 'long'); s.dispatchEvent(new Event('change', {{bubbles: true}})); return 1; }})()")
    press(c, panel("doc-review--settings", "[data-testid=pack-form-save]"))
    cfg = ctx["state"] / "config.json"
    end = time.time() + 10
    got = {}
    while time.time() < end:
        try:
            got = json.loads(cfg.read_text(encoding="utf-8")).get("packs", {}).get("settings", {}).get("doc-review", {})
        except (OSError, ValueError):
            got = {}
        if got.get("style") == "long":
            break
        time.sleep(0.2)
    return {"form_saved": got}


def bundle(c, url, ctx) -> dict:
    alt(c, 8)
    c.wait(f"{CUR}.startsWith('Hello')", 10)
    grant = c.wait(f"{panel('studio-bundle--greet', '[data-testid=pack-bundle-grant]')}?.textContent", 15)
    before = c.js(f"!!{q('[data-testid=pack-bundle-hello]')}")
    from halo_harness.packs.discover import find
    from halo_harness.packs.grants import enable
    enable(find("studio-bundle"), grant=["studio-script"])
    hello = c.wait(f"{panel('studio-bundle--greet', '[data-testid=pack-bundle-hello]')}?.textContent", 20)
    return {"bundle_grant": grant, "bundle_before": before, "bundle_hello": hello}


class PacksStudioDriver(Driver):
    no_chrome = {"skip": "no Chrome found"}

    @contextmanager
    def session(self, c):
        from capture_studio import seeded_home, serve
        from halo_harness.packs.discover import find
        from halo_harness.packs.grants import enable
        from halo_harness.packs.install import install
        state = seeded_home()
        for name, grants in (("doc-review", ["hooks"]), ("studio-bundle", [])):
            ok, lines = install(str(REPO / "tests" / "fixtures" / "packs" / name))
            assert ok, lines
            ok, lines = enable(find(name), grant=grants)
            assert ok, lines
        srv, url = serve(state, True)
        url = url.replace("mode=orchestra&feed=off", "mode=roles&tour=off&view=workspace")
        ctx = {"state": state, "srv": srv}
        try:
            yield tuple((fn, (c, url, ctx)) for fn in (sections, session_panel, palette, form, bundle, events, attention, disabled))
        finally:
            srv.shutdown()
            srv.server_close()
            shutil.rmtree(state.parent, ignore_errors=True)


if __name__ == "__main__":
    sys.exit(PacksStudioDriver(sys.argv[1:]).main())
