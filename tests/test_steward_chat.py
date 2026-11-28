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


@test
def test_the_prompts_front_is_byte_identical_from_round_to_round(ctx: Ctx):
    """3.3.8.0 R2 (5b): the guide (system), then the sections that change least, the findings and the events after
    them, the conversation and the question last: a round's prompt starts with the round before's, and a new question
    keeps every section's bytes in front of it (Ollama reuses the KV prefix)."""
    import json as _json
    from halo_harness.ollama_steward import chat
    with ChatHome([{"tool": "card", "args": {"host": "loop"}}, {"answer": "one"}, {"answer": "two"}]) as h:
        _ask(h, "first question?")
        _ask(h, "second question?")
        bodies = [r.get("body") for r in h.mock.requests if str(r.get("path")).startswith("/api/chat")]
    msgs = [b if isinstance(b, dict) else _json.loads(b) for b in bodies]
    system = [next(m["content"] for m in b["messages"] if m["role"] == "system") for b in msgs]
    user = [b["messages"][-1]["content"] for b in msgs]
    ctx.check(f"three calls, got {len(msgs)}", len(msgs) == 3)
    ctx.check("the system text is the same every call, the rules sentence in it", len(set(system)) == 1
              and "The rule:" in system[0])
    ctx.check("round 2 of a question starts with round 1's prompt, byte for byte", user[1].startswith(user[0]))
    front = user[0].split("Calls per model")[0]  # the calls change with every call (the steward's own among them)
    ctx.check(f"a new question keeps the stable sections' bytes in front ({len(front):,} characters)",
              len(front) > 200 and user[2].startswith(front) and "Earlier -- Q: first question?" in user[2][len(front):])
    order = [user[0].find(x) for x in ("Mode:", "Hardware cards:", "Calls per model", "Findings (here", "The last ")]
    ctx.check(f"the stable parts first, the findings and events last, got {order}", -1 not in order and order == sorted(order))
    ctx.check("the budget drops the events first", chat.DROP[0] == "events" and chat.DROP[-1] == "findings")


# ---- 3.6.0.25 T: the tuner (ollama_steward/tuner.py, tuner_notes.py) on the bench's fake -------------------------

TUNER = "ant:tuner-test"


def _script(replies: list, seen: list, cost: float = 0.0012):
    """A tuner that answers `replies` round by round (then {"done"}), recording what each round was sent."""
    import json

    def call(model, system, user, *, state_dir=None):
        seen.append({"model": model, "system": system, "user": user})
        r = replies[len(seen) - 1] if len(seen) <= len(replies) else {"done": "finished"}
        return {"text": json.dumps(r), "input_tokens": 1000, "output_tokens": 50, "cost_usd": cost, "local": False}
    return call


def _bench_rig():
    from tests.helpers.bench_rig import BenchRig
    return BenchRig(["sw-up:8b"])


def _mem(rig):
    def read():
        used = sum(int(e.get("size_vram") or 0) for e in (rig.mock.ps_response or {}).get("models") or [])
        return {"used": used, "free": 24 * 2 ** 30 - used, "total": 24 * 2 ** 30}
    return read


@test
def test_no_tuner_picked_no_request_and_the_closed_line(ctx: Ctx):
    from halo_harness.ollama_steward import tuner as T
    with _bench_rig() as rig:
        seen: list = []
        got = T.run(rig.state, rig.host, "sw-up:8b", caller=_script([{"done": "x"}], seen))
        ctx.check(f"no tuner: nothing sent, one line, got {got.get('say')!r}", not seen and got["rounds"] == 0
                  and got["say"].startswith("no tuner model is set"))
        n = len(rig.mock.requests)
        off = T.offer(rig.state, rig.host, "sw-up:8b")
        ctx.check(f"the closed line says what a tuner would do, no request, got {off}", off["tuner"] is None
                  and "write a diagnosis, server advice and a guide" in off["line"] and len(rig.mock.requests) == n)


