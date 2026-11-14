"""tests.test_agent_talk -- Halo 3.3.16.2 "agents talking": every way one agent speaks to another yields one
`agent_talk` shape {id, from, to, text, why, re?, cut?} (fleet/talk.py): a parent's task to a child and the child's
hand-back (over a REAL session and its control socket), a steer one agent sends another (`agent_steer` with
`from_agent`; a person's steer is no talk), a Workflow square's hand-off and answer, a hand-over to another machine;
a long text is cut and flagged; the trace export prints a hand-back once, as talk. No real model is called.
Run: python -m tests.test_agent_talk
"""
from __future__ import annotations

import sys
import threading
from pathlib import Path
from types import SimpleNamespace

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from tests.helpers.session_rig import SessionRig, agent_call, gated, text_step, tool_step, wait_for  # noqa: E402
from tests.helpers.runner import Ctx, new_registry, print_results, run_all  # noqa: E402

test, TESTS = new_registry()
BY = {"by": "tester"}


def _tree():
    from halo_harness.agent.agent_registry import tree_for
    root = SimpleNamespace(agent_id=None)
    tree = tree_for(root)
    got: list = []
    tree.add_listener(lambda kind, aid, data: kind == "agent_talk" and got.append(data))
    tree.add("r1", session=SimpleNamespace(agent_id="r1"), parent="main", name="researcher", state="running", kind="subagent")
    return tree, got


@test
def test_a_task_and_its_hand_back_over_a_real_session(ctx: Ctx):
    gate = threading.Event()
    with SessionRig() as rig:
        try:
            m_d = rig.script("talk-d", [gated(gate, text_step("D found two places: basket.py and tax.py"))])
            m_main = rig.script("talk-main", [tool_step(agent_call("d", "D: find where the discount applies", m_d)),
                                              text_step("main done")])
            session = rig.session(m_main)
            controller = rig.controller(session)
            from halo_harness.remote import runtime
            act = runtime.start_for_controller(controller)
            c, reader = rig.client(act), rig.reader(act)
            controller.submit("go")
            task = wait_for(lambda: reader.of("agent_talk") and reader.of("agent_talk")[0]["data"])
            ctx.check(f"the task: main -> the child, why task, the prompt's words, got {task}",
                      task and task["from"] == "main" and task["to"] != "main" and task["why"] == "task"
                      and task["text"] == "D: find where the discount applies" and task["from_name"] == "main")
            did = task["to"] if task else ""
            r = c.call("agent_steer", agent_id=did, text="only the tax rules", from_agent="main", **BY)
            ctx.check(f"main's steer to it is accepted, got {r}", r["ok"])
            steer = wait_for(lambda: next((f["data"] for f in reader.of("agent_talk") if f["data"]["why"] == "steer"), None))
            ctx.check(f"another agent's steer is a steer talk, got {steer}", steer and steer["from"] == "main" and steer["to"] == did
                      and steer["text"] == "only the tax rules")
            c.call("agent_steer", agent_id=did, text="a person steers", **BY)
            gate.set()
            back = wait_for(lambda: next((f["data"] for f in reader.of("agent_talk") if f["data"]["why"] == "hand-back"), None))
            ctx.check(f"the hand-back: the child -> main, answering the task, got {back}",
                      back and back["from"] == did and back["to"] == "main" and back["re"] == task["id"]
                      and back["text"] == "D found two places: basket.py and tax.py")
            ctx.check("the session's turn ends", wait_for(lambda: not session.busy, 15))
            talks = [f["data"] for f in reader.of("agent_talk")]
            ctx.check(f"a person's steer is no talk; one task, one steer, one hand-back, got {[t['why'] for t in talks]}",
                      [t["why"] for t in talks] == ["task", "steer", "hand-back"])
            ctx.check("each frame names its speaker as agent_id", all(f["agent_id"] == f["data"]["from"] for f in reader.of("agent_talk")))
        finally:
            gate.set()


