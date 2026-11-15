"""tests.test_main_model_check -- Halo 3.3.5.0 R0b (d): the main model picked
cannot orchestrate here -- one plain line and the coder-lane offer
(`agent/main_model_check.py`, `agent/model_card_switch.py`), through the
loop rig (tests/helpers/model_switch_rig.py: a fake Ollama on 127.0.0.1:0)
with one more model, `coder:30b` (tools declared, the probe got no call):

1. `/model` to it: the card's `how` lines come before the switch line, the
   main-model line after it, with the offer (`local-coder`: roles.coder on
   it, main on the best local orchestrator);
2. accept -> roles.coder on the model (a plain session: 3.6.0.0 R5c), the
   session's role table updated, and a NEW session's coder child runs on the
   model, routed by "fix", at depth 2; go ahead -> nothing written;
3. a model that can orchestrate -> no line;
4. a sub-agent on the coder lane gets the flattened text protocol (no tool
   catalog on its wire, tool turns as text);
5. `halo config set model` prints the line and the command (writes
   nothing); Studio's `POST models/lane` points roles.coder and sets `model`;
6. the TUI's one-key card: y / Enter accepts, any other key goes ahead.
Never a real server, never a model call, a fake home per rig.
Run: python -m tests.test_main_model_check
"""
from __future__ import annotations

import contextlib
import io
import os
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

os.environ.setdefault("BRIDGE_TEST_HOME", tempfile.mkdtemp(prefix="m1-mmc-"))
os.environ.setdefault("BRIDGE_TEST_NO_BACKGROUND_NET", "1")

from tests.helpers import model_switch_rig as R  # noqa: E402
from tests.helpers.runner import Ctx, new_registry, print_results, run_all  # noqa: E402

test, TESTS = new_registry()
CODER = "ol:coder:30b@lan"
LINE = ("coder:30b is a coding model with no tool calling on this server: it can write and answer but cannot act; "
        "as the main agent it would not run tools")


@contextlib.contextmanager
def _rig():
    R.MODELS["coder:30b"] = (65536, ["completion", "tools"])
    try:
        with R.Rig() as rig:
            from halo_harness.providers.ollama_capability import save_capability_cache
            digest = f"sha256:m0{list(R.MODELS).index('coder:30b')}"
            save_capability_cache(rig.state_dir, {digest: {"tool_calls": False, "checked_at": 0.0, "model": "coder:30b",
                                                           "host": "lan"}})
            yield rig
    finally:
        R.MODELS.pop("coder:30b", None)


def _switch(rig, session, raw):
    from halo_harness import events
    ref, profile, creds = rig.resolve(raw)
    return rig.run(session, [events.Command("set_model", {"model_ref": ref, "model_profile": profile, "creds": creds})])


def _config(key):
    from halo_harness.theme import get_config_value
    return get_config_value(key, default=None)


@test
def test_the_line_and_the_offer_after_model(ctx: Ctx):
    with _rig() as rig:
        s = rig.session("ol:big:30b@lan")
        evs = _switch(rig, s, CODER)
        order = [e.data.get("state") for e in evs if e.kind == "turn_marker"]
        card = R.markers(evs, "card")
        check = [e for e in evs if e.kind == "turn_marker" and e.data.get("state") == "model-check"]
    ctx.check(f"the card, the switch's two lines, then the check, got {order}",
              order[:4] == ["card", "switch", "switch", "model-check"])
    ctx.check(f"the card's how lines, got {card}", card and card[0].startswith(f"{CODER}, a coding model -- how Halo calls it:")
              and "no tools: answers only" in card[0] and "dialect: native" in card[0])
    data = check[0].data if check else {}
    ctx.check(f"the one plain line, got {data.get('line')!r}", data.get("line") == LINE)
    offer = data.get("offer") or {}
    ctx.check(f"the offer: local-coder, the coder on it, main on the best local orchestrator, got {offer}",
              offer.get("lineup") == "local-coder" and offer.get("coder") == CODER and offer.get("orchestrator") == "ol:big:30b"
              and f"halo roles point coder {CODER}" in offer.get("command", ""))
    ctx.check(f"the line ends with the offer in words, got {data.get('text')!r}",
              data.get("text", "").endswith("Keep it as the coder lane under ol:big:30b (roles.coder), or go ahead anyway."))