@test
def test_the_tuner_job_proposals_texts_and_what_is_sent(ctx: Ctx):
    import getpass
    from halo_harness.ollama_steward import tuner as T
    from halo_harness.ollama_steward import tuner_notes as N
    from halo_harness.providers.local_sweep_run import sweep
    with _bench_rig() as rig:
        sweep(rig.host, "sw-up:8b", state_dir=rig.state, card=rig.card, start=98304, max_loads=2, sessions=lambda: [],
              memory=_mem(rig))
        off = T.offer(rig.state, rig.host, "sw-up:8b", tuner=TUNER, card=rig.card)
        ctx.check(f"said before: which model, what is sent, the cost, what it writes, got {off}", off["tuner"] == TUNER
                  and off["sends"].endswith("no file path, no host name, no address, no user name")
                  and "(at most 8 rounds)" in off["cost"] and off["writes"].startswith("nothing to the Ollama store")
                  # after the review: each window it asks for is a load, said before
                  and "each window it asks for is a load on fake: Halo unloads what is loaded and puts it back after, "
                      "at most 6 loads" in off["writes"])
        seen: list = []
        replies = [{"tool": "measure", "args": {"window": 65536}}, {"tool": "measure", "args": {"window": 49152}},
                   {"tool": "measure", "args": {"window": 262144}},
                   {"tool": "measure", "args": {"window": 40960, "num_batch": 512}},
                   {"tool": "write", "args": {"kind": "diagnosis", "text": "it spills at its start: the window is too large"}},
                   {"tool": "write", "args": {"kind": "advice", "settings": [
                       {"key": "OLLAMA_KV_CACHE_TYPE", "value": "q8_0", "why": "halves the KV cache"},
                       {"key": "OLLAMA_SCHED_SPREAD", "value": "1", "why": "not a setting it may advise"}]}},
                   {"tool": "write", "args": {"kind": "guide", "best_at": ["short code edits"], "avoid": ["long PDFs"],
                                               "text": "a quick coder"}},
                   {"done": "tuned"}]
        got = T.run(rig.state, rig.host, "sw-up:8b", tuner=TUNER, caller=_script(replies, seen), card=rig.card,
                    memory=_mem(rig))
        ctx.check(f"measured, kept, refused, counted, got {got.get('say')!r}", got["measured"] == 2 and got["kept"] == 1
                  and got["refused"] == 2 and got["dropped"] == 1 and got["rounds"] == 8)
        from halo_harness.providers import local_sweep as S
        rec = S.load(rig.state, rig.host.url, "sw-up:8b")
        ctx.check(f"the proposal became the pick only by the sweep's rule, got {rec['pick']} {rec['why']!r}",
                  rec["pick"] == 65536 and sorted(r["window"] for r in rec["windows"]) == [49152, 65536, 81920, 98304])
        notes = N.read(rig.state, "fake", "sw-up:8b", digest="sha256:sw-up-8b")
        ctx.check(f"the three texts kept with who and when, got {sorted(notes)}", sorted(notes) == ["advice", "diagnosis", "guide"]
                  and all(n["by"] == TUNER and isinstance(n["at"], float) and not n["older_build"] for n in notes.values())
                  and [s["key"] for s in notes["advice"]["settings"]] == ["OLLAMA_KV_CACHE_TYPE"]
                  and notes["advice"]["settings"][0]["server"] and N.by_line(notes["guide"]).startswith(f"written by {TUNER}, "))
        ctx.check(f"its cost at the end, got {got.get('cost')!r}", got["cost"] == "$0.0096" and "cost $0.0096" in got["say"])
        sent = "\n".join(s["system"] + "\n" + s["user"] for s in seen)
        private = [x for x in (rig.host.url, rig.mock.base_url.split("//")[1], str(rig.state), str(rig.home.root), "127.0.0.1",
                               getpass.getuser()) if x and x in sent]
        ctx.check(f"nothing private in what is sent (no path, host, address, user), found {private}",
                  not private and '"window": 65536' in sent and "sw-up:8b" in sent)
        ctx.check("removable", N.remove(rig.state, "fake", "sw-up:8b", "guide")
                  and "guide" not in N.read(rig.state, "fake", "sw-up:8b"))
        other = N.read(rig.state, "fake", "sw-up:8b", digest="sha256:newer")
        ctx.check("another build of the tag: marked, not dropped", other["advice"]["older_build"] is True)


