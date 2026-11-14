"""tests.helpers.studio_ui_live -- the live checks of tests/test_studio_ui.py (Halo 3.0.5.0), kept here so that file
stays small: R3's Agents -> Live, hop keys and Live Roles (tests/helpers/studio_live.py `map` / `roles`) and R4's
panels (`panels`: the timeline's lanes, record and take over, the canvas replay), and the README captures
(studio-roles, studio-roles-live). tests/test_studio_ui.py calls `register` with its own registry, its cached runner
and its Chrome finder, so the tests run there, in that order."""
from __future__ import annotations

from pathlib import Path

from tests.helpers.runner import Ctx, SkipTest

REPO = Path(__file__).resolve().parents[2]


def register(test, json_of, chrome) -> None:
    @test
    def test_live_select_steer_stop_in_headless_chrome(ctx: Ctx):
        """3.0.5.0 R3: over this harness's real session (a lead, an implementer and a researcher mid-work) Agents -> Live
        draws the three agents at work (3.5.0.0: all running here; the waiting lead was a member's); a click selects the researcher and the inspector shows its tail
        (its text and its tool row); a steer typed in the Steer box is echoed as "you" and reaches the researcher's
        next model call, not the implementer's; Stop asks first (the agent still runs) and then stops it."""
        if not chrome():
            raise SkipTest("no Chrome found (the live test needs headless Chrome)")
        r, got = json_of("-m", "tests.helpers.studio_live", "map")
        ctx.check(f"the run finished, got {r.stdout[-300:]!r} {r.stderr[-600:]!r}", r.returncode == 0)
        ctx.check(f"three agents, got {got.get('nodes')}", got.get("nodes") == 3)
        ctx.check(f"all three running, got {got.get('states')}", set(got.get("states") or []) == {"running"})
        ctx.check(f"Live's tree, the agent inspector and the inspector panel, got {got.get('panels')}", got.get("panels") == [1, 1, 1])
        ctx.check(f"click selects; the inspector shows the tail and the tool row, got {got.get('tail_text')!r} / {got.get('tool_label')!r}",
                  got.get("selected") == "researcher" and "pricing notes" in str(got.get("tail_text")) and got.get("tool_rows") == 1
                  and str(got.get("tool_label")).startswith("Bash: git grep"))
        ctx.check(f"the steer is echoed as you and acknowledged, got {got.get('echo')!r}",
                  str(got.get("echo")).startswith("you") and "focus on the discount rules" in str(got.get("echo")) and got.get("steer_ack") == "steered"
                  and got.get("steer_cleared") is True)
        ctx.check("the steer reached the researcher's next model call and not the implementer's",
                  got.get("steer_reached_b") is True and got.get("steer_not_a") is True)
        ctx.check(f"Stop asks first, the agent still running, got {got.get('asked')!r} / {got.get('state_while_asked')}",
                  got.get("asked") == "Stop implementer?" and got.get("state_while_asked") == "running")
        ctx.check(f"then it stops, in the session and on the map, got {got.get('stopped')} / {got.get('node_stopped')} diag={got.get('node_stopped_diag')!r}",
                  got.get("stop_ack") == "stopping" and got.get("stopped") == "stopped" and got.get("node_stopped") == "stopped")

    @test
    def test_live_hop_keys_and_the_tree(ctx: Ctx):
        """3.0.5.0 R3: J hops from the selected live agent to the next live one, K back; Live's tree is GET /api/live's,
        in its order."""
        if not chrome():
            raise SkipTest("no Chrome found (the live test needs headless Chrome)")
        r, got = json_of("-m", "tests.helpers.studio_live", "map")
        ctx.check(f"the run finished, got {r.stderr[-300:]!r}", r.returncode == 0)
        ctx.check(f"J moves to another agent, K comes back, got {got.get('after_j')} / {got.get('after_k')}",
                  bool(got.get("after_j")) and got.get("after_k") == "researcher")
        ctx.check(f"Live's tree is GET /api/live's, got {got.get('rail')} vs {got.get('api_tree')}",
                  got.get("rail") and got.get("rail") == got.get("api_tree") and set(got.get("api_live") or []) <= set(got["rail"]) and len(got["rail"]) >= 3)

    @test
    def test_live_roles_glow_and_live_tab_in_headless_chrome(ctx: Ctx):
        """3.0.5.0 R3 (E): the Roles canvas glows on the cards whose agents work (implementer and researcher typing, the
        main card on its tool); a click opens the Live tab by itself, streaming the agent's text and its tool rows; J hops to
        the next working card with its stream; Space pins its mini stream over the shell, Esc unpins."""
        if not chrome():
            raise SkipTest("no Chrome found (the Live Roles test needs headless Chrome)")
        r, got = json_of("-m", "tests.helpers.studio_live", "roles")
        ctx.check(f"the run finished, got {r.stdout[-300:]!r} {r.stderr[-600:]!r}", r.returncode == 0)
        ctx.check(f"the working cards glow, got {got.get('live_cards')}",
                  set(got.get("live_cards") or []) == {"orchestrator=tool", "implementer=typing", "researcher=typing"})
        ctx.check(f"the Live tab opens by itself and streams text, got {got.get('clicked')} / {got.get('live_text')!r}",
                  got.get("live_tab") == "on" and "Reading the basket" in str(got.get("live_text")))
        ctx.check(f"and its tool rows, got {got.get('live_tool')!r}", got.get("live_tools") == 1 and str(got.get("live_tool")).startswith("Bash: git log"))
        ctx.check(f"J hops to the researcher's card and stream, got {got.get('hop_card')} / {got.get('hop_tools')!r}",
                  got.get("hop_card") == "researcher" and got.get("hop") != got.get("watched") and str(got.get("hop_tools")).startswith("Bash: git grep"))
        ctx.check(f"Space pins the mini stream, Esc unpins it, got {got.get('pinned')!r} / {got.get('unpinned')}",
                  got.get("pinned") == "researcher" and got.get("unpinned") is True)

    @test
    def test_live_timeline_one_lane_per_live_agent(ctx: Ctx):
        """3.0.5.0 R4: Activity's timeline (Live's optional panel) draws one lane per live agent (this harness's three),
        each with its state bar; hovering a bar says who and since when; a click on a lane selects that agent."""
        if not chrome():
            raise SkipTest("no Chrome found (the live test needs headless Chrome)")
        r, got = json_of("-m", "tests.helpers.studio_live", "panels")
        ctx.check(f"the run finished, got {r.stdout[-300:]!r} {r.stderr[-600:]!r}", r.returncode == 0 and not got.get("errors"))
        ctx.check(f"one lane per live agent, got {got.get('lanes')} lanes for {got.get('live_nodes')} live nodes",
                  got.get("lanes") == got.get("live_nodes") == 3 and (got.get("segs") or 0) >= 3)
        ctx.check(f"hover says who and since when, got {got.get('tip')!r}", str(got.get("tip")).startswith("researcher · running since"))
        ctx.check(f"a click on a lane selects that agent, got {got.get('lane_selects')}", got.get("lane_selects") == "researcher")

    @test
    def test_live_replay_scrubs_on_the_roles_canvas(ctx: Ctx):
        """3.0.5.0 R4 (D12); 3.4.1.0 R1 "Time": the reviewer card's history row has "replay"; it opens the finished
        past session on Agents -> Live with the scrubber under the canvas (the one replay control); scrubbing draws
        the main agent alone first, then the reviewer while it worked, and at the end the reviewer is done; the live
        session is not drawn meanwhile, and Now brings it back."""
        if not chrome():
            raise SkipTest("no Chrome found (the live test needs headless Chrome)")
        r, got = json_of("-m", "tests.helpers.studio_live", "panels")
        early, mid, end = got.get("early") or {}, got.get("mid") or {}, got.get("end") or {}
        ctx.check(f"the history row's replay opens the bar, got {got.get('history_replay')} / {got.get('bar')!r}",
                  (got.get("history_replay") or 0) >= 1 and got.get("bar") == "fix the basket rounding")
        ctx.check(f"early only the main agent works, got {early}", early.get("lit") == "main" and early.get("reviewer") == "none")
        ctx.check(f"midway the reviewer works too, got {mid}", mid.get("lit") == "main,reviewer" and mid.get("reviewer") == "running")
        ctx.check(f"at the end the reviewer is done, got {end}", end.get("t") == "600" and end.get("reviewer") == "done")
        ctx.check(f"live waits during the replay, back after it, got {got.get('ignores_live')} / {got.get('closed')}",
                  got.get("ignores_live") is True and got.get("closed") == "live again")

    @test
    def test_live_record_and_take_over_in_headless_chrome(ctx: Ctx):
        """3.0.5.0 R4: Record on the agent panel makes the researcher's recording and Download fetches it with the token;
        Take over opens its brief dialog."""
        if not chrome():
            raise SkipTest("no Chrome found (the live test needs headless Chrome)")
        r, got = json_of("-m", "tests.helpers.studio_live", "panels")
        ctx.check(f"the recording and its download, got {got.get('recording')!r} / {got.get('downloaded')!r}",
                  got.get("recording") == "Recording of researcher" and str(got.get("downloaded")).startswith("Saved ") and ".html" in str(got.get("downloaded")))
        ctx.check(f"Take over asks for the brief, got {got.get('takeover')!r}", got.get("takeover") == "Take over researcher")

    @test
    def test_readme_capture_exists(ctx: Ctx):
        for name in ("studio-roles.png", "studio-roles-live.png"):
            png = REPO / "docs" / "media" / name
            ctx.check(f"docs/media/{name} exists", png.is_file())
            if png.is_file():
                ctx.check(f"{name} is a PNG under 1 MB", png.read_bytes()[:8] == b"\x89PNG\r\n\x1a\n" and png.stat().st_size < 1024 * 1024)
