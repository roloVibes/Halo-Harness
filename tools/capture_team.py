"""tools/capture_team.py -- the Team captures for tools/capture_studio.py
--mode team (Halo 3.0.8.0 round R2), through headless Chrome over the
DevTools protocol (tests/helpers/cdp.py), over tests/helpers/studio_team_rig.py
(no model call: team_rig's fakes drive every stage).

    docs/media/studio-team.png   the rig's team mid-run: `draft` done (accepted), `review` held at its
                                 gate (the gate card open in the Inspector), `notes` with a holder
                                 writing (its badge amber), the change feed under the board

With --dom the section is read twice -- the Start view first (Studio over a
folder with no team file), then the seeded team's board -- and the
data-testid values are counted (the last stdout line is the JSON:
{"start": {...}, "team": {...}}). Never two Chromes at once.
"""
from __future__ import annotations

import json
import threading
import time
from pathlib import Path

IDS = ("section-tab", "team-start", "team-start-init", "team-board", "team-inspector", "team-feed", "team-member", "team-stage",
       "team-block", "team-edge", "team-runbar", "panel-about", "team-gate-card", "team-event", "status-team", "legacy-frame")
STAGES = "document.querySelectorAll('[data-testid=\"team-stage\"]').length"


def counts(c) -> dict:
    out = c.js("Object.fromEntries(" + json.dumps(list(IDS)) + ".map((k) => [k, document.querySelectorAll(`[data-testid=\"${k}\"]`).length]))")
    out["edge_kinds"] = c.js("[...document.querySelectorAll('[data-testid=\"team-edge\"]')].map((e) => e.dataset.kind).sort()")
    return out


def mid_run(rig) -> None:
    """draft done, review gated, notes held by a hand edit (no runner left live)."""
    from halo_harness.team.run import TeamRunner, open_run
    from halo_harness.team.stages import write_answer
    team = rig.team()
    run_dir = open_run(team, cwd=rig.root, state_dir=rig.state)
    runner = TeamRunner(team, run_dir, cwd=rig.root, **rig.fakes.seams())
    runner.request("draft", "Studio")
    runner.loop(until="gate", poll_s=0.05)
    write_answer(run_dir, "draft", "accept")
    runner.loop(until="gate", poll_s=0.05)
    rig.touch("notes", "NOTES.md", "# Notes\n\nlaunch on Tuesday, not Monday\n")


def dom(c) -> dict:
    from halo_harness.studio.server import start_server, url_for
    from tests.helpers.studio_team_rig import StudioTeamRig
    with StudioTeamRig(live=False) as rig:
        empty = rig.home / "empty"
        empty.mkdir()
        bare = start_server(port=0, cwd=empty, state_dir=rig.state)
        threading.Thread(target=bare.serve_forever, daemon=True).start()
        try:
            c.go(url_for(bare, "team").replace("#t=", "&tour=off#t="))
            c.wait("!!document.querySelector('[data-testid=\"team-start\"]')", 30)
            start = counts(c)
            c.go("about:blank")  # the page's live feed closes before its server does
            time.sleep(0.3)
        finally:
            bare.shutdown()
            bare.server_close()
        c.go(rig.url("team"))
        c.wait(f"{STAGES} === 4 && document.querySelectorAll('[data-testid=\"team-edge\"]').length > 0", 30)
        time.sleep(0.4)
        return {"start": start, "team": counts(c)}


def shoot(c, png: Path) -> int:
    from tests.helpers.studio_team_rig import TEAM_UI, StudioTeamRig
    text = TEAM_UI.replace('writes: [copy],\n       trigger: "stage_done:draft"}', 'writes: [copy],\n       trigger: "stage_done:draft", gate: required}')
    with StudioTeamRig(text, live=False) as rig:
        mid_run(rig)
        c.go(rig.url("team"))
        c.wait(f"{STAGES} === 4 && document.querySelector('[data-testid=\"team-stage\"][data-stage=\"review\"]')?.dataset.state === 'gated'", 30)
        c.wait("document.querySelector('[data-testid=\"team-block\"][data-block=\"notes\"]')?.dataset.claim === 'writing'", 15)
        c.click_on("document.querySelector('[data-testid=\"team-stage\"][data-stage=\"review\"] .tm-stage-shape')")
        c.wait("!!document.querySelector('[data-testid=\"team-gate-card\"][data-stage=\"review\"]')", 15)
        c.wait("document.querySelectorAll('[data-testid=\"team-event\"]').length > 5", 15)
        c.wait("!document.querySelector('.toast')", 10)
        time.sleep(1.2)
        return c.shot(png, width=1440, height=900)


def capture(out: str, as_dom: bool, find_chrome) -> int:
    from tests.helpers.cdp import Chrome
    exe = find_chrome()
    if not exe:
        print("no Chrome found")
        return 2
    c = Chrome(exe, width=1440, height=900)
    try:
        if as_dom:
            print(json.dumps(dom(c)))
            return 0
        png = Path(out).resolve()
        size = shoot(c, png)
        ok = size > 10_000
        print(f"{'wrote' if ok else 'FAILED'} {png} ({size} bytes)")
        return 0 if ok else 1
    finally:
        c.close()