@test
def test_the_tuner_stops_and_runs_eight_rounds_at_most(ctx: Ctx):
    import threading
    from halo_harness.ollama_steward import tuner as T
    with _bench_rig() as rig:
        seen: list = []
        got = T.run(rig.state, rig.host, "sw-up:8b", tuner=TUNER, caller=_script([{"tool": "facts"}] * 20, seen))
        ctx.check(f"eight rounds at most, got {got['rounds']} rounds, {len(seen)} calls", got["rounds"] == 8 and len(seen) == 8)
        stop, seen = threading.Event(), []
        got = T.run(rig.state, rig.host, "sw-up:8b", tuner=TUNER, caller=_script([{"tool": "facts"}] * 20, seen),
                    stop=stop, on_line=lambda s: stop.set() if s.startswith("round 1:") else None)
        ctx.check(f"Stop: no round after it, the cost shown, got {got.get('say')!r}", got["stopped"] and len(seen) == 1
                  and "(stopped)" in got["say"] and "cost $0.0012" in got["say"])


@test
def test_a_tuner_measure_waits_for_an_idle_host(ctx: Ctx):
    """After the check: a window the tuner asks for runs only after the idle-host check (ruling 1), at every proposal:
    a call on the host in the last minute refuses it, counted, nothing loaded; the route refuses a start the same way."""
    from halo_harness.ollama_steward import tuner as T
    from tests.helpers.steward_seed import line
    with _bench_rig() as rig:
        rig.home.calls(line(host={"name": "fake", "url": rig.mock.base_url}, model="other:1b", ago=5))
        seen: list = []
        got = T.run(rig.state, rig.host, "sw-up:8b", tuner=TUNER, caller=_script([{"tool": "measure", "args": {"window": 65536}}], seen),
                    card=rig.card, memory=_mem(rig))
        loads = [x for x in rig.mock.bench_calls if x[0] == "sw-up:8b"]
        ctx.check(f"refused and counted, nothing loaded, the tool says why, got {got.get('say')!r} {len(loads)} loads",
                  got["refused"] == 1 and got["measured"] == 0 and not loads and "answered a call" in seen[-1]["user"])


@test
def test_a_diagnosis_after_a_spilling_start_that_stepped_down(ctx: Ctx):
    """After the check: ruling 10(a) reads the sweep's START, not its smallest window: a start that spilled and stepped
    down to a window on the card keeps the diagnosis; a start on the card refuses it."""
    from halo_harness.ollama_steward import tuner as T
    from halo_harness.providers.local_sweep_run import sweep
    diag = [{"tool": "write", "args": {"kind": "diagnosis", "text": "it spills at its start"}}]
    with _bench_rig() as rig:
        sweep(rig.host, "sw-up:8b", state_dir=rig.state, card=rig.card, start=98304, sessions=lambda: [], memory=_mem(rig))
        got = T.run(rig.state, rig.host, "sw-up:8b", tuner=TUNER, caller=_script(diag, []), card=rig.card)
        ctx.check(f"98,304 spilled, 65,536 on the card: kept, got {got.get('say')!r}", got["refused"] == 0
                  and "diagnosis" in got["texts"])
    with _bench_rig() as rig:
        sweep(rig.host, "sw-up:8b", state_dir=rig.state, card=rig.card, start=32768, max_loads=2, sessions=lambda: [],
              memory=_mem(rig))
        seen: list = []
        got = T.run(rig.state, rig.host, "sw-up:8b", tuner=TUNER, caller=_script(diag, seen), card=rig.card)
        ctx.check(f"a start on the card: refused, got {got.get('say')!r}", got["refused"] == 1 and not got["texts"]
                  and "loads wholly on the card at its start" in seen[-1]["user"])
    with _bench_rig() as rig:  # after the review: no sweep at all, so no start row: refused and counted
        seen = []
        got = T.run(rig.state, rig.host, "sw-up:8b", tuner=TUNER, caller=_script(diag, seen), card=rig.card)
        ctx.check(f"no start row: refused, got {got.get('say')!r} {seen[-1]['user'][-200:]!r}", got["refused"] == 1
                  and not got["texts"] and "no diagnosis is kept" in seen[-1]["user"])


