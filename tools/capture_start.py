"""tools/capture_start.py -- the "Start here" overlay for tools/capture_studio.py
--mode start (Halo 3.1.1.0 R1), through `--dump-dom` in headless Chrome.

    docs/media/studio-start.png   a fresh home opening on the overlay

With --dom the page is read three times over one Studio and the data-testid
values are counted (the last stdout line is the JSON):

    fresh      a fresh home (only the shipped lineups, none active, no run): the overlay, no welcome card
    dismissed  after "Just look around" (start/fresh.dismiss): no overlay, the section's welcome instead
    lineup     not dismissed, but a lineup active: no overlay

3.1.7.0 R2: the fresh home draws you@studio (tools/capture_identity.py) and every
page is guarded before it is counted or shot.
"""

from __future__ import annotations

import json
import shutil
import tempfile
from pathlib import Path

from capture_identity import checked_dump, placeholder

IDS = ("start-here", "start-here-run", "start-here-dismiss", "start-step", "section-help", "section-tab", "start-next",
       "roles-start")


def counts(dom: str) -> dict:
    return {k: dom.count(f'data-testid="{k}"') for k in IDS}


def fresh_home() -> Path:
    """A scratch home with nothing of its own (the shipped lineups are copied in on first use, as ever)."""
    import os
    home = Path(tempfile.mkdtemp(prefix="halo-studio-start-"))
    os.environ["BRIDGE_TEST_HOME"] = str(home)
    os.environ.pop("BRIDGE_STATE_DIR", None)
    from halo_harness.providers.config import default_state_dir
    state = Path(default_state_dir())
    state.mkdir(parents=True, exist_ok=True)
    return state


def capture(out: str, dom: bool, chrome, serve) -> int:
    from halo_harness.start import fresh
    state = fresh_home()
    placeholder(state)
    srv, url = serve(state)
    url = url.replace("mode=orchestra", "mode=roles")
    try:
        if dom:
            got = {}
            r = checked_dump(chrome, url, "start fresh")
            if r is None:
                print(json.dumps({"error": "no Chrome found"}))
                return 2
            got["fresh"] = counts(r.stdout)
            status = fresh.status(state.parent / "project", state)  # serve()'s project folder
            got["status"] = {k: status[k] for k in ("fresh", "show", "dismissed")}
            fresh.dismiss(state)
            got["dismissed"] = counts(checked_dump(chrome, url, "start dismissed").stdout)
            (fresh.start_root(state) / fresh.DISMISSED).unlink()
            from halo_harness.theme import set_config_value
            set_config_value("team", "halo-dev-cycle")
            got["lineup"] = counts(checked_dump(chrome, url, "start lineup").stdout)
            print(json.dumps(got))
            return 0
        target = Path(out).resolve()
        checked_dump(chrome, url, target.stem)  # the DOM first: no real path or name in the picture
        r = chrome(["--virtual-time-budget=12000", f"--screenshot={target}", "--window-size=1500,900", "--force-device-scale-factor=2", url])
        if r is None:
            print("no Chrome found: nothing rendered")
            return 2
        ok = target.is_file() and target.stat().st_size > 10_000
        print(f"{'wrote' if ok else 'FAILED'} {target} ({target.stat().st_size if target.is_file() else 0} bytes)")
        return 0 if ok else 1
    finally:
        srv.shutdown()
        srv.server_close()
        shutil.rmtree(state.parent, ignore_errors=True)
