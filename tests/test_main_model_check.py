"""tests.test_main_model_check -- Halo 3.3.5.0 R0b (d): the main model picked
cannot orchestrate here -- one plain line and the coder-lane offer
(`agent/main_model_check.py`, `agent/model_card_switch.py`), through the
loop rig (tests/helpers/model_switch_rig.py: a fake Ollama on 127.0.0.1:0)
with one more model, `coder:30b` (tools declared, the probe got no call):

1. `/model` to it: the card's `how` lines come before the switch line, the
   main-model line after it, with the offer (lineup `local-coder`, main on
   the best local orchestrator);
2. accept -> the lineup written and active, the coder role on the model, the
   session's role table updated; go ahead -> nothing written;
3. a model that can orchestrate -> no line;
4. a sub-agent on the coder lane gets the flattened text protocol (no tool
   catalog on its wire, tool turns as text);
5. `halo config set model` prints the line and the command; Studio's
   `POST models/lane` writes the lineup and sets `model`;
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
              and "halo teams apply local-coder" in offer.get("command", ""))
    ctx.check(f"the line ends with the offer in words, got {data.get('text')!r}",
              data.get("text", "").endswith("Keep it as the coder lane under ol:big:30b (lineup 'local-coder'), or go ahead anyway."))


@test
def test_accept_writes_the_lineup_and_go_ahead_writes_nothing(ctx: Ctx):
    from halo_harness.agent.main_model_check import accept
    from halo_harness.teams_yaml import resolve_team_template
    with _rig() as rig:
        s = rig.session("ol:big:30b@lan")
        evs = _switch(rig, s, CODER)
        offer = next(e.data["offer"] for e in evs if e.kind == "turn_marker" and e.data.get("state") == "model-check")
        ctx.check("going ahead writes nothing: no lineup, no team",
                  resolve_team_template("local-coder") is None and _config("team") is None)
        ok, lines = accept(offer, session=s, state_dir=rig.state_dir)
        tpl = resolve_team_template("local-coder") or {}
        team, coder = _config("team"), _config("roles.coder")
        live = dict(getattr(s.agent_runtime, "role_table", {}) or {})
    ctx.check(f"accepted: one line naming the lane, got {lines[:1]}", ok and lines[0].startswith("lineup 'local-coder' applied")
              and f"{CODER} is the coder lane, ol:big:30b runs main" in lines[0])
    ctx.check(f"the lineup is active and the coder role is on the model, got team={team} coder={coder}",
              team == "local-coder" and coder == CODER)
    main = next((a for a in tpl.get("agents") or [] if a.get("role") == "main"), {})
    ctx.check(f"main is pinned to the orchestrator, the pool on auto, got {tpl.get('agents')}",
              (main.get("models") or {}).get("preference") == "ol:big:30b"
              and {a.get("agent") for a in tpl.get("agents") or []} >= {"auto-coder", "auto-reviewer", "auto-researcher"})
    ctx.check(f"the session's role table follows, got {live.get('coder')}", live.get("coder") == CODER)


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
    from halo_harness.teams_yaml import resolve_team_template
    with _rig() as rig:
        s = rig.session("ol:big:30b@lan")
        _switch(rig, s, "ol:mid:14b@lan")  # the catalog read once, as a session would have
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            rc = cmd_config(["set", "model", CODER])
        text = out.getvalue()
        written, team_after_set = resolve_team_template("local-coder") is not None, _config("team")
        status, body = post_models_lane(Request("POST", "models/lane", {}, {"ref": CODER}, rig.fh["proj"], rig.state_dir))
        model, team = _config("model"), _config("team")
    ctx.check(f"config set: saved, the line, the command, got {text!r}", rc == 0 and LINE in text
              and "halo teams apply local-coder && halo config set model ol:big:30b" in text)
    ctx.check("the lineup file is written but not active", written and team_after_set is None)
    ctx.check(f"Studio's button: the lineup active and model on the orchestrator, got {status} {body}",
              status == 200 and team == "local-coder" and model == "ol:big:30b" and body.get("coder") == CODER)


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
