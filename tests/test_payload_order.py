"""tests.test_payload_order -- Halo 3.3.5.0 R4: the payload ordered so the task
survives a cut, and the prompt's front kept byte-stable
(agent/prompt_wire.py). Ollama cuts an over-window prompt to 4 tokens of the
start plus the tail, so on a local model the memory rides at the front (the
end of the system message) and, on a request sent over the window, the task
summary and the latest words go last. Through the loop rig
(tests/helpers/prompt_budget_rig.py); never a real server or a model call:

1. `order_for_survival`: the compaction summary moves into the last user
   message, before the user's own words; nothing moves without a summary;
2. the prefix (the system message with the memory in it, and the tools) is
   byte-stable across two turns, also when a topic file is touched between
   them (the lean topic order is kept for the session); the ledger says
   `prefix_changed: false`;
3. a request sent anyway over the window: its last user message holds the
   task summary and ends with what the user typed; the memory is at the front.
Run: python -m tests.test_payload_order
"""
from __future__ import annotations

import json
import os
import sys
import tempfile
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

os.environ.setdefault("BRIDGE_TEST_HOME", tempfile.mkdtemp(prefix="pb_order-"))
os.environ.setdefault("BRIDGE_TEST_NO_BACKGROUND_NET", "1")

from tests.helpers.model_switch_rig import ledger_lines  # noqa: E402
from tests.helpers.prompt_budget_rig import Rig, answer, fill_to  # noqa: E402
from tests.helpers.runner import Ctx, new_registry, print_results, run_all  # noqa: E402

test, TESTS = new_registry()
SUMMARY = "<compacted-summary>"


def _say(text: str):
    from halo_harness import events
    return events.Command("user_input", {"text": text})


@test
def test_the_summary_goes_last_before_the_users_words(ctx: Ctx):
    from halo_harness.agent.prompt_wire import order_for_survival
    known = {"memory": set(), "claude_md": set(), "harness": set()}
    summary = f"This session is being continued.\n\n{SUMMARY}\n## Task\nfix the parser\n</compacted-summary>"
    msgs = [{"role": "user", "content": [{"type": "text", "text": summary}, {"type": "text", "text": "earlier words"}]},
            {"role": "assistant", "content": [{"type": "text", "text": "done that"}]},
            {"role": "user", "content": [{"type": "text", "text": "now the tests"}]}]
    out = order_for_survival(msgs, known)
    last = [b["text"] for b in out[-1]["content"]]
    ctx.check(f"the summary, then the user's words, last, got {[t[:20] for t in last]}",
              len(last) == 2 and SUMMARY in last[0] and last[1] == "now the tests")
    ctx.check("the first message keeps its own words, the summary gone from it",
              [b["text"] for b in out[0]["content"]] == ["earlier words"])
    plain = [msgs[1], msgs[2]]
    ctx.check("no summary: nothing moves", order_for_survival(plain, known) == plain)


def _prefix(body: dict) -> str:
    system = next((m["content"] for m in body.get("messages") or [] if m.get("role") == "system"), "")
    return json.dumps([system, body.get("tools") or []], sort_keys=True)


@test
def test_the_prefix_is_byte_stable_across_turns(ctx: Ctx):
    with Rig() as rig:
        rig.script("wide:14b", answer())
        s = rig.session("ol:wide:14b@lan")
        rig.run(s, [_say("first")])
        topic = next(Path(s.session_context.memory_store.memory_dir_path).glob("project_*.md"))
        later = time.time() + 120
        os.utime(topic, (later, later))  # a topic file touched between the turns
        rig.run(s, [_say("second")])
        rig.run(s, [_say("third")])
        bodies = rig.chats("wide:14b")
        ctx.check(f"three requests, got {len(bodies)}", len(bodies) == 3)
        ctx.check("the system message and the tools are byte-identical on every turn",
                  len({_prefix(b) for b in bodies}) == 1)
        system = bodies[0]["messages"][0]["content"]
        ctx.check("the memory rides in that stable front", "Memory directory: " in system)
        turns = [x for x in ledger_lines(rig.state_dir) if x.get("kind") == "turn"]
        ctx.check(f"the ledger: prefix_changed false, prefix_tokens the same, got "
                  f"{[(t.get('prefix_changed'), t.get('prefix_tokens')) for t in turns]}",
                  len(turns) == 3 and not any(t.get("prefix_changed") for t in turns)
                  and len({t.get("prefix_tokens") for t in turns}) == 1)


@test
def test_a_request_sent_anyway_ends_with_the_task(ctx: Ctx):
    from halo_harness import events
    from halo_harness.theme import set_config_value
    with Rig() as rig:
        rig.script("tight:14b", answer())
        s = rig.session("ol:tight:14b@lan")
        rig.run(s, [_say("refactor the parser")])
        rig.run(s, [events.Command("run_compact", {})])
        fill_to(s, 26000)
        rig.mock.requests.clear()
        set_config_value("prompt.preflight", "send")
        rig.run(s, [_say("now run the tests")])
        sent = [b for b in rig.chats("tight:14b") if "Do not mention this summarization" not in json.dumps(b)]
        body = sent[0] if sent else {}
        users = [m for m in body.get("messages") or [] if m.get("role") == "user"]
        last = users[-1]["content"] if users else ""
        ctx.check("the last user message holds the task summary", SUMMARY in last)
        ctx.check(f"and ends with what the user typed, got {last[-40:]!r}", last.rstrip().endswith("now run the tests"))
        ctx.check("no earlier message keeps a second copy of the summary",
                  sum(json.dumps(m).count(SUMMARY) for m in body.get("messages") or []) == 1)
        ctx.check("the memory is at the front (the system message)", "Memory directory: " in body["messages"][0]["content"])


if __name__ == "__main__":
    ctx = Ctx()
    results, passed, failed, skipped = run_all(TESTS, ctx)
    sys.exit(print_results(results, passed, failed, skipped))
