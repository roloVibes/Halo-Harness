"""tools/capture_design.py -- the Design capture for tools/capture_studio.py
--mode design (Halo 3.0.7.0 round R3: a React section of the shell, no
framed classic page).

    docs/media/studio-design.png  the seeded "Launch page" project (tools/design_demo.py): Projects,
                                  Assets, the Artboards canvas with its pins, the Thread of its turns

With --dom the section is read twice, its Start view first (no project
yet), then over the seeded project, and the data-testid values are counted
(the last stdout line is the JSON: {"start": {...}, "design": {...}}).
Never two Chromes at once.
"""

from __future__ import annotations

import json
from pathlib import Path

IDS = ("section-tab", "legacy-frame", "panel-about", "design-start", "design-thread", "design-turn", "design-artboard", "design-pin",
       "design-project", "design-assets", "design-asset", "design-send-box")


def counts(dom: str) -> dict:
    out = {k: dom.count(f'data-testid="{k}"') for k in IDS}
    out["iframes"] = dom.count("<iframe")
    out["title"] = dom.split("<title>")[1].split("</title>")[0] if "<title>" in dom else ""
    return out


def capture(out: str, dom: bool, chrome, serve, state: Path) -> int:
    srv, url = serve(state, True)
    url = url.replace("mode=orchestra", "mode=design").replace("feed=off", "feed=off&tour=off")
    try:
        result: dict = {}
        if dom:  # the Start view first: no project yet
            r = chrome(["--dump-dom", "--window-size=1500,900", url])
            if r is None:
                print("no Chrome found")
                return 2
            result["start"] = counts(r.stdout)
        from design_demo import seed
        seed(state)
        if dom:
            r = chrome(["--dump-dom", "--window-size=1500,900", url])
            result["design"] = counts(r.stdout) if r else {}
            print(json.dumps(result))
            return 0
        return shoot(out, url)
    finally:
        srv.shutdown()
        srv.server_close()


def shoot(out: str, url: str) -> int:
    """The picture through the DevTools protocol, once two artboards and two turns have drawn."""
    import time
    from tests.helpers.chrome_driver import open_chrome
    c = open_chrome()  # the driver base: HALO_CHROME first, one headless Chrome at a time
    if c is None:
        print("no Chrome found: nothing rendered")
        return 2
    try:
        c.go(url)
        c.wait("document.querySelectorAll('[data-testid=\"design-artboard\"]').length >= 2 && document.querySelectorAll('[data-testid=\"design-turn\"]').length >= 2", 30)
        time.sleep(2.5)  # the frames and the images paint
        path = Path(out).resolve()
        size = c.shot(path)
        ok = path.is_file() and size > 10_000
        print(f"{'wrote' if ok else 'FAILED'} {path} ({size} bytes)")
        return 0 if ok else 1
    finally:
        c.close()
