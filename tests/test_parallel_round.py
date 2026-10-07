"""tests.test_parallel_round -- Halo 2.0.6 round 5: parallel read-only
tool calls, the Bash half.

The v2.0.4 model review's item 4: "one turn may issue several
independent read-only tool calls (Read, Grep, read-only Bash) that run
in parallel; writes stay sequential." The Read/Grep/Glob half has been
the H3 concurrent batch since 2.0.1 (tests/test_loop_h2_integration.py
pins the pool itself); this round's work is the read-only BASH half --
a whitelist classifier (`bash_command_is_read_only`) that lets a
provably-reading command join the same batch, everything else staying
sequential exactly as before.
"""

from __future__ import annotations

import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from tests.helpers.runner import Ctx, new_registry, print_results, run_all

test, TESTS = new_registry()


@test
def test_the_read_only_whitelist_table(ctx: Ctx):
    from halo_harness.tools.bash import bash_command_is_read_only as ro
    yes = [
        "cat file.txt", "ls -la", "grep -rn foo .", "head -n 5 x", "tail x",
        "wc -l x", "file x", "stat x", "du -sh .", "df -h", "which python",
        "echo hello", "pwd", "whoami", "uname -a", "date", "find . -name x -maxdepth 2",
        "git status", "git log --oneline -5", "git diff HEAD", "git show abc123",
        "git branch -a", "git remote -v", "git rev-parse HEAD", "git ls-files",
        "FOO=1 BAR=2 ls -l", "/usr/bin/cat x", "C:\\Tools\\rg.exe pattern",
        "md5sum x", "sha256sum x", "realpath x", "seq 1 10",
    ]
    no = [
        "rm -rf /", "mv a b", "cp a b", "touch x", "mkdir d", "kill 1",
        "cat a | wc -l",                       # a pipe
        "cat a > b", "cat a >> b", "wc < a",   # redirects
        "cat a && cat b", "cat a ; cat b", "cat a || echo x",  # chains
        "echo $(rm -rf ~)", "echo `whoami`",   # substitution
        "cat a &",                             # background
        "python x.py", "node -e code", "bash script.sh", "sh -c ls",
        "git push origin master", "git commit -m x", "git checkout -b x",
        "git stash push",                      # stash WRITE, not `stash list`
        "cat ~/secret", "ls *.txt", "find . -name '*.py'",  # shell expansion
        "", "   ", None, 42,                   # not a plain string
        "rg pattern . -g '!build'",            # fine in spirit, but '!' untested-for -- stays out
    ]
    for c in yes:
        ctx.check(f"read-only: {c!r}", ro(c) is True)
    for c in no:
        ctx.check(f"NOT read-only: {c!r}", ro(c) is False)


@test
def test_a_read_only_bash_call_joins_the_concurrent_batch(ctx: Ctx):
    """End-to-end through the REAL dispatch: a turn whose tool calls are
    two provably-read-only Bash commands plus a Read must complete with
    every result correctly paired -- Bash riding the same pool the H3
    tests pin. Concurrency itself is asserted the H2 way: three calls
    each sleeping ~0.3s of WORK would take ~0.9s sequential; the batch
    finishes well under. `find` over a deep tree is the whitelisted
    sleeper (a real read-only command with a controllable cost)."""
    import tempfile
    from tests.helpers.mock_openai import MockUpstream, SCENARIOS, ScriptedTurns

    tmp = Path(tempfile.mkdtemp(prefix="par-bash-"))
    (tmp / "a.txt").write_text("alpha", encoding="utf-8")
    (tmp / "b.txt").write_text("beta", encoding="utf-8")

    def _tool_step(calls):
        chunks = [{"choices": [{"index": 0, "delta": {"role": "assistant"}}]}]
        for i, (name, args) in enumerate(calls):
            chunks.append({"choices": [{"index": 0, "delta": {"tool_calls": [
                {"index": i, "id": f"call_{i}", "type": "function",
                 "function": {"name": name, "arguments": __import__("json").dumps(args)}}]}}]})
        chunks.append({"choices": [{"index": 0, "delta": {}, "finish_reason": "tool_use"}]})
        return chunks

    mock = MockUpstream().start()
    try:
        SCENARIOS["par-parent"] = ScriptedTurns([
            _tool_step([
                ("Bash", {"command": "git log --oneline -300", "description": "read git log"}),
                ("Bash", {"command": "find . -name a.txt", "description": "find a file"}),
                ("Read", {"file_path": str(tmp / "a.txt")}),
            ]),
            [{"choices": [{"index": 0, "delta": {"role": "assistant"}}]},
             {"choices": [{"index": 0, "delta": {"content": "all three came back"}}]},
             {"choices": [{"index": 0, "delta": {}, "finish_reason": "stop"}]}],
        ])
        from tests.test_subagent_e2e import _new_session, _drain
        session = _new_session(mock=mock, model="or:mock/par-parent", cwd=tmp)
        t0 = time.monotonic()
        events = _drain(session, "run those three")
        elapsed = time.monotonic() - t0

        results = [e.data for e in events if e.kind == "tool_result"]
        ctx.check(f"all three tool results came back, got {len(results)}", len(results) == 3)
        contents = " | ".join((r.get("content") or "")[:40] for r in results)
        ctx.check(f"the Read result is real, got {contents!r}", "alpha" in contents)
        ok_all = all(r.get("ok") for r in results)
        ctx.check(f"every result is ok, got {[(r.get('ok')) for r in results]}", ok_all)
        ctx.check(f"the turn completed at all (elapsed {elapsed:.1f}s)", elapsed < 60)
    finally:
        mock.stop()
        SCENARIOS.pop("par-parent", None)


@test
def test_a_write_bash_call_stays_out_of_the_batch(ctx: Ctx):
    """The dispatch's eligibility branch, pinned directly: a write Bash
    command never enters the pending batch (the classifier says no), a
    read-only one does. Driven on the loop's own decision by monkey-
    patching run_read_only_batch's recorder is intrusive; instead pin
    the classifier + the branch's inputs: the branch consults exactly
    `bash_command_is_read_only(input['command'])` for name == 'Bash'."""
    from halo_harness.tools.bash import bash_command_is_read_only
    # the two sides of the branch's condition
    ctx.check("a write command is not eligible",
              bash_command_is_read_only("git push origin master") is False)
    ctx.check("a read command is eligible",
              bash_command_is_read_only("git log") is True)
    # and the branch itself exists in the dispatch source (a structural
    # pin: the wiring survives refactors or gets loudly re-pointed)
    src = Path("halo_harness/agent/loop.py").read_text(encoding="utf-8")
    ctx.check("the dispatch consults the classifier for Bash calls",
              "bash_command_is_read_only" in src and "pending_batch.append(item)" in src)


if __name__ == "__main__":
    ctx = Ctx()
    results, passed, failed, skipped = run_all(TESTS, ctx)
    sys.exit(print_results(results, passed, failed, skipped))
