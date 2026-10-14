"""tests.test_fleet_hub_control -- Halo 3.0.5.0 "Fleet" round R2: commands
from the hub, as B's owner allows (fleet/control.py), over the real routes:
`POST /api/fleet/<B>/<sid>/agents/main/command {cmd: stop}` from A's Studio.

* `ask` (the default): B's TUI gets the card "<name> on <hub> wants to stop
  ..." [allow] [deny]; denied -> refused with the reason (403 / the command's
  state), the session untouched, the refusal in B's transcript; allowed ->
  applied;
* `all`: applied at once, recorded with `by` = the hub's person and `via` =
  "hub <name>"; `none`: refused with the reason the hub shows;
* a print-mode session under `ask` has no one to ask: denied;
* cards are answerable from the hub only with `all` AND fleet.allow_answers,
  scope once, and never the fleet card itself;
* `agent_tail` needs share full.
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from tests.helpers.fleet_hub_rig import HubRig, wait_for
from tests.helpers.runner import Ctx, new_registry, print_results, run_all

test, TESTS = new_registry()


def _stop(rig, sid: str, wait_s: float = 0.5):
    return rig.api("POST", f"fleet/{rig.b_id}/{sid}/agents/main/command",
                   {"cmd": "stop", "reason": "wrong folder", "wait_s": wait_s})


def _meta(controller) -> list:
    return [n["fleet"] for n in controller.session.log.nodes() if n.get("type") == "meta" and n.get("fleet")]


@test
def test_ask_shows_the_card_and_denied_is_refused_allowed_is_applied(ctx: Ctx):
    with HubRig() as rig:
        rig.join()
        controller, act = rig.session()
        sid = act.session_id
        wait_for(lambda: rig.member_session(sid))
        status, body = _stop(rig, sid)
        ctx.check(f"under ask the hub hears `asked` (202), got {status} {body}", status == 202 and body.get("asked")
                  and body.get("command_id"))
        rid = rig.card(controller)
        ctx.check(f"B's session holds the fleet card, got {rid}", bool(rid))
        cards = [ev for ev in list(controller.events.queue) if getattr(ev, "kind", "") == "question"
                 and (ev.data or {}).get("id") == rid] if hasattr(controller.events, "queue") else []
        text = cards[0].data["input"]["question"] if cards else ""
        if not cards:  # the TUI drains controller.events; the feed copy says the same
            got = wait_for(lambda: rig.seen("question", harness=rig.b_id), 5) or []
            text = got[-1]["data"]["input"]["question"] if got else ""
        ctx.check(f"the card names who, where and what, got {text!r}",
                  text.startswith("alice@hub on hub-a wants to stop the main agent") and "wrong folder" in text)
        controller.answer_question(rid, "deny")
        done = wait_for(lambda: (rig.api("GET", f"fleet/commands/{body['command_id']}")[1] or {}).get("state") == "refused")
        state = rig.api("GET", f"fleet/commands/{body['command_id']}")[1]
        ctx.check(f"denied: the command is refused with the owner's reason, got {state}", bool(done)
                  and "denied" in (state.get("error") or ""))
        ctx.check("denied: the session was not interrupted", not controller.session.abort.is_set())
        ctx.check("denied: B's transcript records the refusal with who asked",
                  any(m.get("refused") and m.get("by") == "alice@hub" and m.get("via") == "hub hub-a" for m in _meta(controller)))
        ctx.check("a `fleet` frame told A's feed the outcome",
                  any(f["data"].get("action") == "command" and f["data"].get("state") == "refused"
                      for f in rig.seen("fleet", harness=rig.b_id)))
        status, body = _stop(rig, sid)
        rid = rig.card(controller)
        controller.answer_question(rid, "allow")
        state = wait_for(lambda: (rig.api("GET", f"fleet/commands/{body['command_id']}")[1] or {}).get("state") == "done")
        ctx.check("allowed: the stop is applied (the main agent's turn interrupted)", bool(state)
                  and controller.session.abort.is_set())


@test
def test_all_applies_and_records_by_none_refuses_with_the_reason(ctx: Ctx):
    with HubRig() as rig:
        rig.set_b(**{"fleet.allow_control": "all"})
        rig.join()
        controller, act = rig.session()
        sid = act.session_id
        wait_for(lambda: rig.member_session(sid))
        status, body = _stop(rig, sid, wait_s=10.0)
        ctx.check(f"under all the stop is applied at once (200), got {status} {body}", status == 200
                  and body["result"].get("interrupted") is True and controller.session.abort.is_set())
        ctx.check("no card was shown", not any(k.startswith("fleet-ask:") for k in controller.session._question_waiters))
        meta = [m for m in _meta(controller) if m.get("cmd") == "agent_stop"]
        ctx.check(f"B's transcript records the stop with by and via, got {meta}",
                  meta and meta[-1]["by"] == "alice@hub" and meta[-1]["via"] == "hub hub-a")
        controller.session.abort.clear()
        status, body = rig.api("POST", f"fleet/{rig.b_id}/{sid}/agents/main/command",
                               {"cmd": "steer", "text": "look at the tests first", "wait_s": 10})
        ctx.check(f"a steer from the hub reaches B's main agent, got {status}", status == 200)
        said = wait_for(lambda: [n for n in controller.session.log.nodes() if n.get("type") == "user"
                                 and "look at the tests first" in n["content"][0]["text"]], 8)
        ctx.check("with the hub's origin on the note", bool(said)
                  and said[-1]["content"][0]["text"].startswith("[steer from alice@hub via hub hub-a]"))
        rig.set_b(**{"fleet.allow_control": "none"})
        rig.poke()
        wait_for(lambda: (rig.member() or {}).get("allow_control") == "none", 5)
        status, body = _stop(rig, sid, wait_s=10.0)
        ctx.check(f"under none: refused (403) with the reason the hub shows, got {status} {body}",
                  status == 403 and body.get("refused") and "fleet.allow_control: none" in body.get("error", ""))
        ctx.check("under none: the session was not touched", not controller.session.abort.is_set())


@test
def test_a_print_session_under_ask_is_denied(ctx: Ctx):
    with HubRig() as rig:
        rig.join()
        from halo_harness.remote import runtime
        from tests.helpers.fake_remote_session import FakeSession
        handle, act = runtime.start_for_print(FakeSession("printsession000000000000000000002"), Path(rig.root_b))
        sid = act.session_id
        wait_for(lambda: rig.member_session(sid))
        status, body = _stop(rig, sid, wait_s=10.0)
        ctx.check(f"a print session has no one to ask: denied, got {status} {body}", status == 403
                  and "no one to ask" in body.get("error", ""))
        ctx.check("and nothing was interrupted", not handle.session.abort.is_set())


@test
def test_cards_and_reads_need_the_owner_s_settings(ctx: Ctx):
    with HubRig() as rig:
        rig.set_b(**{"fleet.allow_control": "all"})
        rig.join()
        controller, act = rig.session()
        sid = act.session_id
        wait_for(lambda: rig.member_session(sid))
        controller.submit("please ask first")
        wait_for(lambda: "perm_1" in controller.session._permission_waiters)
        answer = {"cmd": "answer", "kind": "permission", "request_id": "perm_1", "action": "allow", "scope": "always",
                  "wait_s": 10}
        status, body = rig.api("POST", f"fleet/{rig.b_id}/{sid}/command", answer)
        ctx.check(f"without fleet.allow_answers the hub cannot answer a card, got {status} {body}",
                  status == 403 and "allow_answers" in body.get("error", ""))
        rig.set_b(**{"fleet.allow_answers": True})
        rig.poke()
        status, body = rig.api("POST", f"fleet/{rig.b_id}/{sid}/command", answer)
        ctx.check(f"with all + allow_answers the card is answered, got {status} {body}", status == 200)
        ctx.check("once only: no rule was learned (a hub never gets a tool permission)",
                  wait_for(lambda: controller.session.permission_decisions.get("perm_1") is not None)
                  and controller.session.permission_engine.session_rules == []
                  and controller.session.permission_decisions["perm_1"].rule is None)
        status, body = rig.api("POST", f"fleet/{rig.b_id}/{sid}/command",
                               {"cmd": "answer", "kind": "question", "request_id": "fleet-ask:abc", "answer": "allow",
                                "wait_s": 10})
        ctx.check(f"the fleet card itself is never answerable from the hub, got {status} {body}",
                  status == 403 and "never answers the card" in body.get("error", ""))
        status, body = rig.api("POST", f"fleet/{rig.b_id}/{sid}/agents/main/command", {"cmd": "tail", "wait_s": 10})
        ctx.check(f"agent_tail under share events is refused, got {status} {body}", status == 403
                  and "share full" in body.get("error", ""))
        rig.set_b(**{"fleet.share": "full"})
        rig.poke()
        wait_for(lambda: (rig.member() or {}).get("share") == "full", 5)
        status, body = rig.api("POST", f"fleet/{rig.b_id}/{sid}/agents/main/command", {"cmd": "tail", "wait_s": 10})
        ctx.check(f"agent_tail under share full answers, got {status}", status == 200
                  and body["result"]["agent_id"] == "main" and isinstance(body["result"]["events"], list))


if __name__ == "__main__":
    ctx = Ctx()
    results, passed, failed, skipped = run_all(TESTS, ctx)
    sys.exit(print_results(results, passed, failed, skipped))