def _scrub_env(user: str):
    import os
    saved = {k: os.environ.get(k) for k in ("USER", "USERNAME", "LOGNAME")}
    for k in saved:
        os.environ[k] = user

    def back():
        for k, v in saved.items():
            if v is None:
                os.environ.pop(k, None)
            else:
                os.environ[k] = v
    return back


@test
def test_the_request_body_with_a_user_named_tag_and_an_error_with_a_path(ctx: Ctx):
    """After the check: the real call (agent.live_call) to the mock upstream for a model whose tag carries the user name
    and whose load fails with an Ollama error that carries a path: neither reaches the request body."""
    import json
    from halo_harness.ollama_steward import tuner as T
    from tests.helpers.bench_rig import BenchRig
    from tests.helpers.mock_ollama import _finish_chat
    back = _scrub_env("tester")
    try:
        with BenchRig(["tester-coder:8b"]) as rig:
            n = [0]

            def scn(h, body):
                n[0] += 1
                say = '{"tool": "measure", "args": {"window": 32768}}' if n[0] == 1 else '{"done": "ok"}'
                _finish_chat(h, [{"message": {"role": "assistant", "content": say}, "done": False},
                                 {"message": {"role": "assistant", "content": ""}, "done": True, "done_reason": "stop",
                                  "prompt_eval_count": 900, "eval_count": 9, "eval_duration": 1000,
                                  "prompt_eval_duration": 1000}])
            rig.mock.scenarios["tuner-mock:1b"] = scn
            rig.mock.tags_response["models"].append({"name": "tuner-mock:1b", "model": "tuner-mock:1b", "size": 1000,
                                                     "digest": "sha256:tm", "details": {"family": "qwen3"}})
            rig.mock.show_responses["tuner-mock:1b"] = {"capabilities": ["completion"], "details": {"family": "qwen3"},
                                                        "model_info": {"qwen3.context_length": 32768}}
            got = T.run(rig.state, rig.host, "tester-coder:8b", tuner="ol:tuner-mock:1b@fake", card=rig.card)
            sent = "\n".join(json.dumps(r.get("body"), ensure_ascii=False) for r in rig.mock.requests
                             if r.get("path") == "/api/chat" and (r.get("body") or {}).get("model") == "tuner-mock:1b")
    finally:
        back()
    leaks = [x for x in ("tester", "/data/", "blobs") if x in sent]
    ctx.check(f"two rounds, the failed load's answer sent scrubbed, got {got.get('say')!r}, leaks {leaks}",
              got["rounds"] == 2 and "<name>-coder:8b" in sent and "did not load" in sent and "<path>" in sent and not leaks)
    # after the review: the reviewer's probes through the same real call: a tag behind a LAN registry, a user name with
    # a space inside the Windows path of the error, and an /api/ path that is no Ollama endpoint
    from tests.helpers import mock_ollama_bench as MB
    reg = "nas.lan:5000/team/tester-coder:8b"
    MB.SWEEP[reg] = {**MB.spec("tester-coder:8b"), "fail": SPACED_ERR + " (see /api/home/someone/x)"}
    back = _scrub_env("Pat Tester")
    try:
        with BenchRig([reg]) as rig:
            n = [0]
            rig.mock.scenarios["tuner-mock:1b"] = scn
            rig.mock.tags_response["models"].append({"name": "tuner-mock:1b", "model": "tuner-mock:1b", "size": 1000,
                                                     "digest": "sha256:tm", "details": {"family": "qwen3"}})
            rig.mock.show_responses["tuner-mock:1b"] = {"capabilities": ["completion"], "details": {"family": "qwen3"},
                                                        "model_info": {"qwen3.context_length": 32768}}
            got = T.run(rig.state, rig.host, reg, tuner="ol:tuner-mock:1b@fake", card=rig.card)
            sent = "\n".join(json.dumps(r.get("body"), ensure_ascii=False) for r in rig.mock.requests
                             if r.get("path") == "/api/chat" and (r.get("body") or {}).get("model") == "tuner-mock:1b")
    finally:
        back()
        MB.SWEEP.pop(reg, None)
    leaks = [x for x in ("Pat", "Tester", "tester", "nas.lan", ":5000", "profiles", "blobs", "someone") if x in sent]
    ctx.check(f"the probes through the real call: two rounds, scrubbed, got {got.get('say')!r}, leaks {leaks}",
              got["rounds"] == 2 and "<address>/team/<name>-coder:8b" in sent and "did not load" in sent and not leaks)


