"""tools/capture_studio.py -- render docs/media/studio.png: Halo Studio over a
scratch home seeded with the shipped lineups, the halo-dev-cycle lineup
open, through headless Chrome (Halo 2.1.0 round B3). Also the smoke
`tests/test_studio_ui.py` runs: the page boots, draws nodes, no console
errors. Usage: python tools/capture_studio.py [--out PATH] [--dom] [--mode roles|agents|shell|orchestra|fleet|start|packs|setup|settings|local] [--panel ollama]

3.0.7.0 R2: `--mode roles` (the default; tools/capture_roles.py) renders the
React Roles section: a seeded lineup with two tiers and a live card
(docs/media/studio-roles.png), with --dom its Start view and the seeded
lineup with a bio open, counted by data-testid; 3.0.7.0 R3's `--mode design` is the design pack's
(halo_harness/templates/packs/design/tests/capture_design.py, 3.3.13.0 R2); `--mode shell` renders the React shell at / (Orchestra and
Roles) and, with --dom, counts its data-testid values. R4: `--mode
orchestra` seeds a finished Orchestra run (the R2 fixture: basket.py, five
lanes, one judged conflict, the report) in a temp git repo, opens the shell's
Orchestra section over it (docs/media/studio-orchestra.png) and, with --dom,
counts the run console's data-testid values.
R6b: `--mode orchestra` lives in tools/capture_orchestra.py and also
renders the Start view over a repo with no run (studio-orchestra-start.png). 3.0.5.0 R3:
`--mode fleet` (tools/capture_fleet.py) seeds two harnesses with five agents
(tests/helpers/studio_fleet_rig.py); 3.3.16.0 R2 (the Fleet fold) renders Agents -> Live on the fleet with a
conflict edge and the glance (studio-fleet.png), Setup -> Machines (studio-fleet-panels.png), a machine's Specs page
with Who can... gridcraft (studio-fleet-capabilities.png) and a planned mission on Live (studio-fleet-mission.png);
--dom counts their test ids (3.1.5.0 R3: studio-roles-live.png and the Session dashboard are
tools/capture_session_anim.py's, with their GIFs). 3.3.16.0 R1: `--mode team` (the Team section) went with
Team's board; `--mode roles` renders Agents on Cast and `--mode agents` the same page as studio-agents.png, the modes
banner's Agents tile; `--mode orchestra` renders Agents on Runs. 3.2.0.0 R7: `--mode packs`
(tools/capture_packs.py) installs and enables the shipped doc-review pack and renders the Pack Manager
(studio-packs.png, the modes banner's seventh tile); --dom counts it. 3.3.0.0 R4: `--mode setup`
(tools/capture_setup.py) renders Setup as `halo init` opens it, a provider set from a placeholder env file
(studio-setup.png, the banner's eighth tile and the README's first screenshot after install); --dom counts it.
3.3.3.0 R2: `--mode settings` (tools/capture_settings.py) renders Settings on its Fleet page (studio-settings.png, the
banner's ninth tile); --dom counts it. (3.3.4.0 R5's `--mode fleet --panel ollama` went with the Fleet section's
Ollama panel in 3.3.16.0 R2: Local's capture draws the hosts.) 3.3.5.0 R1:
`--mode local` (tools/capture_local.py) renders Local on its Resources page (studio-local.png, the banner's tenth
tile); --dom counts it.
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
    parser.add_argument("--mode", choices=["roles", "agents", "shell", "orchestra", "fleet", "packs", "setup", "settings", "local", "workflows", "picker"], default="roles", help="the section to render (the design pack's section: its tests/capture_design.py)")
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
    from capture_identity import placeholder
    state = seeded_home()
    placeholder(state)  # 3.1.7.0 R2: every capture draws you@studio (exit 2 when the name would be this machine's)
    if args.mode == "fleet":  # two harnesses, five agents: Live on the fleet, Setup -> Machines, specs, a mission (tools/capture_fleet.py)
        from capture_fleet import capture as capture_fleet
        if args.out.endswith("studio.png"):
            args.out = args.out[:-4] + "-fleet.png"
        try:
            return capture_fleet(args.out, args.dom, find_chrome)
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
    if args.mode == "local":  # 3.3.5.0 R1: Local on its Resources page (tools/capture_local.py)
        from capture_local import capture as capture_local
        if args.out.endswith("studio.png"):
            args.out = args.out[:-4] + "-local.png"
        try:
            return capture_local(args.out, args.dom, serve, state)
        finally:
            shutil.rmtree(state.parent, ignore_errors=True)
    if args.mode == "workflows":  # 3.3.16.1: Agents -> Workflows with three squares and the library (tools/capture_workflows.py)
        from capture_workflows import capture as capture_workflows
        if args.out.endswith("studio.png"):
            args.out = args.out[:-4] + "-workflows.png"
        try:
            return capture_workflows(args.out, args.dom, serve, state)
        finally:
            shutil.rmtree(state.parent, ignore_errors=True)
    if args.mode == "picker":  # 3.3.17.1: the model picker open on a role (tools/capture_picker.py)
        from capture_picker import capture as capture_picker
        if args.out.endswith("studio.png"):
            args.out = args.out[:-4] + "-model-picker.png"
        try:
            return capture_picker(args.out, args.dom, serve, state)
        finally:
            shutil.rmtree(state.parent, ignore_errors=True)
    if args.mode in ("roles", "agents"):  # 3.0.7.0 R2: the React Roles section (tools/capture_roles.py); 3.3.16.0 R1: Agents, Cast
        from capture_roles import capture as capture_roles
        if args.out.endswith("studio.png"):
            args.out = args.out[:-4] + f"-{args.mode}.png"
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
            budget = "--virtual-time-budget=20000"  # the Roles canvas needs the lineup fetched: 6 s is short on the Windows runner
            roles_url = url.replace("mode=orchestra", "mode=roles")
            a, b = checked_dump(chrome, url, "shell orchestra", budget), checked_dump(chrome, roles_url, "shell roles", budget)
            if b is not None and shell_counts(b.stdout).get("roles-canvas") == 0:  # the lineup fetch outran 20 s once on the Windows runner (e0957871): one more try, twice the budget
                b = checked_dump(chrome, roles_url, "shell roles", "--virtual-time-budget=40000")
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
