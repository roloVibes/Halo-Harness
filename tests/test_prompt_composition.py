"""tests.test_prompt_composition -- Halo 3.3.5.0 R4: what a request is made of,
and the memory block sent once (agent/prompt_composition.py,
agent/prompt_wire.py, agent/compact_budget.py). Through the loop rig
(tests/helpers/prompt_budget_rig.py: a real Session over a fake Ollama on
127.0.0.1:0, a fake home that seeds its own MEMORY.md and two topic files);
never a real server, never a model call:

1. the double block: a session whose first request is larger than the window
   compacts before it is sent; the compacted request carries the memory block
   once (the verbatim tail no longer carries the snapshots the compaction
   re-injects -- before, every compaction added another copy) and
   `duplicates` is empty; `dedupe` keeps the newest of two blocks and names
   the other;
2. the parts: memory and the topic index in the system message on a local
   model, their tokens, the tools' tokens, the parts adding up to the total;
   a model whose card says its system role is weak gets them at the front of
   its first user message instead;
3. the ledger line's `composition` and `prefix_tokens`; `/cost` and `/status`
   print the one line.
Run: python -m tests.test_prompt_composition
"""
from __future__ import annotations

import json
import os
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

os.environ.setdefault("BRIDGE_TEST_HOME", tempfile.mkdtemp(prefix="pb_comp-"))
os.environ.setdefault("BRIDGE_TEST_NO_BACKGROUND_NET", "1")

from tests.helpers.prompt_budget_rig import Rig, answer  # noqa: E402
from tests.helpers.model_switch_rig import ledger_lines  # noqa: E402
from tests.helpers.runner import Ctx, new_registry, print_results, run_all  # noqa: E402

test, TESTS = new_registry()
DIR = "Memory directory: "


def _say(text: str):
    from halo_harness import events
    return events.Command("user_input", {"text": text})


def _memory_copies(body: dict) -> "tuple[int, int]":
    msgs = body.get("messages") or []
    system = sum(m.get("content", "").count(DIR) for m in msgs if m.get("role") == "system")
    users = sum(m.get("content", "").count(DIR) for m in msgs if m.get("role") != "system")
    return system, users


@test
def test_a_compacted_request_carries_the_memory_once(ctx: Ctx):
    from halo_harness.agent.derive import derive_request
    from halo_harness.agent.prompt_composition import dedupe, known_texts
    with Rig() as rig:
        rig.script("tiny:3b", answer())
        s = rig.session("ol:tiny:3b@lan")
        evs = rig.run(s, [_say("hi there")])
        answering = [b for b in rig.chats("tiny:3b") if "Do not mention this summarization" not in json.dumps(b)]
        ctx.check(f"a compaction ran before the first answer, got {[e.data.get('phase') for e in evs if e.kind == 'compaction']}",
                  any(e.kind == "compaction" and e.data.get("phase") == "done" for e in evs))
        ctx.check("the answering request went out", bool(answering))
        sys_n, user_n = _memory_copies(answering[-1]) if answering else (0, 0)
        ctx.check(f"the memory block once, in the system message: system {sys_n}, user turns {user_n}",
                  (sys_n, user_n) == (1, 0))
        _sys, messages, _tools = derive_request(s.log, tools=None)
        _out, dups = dedupe(messages, known_texts(s))
        ctx.check(f"the compacted log holds no second copy, got {dups}", dups == [])
        comp = s._prompt_composition
        ctx.check(f"the composition names no duplicate, got {comp.get('duplicates')}", comp.get("duplicates") == [])
        tail = [n for n in s.log.nodes() if n.get("type") == "user" and n.get("kind") == "compaction_tail"]
        ctx.check("the verbatim tail kept the typed words and none of the snapshots",
                  any("hi there" in json.dumps(n.get("content")) for n in tail)
                  and not any(DIR in json.dumps(n.get("content")) for n in tail))