@test
def test_the_request_body_on_the_mock_upstream_holds_nothing_private(ctx: Ctx):
    """The real call (agent.live_call) to a tuner on the tests' mock upstream: the request body the upstream got."""
    import getpass
    import json
    from halo_harness.ollama_steward import tuner as T
    from tests.helpers.mock_ollama import _finish_chat
    with _bench_rig() as rig:
        def scn(h, body):
            _finish_chat(h, [{"message": {"role": "assistant", "content": '{"done": "nothing to add"}'}, "done": False},
                             {"message": {"role": "assistant", "content": ""}, "done": True, "done_reason": "stop",
                              "prompt_eval_count": 900, "eval_count": 9, "eval_duration": 1000, "prompt_eval_duration": 1000}])
        rig.mock.scenarios["tuner-mock:1b"] = scn
        rig.mock.tags_response["models"].append({"name": "tuner-mock:1b", "model": "tuner-mock:1b", "size": 1000,
                                                 "digest": "sha256:tm", "details": {"family": "qwen3", "parameter_size": "1B"}})
        rig.mock.show_responses["tuner-mock:1b"] = {"capabilities": ["completion"], "details": {"family": "qwen3"},
                                                    "model_info": {"qwen3.context_length": 32768}}
        got = T.run(rig.state, rig.host, "sw-up:8b", tuner="ol:tuner-mock:1b@fake", card=rig.card)
        bodies = [json.dumps(r.get("body"), ensure_ascii=False) for r in rig.mock.requests
                  if r.get("path") == "/api/chat" and (r.get("body") or {}).get("model") == "tuner-mock:1b"]
        sent = "\n".join(bodies)
        private = [x for x in (rig.mock.base_url.split("//")[1], str(rig.state), str(rig.home.root), "127.0.0.1",
                               getpass.getuser()) if x and x in sent]
        ctx.check(f"one round, the body carries the facts and nothing private, got {got.get('say')!r} {len(bodies)} "
                  f"bodies, found {private}", got["rounds"] == 1 and len(bodies) == 1 and "sw-up:8b" in sent
                  and "The facts:" in sent and not private)


