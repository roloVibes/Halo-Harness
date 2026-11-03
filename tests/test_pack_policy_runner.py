"""tests.test_pack_policy_runner -- the policy hook runner and the dry run (Halo 3.3.10.0 R1; packs/policy.py,
packs/policy_proc.py, packs/cli_policy.py; docs/EXTENSION_API.md "Policy hooks", draft). The fixture's `run`
(tests/fixtures/packs/policy-fence/policy/fence.py) is a real subprocess speaking the protocol over stdin/stdout on
this machine; a slow answer comes from its HALO_POLICY_TEST_SLOW_MS seam, never a sleep here:

1. armed(): only a running pack with hooks granted, armed in mode.json, its when.modes taking the mode;
2. one process answers every request (one spawn), deny outside the project, allow inside, the pack's reason/rule;
3. when.tools filters a call before the process: not asked, not logged;
4. the budget: a late answer is on_error (deny here) with a logged line, and dropped when it arrives;
5. a malformed answer, a process that ends, a command that does not start: on_error, said in one line;
6. redact: a named variable's value never reaches the process; every verdict and error is a `policy` row, without
   the input; winner(): deny over ask over allow; disarming stops the process;
7. `halo pack policy test`: the verdict line with its time, arms nothing, the process stopped after.
Run: python -m tests.test_pack_policy_runner
"""

from __future__ import annotations

import dataclasses
import json
import os
import sys
from contextlib import contextmanager
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from tests.helpers.packs_home import PacksHome  # noqa: E402
from tests.helpers.runner import Ctx, new_registry, print_results, run_all  # noqa: E402

test, TESTS = new_registry()
LONG = 30000  # ms: a budget no healthy answer comes near, on the slowest runner


@contextmanager
def fenced(**env):
    """A home with policy-fence installed, enabled with hooks and its mode on; `env` (HALO_POLICY_TEST_*: the
    fixture's seams) set for its process -- inside the home, which takes every HALO_* variable back on exit."""
    from halo_harness.packs import mode_state as M
    from halo_harness.packs import policy as P
    with PacksHome() as h:
        os.environ.update({k: str(v) for k, v in env.items()})
        h.install(h.source("policy-fence"), enable=True, grants=["hooks"])
        M.set_mode("policy-fence", "fenced", True)
        try:
            yield h, P.armed(cwd=h.repo)[0]
        finally:
            P.stop_all()


def _ask(h, pol, tool, data, *, budget=LONG, agent=""):
    from halo_harness.packs import policy as P
    return P.ask(pol, P.request(pol, tool, data, cwd=h.repo, session="s-1", agent=agent, mode="fenced"), budget_ms=budget)


@test
def test_armed_needs_the_pack_running_the_grant_the_record_and_the_mode(ctx: Ctx):
    from halo_harness.packs import mode_state as M
    from halo_harness.packs import policy as P
    from halo_harness.packs.grants import enable_id, grant
    with PacksHome() as h:
        h.install(h.source("policy-fence"))
        M.set_mode("policy-fence", "fenced", True)
        ctx.check("installed, disabled: nothing armed", P.armed(cwd=h.repo) == [])
        enable_id("policy-fence", cwd=h.repo)
        ctx.check("enabled without hooks: nothing armed", P.armed(cwd=h.repo) == [])
        grant("policy-fence", ["hooks"], cwd=h.repo)
        got = P.armed(cwd=h.repo)
        ctx.check(f"with hooks and the mode on: fence, got {got}", [p.id for p in got] == ["fence"] and got[0].on_error == "deny"
                  and got[0].tools == ("Write", "Edit") and got[0].modes == ("fenced",))
        M.set_mode("policy-fence", "fenced", False)
        M.arm("policy-fence", "fence")
        ctx.check("armed but its mode is off: not answering", P.armed(cwd=h.repo) == [])


@test
def test_one_process_answers_with_the_packs_words(ctx: Ctx):
    with fenced() as (h, pol):
        from halo_harness.packs import policy as P
        v = _ask(h, pol, "Write", {"file_path": "/tmp/x", "content": "hello"})
        ctx.check(f"outside the project: deny, the pack's reason and rule, got {v}", v.action == "deny"
                  and v.reason == "outside the project" and v.rule == "outside-project" and v.scope == "session"
                  and v.source == "pack:policy-fence/fence" and not v.error and v.asked)
        ctx.check(f"the line, got {v.line()!r}", v.line() == f"deny -- fence: outside the project ({v.ms} ms)")
        proc = P.process(pol)
        pid = proc.pid
        v2 = _ask(h, pol, "Edit", {"file_path": "src/app.py"})
        v3 = _ask(h, pol, "Write", {"file_path": str(h.repo / "notes.txt")})
        ctx.check(f"inside: allow, got {v2.action} {v3.action}", v2.action == v3.action == "allow" and v2.rule == "inside-project")
        ctx.check(f"one spawn for three requests, got {proc.started}", proc.started == 1 and proc.pid == pid and proc.alive)


