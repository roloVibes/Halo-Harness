"""tests.test_session_control -- Halo 3.0.5.0 "Fleet" round R1: agent-level
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
tests/test_session_registry.py.
"""
from __future__ import annotations

import json
import sys
import threading
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from tests.helpers.session_rig import SessionRig, agent_call, gated, recorded, text_step, tool_step, wait_for
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
    with SessionRig() as rig:
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
            ctx.check("remote.enabled is false and the socket opened anyway (control.enabled defaults on)",
                      act is not None and registry.endpoint_for(session.log.session_id) == act.endpoint)
            feed = rig.reader(act)
            c = rig.client(act)
            hello = feed.frames[0] if feed.frames else {}
            ctx.check(f"the first frame on subscribe is this session's `registry` hello, got {hello.get('event')}",
                      hello.get("event") == "registry" and hello["data"]["action"] == "hello"
                      and hello["data"]["harness"]["id"] and hello["data"]["kind"] == "tui"
                      and "endpoint" not in hello["data"] and "token" not in hello["data"])
            controller.submit("go")
            # 60 s, not the 15 s default: the Windows runner (6d75a1b3) had no agent rows yet at 15 s
            rows = wait_for(lambda: (lambda r: r if len(r) >= 4 and _by_name(c, "C:") else None)(_rows(c)), 60)
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
            notes = [n.get("control_note") for n in session.log.nodes() if n.get("type") == "meta" and n.get("control_note")]
            ctx.check(f"the parent (main) transcript got exactly one line, got {notes}",
                      len(notes) == 1 and notes[0].startswith("general-purpose") and
                      "steered from Studio: focus on the index format" in notes[0] and "tester" not in notes[0])
            ctx.check("pause B", c.call("pause", agent_id=bid, **BY)["result"] == {"paused": bid})
            gate_b.set()
            ctx.check("B holds at its tool boundary: state paused",
                      wait_for(lambda: _rows(c)[bid]["state"] == "paused", 10))
            time.sleep(0.6)
            ctx.check("while paused B neither runs the tool nor calls the model again",
                      len(b_seen) == 1 and not any(n.get("type") == "tool_result" for n in _child_nodes(rig, session, bid)))
            ctx.check("resume B", c.call("resume", agent_id=bid, **BY)["result"]["was_paused"] is True)
            ctx.check("B finishes", wait_for(lambda: _rows(c)[bid]["state"] == "done", 15))
            steer = "[steer from Studio] focus on the index format"
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
                      "stopped from Studio: enough for now" in results.get("call_a", ""))
            texts = [b.get("text") for n in session.log.nodes() if n.get("type") == "assistant"
                     for b in n.get("content") or [] if b.get("type") == "text"]
            ctx.check("and the main agent carried on to its own answer", "main done" in texts)
            c_results = [str(n.get("content")) for n in _child_nodes(rig, session, cc["agent_id"]) if n.get("type") == "tool_result"]
            ctx.check(f"C's tool was left unrun with the stop reason, got {c_results}",
                      any("not run: stopped from Studio" in t for t in c_results))
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


SORTER = {"format": "agent/1", "name": "sorter", "does": "Sorts the files it is given by kind.", "uses": ["read"],
          "careful": "ask-changes", "model": "auto"}


