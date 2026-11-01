"""tests.test_steward_chat -- Halo 3.3.7.0 R5: the steward's chat (ollama_steward/chat.py, chat_tools.py, chat_acts.py,
chat_log.py; studio/local_steward_chat_api.py; `halo ollama steward chat`), over tests/helpers/chat_rig.ChatHome: a
fake model on 127.0.0.1:0 answering fixed JSON, one reply per call, through the real live call (agent.live_call):

1. a read: the model asks for the card, then answers; the tool's answer went into its next prompt; the log has the
   question, the tool and the answer, the answer with its cost ("local, N s") and the steward's model;
2. a proposal that lands: num_predict citing the window finding -- the profile has it (auto mode);
3. one refused by the guard: num_ctx above the measured cap is dropped with the reason, a change citing no finding is
   refused, and a second change in one answer waits;
4. a bench becomes a button (the bench route, the CLI line); nothing ran;
5. "ask a bigger model": its cost said first (bigger_cost), then one call to the session's main model, a `bigger` row;
6. the CLI prints the answer and the cost; GET / POST local/steward/chat answer the log and a turn.
Never a real model or server.
Run: python -m tests.test_steward_chat
"""
from __future__ import annotations

import contextlib
import io
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from tests.helpers.provider_env_defaults import ensure_default_provider_credentials  # noqa: E402
ensure_default_provider_credentials()

from tests.helpers.chat_rig import MAIN, STEWARD, ChatHome  # noqa: E402
from tests.helpers.runner import Ctx, new_registry, print_results, run_all  # noqa: E402

test, TESTS = new_registry()
KEY = "loop|qwen3.8:27b"


def _ask(h, q: str, **kw):
    from halo_harness.ollama_steward.chat import ask
    return ask(h.state, q, **kw)


def _profile():
    from halo_harness.ollama_steward.profiles import all_profiles
    return all_profiles().get(KEY) or {}


@test
def test_a_read_then_the_answer_and_the_log(ctx: Ctx):
    from halo_harness.ollama_steward.chat_log import read
    with ChatHome([{"tool": "card", "args": {"host": "loop"}},
                   {"answer": "The 24 GB card on loop holds nothing else; the 27B's prompts reach 31k of 32k."}]) as h:
        got = _ask(h, "what holds the card on loop?")
        ctx.check(f"the answer, got {got['answer']!r}", got["answer"].startswith("The 24 GB card on loop"))
        ctx.check(f"one tool, the card, got {got['tools']}", [t["tool"] for t in got["tools"]] == ["card"]
                  and "'loop'" in got["tools"][0]["text"])
        ctx.check(f"two calls to the steward's model, got {h.calls(STEWARD)}", h.calls(STEWARD) == 2 and h.calls(MAIN) == 0)
        bodies = [str(r.get("body")) for r in h.mock.requests if str(r.get("path")).startswith("/api/chat")]
        ctx.check(f"the tool's answer went into the next prompt, got {len(bodies)} chat calls",
                  len(bodies) == 2 and "TOOL card" not in bodies[0] and 'TOOL card {"host": "loop"}' in bodies[1])
        ctx.check(f"the cost: local, seconds, got {got['cost']!r}", got["cost"].startswith("local, ") and got["cost"].endswith(" s"))
        rows = read(h.state)
        ctx.check(f"the log: question, tool, answer, got {[r['role'] for r in rows]}", [r["role"] for r in rows]
                  == ["user", "tool", "steward"] and rows[-1]["model"] == f"ol:{STEWARD}@loop"
                  and rows[-1]["cost"] == got["cost"] and rows[0]["text"] == "what holds the card on loop?")
        ctx.check(f"the context is in budget, said, got {got['context_tokens']} {got['left_out']}",
                  0 < got["context_tokens"] <= 6000)


@test
def test_a_proposal_that_lands(ctx: Ctx):
    with ChatHome([]) as h:
        fid = h.finding
    with ChatHome([{"tool": "propose", "args": {"key": KEY, "field": "num_predict", "to": 4096, "why": "room for the reply",
                                                "finding": fid}},
                   {"answer": "num_predict is 4,096 on loop now: the reply has room."}]) as h:
        ctx.check(f"the rig's finding, got {h.finding!r}", h.finding == fid and fid)
        got = _ask(h, "give the 27B's reply more room")
        t = got["tools"][0]
        ctx.check(f"it landed, said, got {t}", t["tool"] == "propose" and t["ok"] and "num_predict 4096" in t["text"])
        ctx.check(f"the profile has it, got {_profile()}", _profile().get("num_predict") == 4096)


