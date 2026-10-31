"""tests.test_prompt_preflight -- Halo 3.3.5.0 R4: a local request that will not fit
its window is a decision the user sees before it is sent (agent/preflight.py).
Through the loop rig (tests/helpers/prompt_budget_rig.py: a real Session over
a fake Ollama on 127.0.0.1:0; `tight:14b` is the 32k fake): a history of
about 41k tokens, then a turn. Never a real server, never a model call:

1. nobody to answer (`-p`, the default `prompt.preflight: ask`): the line
   "prompt N tokens · window 32,768 · usable 16,386 · this will be cut", then
   compact; the ledger's next turn line says `preflight: "compact"` and the
   session log holds a `preflight` node;
2. `prompt.preflight: send`: sent as it is, no compaction before it, the
   ledger says "sent";
3. an interactive session: the card (position "preflight") with the three
   choices, compact the default; answering "send" sends, "switch" moves the
   session to the smallest window on the host that holds it (`big:30b`) and the call
   goes there, "accept" (Studio's attention row) compacts;
4. the steward's `window-asked-small` skips a trim that was chosen (the
   ledger's `preflight: "sent"`, and the log's line beside it).
Run: python -m tests.test_prompt_preflight
"""
from __future__ import annotations

import json
import os
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

os.environ.setdefault("BRIDGE_TEST_HOME", tempfile.mkdtemp(prefix="pb_prompt_preflight-"))
os.environ.setdefault("BRIDGE_TEST_NO_BACKGROUND_NET", "1")

from tests.helpers.model_switch_rig import ledger_lines, markers  # noqa: E402
from tests.helpers.prompt_budget_rig import Rig, answer, fill_to  # noqa: E402
from tests.helpers.runner import Ctx, new_registry, print_results, run_all  # noqa: E402

test, TESTS = new_registry()
MARK = "Do not mention this summarization"


def _say(text: str = "go on"):
    from halo_harness import events
    return events.Command("user_input", {"text": text})


def _session(rig, ref: str = "ol:tight:14b@lan", tokens: int = 26000):
    """A session that already ran one turn on the 32k fake, then a history padded to a ~41k-token prompt."""
    for m in ("tight:14b", "wide:14b"):
        rig.script(m, answer())
    s = rig.session(ref)
    rig.run(s, [_say("hi")])
    fill_to(s, tokens)
    rig.mock.requests.clear()
    from halo_harness.ollama_steward.ledger import traffic_path
    traffic_path(rig.state_dir).unlink(missing_ok=True)
    return s


def _turn_lines(rig) -> list:
    return [x for x in ledger_lines(rig.state_dir) if x.get("kind") == "turn"]


def _compactions(evs) -> int:
    return sum(1 for e in evs if e.kind == "compaction" and e.data.get("phase") == "done")


@test
def test_nobody_to_answer_the_default_compacts_with_the_line(ctx: Ctx):
    with Rig() as rig:
        s = _session(rig)
        evs = rig.run(s, [_say()])
        lines = markers(evs, "preflight")
        ctx.check(f"one preflight line, got {lines}", len(lines) == 1)
        line = lines[0] if lines else ""
        ctx.check(f"the numbers and the cut, got {line!r}", line.startswith("↳ prompt ") and " tokens · window 32,768 · "
                  "usable 16,386 · this will be cut: compacting first (prompt.preflight: ask)" in line)
        ctx.check(f"a compaction before the answer, got {_compactions(evs)}", _compactions(evs) >= 1)
        turns = _turn_lines(rig)
        ctx.check(f"the ledger's next turn line: preflight compact, got {[t.get('preflight') for t in turns]}",
                  bool(turns) and turns[0].get("preflight") == "compact")
        node = next((n for n in s.log.nodes() if n.get("type") == "preflight"), {})
        ctx.check(f"the session log's preflight node, got {node}", node.get("choice") == "compact" and node.get("asked") is False)


