"""tools/capture_studio.py -- render docs/media/studio.png: Halo Studio over a
scratch home seeded with the shipped lineups, the halo-dev-cycle lineup
open, through headless Chrome (Halo 2.1.0 round B3). Also the smoke
`tests/test_studio_ui.py` runs: the page boots, draws nodes, no console
errors. Usage: python tools/capture_studio.py [--out PATH] [--dom] [--mode roles|org|design|shell|orchestra|flow|media|fleet]

3.0.3.0: roles/org/design --dom render the classic page at /legacy/ (what the
shell frames); since 3.0.4.0 docs round `--mode org|design` screenshots go
through the shell (Alt+3 / Alt+4, the page embedded); `--mode shell` renders the React shell at / (Orchestra and
Roles) and, with --dom, counts its data-testid values. R4: `--mode
orchestra` seeds a finished Orchestra run (the R2 fixture: basket.py, five
lanes, one judged conflict, the report) in a temp git repo, opens the shell's
Orchestra section over it (docs/media/studio-orchestra.png) and, with --dom,
counts the run console's data-testid values. 3.0.4.0 R6: `--mode flow` and
`--mode media` (tools/capture_flow.py) seed a finished flow run and one
waiting at its confirm gate over a FakeComfy and render the Flow section
(docs/media/studio-flow.png, studio-media.png); --dom counts its test ids.
R6b: `--mode orchestra` lives in tools/capture_orchestra.py and also
renders the Start view over a repo with no run (studio-orchestra-start.png)
and the Roles section with its groups (studio-roles.png). 3.0.5.0 R3:
`--mode fleet` (tools/capture_fleet.py) seeds two harnesses with five agents
(tests/helpers/studio_fleet_rig.py) and renders the Fleet section
(studio-fleet.png) and the Roles canvas glowing with its Live tab open
(studio-roles-live.png), R4 also the panels with a conflict on the map and
the digest in the rail (studio-fleet-panels.png), 3.0.6.0 R6 the Capabilities panel
with Who can... gridcraft (studio-fleet-capabilities.png), 3.0.6.0 R8 a planned mission
(studio-fleet-mission.png); --dom counts their test ids.
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


def serve(state: Path, shell: bool = False, proj: "Path | None" = None):
    from halo_harness.studio.server import start_server, url_for
    proj = proj or state.parent / "project"  # an empty project dir: nothing resolves to project scope
    proj.mkdir(exist_ok=True)
    srv = start_server(port=0, cwd=proj, state_dir=state)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    if shell:
        return srv, url_for(srv).replace("/#t=", "/?mode=orchestra&feed=off#t=")  # an open EventSource stalls --virtual-time-budget
    return srv, url_for(srv, legacy=True).replace("/index.html#t=", "/index.html?tour=off#t=")


def shell_counts(dom: str) -> dict:
    return {k: dom.count(f'data-testid="{k}"') for k in ("section-tab", "orchestra-root", "start-view", "legacy-frame")}


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
    parser.add_argument("--mode", choices=["roles", "org", "design", "shell", "orchestra", "flow", "media", "fleet"], default="roles", help="org: the halo-dev-cycle company over a fake Paperclip; design: a seeded Launch page project (tools/design_demo.py); both framed by the shell")
    args = parser.parse_args(argv)
    args.org = args.org or args.mode == "org"
    design = args.mode == "design"
    state = seeded_home()
    if args.mode in ("flow", "media"):  # the Flow section over seeded runs (tools/capture_flow.py)
        from capture_flow import capture
        from halo_harness.studio.server import url_for
        if args.out.endswith("studio.png"):
            args.out = args.out[:-4] + f"-{args.mode}.png"
        try:
            return capture(args.mode, args.out, args.dom, chrome, url_for)
        finally:
            shutil.rmtree(state.parent, ignore_errors=True)
    if args.mode == "fleet":  # two harnesses, five agents: the map, the agent panel, Live Roles (tools/capture_fleet.py)
        from capture_fleet import capture as capture_fleet
        if args.out.endswith("studio.png"):
            args.out = args.out[:-4] + "-fleet.png"
        try:
            return capture_fleet(args.out, args.dom, find_chrome)
        finally:
            shutil.rmtree(state.parent, ignore_errors=True)
    if args.mode == "orchestra":  # the run console, the Start view and Roles with its groups (tools/capture_orchestra.py)
        from capture_orchestra import capture as capture_orchestra
        if args.out.endswith("studio.png"):
            args.out = args.out[:-4] + "-orchestra.png"
        try:
            return capture_orchestra(args.out, args.dom, chrome, serve, state)
        finally:
            shutil.rmtree(state.parent, ignore_errors=True)
    fake = None
    if design:
        from design_demo import seed
        proj = seed(state)
        if args.out.endswith("studio.png"):
            args.out = args.out[:-4] + "-design.png"
    if args.org:
        from halo_harness.paperclip.client import Paperclip, save_config
        from halo_harness.paperclip.sync import sync_lineup
        from tests.helpers.fake_paperclip import FakePaperclip
        fake = FakePaperclip(company_name="Halo Harness")
        from halo_harness.theme import set_config_value
        set_config_value("paperclip.enabled", True)  # Org mode is off by default; the picture shows it on
        save_config({"base_url": fake.base_url, "company_id": fake.company["id"]}, state)
        sync_lineup(Paperclip(fake.base_url), fake.company["id"], "halo-dev-cycle", cwd=state.parent / "project", state_dir=state, out=open(os.devnull, "w"))
        if args.out.endswith("studio.png"):
            args.out = args.out[:-4] + "-org.png"
    shell = args.mode == "shell" or (args.mode in ("org", "design") and not args.dom)  # --dom counts the classic page itself
    if shell and args.out.endswith("studio.png"):
        args.out = args.out[:-4] + "-shell.png"
    srv, url = serve(state, shell)
    if shell and args.mode in ("org", "design"):  # the shell frames the page in embedded mode
        url = url.replace("mode=orchestra", f"mode={args.mode}").replace("feed=off", "feed=off&tour=off")
    elif args.org:
        url = url.replace("?tour=off", "?tour=off&mode=org")
    elif design:
        url = url.replace("?tour=off", "?tour=off&mode=design")
    try:
        if args.dom and shell:  # the shell twice: Orchestra (its Start view: no run here) and Roles (the framed classic page)
            a, b = chrome(["--dump-dom", url]), chrome(["--dump-dom", url.replace("mode=orchestra", "mode=roles")])
            if a is None or b is None:
                print("no Chrome found")
                return 2
            print(json.dumps({"orchestra": shell_counts(a.stdout), "roles": shell_counts(b.stdout),
                              "title": a.stdout.split("<title>")[1].split("</title>")[0] if "<title>" in a.stdout else ""}))
            return 0
        if args.dom:
            r = chrome(["--dump-dom", url])
            if r is None:
                print("no Chrome found")
                return 2
            print(json.dumps({"cards": r.stdout.count('class="d-card'), "frames": r.stdout.count("<iframe"), "pins": r.stdout.count('class="d-pin"'), "tabs": r.stdout.count("data-tab=") if design else 0,
                              "nodes": r.stdout.count('class="node'), "groups": r.stdout.count('data-testid="canvas-group"'), "title": r.stdout.split("<title>")[1].split("</title>")[0] if "<title>" in r.stdout else ""}))
            return 0
        out = Path(args.out).resolve()
        r = chrome(["--virtual-time-budget=20000", f"--screenshot={out}", "--window-size=1500,900", "--force-device-scale-factor=2", url])
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