@test
def test_accept_points_the_coder_and_a_new_session_runs_on_it(ctx: Ctx):
    """3.6.0.0 R5c: the offer keeps a plain session and points roles.coder at the model (R5b wrote a map whose lines
    were main-decides only, depth 1): a new session hands "fix ..." to its coder card, the child runs on the model,
    and the depth is the plain session's 2 -- what 3.5's lane lineup did."""
    from halo_harness.agent.main_model_check import accept
    from tests.test_crew_compile import _child
    with _rig() as rig:
        s = rig.session("ol:big:30b@lan")
        evs = _switch(rig, s, CODER)
        offer = next(e.data["offer"] for e in evs if e.kind == "turn_marker" and e.data.get("state") == "model-check")
        ctx.check("going ahead writes nothing: no role, no map",
                  _config("roles.coder") is None and _config("crew.map") is None)
        ok, lines = accept(offer, session=s, state_dir=rig.state_dir)
        live = dict(getattr(s.agent_runtime, "role_table", {}) or {})
        role, in_use = _config("roles.coder"), _config("crew.map")
        from halo_harness import headless  # a new session, as `halo -p` builds one
        fresh = headless.build_session(cwd=rig.fh["proj"], model_ref_raw="ol:big:30b@lan", print_mode=True,
                                       cli_flags={}).session
        rt = fresh.agent_runtime
        word, card = fresh.team_control.route_call({"prompt": "fix the failing parser test"}, "fix the parser")
        child = _child(fresh, rt.agents["coder"], card, "fix the failing parser test")
        depth = rt.max_depth
        fresh.close_runtimes()
    ctx.check(f"accepted: one line naming the role and main, got {lines[:1]}", ok
              and lines[0] == f"roles.coder = {CODER}: new sessions hand code work to it, ol:big:30b runs main")
    ctx.check(f"roles.coder on the model, no map put in use, got {role} {in_use}", role == CODER and in_use is None)
    ctx.check(f"the session's role table follows, got {live.get('coder')}", live.get("coder") == CODER)
    ctx.check(f"a new session routes 'fix' to its coder card, got {word} {card}", (word, card) == ("fix", "coder"))
    ctx.check(f"and that child runs on the model, got {child['model']}", child["model"] == CODER)
    ctx.check(f"at the plain session's depth, got {depth}", depth == 2)


@test
def test_accept_takes_a_map_out_of_use_and_says_how_to_bring_it_back(ctx: Ctx):
    """3.6.0.0 R5c: as applying 3.5's lane lineup replaced the lineup in force, accepting takes a map you put in use
    out of use (roles.coder reaches a plain session only), and the line names the command that brings it back."""
    from halo_harness.agent.main_model_check import accept
    from halo_harness.theme import set_config_value
    with _rig() as rig:
        set_config_value("crew.map", "mine")
        ok, lines = accept({"lineup": "local-coder", "coder": CODER, "orchestrator": "ol:big:30b"}, state_dir=rig.state_dir)
        in_use = _config("crew.map")
    ctx.check(f"the map out of use, one line with the way back, got {in_use} {lines}", ok and not in_use
              and "map mine is no longer in use (halo maps use mine brings it back)" in lines)


@test
def test_accept_names_what_it_replaced_and_the_roles_it_switches_back_on(ctx: Ctx):
    """3.6.0.0 R5c (the judge's S-c): over a roles.coder you set and roles you parked (roles off), the same answer says
    "(was <old coder>)" and names each parked role that runs again; a role no session reads is not named."""
    from halo_harness.agent.main_model_check import accept
    from halo_harness.theme import set_config_value
    with _rig() as rig:
        set_config_value("roles.coder", "ol:old-coder:7b@lan")
        set_config_value("roles.planner", "ol:plan:14b@lan")
        set_config_value("roles.verify", "ol:qwen3.5:9b@lan")
        set_config_value("roles.enabled", False)
        ok, lines = accept({"lineup": "local-coder", "coder": CODER, "orchestrator": "ol:big:30b"}, state_dir=rig.state_dir)
    ctx.check(f"the coder line says what it replaced, got {lines[:1]}", ok and lines[0] ==
              f"roles.coder = {CODER} (was ol:old-coder:7b@lan): new sessions hand code work to it, ol:big:30b runs main")
    ctx.check(f"the roles-on line names the parked roles that run again, got {lines[1:]}",
              "roles are on again (they were off: one model for everything); your roles run again: "
              "planner on ol:plan:14b@lan" in lines and not any("verify" in x for x in lines))