@test
def test_when_tools_filters_before_the_process(ctx: Ctx):
    from halo_harness.packs.events_log import since
    with fenced() as (h, pol):
        from halo_harness.packs import policy as P
        before = {k: p.started for k, p in P._procs.items()}  # R2: a session process starts it as it is armed
        v = _ask(h, pol, "Read", {"file_path": "/etc/hosts"})
        ctx.check(f"not named: allow, not asked, got {v}", v.action == "allow" and not v.asked and v.ms == 0)
        ctx.check("the ask started no process, nothing logged",
                  {k: p.started for k, p in P._procs.items()} == before and since("policy-fence:policy") == [])
        star = dataclasses.replace(pol, tools=("*",))
        ctx.check("* names every tool", P.matches(star, "Read") and P.matches(dataclasses.replace(pol, tools=()), "Bash"))


@test
def test_a_late_answer_is_on_error_and_dropped_when_it_comes(ctx: Ctx):
    from halo_harness.packs.events_log import since
    with fenced(HALO_POLICY_TEST_SLOW_MS=1500) as (h, pol):
        from halo_harness.packs import policy as P
        v = _ask(h, pol, "Write", {"file_path": str(h.repo / "a.txt")}, budget=200)
        ctx.check(f"the budget passes: on_error deny with what happened, got {v}", v.action == "deny" and v.rule == "on_error"
                  and v.error == "no answer within 200 ms" and v.reason == "on_error deny (no answer within 200 ms)")
        v2 = _ask(h, pol, "Write", {"file_path": "/tmp/y"})
        proc = P.process(pol)
        ctx.check(f"the next request gets its own answer, the late one dropped, got {v2} dropped={proc.dropped}",
                  v2.action == "deny" and v2.rule == "outside-project" and proc.dropped == 1 and proc.started == 1)
        rows = [r["data"] for r in since("policy-fence:policy")]
        ctx.check(f"both logged, the error with its line, got {rows}", len(rows) == 2 and rows[0]["error"] == "no answer within 200 ms"
                  and rows[0]["verdict"] == "deny" and "error" not in rows[1] and rows[1]["rule"] == "outside-project")


@test
def test_a_malformed_answer_and_a_process_that_ends(ctx: Ctx):
    with fenced(HALO_POLICY_TEST_BAD=1) as (h, pol):
        v = _ask(h, pol, "Write", {"file_path": "/tmp/x"})
        ctx.check(f"not JSON: on_error, got {v}", v.action == "deny" and v.error.startswith("a malformed answer (not JSON)"))
        allow = dataclasses.replace(pol, on_error="allow")
        from halo_harness.packs import policy as P
        v = P.ask(allow, P.request(allow, "Write", {"file_path": "/tmp/x"}, cwd=h.repo), budget_ms=LONG, keep=False)
        ctx.check(f"on_error allow (the default) answers allow, got {v}", v.action == "allow" and v.reason.startswith("on_error allow ("))
    with fenced(HALO_POLICY_TEST_EXIT=1) as (h, pol):
        from halo_harness.packs import policy as P
        v = _ask(h, pol, "Write", {"file_path": "/tmp/x"})
        ctx.check(f"the process ends before it answers: on_error, said with its exit, got {v}", v.action == "deny"
                  and v.error.startswith("the process ended") and "exit 3" in v.error)
        v2 = _ask(h, pol, "Write", {"file_path": "/tmp/x"})
        ctx.check(f"the next request starts it again, got {P.process(pol).started}", v2.error and P.process(pol).started == 2)
    with fenced() as (h, pol):
        from halo_harness.packs import policy as P
        gone = dataclasses.replace(pol, argv=(str(h.home / "no-such-program"),))
        v = P.ask(gone, P.request(gone, "Write", {"file_path": "/tmp/x"}, cwd=h.repo), budget_ms=LONG, keep=False)
        ctx.check(f"a command that does not start: on_error, one line, got {v}", v.action == "deny" and v.error.startswith("it did not start: "))
        (h.packs / "policy-fence" / "policy" / "fence.py").unlink()
        v = _ask(h, pol, "Write", {"file_path": "/tmp/x"})
        ctx.check(f"its script gone: the interpreter ends, on_error, got {v}", v.action == "deny" and v.error.startswith("the process ended"))


