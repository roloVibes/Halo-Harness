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
        reviewer) the Fleet map draws two harness boxes and five agents in three
        states; a click selects the researcher and the inspector shows its tail
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
        ctx.check(f"two harness boxes, five agents, got {got.get('boxes')} / {got.get('nodes')} {got.get('labels')}",
                  got.get("boxes") == 2 and got.get("nodes") == 5 and got.get("labels") == ["rolo@studio", "kali@lab"])
        ctx.check(f"three states (running, waiting, done), got {got.get('states')}", set(got.get("states") or []) == {"running", "waiting", "done"})
        ctx.check(f"the map, the agent panel and the rail, got {got.get('panels')}", got.get("panels") == [1, 1, 1])
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
        ctx.check(f"then it stops, in the session and on the map, got {got.get('stopped')} / {got.get('node_stopped')}",
                  got.get("stop_ack") == "stopping" and got.get("stopped") == "stopped" and got.get("node_stopped") == "stopped")
        ctx.check(f"a member's agent: its tail and a steer through the hub, got {got.get('member_steer')!r}",
                  got.get("member_steer") == "answer the second question first" and "Two questions" in str(got.get("member_tail")))
        ctx.check(f"D13: a spawn shows the new node and lights its edge, got {got.get('spawned')} / {got.get('spawn_tool')}",
                  (got.get("spawned") or 0) >= 1 and got.get("spawn_tool") == "Bash")


    @test
    def test_fleet_hop_keys_and_the_rail(ctx: Ctx):
        """3.0.5.0 R3: J hops from the selected live agent to the next live one
        (across harnesses), K back; the rail's tree (harness > session > agent)
        is GET /api/fleet's, in its order."""
        if not chrome():
            raise SkipTest("no Chrome found (the Fleet test needs headless Chrome)")
        r, got = json_of("-m", "tests.helpers.studio_fleet", "map")
        ctx.check(f"the run finished, got {r.stderr[-300:]!r}", r.returncode == 0)
        ctx.check(f"J moves to another agent, K comes back, got {got.get('after_j')} / {got.get('after_k')}",
                  bool(got.get("after_j")) and got.get("after_k") == "researcher")
        ctx.check(f"the rail tree is GET /api/fleet's, got {got.get('rail')} vs {got.get('api_tree')}",
                  got.get("rail") and got.get("rail") == got.get("api_tree") and len(got.get("rail")) == 9)


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
        """3.0.5.0 R3: tools/capture_studio.py --mode fleet --dom: the section
        (six tabs, the map, the agent panel, the rail, five nodes, two boxes;
        R4: People, Costs, Health, Attention and Activity too), its
        Start view (?view=start: the pair card and the settings, no map) and Live
        Roles (three glowing cards, the Live tab)."""
        if not chrome():
            raise SkipTest("no Chrome found (the capture needs headless Chrome)")
        r, got = json_of(str(REPO / "tools" / "capture_studio.py"), "--mode", "fleet", "--dom")
        ctx.check(f"the capture tool ran, got {r.stdout[-300:]!r} {r.stderr[-300:]!r}", r.returncode == 0)
        f, s, ro = got.get("fleet", {}), got.get("start", {}), got.get("roles", {})
        ctx.check(f"the section, got {f}", f.get("section-tab") == 8 and f.get("fleet-map") == 1 and f.get("fleet-agent") == 1
                  and f.get("fleet-rail") == 1 and f.get("fleet-node") == 5 and f.get("fleet-box") == 2 and f.get("fleet-start") == 0
                  and all(f.get(k) == 1 for k in ("fleet-people", "fleet-costs", "fleet-health", "fleet-attention", "fleet-activity",
                                                   "fleet-capabilities", "fleet-mission")))
        ctx.check(f"the Start view, got {s}", s.get("fleet-start") == 1 and s.get("fleet-pair") == 1 and s.get("fleet-settings") == 1
                  and s.get("fleet-map") == 0 and s.get("fleet-rail") == 1)
        ctx.check(f"Live Roles, got {ro}", ro.get("live-card") == 3 and ro.get("live-tab") == 1 and ro.get("section-tab") == 8)


    @test
    def test_fleet_attention_answers_an_approval_in_headless_chrome(ctx: Ctx):
        """3.0.5.0 R4: the seven Fleet panels show, each with its about line; the
        attention queue lists the member's question and approval cards and its
        count shows in the status bar and the rail; a click on the approval row
        and A answers it on the member through the hub, and the row leaves."""
        if not chrome():
            raise SkipTest("no Chrome found (the Fleet test needs headless Chrome)")
        r, got = json_of("-m", "tests.helpers.studio_fleet", "panels")
        ctx.check(f"the run finished, got {r.stdout[-300:]!r} {r.stderr[-600:]!r}", r.returncode == 0 and not got.get("errors"))
        ctx.check(f"nine panels (R6: Capabilities, R8: Mission), each with its about line, got {got.get('panels')} / {got.get('abouts')}",
                  got.get("panels") == [1] * 9 and got.get("abouts") == 9)
        ctx.check(f"the queue holds the member's two cards, got {got.get('attn_kinds')}", sorted(got.get("attn_kinds") or []) == ["approval", "question"])
        ctx.check(f"the count in the status bar and the rail, got {got.get('status_attn')!r} / {got.get('rail_attn')!r}",
                  "2 need you" in str(got.get("status_attn")) and "2 NEED YOU" in str(got.get("rail_attn")))
        ctx.check(f"A on the approval row answers it on the member, got {got.get('approval_sent')}",
                  got.get("approval_selected") == "selected" and got.get("approval_sent") == {"kind": "approval", "request_id": got.get("approval_id"), "action": "accept"}
                  and got.get("approval_gone") == "gone")


    @test
    def test_fleet_timeline_one_lane_per_live_agent(ctx: Ctx):
        """3.0.5.0 R4: Activity's timeline draws one lane per live agent (four:
        this harness's three and the member's waiting lead), each with its state
        bar; hovering a bar says who and since when; a click on a lane selects
        that agent (the Agent panel shows it)."""
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
        both edit shop/basket.py, the map draws the amber warning edge between
        them and a chip on both cards, the attention queue raises the row, and
        By project shows each card's git chips with the edge still drawn."""
        if not chrome():
            raise SkipTest("no Chrome found (the Fleet test needs headless Chrome)")
        r, got = json_of("-m", "tests.helpers.studio_fleet", "panels")
        ctx.check(f"the warning edge and the chips, got {got.get('conflict_edge')} / {got.get('conflict_chips')}",
                  got.get("conflict_edge") == "basket.py" and got.get("conflict_chips") == 2)
        ctx.check(f"the attention row names both, got {got.get('conflict_row')!r}",
                  str(got.get("conflict_row")).endswith("are both editing basket.py") and "reviewer" in str(got.get("conflict_row")))
        ctx.check(f"By project: git chips per card, the edge kept, got {got.get('git_chips')} / {got.get('edge_by_project')}",
                  got.get("git_chips") == 2 and got.get("edge_by_project") == 1)


    @test
    def test_fleet_digest_after_an_absence(ctx: Ctx):
        """3.0.5.0 R4: with halo.fleet.lastSeen two hours back, the tab regaining
        the focus shows "While you were away" in the rail with the totals per
        harness; Dismiss closes it and sets lastSeen to now."""
        if not chrome():
            raise SkipTest("no Chrome found (the Fleet test needs headless Chrome)")
        r, got = json_of("-m", "tests.helpers.studio_fleet", "panels")
        text = str(got.get("digest"))
        ctx.check(f"the card, its totals and both harnesses, got {text!r}",
                  text.startswith("WHILE YOU WERE AWAY") and "started" in text and "rolo@studio" in text and "kali@lab" in text and got.get("digest_where") == "rail")
        ctx.check(f"Dismiss closes it and updates lastSeen, got {got.get('digest_dismissed')}", got.get("digest_dismissed") == "dismissed")


    @test
    def test_fleet_replay_scrubs_on_the_roles_canvas(ctx: Ctx):
        """3.0.5.0 R4 (D12): the reviewer card's history row has "replay"; it
        opens the scrub bar on the Roles canvas for the finished past session;
        scrubbing lights the main card first, then the reviewer while it worked,
        and at the end the reviewer is done; live updates wait meanwhile, and
        closing the bar brings the live glow back."""
        if not chrome():
            raise SkipTest("no Chrome found (the Fleet test needs headless Chrome)")
        r, got = json_of("-m", "tests.helpers.studio_fleet", "panels")
        early, mid, end = got.get("early") or {}, got.get("mid") or {}, got.get("end") or {}
        ctx.check(f"the history row's replay opens the bar, got {got.get('history_replay')} / {got.get('bar')!r}",
                  (got.get("history_replay") or 0) >= 1 and got.get("bar") == "fix the basket rounding")
        ctx.check(f"early only the main agent works, got {early}", early.get("lit") == "main" and early.get("reviewer") == "none")
        ctx.check(f"midway the reviewer works too, got {mid}", mid.get("lit") == "main,reviewer" and mid.get("reviewer") == "typing")
        ctx.check(f"at the end the reviewer is done, got {end}", end.get("t") == "600" and end.get("reviewer") == "done")
        ctx.check(f"live waits during the replay, back after it, got {got.get('ignores_live')} / {got.get('closed')}",
                  got.get("ignores_live") is True and got.get("closed") == "live again")

    @test
    def test_fleet_record_take_over_and_message_in_headless_chrome(ctx: Ctx):
        """3.0.5.0 R4: Record on the agent panel makes the researcher's recording
        and Download fetches it with the token; Take over opens its brief
        dialog; People's Message reaches the member's owner as a note."""
        if not chrome():
            raise SkipTest("no Chrome found (the Fleet test needs headless Chrome)")
        r, got = json_of("-m", "tests.helpers.studio_fleet", "panels")
        ctx.check(f"the recording and its download, got {got.get('recording')!r} / {got.get('downloaded')!r}",
                  got.get("recording") == "Recording of researcher" and str(got.get("downloaded")).startswith("Saved ") and ".html" in str(got.get("downloaded")))
        ctx.check(f"Take over asks for the brief, got {got.get('takeover')!r}", got.get("takeover") == "Take over researcher")
        ctx.check(f"Message reaches the member as a note, got {got.get('note')!r}", got.get("note") == "lunch in ten")

    @test
    def test_fleet_capabilities_and_who_in_headless_chrome(ctx: Ctx):
        """3.0.6.0 R6: the Capabilities panel lists both harnesses with their MCP servers (the member's
        gridcraft opens to its two tools), the map's boxes carry their chips, "gridcraft" in Who can...
        ranks the member first and a click picks it (card, map box, its main agent); People's specs
        link focuses this harness's card; the hub asked the member for its catalog once."""
        if not chrome():
            raise SkipTest("no Chrome found (the Fleet test needs headless Chrome)")
        r, got = json_of("-m", "tests.helpers.studio_fleet", "caps")
        ctx.check(f"the run finished, got {r.stderr[-300:]!r}", r.returncode == 0)
        ctx.check(f"two spec cards with their servers, got {got.get('cards')} / {got.get('member_servers')} / {got.get('local_servers')}",
                  got.get("cards") == ["rolo@studio", "kali@lab"] and got.get("member_servers") == ["gridcraft"]
                  and "designcraft" in (got.get("local_servers") or []) and "What every harness can do" in str(got.get("about")))
        ctx.check(f"gridcraft opens to its tools, got {got.get('member_tools')!r}", got.get("member_tools") == "write_range,insert_chart")
        chips = got.get("box_chips") or {}
        ctx.check(f"capability chips on both boxes, got {chips}", chips.get("rolo@studio", [])[:2] == ["studio", "gpu"]
                  and chips.get("kali@lab", [])[:2] == ["linux", "data"])
        ctx.check(f"who gridcraft ranks the member first, got {got.get('who')} / {got.get('who_why')!r}",
                  (got.get("who") or [None])[0] == "kali@lab" and "gridcraft" in str(got.get("who_why")))
        ctx.check(f"a click picks it: card, box, its main agent, got {got.get('picked_card')} / {got.get('picked_box')} / {got.get('selected')}",
                  got.get("picked_card") == "focused" and got.get("picked_box") == "kali@lab" and str(got.get("selected")).endswith("|main")
                  and str(got.get("selected")).startswith("c0ffee"))
        ctx.check(f"the hub asked once; specs focuses this card, got {got.get('caps_asks')} / {got.get('specs_focus')}",
                  got.get("caps_asks") == 1 and got.get("specs_focus") == "focused")

    @test
    def test_readme_capture_exists(ctx: Ctx):
        for name in ("studio-roles.png", "studio-fleet.png", "studio-roles-live.png", "studio-fleet-panels.png",
                     "studio-fleet-capabilities.png", "studio-fleet-mission.png"):
            png = REPO / "docs" / "media" / name
            ctx.check(f"docs/media/{name} exists", png.is_file())
            if png.is_file():
                ctx.check(f"{name} is a PNG under 1 MB", png.read_bytes()[:8] == b"\x89PNG\r\n\x1a\n" and png.stat().st_size < 1024 * 1024)