@test
def test_a_model_that_can_orchestrate_gets_no_line(ctx: Ctx):
    with _rig() as rig:
        s = rig.session("ol:big:30b@lan")
        evs = _switch(rig, s, "ol:mid:14b@lan")
    ctx.check("no model-check line", not [e for e in evs if e.kind == "turn_marker" and e.data.get("state") == "model-check"])
    ctx.check("the card's how lines still come first", R.markers(evs, "card"))


@test
def test_a_sub_agent_on_the_coder_lane_gets_the_flattened_protocol(ctx: Ctx):
    from halo_harness.agent.model_switch_history import apply_to_wire
    from halo_harness.agent.subagent import _run_child_to_completion
    with _rig() as rig:
        child = rig.session(CODER)
        child._parent_model_raw = "ol:big:30b"
        _run_child_to_completion(child, "implement the parser", agent_id="c1", parent_tool_use_id="t1")
        body = rig.chats("coder:30b")[0]
        wire = apply_to_wire(child, [
            {"role": "user", "content": [{"type": "text", "text": "go"}]},
            {"role": "assistant", "content": [{"type": "tool_use", "id": "a1", "name": "Read", "input": {"path": "x.py"}}]},
            {"role": "user", "content": [{"type": "tool_result", "tool_use_id": "a1", "content": "print(1)"}]}])
    ctx.check(f"the child knows its model takes no tools, got {getattr(child, '_switch_caps', {})}",
              (getattr(child, "_switch_caps", None) or {}).get("tools") is False)
    ctx.check(f"no tool catalog on its wire, got {len(body.get('tools') or [])} tools", not body.get("tools"))
    texts = [b.get("text") for m in wire for b in m["content"] if isinstance(b, dict)]
    ctx.check(f"tool turns go as text, got {texts}", '[tool call: Read {"path": "x.py"}]' in texts
              and "[result of Read: print(1)]" in texts)


@test
def test_config_set_model_and_studios_lane_button(ctx: Ctx):
    from halo_harness.config_cli import cmd_config
    from halo_harness.studio.api import Request
    from halo_harness.studio.model_card_api import post_models_lane
    with _rig() as rig:
        s = rig.session("ol:big:30b@lan")
        _switch(rig, s, "ol:mid:14b@lan")  # the catalog read once, as a session would have
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            rc = cmd_config(["set", "model", CODER])
        text = out.getvalue()
        role_after_set = _config("roles.coder")
        status, body = post_models_lane(Request("POST", "models/lane", {}, {"ref": CODER}, rig.fh["proj"], rig.state_dir))
        model, role, team = _config("model"), _config("roles.coder"), _config("crew.map")
    ctx.check(f"config set: saved, the line, the command, got {text!r}", rc == 0 and LINE in text
              and f"halo roles point coder {CODER} && halo config set model ol:big:30b" in text)
    ctx.check(f"config set writes no role, got {role_after_set}", role_after_set is None)
    ctx.check(f"Studio's button: roles.coder on the model and model on the orchestrator, got {status} {body}",
              status == 200 and role == CODER and team is None and model == "ol:big:30b" and body.get("coder") == CODER)


@test
def test_the_tui_card_is_one_keystroke(ctx: Ctx):
    from types import SimpleNamespace
    from halo_harness.tui.widgets.lane_offer import LaneOfferCard
    got = []
    offer = {"lineup": "local-coder", "coder": CODER, "orchestrator": "ol:big:30b"}
    yes = LaneOfferCard(line=LINE, offer=offer, on_decide=got.append)
    yes.action_accept()
    yes.action_accept()
    no = LaneOfferCard(line=LINE, offer=offer, on_decide=got.append)
    stopped = []
    no.on_key(SimpleNamespace(key="x", stop=lambda: stopped.append(1)))
    no.on_key(SimpleNamespace(key="y", stop=lambda: stopped.append(1)))
    ctx.check(f"y/Enter accepts once, any other key goes ahead once, got {got}", got == [True, False])
    ctx.check("the other key is consumed", stopped == [1])


if __name__ == "__main__":
    results, passed, failed, skipped = run_all(TESTS, Ctx())
    sys.exit(print_results(results, passed, failed, skipped))
