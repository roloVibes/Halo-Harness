"""tests.test_fleet_think -- Halo 3.3.16.2 "thinking you can see": an agent's thinking reaches the feed as
`thinking_chunk` frames (fleet/think.py through the agent tree, agent/agent_observe.py), one id per thought so the
Live column grows ONE row; the thought ends when the agent acts, with how long it thought and, when the provider
reports them, its reasoning tokens; a model with no thinking yields none. No model is called.
Run: python -m tests.test_fleet_think
"""
from __future__ import annotations

import sys
from pathlib import Path
from types import SimpleNamespace

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from tests.helpers.provider_env_defaults import ensure_scoped_state_dir_once  # noqa: E402
from tests.helpers.runner import Ctx, new_registry, print_results, run_all  # noqa: E402

ensure_scoped_state_dir_once()
test, TESTS = new_registry()


class Clock:
    def __init__(self) -> None:
        self.t = 100.0

    def __call__(self) -> float:
        return self.t


def _ev(kind: str, **data):
    return SimpleNamespace(kind=kind, data=data)


@test
def test_chunks_of_one_thought_share_one_id_and_end_when_it_acts(ctx: Ctx):
    from halo_harness.fleet.think import FLUSH_S, ThinkFeed
    clock = Clock()
    f = ThinkFeed(clock)
    out = []
    for i, word in enumerate(("The basket ", "rounds ", "before tax, ", "so I read it.")):
        clock.t += FLUSH_S * 0.6 if i else 0
        out += f.feed(_ev("thinking_delta", text=word))
    clock.t += 0.3
    out += f.feed(_ev("tool_use_ready", id="c1", name="Read"))
    ctx.check(f"several frames while it grows, then one that ends it, got {out}", len(out) >= 2 and out[-1].get("end") is True)
    ctx.check("every frame of the thought has one id", len({d["id"] for d in out}) == 1)
    ctx.check("joined, they are the whole thought", "".join(d["text"] for d in out) == "The basket rounds before tax, so I read it.")
    ms = out[-1].get("ms")
    ctx.check(f"the end says how long it thought (about {int((clock.t - 100) * 1000)} ms), got {ms}", ms == int(round((clock.t - 100) * 1000)))
    ctx.check("a tool call after it opens no new thought", f.feed(_ev("tool_result", id="c1")) == [])
    nxt = f.feed(_ev("thinking_delta", text="Now the test.")) + f.feed(_ev("text_delta", text="Done."))
    ctx.check(f"the next thought has a new id, got {nxt}", nxt and nxt[0]["id"] != out[0]["id"] and nxt[-1].get("end"))


@test
def test_reasoning_tokens_join_the_thought_at_message_end(ctx: Ctx):
    from halo_harness.fleet.think import ThinkFeed
    f = ThinkFeed(Clock())
    out = f.feed(_ev("thinking_delta", text="one lump of reasoning"))
    out += f.feed(_ev("message_end", usage={"output_tokens": 40, "reasoning_tokens": 812}))
    ctx.check(f"the end, then the tokens on the same id, got {out}", len(out) == 2 and out[0].get("end") and out[1] == {
        "id": out[0]["id"], "text": "", "end": True, "tokens": 812})
    ctx.check("a one-shot reasoning block has no length of its own (no ms)", "ms" not in out[0])
    ctx.check("no tokens without a thought", f.feed(_ev("message_end", usage={"reasoning_tokens": 9})) == [])


@test
def test_a_model_with_no_thinking_yields_none(ctx: Ctx):
    from halo_harness.fleet.think import ThinkFeed
    f = ThinkFeed(Clock())
    out = []
    for ev in (_ev("message_start"), _ev("text_delta", text="hi"), _ev("tool_use_ready", id="a", name="Bash"),
               _ev("tool_result", id="a"), _ev("message_end", usage={"output_tokens": 3}), _ev("turn_done", reason="end_turn")):
        out += f.feed(ev)
    ctx.check(f"nothing invented, got {out}", out == [] and f.end() == [])


@test
def test_a_long_thought_is_cut_per_frame_and_flagged(ctx: Ctx):
    from halo_harness.fleet.think import CHUNK_CAP, ThinkFeed
    f = ThinkFeed(Clock())
    out = f.feed(_ev("thinking_delta", text="x" * (CHUNK_CAP + 50)))
    ctx.check(f"one frame, cut at {CHUNK_CAP} and flagged", len(out) == 1 and len(out[0]["text"]) == CHUNK_CAP and out[0].get("cut"))


@test
def test_the_agent_tree_publishes_every_agents_thoughts(ctx: Ctx):
    from halo_harness import events
    from halo_harness.agent.agent_registry import tree_for
    root = SimpleNamespace(agent_id=None)
    tree = tree_for(root)
    got: list = []
    tree.add_listener(lambda kind, aid, data: got.append((kind, aid, data)))
    tree.started("main", root, "fix the basket")
    child = SimpleNamespace(agent_id="r1")
    tree.add("r1", session=child, parent="main", name="researcher", state="queued", kind="subagent")
    tree.started("r1", child, "read the notes")
    for piece in ("I should ", "check the notes"):
        tree.observe("r1", events.thinking_delta(piece))
    tree.observe("main", events.thinking_delta("While it reads, "))
    tree.observe("r1", events.text_delta("They agree."))
    tree.ended("main")
    frames = [(aid, d) for kind, aid, d in got if kind == "thinking_chunk"]
    r1 = [d for aid, d in frames if aid == "r1"]
    ctx.check(f"a sub-agent's thought, unfollowed, reaches the feed as one id, got {frames}",
              r1 and len({d["id"] for d in r1}) == 1 and "".join(d["text"] for d in r1) == "I should check the notes" and r1[-1].get("end"))
    mn = [d for aid, d in frames if aid == "main"]
    ctx.check("main's open thought ends with its turn", mn and mn[-1].get("end") and "".join(d["text"] for d in mn) == "While it reads, ")
    ctx.check("no agent_event without a follow", not any(k == "agent_event" for k, *_ in got))


@test
def test_the_feed_kinds_carry_the_new_frames(ctx: Ctx):
    from halo_harness.fleet.protocol import FULL_KINDS, frame_allowed
    from halo_harness.studio.feed_kinds import DEFAULT_KINDS
    ui = (Path(__file__).resolve().parent.parent / "halo_harness/studio/ui/src/lib/events.ts").read_text(encoding="utf-8")
    for k in ("thinking_chunk", "agent_talk"):
        ctx.check(f"Studio asks every session for {k}", k in DEFAULT_KINDS)
        ctx.check(f"events.ts KNOWN_KINDS knows {k}", f'"{k}"' in ui)
        ctx.check(f"{k} is content: a full share only", k in FULL_KINDS and frame_allowed("full", k) and not frame_allowed("events", k))


if __name__ == "__main__":
    ctx = Ctx()
    results, passed, failed, skipped = run_all(TESTS, ctx)
    sys.exit(print_results(results, passed, failed, skipped))
