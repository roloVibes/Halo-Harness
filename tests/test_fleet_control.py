"""tests.test_fleet_control -- Halo 3.0.5.0 "Fleet" round R1: agent-level
control inside a session, over a REAL in-process session (tests/helpers/
fleet_rig.py: the real Session, Controller and control socket, a scripted
mock model). The main agent spawns A and B; A spawns C. Over the socket:
`agents` shows the tree with states and parents; `agent_tail` returns a
child's own entries; a nudge to B lands as a user-role note before B's next
model call and B's parent gets one line; `pause`/`resume` hold B at its tool
boundary; a redirect updates A's task; `agent_stop` on A ends A and C, the
main agent gets the stopped hand-back and carries on; `agent_state`,
`agent_event` (B followed) and `fleet` frames arrive on `subscribe`, every
frame carrying `session_id` and `harness`. The rest of the round (shutdown,
--private, the two switches, old registry rows, Studio and the CLI) is in
tests/test_fleet_session.py.
"""
from __future__ import annotations

import json
import sys
import threading
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from tests.helpers.fleet_rig import FleetRig, agent_call, gated, recorded, text_step, tool_step, wait_for
from tests.helpers.runner import Ctx, new_registry, print_results, run_all

test, TESTS = new_registry()
BY = {"by": "tester", "via": "Studio"}


def _rows(c) -> dict:
    return {r["agent_id"]: r for r in c.call("agents")["result"]["agents"]}


def _by_name(c, prefix: str):
    return next((r for r in _rows(c).values() if (r.get("task") or "").startswith(prefix)), None)


def _user_texts(body: dict) -> list:
    out = []
    for m in (body or {}).get("messages") or []:
        if m.get("role") == "user":
            out.append(m["content"] if isinstance(m.get("content"), str) else json.dumps(m.get("content")))
    return out