@test
def test_the_guard_refuses_one(ctx: Ctx):
    with ChatHome([]) as h:
        fid = h.finding
    with ChatHome([{"tool": "propose", "args": {"key": KEY, "field": "num_ctx", "to": 999999, "why": "bigger",
                                                "finding": fid}},
                   {"tool": "propose", "args": {"key": KEY, "field": "num_ctx", "to": 65536, "why": "no finding"}},
                   {"answer": "The window stays: 999,999 is above what the card measured."}]) as h:
        got = _ask(h, "make the window as big as possible")
        a, b = got["tools"][0], got["tools"][1]
        ctx.check(f"above the cap: dropped with the reason, got {a}", not a["ok"] and "above" in a["text"]
                  and "65536" in a["text"])
        ctx.check(f"no finding cited: refused, the ids named, got {b}", not b["ok"]
                  and b["text"].startswith("a change names the finding it acts on: ") and fid in b["text"])
        ctx.check(f"nothing changed, got {_profile()}", "num_ctx" not in _profile())


@test
def test_a_bench_becomes_a_button(ctx: Ctx):
    with ChatHome([{"tool": "bench", "args": {"model": "qwen3.8:27b", "host": "loop", "quick": True}},
                   {"answer": "A quick bench measures the 27B; press Bench when the card is free."}]) as h:
        got = _ask(h, "how fast is the 27B?")
        b = got["buttons"][0] if got["buttons"] else {}
        ctx.check(f"the one button, got {b}", b.get("verb") == "bench" and b.get("route") == "local/host/loop/bench"
                  and b.get("body") == {"model": "qwen3.8:27b", "quick": True}
                  and b.get("cli") == "halo local bench --host loop --model qwen3.8:27b --quick")
        from halo_harness.ollama_steward.chat_log import read
        ctx.check("the button is in the log", any(r["role"] == "button" and r["action"]["verb"] == "bench" for r in read(h.state)))
        ctx.check(f"nothing ran: no generate, got {h.mock.generated}", h.mock.generated == [])


@test
def test_ask_a_bigger_model(ctx: Ctx):
    from halo_harness.ollama_steward.chat import bigger_cost
    with ChatHome([], main_steps=["The main model's answer: lower the coder's window to 16k."]) as h:
        c = bigger_cost(h.state, "what should I do?")
        ctx.check(f"the cost said first, got {c}", c["model"] == f"ol:{MAIN}@loop" and c["line"].startswith(
            f"ask ol:{MAIN}@loop once: ~") and "free (a local model)" in c["line"])
        got = _ask(h, "what should I do?", bigger=True)
        ctx.check(f"one call to the main model, none to the steward's, got {h.calls(MAIN)} {h.calls(STEWARD)}",
                  h.calls(MAIN) == 1 and h.calls(STEWARD) == 0 and got["answer"].startswith("The main model's answer"))
        from halo_harness.ollama_steward.chat_log import read
        ctx.check("a bigger row", read(h.state)[-1]["role"] == "bigger")


@test
def test_the_cli_and_the_studio_routes(ctx: Ctx):
    from halo_harness.ollama_steward.cli_steward import cmd_ollama_steward
    from halo_harness.studio.api import Request, dispatch
    with ChatHome([{"answer": "Nothing is wrong on loop."}, {"answer": "Still fine."}]) as h:
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            rc = cmd_ollama_steward(["chat", "is anything wrong?"])
        text = out.getvalue()
        ctx.check(f"the CLI: the answer, then the model and the cost, got {rc} {text!r}", rc == 0
                  and text.startswith("Nothing is wrong on loop.\n") and f"(ol:{STEWARD}@loop: local, " in text)

        def call(method, path, body=None):
            return dispatch(Request(method=method, path=path, query={}, body=body or {}, cwd=Path(h.root),
                                    state_dir=h.state, server=None))
        st, body = call("POST", "local/steward/chat", {"question": "and now?"})
        ctx.check(f"POST local/steward/chat, got {st} {body.get('answer')!r}", st == 200 and body["answer"] == "Still fine."
                  and body["cost"].startswith("local, "))
        st, body = call("GET", "local/steward/chat")
        ctx.check(f"GET: the log and the model, got {[r['role'] for r in body.get('rows') or []]}", st == 200
                  and [r["role"] for r in body["rows"]] == ["user", "steward", "user", "steward"]
                  and body["model"] == f"ol:{STEWARD}@loop")
        st, body = call("POST", "local/steward/chat", {})
        ctx.check(f"no question: 422, got {st}", st == 422)


if __name__ == "__main__":
    ctx = Ctx()
    results, passed, failed, skipped = run_all(TESTS, ctx)
    sys.exit(print_results(results, passed, failed, skipped))
