"""tests.helpers.studio_ui_fleet -- the Fleet checks of tests/test_studio_ui.py
(Halo 3.0.5.0), kept here so that file stays small: R3's map, hop keys,
Live Roles and capture counts (tests/helpers/studio_fleet.py `map` / `roles`,
tools/capture_studio.py --mode fleet --dom) and R4's panels (`panels`:
the attention queue answering an approval, the timeline's lanes, the
conflict edge, the digest after an absence, the canvas replay), and the
README captures (studio-roles, studio-fleet, studio-roles-live, studio-fleet-panels).
tests/test_studio_ui.py calls `register` with its own registry, its cached
runner and its Chrome finder, so the tests run there, in that order."""
from __future__ import annotations

from pathlib import Path

from tests.helpers.runner import Ctx, SkipTest

REPO = Path(__file__).resolve().parents[2]


def register(test, json_of, chrome) -> None:
    @test
    def test_fleet_map_select_steer_stop_in_headless_chrome(ctx: Ctx):
        """3.0.5.0 R3: over this harness's real session (a lead, an implementer
        and a researcher mid-work) and a member harness (a waiting lead, a done
        reviewer) Agents -> Live on the fleet (3.3.16.0 R2: the Fleet map went) draws two machine boxes and the four
        agents at work in two states (3.3.18.0: the reviewer finished before the page loaded: History's, not drawn); a click selects the researcher and the inspector shows its tail
        (its text and its tool row); a steer typed in the Steer box is echoed as
        "you" and reaches the researcher's next model call, not the implementer's;
        Stop asks first (the agent still runs) and then stops it; a steer to the
        member's agent goes through the hub to that member; when the member's
        lead spawns a verifier, its node appears live with its tool icon and the
        edge from its parent lights (D13)."""
        if not chrome():
            raise SkipTest("no Chrome found (the Fleet test needs headless Chrome)")
        r, got = json_of("-m", "tests.helpers.studio_fleet", "map")
        ctx.check(f"the run finished, got {r.stdout[-300:]!r} {r.stderr[-600:]!r}", r.returncode == 0)
        ctx.check(f"two harness boxes, four agents, got {got.get('boxes')} / {got.get('nodes')} {got.get('labels')}",
                  got.get("boxes") == 2 and got.get("nodes") == 4 and got.get("labels") == ["you@studio", "kali@lab"])
        ctx.check(f"two states (running, waiting), got {got.get('states')}", set(got.get("states") or []) == {"running", "waiting"})
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
        ctx.check(f"a member's agent: its tail and a steer through the hub, got {got.get('member_steer')!r}",
                  got.get("member_steer") == "answer the second question first" and "Two questions" in str(got.get("member_tail")))
        ctx.check(f"D13: a spawn shows the new node and lights its edge, got {got.get('spawned')} / {got.get('spawn_tool')}",
                  (got.get("spawned") or 0) >= 1 and got.get("spawn_tool") == "Bash")


    @test
    def test_fleet_hop_keys_and_the_rail(ctx: Ctx):
        """3.0.5.0 R3: J hops from the selected live agent to the next live one
        (across harnesses), K back; the tree (harness > session > agent; 3.3.16.0 R2: Live's fleet scope, the
        Tree panel went) is GET /api/fleet's, in its order."""
        if not chrome():
            raise SkipTest("no Chrome found (the Fleet test needs headless Chrome)")
        r, got = json_of("-m", "tests.helpers.studio_fleet", "map")
        ctx.check(f"the run finished, got {r.stderr[-300:]!r}", r.returncode == 0)
        ctx.check(f"J moves to another agent, K comes back, got {got.get('after_j')} / {got.get('after_k')}",
                  bool(got.get("after_j")) and got.get("after_k") == "researcher")
        ctx.check(f"Live's tree is GET /api/fleet's, got {got.get('rail')} vs {got.get('api_tree')}",
                  got.get("rail") and got.get("rail") == got.get("api_tree") and set(got.get("api_live") or []) <= set(got["rail"]) and len(got["rail"]) >= 5)


    @test
    def test_live_roles_glow_and_live_tab_in_headless_chrome(ctx: Ctx):
        """3.0.5.0 R3 (E): the Roles canvas glows on the cards whose agents work
        (implementer and researcher typing, the main card waiting with x2: this
        harness's lead and the member's); a click opens the Live tab by itself,
        streaming the agent's text and its tool rows; J hops to the next working
        card with its stream; Space pins its mini stream over the shell, Esc
        unpins."""
        if not chrome():
            raise SkipTest("no Chrome found (the Live Roles test needs headless Chrome)")
        r, got = json_of("-m", "tests.helpers.studio_fleet", "roles")
        ctx.check(f"the run finished, got {r.stdout[-300:]!r} {r.stderr[-600:]!r}", r.returncode == 0)
        ctx.check(f"the working cards glow, got {got.get('live_cards')}",
                  set(got.get("live_cards") or []) == {"orchestrator=waiting", "implementer=typing", "researcher=typing"})
        ctx.check(f"the main card counts both leads, got {got.get('main_badge')!r}", "\u00d72" in str(got.get("main_badge")))
        ctx.check(f"the Live tab opens by itself and streams text, got {got.get('clicked')} / {got.get('live_text')!r}",
                  got.get("live_tab") == "on" and "Reading the basket" in str(got.get("live_text")))
        ctx.check(f"and its tool rows, got {got.get('live_tool')!r}", got.get("live_tools") == 1 and str(got.get("live_tool")).startswith("Bash: git log"))
        ctx.check(f"J hops to the researcher's card and stream, got {got.get('hop_card')} / {got.get('hop_tools')!r}",
                  got.get("hop_card") == "researcher" and got.get("hop") != got.get("watched") and str(got.get("hop_tools")).startswith("Bash: git grep"))
        ctx.check(f"Space pins the mini stream, Esc unpins it, got {got.get('pinned')!r} / {got.get('unpinned')}",
                  got.get("pinned") == "researcher" and got.get("unpinned") is True)


    @test
    def test_fleet_capture_dom_counts(ctx: Ctx):
        """3.0.5.0 R3: tools/capture_studio.py --mode fleet --dom (3.3.16.0 R2: the pieces' new homes): Agents -> Live on
        the fleet (six section icons, the canvas with two machines, four agents at work, the inspector's glance with a row per
        machine, the Attention chip, Activity; no FLEET cell), Setup -> Machines (the pair card, the settings, the People
        table with both machines, no canvas; no lead: it is drawn only while this harness is alone) and Live Roles on Cast (three glowing cards, the Live tab)."""
        if not chrome():
            raise SkipTest("no Chrome found (the capture needs headless Chrome)")
        r, got = json_of(str(REPO / "tools" / "capture_studio.py"), "--mode", "fleet", "--dom")
        ctx.check(f"the capture tool ran, got {r.stdout[-300:]!r} {r.stderr[-300:]!r}", r.returncode == 0)
        f, s, ro = got.get("live", {}), got.get("machines", {}), got.get("roles", {})
        ctx.check(f"Live on the fleet, got {f}", f.get("section-tab") == 6 and f.get("roles-live-map") == 1 and f.get("live-machine") == 2
                  and f.get("fleet-box") == 2 and f.get("roles-live-node") == 4 and f.get("live-inspector") == 1 and f.get("live-glance") == 1
                  and f.get("live-glance-machine") == 2 and f.get("agents-attention") == 1 and f.get("fleet-activity") == 1 and f.get("status-fleet") == 0)
        ctx.check(f"Setup -> Machines, got {s}", s.get("setup-machines") == 1 and s.get("fleet-pair") == 1 and s.get("fleet-settings") == 1
                  and s.get("fleet-people-list") == 1 and s.get("fleet-person") == 2 and s.get("roles-live-map") == 0)
        ctx.check(f"Live Roles, got {ro}", ro.get("live-card") == 3 and ro.get("live-tab") == 1 and ro.get("section-tab") == 6)


    @test
    def test_fleet_attention_answers_an_approval_in_headless_chrome(ctx: Ctx):
        """3.0.5.0 R4 (3.3.16.0 R2: the Fleet panels' homes): ?mode=fleet shows Live, Agents' Attention chip and the
        inspector strip, the queue closed on load; the chip opens it (Attention), it lists the member's question and
        approval cards, the chip counts them (amber) and so does the glance; a click on the approval row and A answer it
        on the member through the hub, and the row leaves."""
        if not chrome():
            raise SkipTest("no Chrome found (the Fleet test needs headless Chrome)")
        r, got = json_of("-m", "tests.helpers.studio_fleet", "panels")
        ctx.check(f"the run finished, got {r.stdout[-300:]!r} {r.stderr[-600:]!r}", r.returncode == 0 and not got.get("errors"))
        ctx.check(f"Live, the chip and the inspector, the queue closed on load and opened by the chip, got {got.get('panels')} / {got.get('abouts')}",
                  got.get("panels") == [1] * 3 and got.get("closed_on_load") is True and got.get("abouts") == "Attention")
        ctx.check(f"the queue holds the member's two cards, got {got.get('attn_kinds')}", sorted(got.get("attn_kinds") or []) == ["approval", "question"])
        ctx.check(f"the count on the chip (amber) and on the glance, got {got.get('status_attn')!r} / {got.get('rail_attn')!r}",
                  got.get("status_attn") == ["Attention · 2", "warn"] and str(got.get("rail_attn")).startswith("2 decisions"))
        ctx.check(f"A on the approval row answers it on the member, got {got.get('approval_sent')}",
                  got.get("approval_selected") == "selected" and got.get("approval_sent") == {"kind": "approval", "request_id": got.get("approval_id"), "action": "accept"}
                  and got.get("approval_gone") == "gone")


    @test
    def test_fleet_timeline_one_lane_per_live_agent(ctx: Ctx):
        """3.0.5.0 R4: Activity's timeline (3.3.16.0 R2: Live's optional panel) draws one lane per live agent (four:
        this harness's three and the member's waiting lead), each with its state
        bar; hovering a bar says who and since when; a click on a lane selects
        that agent (the inspector shows it)."""
        if not chrome():
            raise SkipTest("no Chrome found (the Fleet test needs headless Chrome)")
        r, got = json_of("-m", "tests.helpers.studio_fleet", "panels")
        ctx.check(f"one lane per live agent, got {got.get('lanes')} lanes for {got.get('live_nodes')} live nodes",
                  got.get("lanes") == got.get("live_nodes") == 4 and (got.get("segs") or 0) >= 4)
        ctx.check(f"hover says who and since when, got {got.get('tip')!r}", str(got.get("tip")).startswith("researcher · running since"))
        ctx.check(f"a click on a lane selects that agent, got {got.get('lane_selects')}", got.get("lane_selects") == "researcher")


    @test
    def test_fleet_conflict_edge_on_the_map(ctx: Ctx):
        """3.0.5.0 R4: when this harness's implementer and the member's reviewer
        both edit shop/basket.py, Live draws the amber warning edge between
        them and a chip on both session nodes, the attention queue raises the row, and
        each session node shows its git chips (3.3.16.0 R2: By project went with the map)."""
        if not chrome():
            raise SkipTest("no Chrome found (the Fleet test needs headless Chrome)")
        r, got = json_of("-m", "tests.helpers.studio_fleet", "panels")
        ctx.check(f"the warning edge and the chips, got {got.get('conflict_edge')} / {got.get('conflict_chips')}",
                  got.get("conflict_edge") == "basket.py" and got.get("conflict_chips") == 2)
        ctx.check(f"the attention row names both, got {got.get('conflict_row')!r}",
                  str(got.get("conflict_row")).endswith("are both editing basket.py") and "reviewer" in str(got.get("conflict_row")))
        ctx.check(f"git chips per session node, the edge kept, got {got.get('git_chips')} / {got.get('edge_by_project')}",
                  got.get("git_chips") == 2 and got.get("edge_by_project") == 1)


    @test
    def test_fleet_digest_after_an_absence(ctx: Ctx):
        """3.0.5.0 R4: with halo.fleet.lastSeen two hours back, the tab regaining
        the focus puts a dot on the rail's Agents icon (3.3.16.0 R2); a click on it opens Live on the fleet
        with "While you were away" at the top of the inspector's glance; Dismiss closes it, sets lastSeen to now and the dot goes."""
        if not chrome():
            raise SkipTest("no Chrome found (the Fleet test needs headless Chrome)")
        r, got = json_of("-m", "tests.helpers.studio_fleet", "panels")
        text = str(got.get("digest"))
        ctx.check(f"the card, its totals and both harnesses, got {text!r}",
                  text.startswith("WHILE YOU WERE AWAY") and "started" in text and "you@studio" in text and "kali@lab" in text and got.get("digest_where") == "live")
        ctx.check(f"the Agents icon's dot; Dismiss closes it, updates lastSeen, the dot goes, got {got.get('digest_dot')} {got.get('digest_dismissed')} {got.get('digest_dot_gone')}", got.get("digest_dot") is True and got.get("digest_dismissed") == "dismissed" and got.get("digest_dot_gone") is True)


    @test
    def test_fleet_replay_scrubs_on_the_roles_canvas(ctx: Ctx):
        """3.0.5.0 R4 (D12); 3.4.1.0 R1 "Time": the reviewer card's history row has "replay"; it opens the finished
        past session on Agents -> Live with the scrubber under the canvas (the one replay control); scrubbing draws
        the main agent alone first, then the reviewer while it worked, and at the end the reviewer is done; the live
        session is not drawn meanwhile, and Now brings it back."""
        if not chrome():
            raise SkipTest("no Chrome found (the Fleet test needs headless Chrome)")
        r, got = json_of("-m", "tests.helpers.studio_fleet", "panels")
        early, mid, end = got.get("early") or {}, got.get("mid") or {}, got.get("end") or {}
        ctx.check(f"the history row's replay opens the bar, got {got.get('history_replay')} / {got.get('bar')!r}",
                  (got.get("history_replay") or 0) >= 1 and got.get("bar") == "fix the basket rounding")
        ctx.check(f"early only the main agent works, got {early}", early.get("lit") == "main" and early.get("reviewer") == "none")
        ctx.check(f"midway the reviewer works too, got {mid}", mid.get("lit") == "main,reviewer" and mid.get("reviewer") == "running")
        ctx.check(f"at the end the reviewer is done, got {end}", end.get("t") == "600" and end.get("reviewer") == "done")
        ctx.check(f"live waits during the replay, back after it, got {got.get('ignores_live')} / {got.get('closed')}",
                  got.get("ignores_live") is True and got.get("closed") == "live again")

    @test
    def test_fleet_record_take_over_and_message_in_headless_chrome(ctx: Ctx):
        """3.0.5.0 R4: Record on the agent panel makes the researcher's recording
        and Download fetches it with the token; Take over opens its brief
        dialog; the member machine's summary's Message (People's row) reaches the member's owner as a note."""
        if not chrome():
            raise SkipTest("no Chrome found (the Fleet test needs headless Chrome)")
        r, got = json_of("-m", "tests.helpers.studio_fleet", "panels")
        ctx.check(f"the recording and its download, got {got.get('recording')!r} / {got.get('downloaded')!r}",
                  got.get("recording") == "Recording of researcher" and str(got.get("downloaded")).startswith("Saved ") and ".html" in str(got.get("downloaded")))
        ctx.check(f"Take over asks for the brief, got {got.get('takeover')!r}", got.get("takeover") == "Take over researcher")
        ctx.check(f"Message reaches the member as a note, got {got.get('note')!r}", got.get("note") == "lunch in ten")

    @test
    def test_fleet_capabilities_and_who_in_headless_chrome(ctx: Ctx):
        """3.0.6.0 R6 (3.3.16.0 R2: a machine's summary's Specs page on Live): both machines' spec cards with
        their MCP servers (the member's gridcraft opens to its two tools), the machine nodes carry their chips,
        "gridcraft" in Who can... ranks the member first and a click picks it (its card focused, its box lit, its
        summary); People's specs link focuses this harness's card; the hub asked the member for its catalog once."""
        if not chrome():
            raise SkipTest("no Chrome found (the Fleet test needs headless Chrome)")
        r, got = json_of("-m", "tests.helpers.studio_fleet", "caps")
        ctx.check(f"the run finished, got {r.stderr[-300:]!r}", r.returncode == 0)
        ctx.check(f"two spec cards with their servers, got {got.get('cards')} / {got.get('member_servers')} / {got.get('local_servers')}",
                  got.get("cards") == ["you@studio", "kali@lab"] and got.get("member_servers") == ["gridcraft"]
                  and "designcraft" in (got.get("local_servers") or []) and got.get("about") == "Specs and who can...")
        ctx.check(f"gridcraft opens to its tools, got {got.get('member_tools')!r}", got.get("member_tools") == "write_range,insert_chart")
        chips = got.get("box_chips") or {}
        ctx.check(f"capability chips on both machine nodes, got {chips}", chips.get("you@studio", [])[:2] == ["studio", "gpu"]
                  and chips.get("kali@lab", [])[:2] == ["linux", "data"])
        ctx.check(f"who gridcraft ranks the member first, got {got.get('who')} / {got.get('who_why')!r}",
                  (got.get("who") or [None])[0] == "kali@lab" and "gridcraft" in str(got.get("who_why")))
        ctx.check(f"a click picks it: card, box, its summary, got {got.get('picked_card')} / {got.get('picked_box')} / {got.get('selected')}",
                  got.get("picked_card") == "focused" and got.get("picked_box") == "kali@lab" and str(got.get("selected")).startswith("c0ffee"))
        ctx.check(f"the hub asked once; specs focuses this card, got {got.get('caps_asks')} / {got.get('specs_focus')}",
                  got.get("caps_asks") == 1 and got.get("specs_focus") == "focused")
        row = next((h for h in got.get("recall_hits") or [] if h[0] == "finding"), [None, "", ""])
        ctx.check(f"3.1.8.0 R4: the recall box shows the finding with its chip, id, by and day, got {got.get('recall_hits')}",
                  row[1] == "basket total rounds half up with decimal"
                  and row[2] == f"{got.get('recall_id')} · by gate · {got.get('recall_when')} · checked")

    @test
    def test_readme_capture_exists(ctx: Ctx):
        for name in ("studio-roles.png", "studio-fleet.png", "studio-roles-live.png", "studio-fleet-panels.png",
                     "studio-fleet-capabilities.png", "studio-fleet-mission.png"):
            png = REPO / "docs" / "media" / name
            ctx.check(f"docs/media/{name} exists", png.is_file())
            if png.is_file():
                ctx.check(f"{name} is a PNG under 1 MB", png.read_bytes()[:8] == b"\x89PNG\r\n\x1a\n" and png.stat().st_size < 1024 * 1024)