@test
def test_agent_tree_tail_steer_pause_redirect_stop_and_frames(ctx: Ctx):
    gate_b, gate_c = threading.Event(), threading.Event()
    b_seen: list = []
    c_seen: list = []
    with FleetRig() as rig:
        try:
            m_c = rig.script("fleet-c", [gated(gate_c, tool_step(("Glob", {"pattern": "*.md"}, "call_c1")), c_seen),
                                         text_step("C done")])
            m_a = rig.script("fleet-a", [tool_step(agent_call("c", "C: check the notes", m_c)), text_step("A done")])
            m_b = rig.script("fleet-b", [gated(gate_b, tool_step(("Glob", {"pattern": "*.md"}, "call_b1")), b_seen),
                                         recorded(text_step("B done"), b_seen)])
            m_main = rig.script("fleet-main", [tool_step(agent_call("a", "A: research the notes\nin depth", m_a),
                                                         agent_call("b", "B: build the index", m_b)),
                                               text_step("main done")])
            session = rig.session(m_main)
            controller = rig.controller(session)
            from halo_harness.remote import registry, runtime
            act = runtime.start_for_controller(controller)
            ctx.check("remote.enabled is false and the socket opened anyway (fleet.enabled defaults on)",
                      act is not None and registry.endpoint_for(session.log.session_id) == act.endpoint)
            feed = rig.reader(act)
            c = rig.client(act)
            hello = feed.frames[0] if feed.frames else {}
            ctx.check(f"the first frame on subscribe is this session's `fleet` hello, got {hello.get('event')}",
                      hello.get("event") == "fleet" and hello["data"]["action"] == "hello"
                      and hello["data"]["harness"]["id"] and hello["data"]["kind"] == "tui"
                      and "endpoint" not in hello["data"] and "token" not in hello["data"])
            controller.submit("go")
            rows = wait_for(lambda: (lambda r: r if len(r) >= 4 and _by_name(c, "C:") else None)(_rows(c)))
            ctx.check(f"agents: main plus A, B and C, got {sorted((rows or {}).keys())}", rows is not None)
            a, b, cc = _by_name(c, "A:"), _by_name(c, "B:"), _by_name(c, "C:")
            main = (rows or {}).get("main") or {}
            ctx.check("main is the root (kind main, no parent)", main.get("kind") == "main" and main.get("parent") is None)
            ctx.check("A and B hang under main, C under A",
                      a["parent"] == "main" and b["parent"] == "main" and cc["parent"] == a["agent_id"])
            ctx.check(f"each row has its task, model, kind and a live state, got A={a}",
                      a["task"] == "A: research the notes" and a["model"] == m_a and a["kind"] == "subagent"
                      and a["state"] in ("running", "queued") and b["state"] in ("running", "queued")
                      and a["transcript"].endswith(f"agent-{a['agent_id']}.jsonl") and a["since"] > 0)
            tail = c.call("agent_tail", agent_id=a["agent_id"], n=50)["result"]["events"]
            kinds = [e["kind"] for e in tail]
            ctx.check(f"agent_tail on A: its prompt and its spawn of C, got {kinds}",
                      kinds[:1] == ["user"] and "A: research the notes" in tail[0]["text"]
                      and any(e["kind"] == "spawn" and e["task"] == "C: check the notes" for e in tail))
            only = c.call("agent_tail", agent_id=a["agent_id"], kinds=["spawn"])["result"]["events"]
            ctx.check("agent_tail kinds filters", only and all(e["kind"] == "spawn" for e in only))
            ctx.check("an unknown agent is an error", c.call("agent_tail", agent_id="nobody")["ok"] is False)
            bid = b["agent_id"]
            ctx.check("B's and C's first model calls are in flight", wait_for(lambda: b_seen and c_seen, 10))
            ctx.check("follow B", bid in c.call("agent_follow", agent_id=bid, on=True, **BY)["result"]["following"])
            r = c.call("agent_steer", agent_id=bid, text="focus on the index format", **BY)
            ctx.check(f"a nudge to B goes to its inbox, got {r}", r["ok"] and r["result"]["delivered"] == "inbox")
            notes = [n.get("fleet_note") for n in session.log.nodes() if n.get("type") == "meta" and n.get("fleet_note")]
            ctx.check(f"the parent (main) transcript got exactly one line, got {notes}",
                      len(notes) == 1 and notes[0].startswith("general-purpose") and
                      "steered from Studio by tester: focus on the index format" in notes[0])
            ctx.check("pause B", c.call("pause", agent_id=bid, **BY)["result"] == {"paused": bid})
            gate_b.set()
            ctx.check("B holds at its tool boundary: state paused",
                      wait_for(lambda: _rows(c)[bid]["state"] == "paused", 10))
            time.sleep(0.6)
            ctx.check("while paused B neither runs the tool nor calls the model again",
                      len(b_seen) == 1 and not any(n.get("type") == "tool_result" for n in _child_nodes(rig, session, bid)))
            ctx.check("resume B", c.call("resume", agent_id=bid, **BY)["result"]["was_paused"] is True)
            ctx.check("B finishes", wait_for(lambda: _rows(c)[bid]["state"] == "done", 15))
            steer = "[steer from tester via Studio] focus on the index format"
            ctx.check(f"the note is a user-role message in B's next model call, got {len(b_seen)} calls",
                      len(b_seen) == 2 and any(steer in t for t in _user_texts(b_seen[1]))
                      and not any(steer in t for t in _user_texts(b_seen[0])))
            nodes = _child_nodes(rig, session, bid)
            order = [n.get("type") + (":" + n["kind"] if n.get("kind") else "") for n in nodes
                     if n.get("type") in ("tool_result", "user", "assistant")]
            ctx.check(f"in B's transcript the note sits after the tool result and before its answer, got {order}",
                      "tool_result" in order and "user:steer" in order and order.index("tool_result") < order.index("user:steer")
                      and order[-1] == "assistant")
            btail = [e["kind"] for e in c.call("agent_tail", agent_id=bid)["result"]["events"]]
            ctx.check(f"B's tail records the commands and ends with its hand-back, got {btail}",
                      btail.count("control") >= 3 and btail[-1] == "handback")
            aid = a["agent_id"]
            r = c.call("agent_steer", agent_id=aid, text="switch to the docs folder\nand only that", mode="redirect", **BY)
            ctx.check("a redirect updates A's task", r["ok"] and _rows(c)[aid]["task"] == "switch to the docs folder")
            r = c.call("agent_stop", agent_id=aid, reason="enough for now", **BY)
            ctx.check(f"agent_stop A stops A and its subtree (C), got {r}",
                      r["ok"] and set(r["result"]["stopping"]) == {aid, cc["agent_id"]})
            gate_c.set()
            ctx.check("the session's turn ends", wait_for(lambda: session.turn_count and not session.busy, 20))
            final = _rows(c)
            ctx.check(f"A and C stopped, B done, main done, got { {k: v['state'] for k, v in final.items()} }",
                      final[aid]["state"] == "stopped" and final[cc["agent_id"]]["state"] == "stopped"
                      and final[bid]["state"] == "done" and final["main"]["state"] == "done")
            results = {n["tool_use_id"]: str(n.get("content")) for n in session.log.nodes() if n.get("type") == "tool_result"}
            ctx.check(f"main got A's stopped hand-back, got {results.get('call_a', '')[:120]!r}",
                      "stopped by tester from Studio: enough for now" in results.get("call_a", ""))
            texts = [b.get("text") for n in session.log.nodes() if n.get("type") == "assistant"
                     for b in n.get("content") or [] if b.get("type") == "text"]
            ctx.check("and the main agent carried on to its own answer", "main done" in texts)
            c_results = [str(n.get("content")) for n in _child_nodes(rig, session, cc["agent_id"]) if n.get("type") == "tool_result"]
            ctx.check(f"C's tool was left unrun with the stop reason, got {c_results}",
                      any("not run: stopped by tester from Studio" in t for t in c_results))
            states = feed.of("agent_state")
            ctx.check(f"agent_state frames for the tree, with session_id and harness, got {len(states)}",
                      states and all(f.get("session_id") == session.log.session_id and f.get("harness") == hello["data"]["harness"]["id"]
                                     for f in states)
                      and any(f["agent_id"] == bid and f["data"]["state"] == "paused" for f in states)
                      and any(f["agent_id"] == aid and f["data"]["state"] == "stopped" for f in states))
            evs = [f["data"]["kind"] for f in feed.of("agent_event", bid)]
            ctx.check(f"agent_event frames for followed B: its tool call, result, the note and its text, got {evs}",
                      {"tool_call", "tool_result", "user", "text"} <= set(evs))
            ctx.check("no agent_event frames for an agent nobody follows", not feed.of("agent_event", aid))
        finally:
            gate_b.set()
            gate_c.set()


def _child_nodes(rig, session, agent_id: str) -> list:
    from halo_harness.agent.agent_registry import tree_for
    child = tree_for(session).session_of(agent_id)
    if child is not None:
        return child.log.nodes()
    path = Path(tree_for(session).row(agent_id)["transcript"])
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


if __name__ == "__main__":
    ctx = Ctx()
    results, passed, failed, skipped = run_all(TESTS, ctx)
    sys.exit(print_results(results, passed, failed, skipped))