@test
def test_the_scrub(ctx: Ctx):
    import os
    from halo_harness.ollama_steward.tuner import scrub
    from halo_harness.providers.ollama import OllamaHost
    saved = {k: os.environ.get(k) for k in ("USER", "USERNAME")}
    os.environ["USER"] = os.environ["USERNAME"] = "pat-tester"
    try:
        host = OllamaHost(name="gpu-box", url="http://gpu-box.lan:11434")
        got = scrub("pat-tester loads D:\\models\\blobs\\sha256-ab from /opt/ollama/models and ~/models on gpu-box "
                    "(gpu-box.lan, http://gpu-box.lan:11434/api/ps, 192.0.2.10:11434, 2001:db8::1, \\\\share\\x) prologue",
                    host)
    finally:
        for k, v in saved.items():
            if v is None:
                os.environ.pop(k, None)
            else:
                os.environ[k] = v
    leaks = [x for x in ("pat-tester", "models\\blobs", "/opt/", "~/models", "gpu-box", "192.0.2", "2001:db8", "share")
             if x in got]
    ctx.check(f"no user, path, host or address left, got {got!r} (leaks {leaks})", not leaks and "prologue" in got
              and got.count("<path>") >= 3 and got.count("<address>") >= 3)
    # after the check: a name next to '-' or '_' (a model tag), a host name with a digit after it, any absolute POSIX
    # path, an address after a word character, an Ollama error that carries a path
    back = _scrub_env("pat")
    try:
        host = OllamaHost(name="gpu-box", url="http://gpu-box.lan:11434")
        cases = {"pat-coder:latest": "<name>-coder:latest", "pat_coder:latest": "<name>_coder:latest",
                 "qwen3:8b-gpu-box": "qwen3:8b-<name>", "gpu-box2": "<name>2", "PAT-coder": "<name>-coder",
                 "/data/ollama/models/blobs/sha256-ab": "<path>", "/run/media/disk/x": "<path>", "/models/blobs/x": "<path>",
                 "x_10.1.2.3": "x_<address>", "x_C:\\models\\a": "x_<path>",
                 "open /data/ollama/models/blobs/sha256-ab12: no such file": "open <path> no such file",
                 "patch the compat layer, 120 tok/s, /api/ps did not answer": "patch the compat layer, 120 tok/s, /api/ps did not answer"}
        got = {k: scrub(k, host) for k in cases}
    finally:
        back()
    wrong = {k: v for k, v in got.items() if v != cases[k]}
    ctx.check(f"every case scrubbed, nothing else touched, wrong {wrong}", not wrong)
    # after the review: a user name with a space inside a Windows path (the path pass stops at the space), each part
    # of such a name alone, a registry or LAN host in front of a model tag, and an /api/ path that is no Ollama endpoint
    back = _scrub_env("Pat Tester")
    try:
        host = OllamaHost(name="gpu-box", url="http://gpu-box.lan:11434")
        cases = {SPACED_ERR: "Error: open <path> The system cannot find the file",
                 "/srv/Pat Tester/models/x: gone": "<path> gone", "Tester said so, and pat": "<name> said so, and <name>",
                 "registry.corp.example:5000/team/model:latest": "<address>/team/model:latest",
                 "model nas.lan:5000/team/coder:latest": "model <address>/team/coder:latest",
                 "hf.co/someone/Qwen-GGUF:Q4": "hf.co/someone/Qwen-GGUF:Q4",
                 "/api/home/someone/x": "<path>", "/api/someonex/y": "<path>",
                 "/api/ps and /api/tags did not answer": "/api/ps and /api/tags did not answer",
                 "llama3.1:8b, 120 tok/s, 1.5/2": "llama3.1:8b, 120 tok/s, 1.5/2"}
        got = {k: scrub(k, host) for k in cases}
    finally:
        back()
    wrong = {k: v for k, v in got.items() if v != cases[k]}
    ctx.check(f"a spaced name, a host in a tag, a non-endpoint /api/ path scrubbed, wrong {wrong}", not wrong)


SPACED_ERR = "Error: open D:\\profiles\\Pat Tester\\.ollama\\models\\blobs\\sha256-1: The system cannot find the file"


if __name__ == "__main__":
    ctx = Ctx()
    results, passed, failed, skipped = run_all(TESTS, ctx)
    sys.exit(print_results(results, passed, failed, skipped))
