"""tools/capture_studio.py -- render docs/media/studio.png: Halo Studio over a
scratch home seeded with the shipped lineups, the halo-dev-cycle lineup
open, through headless Chrome (Halo 2.1.0 round B3). Also the smoke
`tests/test_studio_ui.py` runs: the page boots, draws nodes, no console
errors. Usage: python tools/capture_studio.py [--out PATH] [--dom] [--mode roles|org|design|design-knob]
"""

from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
import tempfile
import threading
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO))
sys.path.insert(0, str(REPO / "tools"))


def find_chrome() -> "str | None":
    from capture_screens import find_chrome as _find
    return _find(os.environ.get("HALO_CHROME", ""))


def seeded_home() -> Path:
    """A scratch ~/.halo with the shipped lineups copied in and
    halo-dev-cycle active, so the page opens on a real graph."""
    home = Path(tempfile.mkdtemp(prefix="halo-studio-capture-"))
    os.environ["BRIDGE_TEST_HOME"] = str(home)
    os.environ.pop("BRIDGE_STATE_DIR", None)
    from halo_harness.providers.config import default_state_dir
    from halo_harness.teams_yaml import ensure_builtin_team_templates
    from halo_harness.theme import set_config_value
    state = Path(default_state_dir())
    state.mkdir(parents=True, exist_ok=True)
    ensure_builtin_team_templates(state_dir=state)
    set_config_value("team", "halo-dev-cycle")
    set_config_value("roles.enabled", True)
    return state


def serve(state: Path):
    from halo_harness.studio.server import start_server, url_for
    proj = state.parent / "project"  # an empty project dir: nothing resolves to project scope
    proj.mkdir(exist_ok=True)
    srv = start_server(port=0, cwd=proj, state_dir=state)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    return srv, url_for(srv).replace("/#t=", "/?tour=off#t=")


def chrome(args: list, timeout: int = 90) -> "subprocess.CompletedProcess | None":
    exe = find_chrome()
    if not exe:
        return None
    profile = tempfile.mkdtemp(prefix="halo-chrome-")
    cmd = [exe, "--headless=new", "--disable-gpu", "--hide-scrollbars", f"--user-data-dir={profile}",
           "--virtual-time-budget=6000", *args]
    try:
        return subprocess.run(cmd, capture_output=True, encoding="utf-8", errors="replace", timeout=timeout)
    finally:
        shutil.rmtree(profile, ignore_errors=True)


def main(argv: list) -> int:
    parser = argparse.ArgumentParser(description="Render docs/media/studio.png through headless Chrome")
    parser.add_argument("--out", default=str(REPO / "docs" / "media" / "studio.png"))
    parser.add_argument("--dom", action="store_true", help="print the rendered DOM's node count instead of a PNG")
    parser.add_argument("--org", action="store_true", help="Org mode over a fake Paperclip seeded with the halo-dev-cycle company")
    parser.add_argument("--mode", choices=["roles", "org", "design", "design-knob"], default="roles", help="design: a seeded Launch page project (tools/design_demo.py), 1440x900; design-knob: the same with the Knobs tab open and Spacing moved to 48")
    args = parser.parse_args(argv)
    args.org = args.org or args.mode == "org"
    design = args.mode in ("design", "design-knob")
    state = seeded_home()
    fake = None
    if design:
        from design_demo import seed
        proj = seed(state)
        if args.mode == "design-knob":  # the Spacing knob moved to 48, exactly what the Knobs slider does
            from halo_harness.design import controls as C
            page = proj.artboard_dir("hero") / "index.html"
            html = page.read_text(encoding="utf-8")
            page.write_text(C.apply_css_control(html, "--space", C.css_value(html, "--space", 48, "px")), encoding="utf-8")
            proj.set_control("hero", "Spacing", 48)
            proj.snapshot(note="knob Spacing")
        if args.out.endswith("studio.png"):
            args.out = args.out[:-4] + "-design.png"
    if args.org:
        from halo_harness.paperclip.client import Paperclip, save_config
        from halo_harness.paperclip.sync import sync_lineup
        from tests.helpers.fake_paperclip import FakePaperclip
        fake = FakePaperclip(company_name="Halo Harness")
        save_config({"base_url": fake.base_url, "company_id": fake.company["id"]}, state)
        sync_lineup(Paperclip(fake.base_url), fake.company["id"], "halo-dev-cycle", cwd=state.parent / "project", state_dir=state, out=open(os.devnull, "w"))
        if args.out.endswith("studio.png"):
            args.out = args.out[:-4] + "-org.png"
    srv, url = serve(state)
    if args.org:
        url = url.replace("?tour=off", "?tour=off&mode=org")
    if design:
        url = url.replace("?tour=off", "?tour=off&mode=design" + ("&dtab=knobs" if args.mode == "design-knob" else ""))
    try:
        if args.dom:
            r = chrome(["--dump-dom", url])
            if r is None:
                print("no Chrome found")
                return 2
            print(json.dumps({"cards": r.stdout.count('class="d-card'), "frames": r.stdout.count("<iframe"), "pins": r.stdout.count('class="d-pin"'), "tabs": r.stdout.count("data-tab=") if design else 0,
                              "nodes": r.stdout.count('class="node'), "title": r.stdout.split("<title>")[1].split("</title>")[0] if "<title>" in r.stdout else ""}))
            return 0
        out = Path(args.out).resolve()
        r = chrome([f"--screenshot={out}", "--window-size=1440,900" if design else "--window-size=1500,900", "--force-device-scale-factor=2", url])
        if r is None:
            print("no Chrome found: nothing rendered")
            return 2
        ok = out.is_file() and out.stat().st_size > 10_000
        print(f"{'wrote' if ok else 'FAILED'} {out} ({out.stat().st_size if out.is_file() else 0} bytes)")
        return 0 if ok else 1
    finally:
        srv.shutdown()
        srv.server_close()
        if fake is not None:
            fake.close()
        shutil.rmtree(state.parent, ignore_errors=True)


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
