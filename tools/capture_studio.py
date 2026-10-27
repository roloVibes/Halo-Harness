"""tools/capture_studio.py -- render docs/media/studio.png: Halo Studio over a
scratch home seeded with the shipped lineups, the halo-dev-cycle lineup
open, through headless Chrome (Halo 2.1.0 round B3). Also the smoke
`tests/test_studio_ui.py` runs: the page boots, draws nodes, no console
errors. Usage: python tools/capture_studio.py [--out PATH] [--dom] [--mode roles|design|shell|orchestra|fleet|team|start|packs|setup]

3.0.7.0 R2: `--mode roles` (the default; tools/capture_roles.py) renders the
React Roles section: a seeded lineup with two tiers and a live card
(docs/media/studio-roles.png), with --dom its Start view and the seeded
lineup with a bio open, counted by data-testid; 3.0.7.0 R3: `--mode design` (tools/capture_design.py) renders
the React Design section over a seeded design
project (docs/media/studio-design.png; with --dom the Start
view and the section, counted by data-testid); `--mode shell` renders the React shell at / (Orchestra and
Roles) and, with --dom, counts its data-testid values. R4: `--mode
orchestra` seeds a finished Orchestra run (the R2 fixture: basket.py, five
lanes, one judged conflict, the report) in a temp git repo, opens the shell's
Orchestra section over it (docs/media/studio-orchestra.png) and, with --dom,
counts the run console's data-testid values.
R6b: `--mode orchestra` lives in tools/capture_orchestra.py and also
renders the Start view over a repo with no run (studio-orchestra-start.png). 3.0.5.0 R3:
`--mode fleet` (tools/capture_fleet.py) seeds two harnesses with five agents
(tests/helpers/studio_fleet_rig.py) and renders the Fleet section
(studio-fleet.png; 3.1.5.0 R3: the Roles canvas glowing, studio-roles-live.png, and the Session
dashboard are tools/capture_session_anim.py's, with their GIFs), R4 also the panels with a conflict on the map and
the digest in the rail (studio-fleet-panels.png), 3.0.6.0 R6 the Capabilities panel
with Who can... gridcraft (studio-fleet-capabilities.png), 3.0.6.0 R8 a planned mission
(studio-fleet-mission.png); --dom counts their test ids. 3.0.8.0 R2: `--mode team`
(tools/capture_team.py) seeds team_rig's team mid-run and renders the Team section
(studio-team.png); --dom counts its Start view and the seeded board. 3.2.0.0 R7: `--mode packs`
(tools/capture_packs.py) installs and enables the shipped doc-review pack and renders the Pack Manager
(studio-packs.png, the modes banner's seventh tile); --dom counts it. 3.3.0.0 R4: `--mode setup`
(tools/capture_setup.py) renders Setup as `halo init` opens it, a provider set from a placeholder env file
(studio-setup.png, the banner's eighth tile and the README's first screenshot after install); --dom counts it.
3.3.3.0 R2: `--mode settings` (tools/capture_settings.py) renders Settings on its Fleet page (studio-settings.png, the
banner's ninth tile); --dom counts it.
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
    """3.1.0.0 R1: the driver base's (tests/helpers/chrome_driver.py): HALO_CHROME first."""
    from tests.helpers.chrome_driver import find_chrome as _find
    return _find()


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


def serve(state: Path, shell: bool = True, proj: "Path | None" = None, slow_ms: "int | None" = None):
    """Studio over `state`; the URL opens the shell on Orchestra with the feed off (`shell` is kept for the callers).
    `slow_ms` (3.3.0.0 R7): every API answer that many ms late; None passes `HALO_STUDIO_SLOW_MS` through."""
    from halo_harness.studio.server import start_server, url_for
    proj = proj or state.parent / "project"  # an empty project dir: nothing resolves to project scope
    proj.mkdir(exist_ok=True)
    srv = start_server(port=0, cwd=proj, state_dir=state, slow_ms=slow_ms)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    return srv, url_for(srv).replace("/#t=", "/?mode=orchestra&feed=off#t=")  # an open EventSource stalls --virtual-time-budget


def shell_counts(dom: str) -> dict:
    return {k: dom.count(f'data-testid="{k}"') for k in ("section-tab", "orchestra-root", "start-view", "roles-canvas", "roles-start", "legacy-frame")}


def chrome(args: list, timeout: int = 90) -> "subprocess.CompletedProcess | None":
    """One `--dump-dom` / `--screenshot` run under the one-Chrome-at-a-time lock (chrome_driver.one_shot)."""
    from tests.helpers.chrome_driver import one_shot
    return one_shot(args, timeout=timeout)


def main(argv: list) -> int:
    parser = argparse.ArgumentParser(description="Render docs/media/studio.png through headless Chrome")
    parser.add_argument("--out", default=str(REPO / "docs" / "media" / "studio.png"))
    parser.add_argument("--dom", action="store_true", help="print the rendered DOM's node count instead of a PNG")
    parser.add_argument("--mode", choices=["roles", "design", "shell", "orchestra", "fleet", "team", "start", "packs", "setup", "settings"], default="roles", help="design: a seeded Launch page project (tools/design_demo.py), the React section (tools/capture_design.py)")
    args = parser.parse_args(argv)
    from capture_identity import begin
    from tests.helpers.chrome_driver import scope_home
    begin()  # 3.1.7.0 R2: the neutral temp root and you@studio before the scratch home is made
    made = scope_home()  # first thing (3.1.0.0 R1): nothing below reads the real home; seeded_home re-scopes it
    try:
        return _render(args)
    finally:
        if made is not None:
            shutil.rmtree(made, ignore_errors=True)