@test
def test_the_one_shape_and_a_cut_text(ctx: Ctx):
    from halo_harness.live.talk import TALK_CAP, WHYS, shape
    d = shape("main", "r1", "y" * (TALK_CAP + 10), "task", re="m0")
    ctx.check(f"from / to / why / text / id / ts, cut flagged with the whole length, got {sorted(d)}",
              {"id", "from", "to", "text", "why", "ts", "re", "cut", "chars"} == set(d) and len(d["text"]) == TALK_CAP
              and d["cut"] is True and d["chars"] == TALK_CAP + 10)
    ctx.check("a short text is not flagged", "cut" not in shape("a", "b", "hi", "steer"))
    ctx.check(f"the reasons, got {WHYS}", WHYS == ("task", "hand-back", "steer", "square", "hand-over"))


@test
def test_a_square_hand_off_and_what_came_back(ctx: Ctx):
    from halo_harness.live.talk import on_square, on_turn_ended, on_turn_started
    tree, got = _tree()
    sent = on_square(tree, "main", "sq-1", "media", "read the PDF and list the totals")
    on_square(tree, "main", "sq-1", "media", "Totals: 3", back=True, re=sent["id"])
    ctx.check(f"main -> the square, then back, why square with its name, got {got}", len(got) == 2
              and (got[0]["from"], got[0]["to"], got[0]["why"], got[0]["square"]) == ("main", "sq-1", "square", "media")
              and (got[1]["from"], got[1]["to"], got[1]["re"], got[1]["text"]) == ("sq-1", "main", sent["id"], "Totals: 3"))
    tree.update("r1", square={"name": "research", "engine": "session"})
    child = SimpleNamespace(log=SimpleNamespace(nodes=lambda: [{"type": "assistant", "content": [{"type": "text", "text": "Found it."}]}]))
    t = on_turn_started(tree, "r1", "brief for the square")
    b = on_turn_ended(tree, "r1", child)
    ctx.check(f"a session square's own agent: its task and hand-back are why square, got {t} {b}",
              t["why"] == "square" and t["square"] == "research" and b["why"] == "square" and b["re"] == t["id"])
    ctx.check("the main agent's own turn is no talk", on_turn_started(tree, "main", "the user's prompt") is None)


@test
def test_a_hand_over_names_the_machine(ctx: Ctx):
    from halo_harness.live.talk import hand_over_frame
    f = hand_over_frame(harness="h1", session_id="s1", aid="r1", name="researcher", machine="kali", text="# Hand-off: the basket")
    d = f["data"]
    ctx.check(f"an agent_talk frame from the agent, to the machine, got {f}", f["event"] == "agent_talk" and f["agent_id"] == "r1"
              and f["session_id"] == "s1" and d["why"] == "hand-over" and d["machine"] == "kali" and d["to"] == "" and d["from"] == "r1")


@test
def test_the_trace_prints_a_hand_back_once_as_talk(ctx: Ctx):
    from halo_harness.session_trace_talk import fold_talk, thinking_rows
    rows = [(1.0, "user prompt", "user prompt", "find the discount", False),
            (2.0, "assistant text", "assistant text", "Looking.", False),
            (3.0, "tool call", "tool call: Read", "", False),
            (4.0, "assistant text", "assistant text", "It is in basket.py.", False)]
    out = fold_talk(rows, "researcher")
    ctx.check(f"the task is talk from main, got {out[0]}", out[0][1] == "talk" and out[0][2] == "talk: main -> researcher (task)")
    ctx.check("the hand-back takes the last text's place", out[3][1] == "talk" and out[3][2] == "talk: researcher -> main (hand-back)")
    ctx.check("its words are printed once", sum(1 for r in out if r[3] == "It is in basket.py.") == 1 and len(out) == len(rows))
    th = thinking_rows({"reasoning": {"text": "rounding first"}, "content": [{"type": "thinking", "thinking": "then tax"}]}, 5.0)
    ctx.check(f"thinking rows, in order, got {th}", [r[3] for r in th] == ["rounding first", "then tax"] and all(r[1] == "thinking" for r in th))
    ctx.check("a model with no thinking gives none", thinking_rows({"content": [{"type": "text", "text": "hi"}]}, 1.0) == [])


if __name__ == "__main__":
    ctx = Ctx()
    results, passed, failed, skipped = run_all(TESTS, ctx)
    sys.exit(print_results(results, passed, failed, skipped))
