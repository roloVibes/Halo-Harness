"""tests.test_policy_proc_deadline -- the policy pipe has a deadline (Halo 3.3.14.0 R2, REVIEW #12 PERMS-6;
packs/policy_proc.py):

1. a stub policy that never reads its stdin, asked with a 2 MB request: the call returns at the budget (plus a little),
   says "policy did not answer in <n>s", and the process is ended;
2. the next call starts it again (a fresh process) and, with a policy that answers, works;
3. a small request to a policy that answers is unchanged.
No pack is installed: PolicyProcess runs a stub program from a scratch folder.
Run: python -m tests.test_policy_proc_deadline"""
from __future__ import annotations

import os
import sys
import tempfile
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from tests.helpers.runner import Ctx, new_registry, print_results, run_all  # noqa: E402

test, TESTS = new_registry()
STUB = """import json, os, sys, time
flag = os.path.join(os.path.dirname(os.path.abspath(__file__)), "deaf.flag")
if os.path.exists(flag):
    os.remove(flag)
    time.sleep(60)  # never reads its input
for raw in sys.stdin:
    req = json.loads(raw)
    print(json.dumps({"id": req["id"], "decision": "allow"}), flush=True)
"""


def _env() -> dict:
    return {k: v for k, v in os.environ.items() if not k.startswith(("OPENROUTER_", "ANTHROPIC_", "DATABRICKS_"))}


@test
def test_a_policy_that_stops_reading_is_ended_at_the_budget(ctx: Ctx):
    from halo_harness.packs.policy_proc import PolicyProcess
    d = Path(tempfile.mkdtemp(prefix="policy-deaf-"))
    (d / "stub.py").write_text(STUB, encoding="utf-8")
    (d / "deaf.flag").write_text("x", encoding="utf-8")
    p = PolicyProcess([sys.executable, str(d / "stub.py")], cwd=d, env=_env(), label="deaf")
    try:
        t0 = time.monotonic()
        answer, why, _ms = p.ask({"tool": "Write", "input": {"content": "x" * 2_000_000}}, budget_s=0.5)
        took = time.monotonic() - t0
        ctx.check(f"it returns at the budget, took {took:.2f}s", took < 0.5 + 2.5)
        ctx.check(f"the one line, got {why!r}", answer is None and why.startswith("policy did not answer in 0.5s"))
        ctx.check("the process is ended", p.proc is None)
        answer, why, _ms = p.ask({"tool": "Read", "input": {"file_path": "a"}}, budget_s=5.0)
        ctx.check(f"the next call starts it again and works, got {answer} {why!r}", answer is not None
                  and answer.get("decision") == "allow" and p.started == 2)
        answer, why, _ms = p.ask({"tool": "Read", "input": {"file_path": "b"}}, budget_s=5.0)
        ctx.check("and the one after on the same process", answer is not None and p.started == 2)
    finally:
        p.stop()
        import shutil
        shutil.rmtree(d, ignore_errors=True)


if __name__ == "__main__":
    ctx = Ctx()
    results, passed, failed, skipped = run_all(TESTS, ctx)
    sys.exit(print_results(results, passed, failed, skipped))