@test
def test_agent_put_and_gone_over_the_socket(ctx: Ctx):
    """3.6.0.15 UN U2: `agent_put` answers {took, why} from crew/use_now.put, `agent_gone` {queued}; bad input answers
    its line; main's transcript records each command without the body."""
    with SessionRig() as rig:
        session = rig.session(rig.script("put-main", [text_step("main done")]))
        from halo_harness.agent.helpers_words import on_auto
        from halo_harness.crew.map_control import control_for
        from halo_harness.crew.map_session import prepare
        if not on_auto(session):  # the rig's session is bare: give it Auto's control, as a top session's start does
            session.team_control = control_for(prepare(None, rig.cwd)[0], cwd=rig.cwd, session=session)
        ctx.check("the session is on Auto", on_auto(session))
        from halo_harness.remote import runtime
        act = runtime.start_for_controller(rig.controller(session))
        c = rig.client(act)
        sha = "0123456789abcdef" * 4
        r = c.call("agent_put", name="sorter", body=SORTER, scope="yours", sha256=sha, **BY)
        ctx.check(f"agent_put took, got {r}", r.get("ok") and r["result"] == {"took": True, "why": ""})
        gp = dict(SORTER, name="general-purpose")
        r = c.call("agent_put", name="general-purpose", body=gp, scope="yours", sha256=sha, **BY)
        ctx.check(f"a built-in's name: refused, got {r}", r.get("ok") and r["result"] == {"took": False, "why": "built-in"})
        r = c.call("agent_gone", name="sorter", scope="yours", **BY)
        ctx.check(f"agent_gone queued, got {r}", r.get("ok") and r["result"] == {"queued": True})
        r = c.call("agent_gone", name="never", scope="yours", **BY)
        ctx.check(f"agent_gone of a name it never had, got {r}", r.get("ok") and r["result"] == {"queued": False})
        for label, fields, line in (
                ("a body that is not a mapping", {"name": "sorter", "body": "x", "scope": "yours", "sha256": sha},
                 "body must be an agent mapping"),
                ("a scope of neither", {"name": "sorter", "body": SORTER, "scope": "starter", "sha256": sha},
                 "scope must be yours or project"),
                ("a short sha256", {"name": "sorter", "body": SORTER, "scope": "yours", "sha256": "abc"},
                 "sha256 must be 64 hex characters"),
                ("another name", {"name": "tidy", "body": SORTER, "scope": "yours", "sha256": sha},
                 "the body's name must be the name")):
            r = c.call("agent_put", **fields, **BY)
            ctx.check(f"{label}: refused with its line, got {r}", r.get("ok") is False and line in str(r.get("error")))
        metas = [n.get("control") for n in session.log.nodes() if n.get("type") == "meta" and n.get("control")]
        puts = [m for m in metas if m.get("cmd") in ("agent_put", "agent_gone")]
        ctx.check(f"main's transcript: one record per command that ran, got {puts}",
                  [(m["cmd"], m["name"]) for m in puts] == [("agent_put", "sorter"), ("agent_put", "general-purpose"),
                                                             ("agent_gone", "sorter"), ("agent_gone", "never")]
                  and puts[0]["via"] == "Studio" and puts[0]["took"] is True and puts[2]["queued"] is True)
        ctx.check("no record carries the body", not [m for m in puts if "body" in m or "does" in json.dumps(m)])
        from halo_harness.peers.protocol import FLEET_CMDS
        ctx.check("a peer cannot send either", not {"agent_put", "agent_gone"} & set(FLEET_CMDS))


@test
def test_a_helper_that_ends_in_its_first_frame_carries_its_end_time(ctx: Ctx):
    """3.6.0.15 F4: a helper that started and ended inside one quiet window reaches the views with its end time:
    its row carries `ended` (time.time() of the end, >= `since`) in the end's own frame and in public_rows();
    a resumed helper is live again (`ended` None); main's row never carries one (its `since` is the session's)."""
    from halo_harness.agent.agent_registry import FIELDS, QUIET_S, AgentTree

    class _Root:
        agent_id = None
        model_ref = None
        log = None

    class _Child:
        agent_id = "helper-1"
        model_ref = None

    tree = AgentTree(_Root())
    frames: list = []
    tree.add_listener(lambda kind, aid, data: frames.append((kind, aid, dict(data))) if kind == "agent_state" else None)
    child = _Child()
    tree.add("helper-1", session=child, parent=tree.root_id, name="writer", kind="subagent")
    t0 = time.monotonic()
    tree.started("helper-1", child, "write the note")
    tree.ended("helper-1")
    ctx.check(f"started and ended inside one quiet window ({QUIET_S} s)", time.monotonic() - t0 < QUIET_S)
    ctx.check("`ended` is an agent row field", "ended" in FIELDS)
    last = [d for k, a, d in frames if a == "helper-1"][-1]
    ctx.check(f"the end's frame is done and carries `ended`, got {last.get('state')} {last.get('ended')}",
              last.get("state") == "done" and isinstance(last.get("ended"), float)
              and last["ended"] >= last["since"])
    row = next(r for r in tree.public_rows() if r["agent_id"] == "helper-1")
    ctx.check(f"public_rows carries the same end, got {row.get('ended')}", row.get("ended") == last.get("ended"))
    tree.started("helper-1", child, "go on")
    again = [d for k, a, d in frames if a == "helper-1"][-1]
    ctx.check(f"a resumed helper is live again: no end, got {again.get('state')} {again.get('ended')}",
              again.get("state") == "running" and again.get("ended") is None)
    tree.ended("helper-1")
    ctx.check("its next end carries `ended` again", isinstance(tree.row("helper-1").get("ended"), float))
    tree.started(tree.root_id, _Root(), "main's task")
    tree.ended(tree.root_id)
    main = next(r for r in tree.public_rows() if r["agent_id"] == tree.root_id)
    ctx.check(f"main's row never carries `ended`, got {main.get('ended')}", main.get("ended") is None)


