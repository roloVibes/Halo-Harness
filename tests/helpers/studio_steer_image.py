"""tests.helpers.studio_steer_image -- Halo 3.3.6.0 R6 "Studio takes an image", through real events in headless
Chrome on the driver base (tests/helpers/chrome_driver.Driver), over tests/helpers/studio_fleet_rig.py (this
harness's real session behind the real Controller and control socket, which works while the test holds its
agents). tests/test_studio_steer_image.py runs it as a subprocess:

    python -m tests.helpers.studio_steer_image steer
        the Screenshot button (the capture seam's fixture under the test flag) -> the chip from the harness's own
        capture; the session's model cannot see -> the chip's offer line and three buttons, "Text only" picked;
        a base64 PNG pasted into the Live steer (a ClipboardEvent carrying a File) -> the chip (name, 4 x 3, size)
        -> Send -> the agents released -> the session log's image block (the steer's `steer_image` snapshot at its
        safe point) with `image_path` and no base64.

The last stdout line is a JSON object of what it saw (exit 2: no Chrome). No model is called, nothing is captured
from the real screen."""
from __future__ import annotations

import base64
import dataclasses
import json
import os
import sys
import time
from contextlib import contextmanager
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO))

from tests.helpers.chrome_driver import Driver  # noqa: E402

FIXTURE = REPO / "tests" / "fixtures" / "vision" / "shot.png"
BOX = "document.querySelector('[data-testid=\"session-live-steer\"]')"
AREA = f"{BOX}?.querySelector('[data-testid=\"fleet-steer\"]')"
CHIP = "document.querySelector('[data-testid=\"session-steer-image\"]')"
SENT = "what does this screenshot show"


def _logged_images(rig, after: int) -> list:
    """Image blocks the session logged since node `after` (a steer's image lands as a `steer_image` snapshot)."""
    nodes = rig.session.log.nodes()[after:]
    return [b for n in nodes if n.get("type") in ("user", "snapshot") for b in (n.get("content") or [])
            if isinstance(b, dict) and b.get("type") == "image"]


def _chip(c) -> dict:
    return c.js(f"(() => {{ const e = {CHIP}; return e && {{name: e.dataset.name, w: e.dataset.w, h: e.dataset.h, from: e.dataset.from, "
                "text: e.textContent}; })()") or {}


def _q(testid: str) -> str:
    return f"document.querySelector('[data-testid=\"{testid}\"]')"


def screenshot(c, rig) -> dict:
    """While the session works: the Screenshot button's capture is the chip; a model that cannot see shows the offer."""
    os.environ["HALO_SCREENSHOT_FIXTURE"] = str(FIXTURE)
    rig.closers.append(lambda: os.environ.pop("HALO_SCREENSHOT_FIXTURE", None))
    c.go(rig.url("session"))
    c.wait(f"!!{AREA} && !{AREA}.disabled", 40)
    btn = _q("session-live-screenshot")
    out = {"button_title": c.js(f"{btn}?.title")}
    c.click_on(btn)
    out["shot_chip"] = c.wait(f"(() => {{ const e = {CHIP}; return e && e.dataset.from === 'screenshot' && e.dataset.w && 'ok'; }})()", 20) and _chip(c)
    out["offer_line"] = c.wait(f"{_q('session-steer-eyes-line')}?.textContent", 20)
    out["offer_buttons"] = c.js("[...document.querySelectorAll('button[data-testid^=session-steer-eyes-]')]"
                                ".map((b) => [b.dataset.testid, b.disabled, b.getAttribute('aria-pressed')])")
    c.click_on(_q("session-steer-eyes-send"))
    out["picked"] = c.wait(f"{_q('session-steer-eyes-send')}?.getAttribute('aria-pressed') === 'true' && 'send'", 5)
    c.click_on(_q("session-steer-image-remove"))
    out["removed"] = c.wait(f"!{CHIP} && 'gone'", 5) or False
    return out


def paste(c, rig) -> dict:
    """A base64 PNG pasted into the steer -> the chip -> Send -> the log's image block (its path, no base64)."""
    from tests.helpers.fleet_rig import wait_for
    rig.session.model_profile = dataclasses.replace(rig.session.model_profile, vision=True)
    rig.session._eyes_fact = None
    b64 = base64.b64encode(FIXTURE.read_bytes()).decode("ascii")
    c.js(f"(() => {{ const bin = atob('{b64}'); const u = new Uint8Array(bin.length); for (let i = 0; i < bin.length; i++) u[i] = bin.charCodeAt(i); "
         "const dt = new DataTransfer(); dt.items.add(new File([u], 'clip.png', {type: 'image/png'})); "
         f"{AREA}.focus(); {AREA}.dispatchEvent(new ClipboardEvent('paste', {{clipboardData: dt, bubbles: true, cancelable: true}})); return 1; }})()")
    out = {"chip": c.wait(f"(() => {{ const e = {CHIP}; return e && e.dataset.w && e.dataset.name; }})()", 15) and _chip(c)}
    after = len(rig.session.log.nodes())
    c.click_on(AREA)
    c.type_text(SENT)
    c.key("Enter")
    out["chip_cleared"] = c.wait(f"!{CHIP} && 'gone'", 15) or False
    rig.release("a")
    rig.release("b")
    out["logged"] = (wait_for(lambda: _logged_images(rig, after), 60) or [])[:1]
    out["kinds"] = [n.get("kind") for n in rig.session.log.nodes()[after:] if n.get("type") == "snapshot"]
    return out


class SteerImageDriver(Driver):
    no_chrome = {"skip": "no Chrome found"}

    @contextmanager
    def session(self, c):
        from tests.helpers.studio_fleet_rig import StudioFleetRig
        with StudioFleetRig() as rig:
            yield ((screenshot, (c, rig)), (paste, (c, rig)))


if __name__ == "__main__":
    sys.exit(SteerImageDriver(sys.argv[1:]).main())
