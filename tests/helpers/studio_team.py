"""tests.helpers.studio_team -- the Studio Team tab (Halo 3.0.8.0 round R2) in
headless Chrome over the DevTools protocol (tests/helpers/cdp.py), over
tests/helpers/studio_team_rig.py (team_rig's team in Studio's own folder, the
runner's seams = the fakes; no model call). tests/test_studio_ui.py runs it
as a subprocess with a scrubbed environment (tests/helpers/studio_ui_team.py):

    python -m tests.helpers.studio_team

* the seeded team draws its board: three member columns, four stage boxes,
  three block nodes, eight edges;
* Run on `draft` (its Inspector face): the box turns running (the writer's
  spawn is held after its write, so `copy` holds a part, amber), then gated,
  and the gate card opens;
* the Fleet Attention queue lists a `team_gate` row; `o` opens the Team
  section on `draft` with its gate card;
* Accept: `review` runs (held again), the `stage_done:draft` edge lights, a
  change line of `review` lands in the feed; released, `post` waits at its gate;
* a hand edit of NOTES.md through the guard: the `notes` badge goes amber, a
  change line lands in the feed, and `build` (block_change:notes) fires after
  its 5 s settle window;
* Stop (a reason on the card) ends the run: stopped, `post` skipped.

The last stdout line is a JSON object of what it saw (exit 2: no Chrome)."""
from __future__ import annotations

import sys
import threading
import time
from contextlib import contextmanager
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO))
sys.path.insert(0, str(REPO / "tools"))

from tests.helpers.chrome_driver import Driver  # noqa: E402

STAGE = "document.querySelector('[data-testid=\"team-stage\"][data-stage=\"{}\"]')"
BLOCK = "document.querySelector('[data-testid=\"team-block\"][data-block=\"{}\"]')"
TID = "document.querySelector('[data-testid=\"{}\"]')"
ROW = "document.querySelector('[data-testid=\"fleet-attn-row\"][data-kind=\"team_gate\"]')"
N = "document.querySelectorAll('[data-testid=\"{}\"]').length"


def state(c, sid: str, want: str, timeout: float = 20):
    return c.wait(f"{STAGE.format(sid)}?.dataset.state === '{want}' && '{want}'", timeout)


def click(c, expr: str) -> None:
    c.js(f"({expr}).scrollIntoView({{block: 'center', inline: 'center'}}); 1")
    time.sleep(0.15)
    c.click_on(expr)


def event_line(c, kind: str, needle: str, timeout: float = 20):
    return c.wait(f"[...document.querySelectorAll('[data-testid=\"team-event\"][data-kind=\"{kind}\"]')].map((e) => e.textContent)"
                  f".find((t) => t.includes('{needle}'))", timeout)


def board_and_gate(c, rig, out: dict) -> None:
    c.go(rig.url("team"))
    c.wait(f"{N.format('team-stage')} === 4 && {N.format('team-edge')} > 0", 30)
    out["board"] = {k: c.js(N.format(k)) for k in ("team-member", "team-stage", "team-block", "team-edge")}
    out["edge_kinds"] = c.js("[...document.querySelectorAll('[data-testid=\"team-edge\"]')].map((e) => e.dataset.kind).sort()")
    click(c, f"{STAGE.format('draft')}.querySelector('.tm-stage-shape')")
    c.wait("document.querySelector('[data-testid=\"team-stage-face\"]')?.dataset.stage === 'draft'", 10)
    click(c, TID.format("team-run-stage"))
    out["draft_running"] = state(c, "draft", "running")
    out["copy_writing"] = c.wait(f"{BLOCK.format('copy')}?.dataset.claim === 'writing' && 'writing'", 15)
    out["agent_chip"] = c.wait("document.querySelector('[data-testid=\"team-member\"][data-member=\"writer\"] [data-testid=\"team-agent-chip\"]')?.dataset.stage", 10)
    rig.fakes.hold[("writer", "draft")].set()
    out["draft_gated"] = state(c, "draft", "gated")
    out["gate_card"] = c.wait("document.querySelector('[data-testid=\"team-gate-card\"]')?.dataset.stage", 15)
    out["status_team"] = c.wait(f"{TID.format('status-team')}?.textContent.includes('at a gate') && {TID.format('status-team')}.textContent", 15)