def _render(args) -> int:
    if args.mode == "start":  # 3.1.1.0 R1: a fresh home's "Start here" overlay (tools/capture_start.py)
        from capture_start import capture as capture_start
        if args.out.endswith("studio.png"):
            args.out = args.out[:-4] + "-start.png"
        return capture_start(args.out, args.dom, chrome, serve)
    from capture_identity import placeholder
    state = seeded_home()
    placeholder(state)  # 3.1.7.0 R2: every capture draws you@studio (exit 2 when the name would be this machine's)
    if args.mode == "fleet":  # two harnesses, five agents: the map, the agent panel, Live Roles (tools/capture_fleet.py)
        from capture_fleet import capture as capture_fleet
        if args.out.endswith("studio.png"):
            args.out = args.out[:-4] + "-fleet.png"
        try:
            return capture_fleet(args.out, args.dom, find_chrome)
        finally:
            shutil.rmtree(state.parent, ignore_errors=True)
    if args.mode == "team":  # 3.0.8.0 R2: the Team section over team_rig's team (tools/capture_team.py)
        from capture_team import capture as capture_team
        if args.out.endswith("studio.png"):
            args.out = args.out[:-4] + "-team.png"
        try:
            return capture_team(args.out, args.dom, find_chrome)
        finally:
            shutil.rmtree(state.parent, ignore_errors=True)
    if args.mode == "packs":  # 3.2.0.0 R7: the Pack Manager over the shipped pack (tools/capture_packs.py)
        from capture_packs import capture as capture_packs
        if args.out.endswith("studio.png"):
            args.out = args.out[:-4] + "-packs.png"
        try:
            return capture_packs(args.out, args.dom, serve, state)
        finally:
            shutil.rmtree(state.parent, ignore_errors=True)
    if args.mode == "setup":  # 3.3.0.0 R4: Setup as halo init opens it (tools/capture_setup.py)
        from capture_setup import capture as capture_setup
        if args.out.endswith("studio.png"):
            args.out = args.out[:-4] + "-setup.png"
        try:
            return capture_setup(args.out, args.dom, serve, state)
        finally:
            shutil.rmtree(state.parent, ignore_errors=True)
    if args.mode == "settings":  # 3.3.3.0 R2: Settings on its Fleet page (tools/capture_settings.py)
        from capture_settings import capture as capture_settings
        if args.out.endswith("studio.png"):
            args.out = args.out[:-4] + "-settings.png"
        try:
            return capture_settings(args.out, args.dom, serve, state)
        finally:
            shutil.rmtree(state.parent, ignore_errors=True)
    if args.mode == "design":  # 3.0.7.0 R3: the React section over a seeded project (tools/capture_design.py)
        from capture_design import capture as capture_design
        if args.out.endswith("studio.png"):
            args.out = args.out[:-4] + "-design.png"
        try:
            return capture_design(args.out, args.dom, chrome, serve, state)
        finally:
            shutil.rmtree(state.parent, ignore_errors=True)
    if args.mode == "roles":  # 3.0.7.0 R2: the React Roles section (tools/capture_roles.py)
        from capture_roles import capture as capture_roles
        if args.out.endswith("studio.png"):
            args.out = args.out[:-4] + "-roles.png"
        try:
            return capture_roles(args.out, args.dom, serve, state)
        finally:
            shutil.rmtree(state.parent, ignore_errors=True)
    if args.mode == "orchestra":  # the run console and its Start view (tools/capture_orchestra.py)
        from capture_orchestra import capture as capture_orchestra
        if args.out.endswith("studio.png"):
            args.out = args.out[:-4] + "-orchestra.png"
        try:
            return capture_orchestra(args.out, args.dom, chrome, serve, state)
        finally:
            shutil.rmtree(state.parent, ignore_errors=True)
    if args.out.endswith("studio.png"):  # --mode shell
        args.out = args.out[:-4] + "-shell.png"
    srv, url = serve(state)
    try:
        if args.dom:  # the shell twice: Orchestra (its Start view: no run here) and Roles (the canvas of the active lineup)
            from capture_identity import checked_dump
            a, b = checked_dump(chrome, url, "shell orchestra"), checked_dump(chrome, url.replace("mode=orchestra", "mode=roles"), "shell roles")
            if a is None or b is None:
                print("no Chrome found")
                return 2
            print(json.dumps({"orchestra": shell_counts(a.stdout), "roles": shell_counts(b.stdout),
                              "title": a.stdout.split("<title>")[1].split("</title>")[0] if "<title>" in a.stdout else ""}))
            return 0
        out = Path(args.out).resolve()
        from capture_identity import checked_dump
        checked_dump(chrome, url, "shell")  # the DOM first: no real path or name in the picture
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
        shutil.rmtree(state.parent, ignore_errors=True)


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