@test
def test_preflight_send_sends_it_as_it_is(ctx: Ctx):
    from halo_harness.theme import set_config_value
    with Rig() as rig:
        set_config_value("prompt.preflight", "send")
        s = _session(rig)
        evs = rig.run(s, [_say()])
        lines = markers(evs, "preflight")
        ctx.check(f"the line says it is sent anyway, got {lines}", lines and "sending anyway" in lines[0])
        chats = rig.chats("tight:14b")
        ctx.check("the first request is the answer itself, no compaction before it", chats and MARK not in json.dumps(chats[0]))
        sent = [b for b in chats if MARK not in json.dumps(b)]
        ctx.check("the request went out at the window", sent and (sent[0].get("options") or {}).get("num_ctx") == 32768)
        turns = _turn_lines(rig)
        ctx.check(f"the ledger says sent, got {[t.get('preflight') for t in turns]}", turns and turns[0].get("preflight") == "sent")


@test
def test_an_interactive_session_asks_and_each_answer_does_what_it_says(ctx: Ctx):
    seen: dict = {}

    def decide_with(action):
        def decide(ev):
            seen.setdefault(action, ev.data)
            return {"action": action, "instruction": None}
        return decide

    with Rig() as rig:
        s = _session(rig)
        evs = rig.run_answering(s, [_say()], decide_with("send"))
        card = seen.get("send") or {}
        ctx.check(f"the card: position preflight, the line, compact the default, got {card.get('position')}",
                  card.get("position") == "preflight" and "this will be cut" in card.get("text", "")
                  and card.get("default") == "compact" and [c["id"] for c in card.get("choices") or []] == ["compact", "switch", "send"])
        ctx.check(f"it names the smallest window on the host that holds it, got {card.get('switch_to')}",
                  card.get("switch_to") == "ol:big:30b@lan")
        first = rig.chats("tight:14b")[:1]
        ctx.check("send: the first request is the answer itself", first and MARK not in json.dumps(first[0]))
        ctx.check("send: the ledger says sent", (_turn_lines(rig) or [{}])[0].get("preflight") == "sent")
    with Rig() as rig:
        s = _session(rig)
        evs = rig.run_answering(s, [_say()], decide_with("switch"))
        ctx.check(f"switch: the session is on the bigger-window model, got {s.model_ref.raw}", s.model_ref.raw == "ol:big:30b@lan")
        ctx.check("switch: the call went to big:30b", any(MARK not in json.dumps(b) for b in rig.chats("big:30b")))
        ctx.check(f"switch: the switch line, got {markers(evs, 'switch')[:1]}", any("ol:big:30b@lan" in t for t in markers(evs, "switch")))
        ctx.check("switch: the ledger says switch", any(t.get("preflight") == "switch" for t in _turn_lines(rig)))
    with Rig() as rig:
        s = _session(rig)
        evs = rig.run_answering(s, [_say()], decide_with("accept"))
        ctx.check(f"accept (the attention row's a): compacts, got {_compactions(evs)}", _compactions(evs) >= 1)
        ctx.check("the waiting card is gone once answered", getattr(s, "_preflight_pending", None) is None)


@test
def test_the_steward_skips_a_cut_that_was_chosen(ctx: Ctx):
    from halo_harness.ollama_steward.rules import findings
    from tests.helpers.steward_seed import Home, event, line
    with Home() as h:
        h.calls(line(num_ctx_sent=8192, trimmed=True, prompt_eval_count=4098, preflight="sent", ago=300))
        h.events(event("prompt-trimmed", window_sent=8192, limit=4098, prompt=11000, ago=290))
        rules = [f["rule"] for f in findings(h.state)]
        ctx.check(f"a chosen cut is not a finding, got {rules}", "window-asked-small" not in rules)
    with Home() as h:
        h.calls(line(num_ctx_sent=8192, trimmed=True, prompt_eval_count=4098, ago=300))
        rules = [f["rule"] for f in findings(h.state)]
        ctx.check(f"the same trim, not chosen, is one, got {rules}", "window-asked-small" in rules)


if __name__ == "__main__":
    ctx = Ctx()
    results, passed, failed, skipped = run_all(TESTS, ctx)
    sys.exit(print_results(results, passed, failed, skipped))
