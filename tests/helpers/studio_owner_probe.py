"""tests.helpers.studio_owner_probe -- the reviewers' two owner-proof probes in headless Chrome (Halo 3.4.1.2, the
2026-11-12 review's SERVERS-4 and PACKS-2), on the driver base over tests/helpers/packs_studio.PackStudio with the
fixture pack tests/fixtures/packs/owner-probe granted studio-script (its bundle is the attacker):

`probe_open`: the bundle opens Studio's own page in a window on a user gesture and polls it for `data-owner-salt` while
it loads (SERVERS-4); the window is a script's, so Studio serves it no salt and it says VIEW ONLY -- and the page's
`Cross-Origin-Opener-Policy: noopener-allow-popups` cuts the opener off from it (`severed`).
`probe_shell`: with Map.prototype.get, Promise.prototype.then, Headers and Object.prototype getters patched by the
bundle, the shell makes an owner write of its own (the theme menu); it still works, and the bundle caught no proof
(PACKS-2).
`probe_forge`: the bundle POSTs `pack/owner-probe/grant` with every salt and caught value it has, and with none: each is
403, and the pack keeps its grant.
`reloads`: the browser's own reload (CDP Page.reload, as F5) keeps the owner's page (no VIEW ONLY); a script's
`location.reload()` does not (VIEW ONLY), as a window a script opens.
The last stdout line is a JSON object of what it saw (exit 2: no Chrome). No model is called; nothing leaves loopback.

    python -m tests.helpers.studio_owner_probe
"""
from __future__ import annotations

import json
import sys
from contextlib import contextmanager
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO))
sys.path.insert(0, str(REPO / "tools"))

from tests.helpers.chrome_driver import Driver  # noqa: E402

PACK = "owner-probe"
Q = "document.querySelector"


def probe_open(c) -> dict:
    c.call("Runtime.evaluate", expression="window.__probeOpen(); 1", userGesture=True, returnByValue=True)
    c.wait("window.__probe.openDone === true", 30)
    return {"opened": c.js("window.__probe.opened"), "salts": c.js("window.__probe.salts.length"),
            "view_only": c.js("window.__probe.viewOnly"), "severed": c.js("window.__probe.severed")}


def probe_shell(c, s) -> dict:
    c.click_on(f"{Q}('[data-testid=\"theme-menu-btn\"]')")
    item = f"{Q}('[data-testid=\"theme-item\"][data-theme-id=\"midnight\"]')"
    c.wait(f"!!{item}", 15)
    c.click_on(item)
    cfg = s.state / "config.json"

    def theme() -> str:
        try:
            return str(json.loads(cfg.read_text(encoding="utf-8")).get("theme") or "")
        except (OSError, ValueError):
            return ""
    import time
    deadline = time.time() + 20
    while time.time() < deadline and theme() != "midnight":
        time.sleep(0.1)
    return {"shell_theme": theme(), "stolen": c.js("window.__probe.stolen.length")}


def probe_forge(c, s) -> dict:
    from halo_harness.packs import state as S
    got = c.js(f"window.__probeForge({json.dumps(PACK)})")
    return {"forged": got, "granted_after": S.granted(PACK, S.load(s.state))}


def reloads(c) -> dict:
    note = f"!!{Q}('[data-testid=\"owner-note\"]')"
    ready = f"!!{Q}('[data-testid=\"theme-menu-btn\"]')"
    c.call("Page.reload")
    c.wait(f"document.readyState === 'complete' && {ready}", 30)
    out = {"browser_reload_view_only": c.js(note)}
    c.js("location.reload(); 1")
    c.wait(f"document.readyState === 'complete' && {ready} && {note}", 30)
    out["script_reload_view_only"] = c.js(note)
    return out


class OwnerProbeDriver(Driver):
    @contextmanager
    def session(self, c):
        from tests.helpers.packs_studio import PackStudio
        with PackStudio() as s:
            s.install_pack(PACK, grants=["studio-script"])
            c.go(f"{s.base}/?mode={PACK}--probe#t={s.token}")
            c.wait(f"!!window.__probe && window.__probe.mounted && !!{Q}('[data-testid=\"owner-probe-ready\"]')", 40)
            self.out["salt_in_main"] = c.js("!!document.documentElement.dataset.ownerSalt")
            yield ((probe_open, (c,)), (probe_shell, (c, s)), (probe_forge, (c, s)), (reloads, (c,)))


if __name__ == "__main__":
    sys.exit(OwnerProbeDriver(sys.argv[1:]).main())