def attention(c, rig, out: dict) -> None:
    c.go(rig.url("fleet", "&view=workspace"))
    out["attn_row"] = c.wait(f"{ROW}?.querySelector('.fat-what')?.textContent", 30)
    click(c, f"{ROW}.querySelector('.fat-what')")
    c.key("o")
    out["attn_open"] = c.wait("document.querySelector('[data-testid=\"team-stage-face\"]')?.dataset.stage === 'draft' && "
                              "!!document.querySelector('[data-testid=\"team-gate-card\"]') && 'draft'", 20)
    out["attn_section"] = c.js("document.querySelector('[data-testid=\"section-tab\"][aria-selected=\"true\"]')?.textContent || ''")


def accept_and_review(c, rig, out: dict) -> None:
    click(c, TID.format("team-accept"))
    out["review_running"] = state(c, "review", "running")
    out["edge_lit"] = c.wait("document.querySelector('[data-testid=\"team-edge\"][data-kind=\"done\"][data-from=\"draft\"]')?.dataset.lit === 'true' && 'lit'", 15)
    out["review_change"] = event_line(c, "change", "writer@review")
    rig.fakes.hold[("writer", "review")].set()
    out["review_done"] = state(c, "review", "done")
    out["post_gated"] = state(c, "post", "gated")


def block_change(c, rig, out: dict) -> None:
    out["touch"] = rig.touch("notes", "NOTES.md", "# Notes\n\nlaunch on Tuesday\n")
    out["notes_amber"] = c.wait(f"{BLOCK.format('notes')}?.dataset.claim === 'writing' && "
                                f"{BLOCK.format('notes')}.querySelector('[data-testid=\"team-block-badge\"]').dataset.claim", 15)
    out["notes_change"] = event_line(c, "change", "NOTES.md")
    t0 = time.time()
    out["build_fired"] = c.wait(f"['running', 'done'].includes({STAGE.format('build')}?.dataset.state) && {STAGE.format('build')}.dataset.state", 30)
    out["build_after_s"] = round(time.time() - t0, 1)
    out["build_trigger"] = event_line(c, "trigger", "build")
    rig.release("notes")
    out["notes_released"] = c.wait(f"{BLOCK.format('notes')}?.dataset.claim === 'free' && 'free'", 15)


def stop(c, rig, out: dict) -> None:
    click(c, TID.format("team-stop"))
    c.wait(f"!!{TID.format('team-stop-dialog')}", 10)
    click(c, TID.format("team-stop-reason"))
    c.type_text("enough for today")
    click(c, TID.format("team-stop-confirm"))
    out["stopped"] = c.wait(f"{TID.format('team-run-state')}?.dataset.state === 'stopped' && 'stopped'", 20)
    out["post_after"] = state(c, "post", "skipped")
    _, board = rig.api("GET", "team/board")
    out["stop_reason"] = board.get("board", {}).get("stop_reason")


class TeamDriver(Driver):
    """The Team tab over tests/helpers/studio_team_rig.py (the rig scopes its own home)."""

    @contextmanager
    def session(self, c):
        from tests.helpers.studio_team_rig import StudioTeamRig
        with StudioTeamRig() as rig:
            rig.fakes.hold = {("writer", "draft"): threading.Event(), ("writer", "review"): threading.Event()}
            yield tuple((step, (c, rig, self.out)) for step in (board_and_gate, attention, accept_and_review, block_change, stop))


def main() -> int:
    return TeamDriver().main()


if __name__ == "__main__":
    sys.exit(main())