@test
def test_a_pause_set_on_a_waiting_helper_is_on_its_row_until_resume(ctx: Ctx):
    """3.6.0.15 F3: a pause pressed on a helper that waits on an ask is on its row (`pause_set`) from the press until
    a resume, beside its state (still "waiting": it never held); a frame goes out for each change. A grandchild held
    by lineage, and every row under a session-wide pause, carry no `pause_set` (their Resume would take nothing back)."""
    from types import SimpleNamespace
    from halo_harness.agent.agent_registry import FIELDS, AgentTree

    class _Root:
        agent_id = None
        model_ref = None
        log = None

    class _Kid:
        def __init__(self, aid):
            self.agent_id, self.model_ref = aid, None

    tree = AgentTree(_Root())
    frames: list = []
    tree.add_listener(lambda kind, aid, data: frames.append((aid, dict(data))) if kind == "agent_state" else None)
    child, grand = _Kid("helper-1"), _Kid("helper-2")
    tree.add("helper-1", session=child, parent=tree.root_id, name="reader", kind="subagent")
    tree.add("helper-2", session=grand, parent="helper-1", name="scout", kind="subagent")
    tree.started("helper-1", child, "read the notes")
    tree.started("helper-2", grand, "look around")
    tree.observe("helper-1", SimpleNamespace(kind="permission_request", data={}))
    ctx.check(f"the helper waits on an ask, got {tree.state_of('helper-1')}", tree.state_of("helper-1") == "waiting")
    ctx.check("`pause_set` is an agent row field", "pause_set" in FIELDS)
    n = len(frames)
    tree.controls.pause("helper-1", "Studio")
    row = tree.row("helper-1")
    ctx.check(f"after the press: pause_set True, state still waiting, got {row.get('pause_set')} {row.get('state')}",
              row.get("pause_set") is True and row.get("state") == "waiting")
    sent = [d for a, d in frames[n:] if a == "helper-1"]
    ctx.check(f"a frame carried the set pause, got {[d.get('pause_set') for d in sent]}",
              bool(sent) and sent[-1].get("pause_set") is True)
    ctx.check(f"the grandchild, held by lineage, has no pause_set, got {tree.row('helper-2').get('pause_set')}",
              not tree.row("helper-2").get("pause_set"))
    n = len(frames)
    ctx.check("resume takes it back", tree.controls.resume("helper-1") is True)
    ctx.check(f"after resume: pause_set False, got {tree.row('helper-1').get('pause_set')}",
              tree.row("helper-1").get("pause_set") is False)
    sent = [d for a, d in frames[n:] if a == "helper-1"]
    ctx.check(f"a frame carried the resume, got {[d.get('pause_set') for d in sent]}",
              bool(sent) and sent[-1].get("pause_set") is False)
    tree.controls.pause(None, "Studio")
    try:
        ctx.check(f"a session-wide pause sets it on no row, got {[r.get('pause_set') for r in tree.public_rows()]}",
                  not any(r.get("pause_set") for r in tree.public_rows()))
    finally:
        tree.controls.resume(None)
    tree.controls.pause("helper-2", "Studio")
    ctx.check("a pause set on the grandchild is on its row", tree.row("helper-2").get("pause_set") is True)
    n = len(frames)
    tree.ended("helper-2")
    sent = [d for a, d in frames[n:] if a == "helper-2"]
    ctx.check(f"an agent that ended holds no set pause (its button reads Pause again), got {tree.row('helper-2').get('pause_set')}, "
              f"frames {[d.get('pause_set') for d in sent]}",
              tree.row("helper-2").get("pause_set") is False and bool(sent) and sent[-1].get("pause_set") is False)


if __name__ == "__main__":
    ctx = Ctx()
    results, passed, failed, skipped = run_all(TESTS, ctx)
    sys.exit(print_results(results, passed, failed, skipped))