@test
def test_dedupe_keeps_the_newest_block_and_names_the_other(ctx: Ctx):
    from halo_harness.agent.prompt_composition import compose, composition_line, dedupe
    old = DIR + "/m\n\n# Memory (auto-loaded from MEMORY.md)\n\n- old line"
    new = DIR + "/m\n\n# Memory (auto-loaded from MEMORY.md)\n\n- old line\n- new line"
    msgs = [{"role": "user", "content": [{"type": "text", "text": old}, {"type": "text", "text": "do the task"}]},
            {"role": "assistant", "content": [{"type": "text", "text": "ok"}]},
            {"role": "user", "content": [{"type": "text", "text": new}, {"type": "text", "text": "and now"}]}]
    out, dups = dedupe(msgs, {})
    ctx.check(f"one duplicate, the older, got {dups}", len(dups) == 1 and dups[0]["part"] == "memory"
              and dups[0]["where"] == "message 1")
    texts = [b["text"] for m in out for b in m["content"]]
    ctx.check("the newest block stays, the older goes", new in texts and old not in texts and "do the task" in texts)
    comp = compose(None, msgs, [], "system", known={"memory": set(), "claude_md": set(), "harness": set()}, duplicates=dups)
    ctx.check(f"the line says what was taken out, got {composition_line(comp)!r}", "1 repeated block taken out" in composition_line(comp))


@test
def test_the_parts_and_where_the_memory_goes(ctx: Ctx):
    with Rig() as rig:
        rig.script("wide:14b", answer())
        s = rig.session("ol:wide:14b@lan")
        rig.run(s, [_say("what is this repo?")])
        body = rig.chats("wide:14b")[-1]
        ctx.check(f"local: memory in the system message, got {_memory_copies(body)}", _memory_copies(body) == (1, 0))
        c = s._prompt_composition
        sp, up = c["system"]["parts"], c["user"]["parts"]
        ctx.check(f"placement system, got {c['placement']}", c["placement"] == "system")
        ctx.check(f"memory and topics counted in the system, got {sp}", sp["memory"] > 500 and sp["topic_index"] > 10)
        ctx.check(f"the tools counted, got {sp['tools_schema']}", sp["tools_schema"] > 1000)
        ctx.check(f"what you typed is a few tokens, got {up}", 0 < up["text"] < 20)
        named = sum(sp.values()) + sum(up.values()) + c["history"]["tokens"]
        ctx.check(f"the parts add up to the total ({named} vs {c['total']})", named == c["total"])
        from halo_harness.agent.prompt_composition import tokens_of
        wire_system = next(m["content"] for m in body["messages"] if m["role"] == "system")
        ctx.check(f"the prefix is the system message (the memory in it) and the tools, got {c['prefix_tokens']}",
                  abs(c["prefix_tokens"] - (tokens_of(wire_system) + sp["tools_schema"])) <= 3)
    with Rig() as rig:
        rig.script("wide:14b", answer())
        s = rig.session("ol:wide:14b@lan")
        s._prompt_card = {"system_role": "weak"}
        rig.run(s, [_say("hello")])
        body = rig.chats("wide:14b")[-1]
        first_user = next(m for m in body["messages"] if m["role"] == "user")
        ctx.check(f"a weak system role: the memory at the front of the first user message, got {_memory_copies(body)}",
                  _memory_copies(body) == (0, 1) and first_user["content"].startswith(DIR))


@test
def test_the_ledger_line_and_the_cost_line(ctx: Ctx):
    from halo_harness.commands.builtins import _composition_text
    with Rig() as rig:
        rig.script("wide:14b", answer())
        s = rig.session("ol:wide:14b@lan")
        rig.run(s, [_say("hello")])
        turn = [x for x in ledger_lines(rig.state_dir) if x.get("kind") == "turn"]
        comp = (turn[-1] if turn else {}).get("composition") or {}
        ctx.check(f"the ledger's composition, got {comp}", set(comp) == {"system", "memory", "topic_index", "tools_schema",
                                                                        "history", "user", "total"} and comp["memory"] > 0)
        ctx.check(f"prefix_tokens on the line, got {turn[-1].get('prefix_tokens') if turn else None}",
                  bool(turn) and isinstance(turn[-1].get("prefix_tokens"), int) and turn[-1]["prefix_tokens"] > 0)
        line = _composition_text(s)
        ctx.check(f"/cost's line, got {line!r}", line.startswith(f"prompt {comp.get('total', 0):,}: system ")
                  and " · memory " in line and " · topics " in line and " · tools " in line and " · you " in line)
        status = s.status_event().data.get("composition")
        ctx.check(f"the status event carries it for Studio's Cost panel, got {status}", status == comp)


if __name__ == "__main__":
    ctx = Ctx()
    results, passed, failed, skipped = run_all(TESTS, ctx)
    sys.exit(print_results(results, passed, failed, skipped))
