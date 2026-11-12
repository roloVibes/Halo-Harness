"""The design pack's Studio capture (was tools/capture_design.py, `tools/capture_studio.py --mode design`, in Halo's
core; Halo 3.0.7.0 round R3). Run from Halo's checkout (it uses its capture tools and Chrome driver):

    python halo_harness/templates/packs/design/tests/capture_design.py [--out docs/media/studio-design.png] [--dom]

A scratch home (tools/capture_studio.py seeded_home) with this pack linked and enabled with every grant, Studio on the
Design section (`?mode=design--design`) over the seeded "Launch page" project (tests/seed.py): Projects, Assets, the
Artboards canvas with its pins, the Thread of its turns. With --dom the section is read twice, its Start view first
(no project yet), then over the seeded project, and the data-testid values are counted (the last stdout line is the
JSON: {"start": {...}, "design": {...}}). Never two Chromes at once; every page is guarded before it is counted or shot.
"""

from __future__ import annotations

import argparse
import json
import os
from halo_harness.ext import subprocess_safe as subprocess
import sys
import time
from pathlib import Path

PACK = Path(__file__).resolve().parent.parent
REPO = PACK.parents[3]  # halo_harness/templates/packs/design -> the checkout
IDS = ("section-tab", "panel-title", "design-start", "design-thread", "design-turn", "design-artboard", "design-pin",
       "design-project", "design-assets", "design-asset", "design-send-box", "pack-view")


def counts(dom: str) -> dict:
    out = {k: dom.count(f'data-testid="{k}"') for k in IDS}
    out["iframes"] = dom.count("<iframe")
    out["title"] = dom.split("<title>")[1].split("</title>")[0] if "<title>" in dom else ""
    return out


def enable_pack() -> None:
    """Link this folder into the scratch home (BRIDGE_TEST_HOME, set by seeded_home) and enable it with every grant."""
    env = dict(os.environ, PYTHONPATH=str(REPO))
    for argv in (["pack", "install", str(PACK), "--link"], ["pack", "enable", "design", "--grant-all"]):
        subprocess.run([sys.executable, "-m", "halo_harness", *argv], env=env, check=True, capture_output=True, timeout=120)


def shoot(out: str, url: str) -> int:
    """The picture through the DevTools protocol, once two artboards and two turns have drawn."""
    from capture_identity import guard_page
    from tests.helpers.chrome_driver import open_chrome
    c = open_chrome()
    if c is None:
        print("no Chrome found: nothing rendered")
        return 2
    try:
        c.go(url)
        c.wait("document.querySelectorAll('[data-testid=\"design-artboard\"]').length >= 2 && "
               "document.querySelectorAll('[data-testid=\"design-turn\"]').length >= 2", 30)
        time.sleep(2.5)  # the frames and the images paint
        path = Path(out).resolve()
        guard_page(c, path.stem)
        size = c.shot(path)
        ok = path.is_file() and size > 10_000
        print(f"{'wrote' if ok else 'FAILED'} {path} ({size} bytes)")
        return 0 if ok else 1
    finally:
        c.close()


def main(argv=None) -> int:
    sys.path[:0] = [str(REPO), str(REPO / "tools")]  # Halo's tests/ is `tests` here: this pack's seed is loaded by path
    p = argparse.ArgumentParser(prog="capture_design")
    p.add_argument("--out", default=str(REPO / "docs" / "media" / "studio-design.png"))
    p.add_argument("--dom", action="store_true")
    args = p.parse_args(argv)
    from capture_identity import begin, checked_dump, placeholder
    from capture_studio import chrome, seeded_home, serve
    begin()
    state = seeded_home()
    placeholder(state)
    enable_pack()
    srv, url = serve(state, True)
    url = url.replace("mode=orchestra", "mode=design--design").replace("feed=off", "feed=off&tour=off")
    import importlib.util
    from tests.helpers.studio_full import full
    spec = importlib.util.spec_from_file_location("design_pack_seed", PACK / "tests" / "seed.py")
    seeding = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(seeding)
    seed = seeding.seed
    try:
        result: dict = {}
        if args.dom:
            r = checked_dump(chrome, url, "design start", "--window-size=1500,900")
            if r is None:
                print("no Chrome found")
                return 2
            result["start"] = counts(r.stdout)
        seed(state)
        if args.dom:
            r = checked_dump(chrome, full(url), "design", "--window-size=1500,900")
            result["design"] = counts(r.stdout) if r else {}
            print(json.dumps(result))
            return 0
        return shoot(args.out, url.replace("#", "&open=design-thread#", 1))
    finally:
        srv.shutdown()
        srv.server_close()


if __name__ == "__main__":
    sys.exit(main())