@test
def test_redact_the_log_winner_and_stop(ctx: Ctx):
    from halo_harness.packs import mode_state as M
    from halo_harness.packs.events_log import log_path, since
    secret = "plain-value-for-the-redact-test"
    os.environ["PP_POLICY_TEST_VALUE"] = secret
    try:
        with fenced(HALO_POLICY_TEST_ECHO=1) as (h, pol):
            from halo_harness.packs import policy as P
            red = dataclasses.replace(pol, redact=("PP_POLICY_TEST_VALUE", "PP_NOT_SET"))
            v = _ask(h, red, "Write", {"file_path": "a.txt", "content": f"token={secret}", "list": [secret]}, agent="worker-2")
            seen = json.loads(v.reason)
            ctx.check(f"the value never reached the process, its name did, got {seen}", secret not in v.reason
                      and seen["content"] == "token=[redacted:PP_POLICY_TEST_VALUE]" and seen["list"] == ["[redacted:PP_POLICY_TEST_VALUE]"])
            row = since("policy-fence:policy")[-1]["data"]
            ctx.check(f"the row: the call, not its input; the sub-agent named, got {row}", row["tool"] == "Write"
                      and row["agent"] == "worker-2" and row["session"] == "s-1" and "input" not in row)
            ctx.check("the value is nowhere in the events log (this echoing fixture's reason holds the redacted input)",
                      secret not in log_path("policy-fence").read_text(encoding="utf-8"))
            ctx.check("redact of nothing set: the input as it is", P.redact({"a": "b"}, ["PP_NOT_SET"]) == {"a": "b"})
            mk = lambda a: P.Verdict(a, a, pack=a)  # noqa: E731
            ctx.check("winner: deny over ask over allow, the first among equals",
                      P.winner([mk("allow"), mk("ask"), mk("deny")]).action == "deny" and P.winner([mk("allow"), mk("ask")]).action == "ask"
                      and P.winner([]) is None)
            _ask(h, pol, "Write", {"file_path": "a.txt"})
            proc = P.process(pol)
            ctx.check("its process runs", proc.alive)
            M.disarm("policy-fence", "fence")
            ctx.check("disarmed: the process is stopped", not proc.alive and P._procs == {})
    finally:
        os.environ.pop("PP_POLICY_TEST_VALUE", None)


@test
def test_the_budget_setting(ctx: Ctx):
    from halo_harness.packs import policy as P
    with PacksHome() as h:
        ctx.check("unset: 2000", P.default_budget_ms() == 2000)
        h.config({"packs": {"policy": {"budget_ms": 500}}})
        ctx.check("packs.policy.budget_ms", P.default_budget_ms() == 500)
        h.config({"packs": {"policy": {"budget_ms": "soon"}}})
        ctx.check("not a whole number: 2000", P.default_budget_ms() == 2000)
    from halo_harness.settings_catalog import row
    r = row("packs.policy.budget_ms")
    ctx.check("a Settings row (Packs)", r is not None and r.default == 2000 and r.group == "packs" and r.kind == "int")


@test
def test_the_dry_run(ctx: Ctx):
    from halo_harness.packs import mode_state as M
    from halo_harness.packs import policy as P
    with PacksHome() as h:
        h.install(h.source("policy-fence"))
        code, out, err = h.cli("policy", "test", "policy-fence", "fence", "Write", '{"file_path": "/tmp/x"}', "--budget-ms", str(LONG))
        lines = out.splitlines()
        ctx.check(f"a disabled pack: the verdict all the same, got {code} {out!r} {err!r}", code == 0
                  and lines[0].startswith("deny -- fence: outside the project (") and lines[0].endswith(" ms)")
                  and lines[1] == "  rule: outside-project; scope: session")
        ctx.check("it says what a session needs", any("only while mode fenced is on (the mode now: none)" in ln for ln in lines)
                  and any("halo pack enable policy-fence --grant hooks" in ln for ln in lines))
        ctx.check("it armed nothing, kept no process", M.read("policy-fence") == M.empty() and P._procs == {})
        code, out, _ = h.cli("policy", "test", "policy-fence", "fence", "Read", '{"file_path": "/tmp/x"}', "--json")
        data = json.loads(out)
        ctx.check(f"a tool when.tools does not name: not asked, got {data['verdict']}", code == 0
                  and data["verdict"]["asked"] is False and data["verdict"]["action"] == "allow")
        code, _out, err = h.cli("policy", "test", "policy-fence", "gate", "Write", "{}")
        ctx.check(f"an undeclared policy: one line, exit 1, got {err!r}",
                  code == 1 and err.strip() == "halo pack: policy-fence declares no policy 'gate' (contributes.policy: fence)")
        code, _out, err = h.cli("policy", "test", "policy-fence", "fence", "Write", "{not json")
        ctx.check(f"input that is not JSON: one line, got {err!r}", code == 1 and "the tool input is not JSON" in err)
        code, _out, err = h.cli("policy", "test", "policy-fence", "fence", "Write")
        ctx.check(f"too few arguments: usage, exit 2, got {code}", code == 2 and "<tool> '<json input>'" in err)


if __name__ == "__main__":
    ctx = Ctx()
    results, passed, failed, skipped = run_all(TESTS, ctx)
    sys.exit(print_results(results, passed, failed, skipped))
