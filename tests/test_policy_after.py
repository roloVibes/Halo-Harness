"""tests.test_policy_after -- the post-call verdict (Halo 3.3.10.0 R2; packs/policy_after.py, agent/policy_gate.py
`after`; docs/EXTENSION_API.md "Policy hooks"). The `policy-fence` fixture with `after: true` (its copy's pack.yaml),
a real process; its HALO_POLICY_TEST_REDACT / _DROP seams answer redact or drop, _SLOW_MS a late answer:

1. redact: the model and the transcript see the pack's result; the audit row keeps the sha256 of the original;
2. drop: the result is the pack's line;
3. the budget and on_error: a late answer is on_error (deny reads as drop, allow as pass), with the error said;
4. a policy without `after`, or a tool `when.tools` does not name, is not asked after the call.
Run: python -m tests.test_policy_after
"""

from __future__ import annotations

import dataclasses
import sys
from pathlib import Path
from types import SimpleNamespace

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from tests.helpers.policy_session import Upstream, fenced_home, policy_rows, session_in  # noqa: E402
from tests.helpers.runner import Ctx, new_registry, print_results, run_all  # noqa: E402
from tests.helpers.turn_session import request_text, text_step, tool_step  # noqa: E402

test, TESTS = new_registry()
WORD = "PINEAPPLE-7731"


def _gate_after(h, content, *, budget_ms=None):
    """The gate's `after` on one finished Read whose result is `content` (no model, no tool)."""
    from halo_harness import theme
    from halo_harness.agent import policy_gate as G
    from halo_harness.tools.base import ToolResult
    if budget_ms is not None:
        theme.set_config_value("packs.policy.budget_ms", budget_ms)
    s = SimpleNamespace(cwd=h.repo, agent_id=None, log=SimpleNamespace(session_id="s-after"),
                        permission_engine=SimpleNamespace(mode="default"))
    item = {"name": "Read", "input": {"file_path": str(h.repo / "a.txt")}}
    return G.after(s, item, ToolResult(content, duration_ms=12.0)), item


@test
def test_redact_the_model_sees_the_packs_result_the_audit_keeps_the_hash(ctx: Ctx):
    from halo_harness.packs.policy_after import digest
    with fenced_home(after=True, HALO_POLICY_TEST_REDACT=WORD) as h:
        (h.repo / "notes.txt").write_text(f"the code is {WORD} today\n", encoding="utf-8")
        with Upstream("pa-redact", [tool_step("Read", {"file_path": str(h.repo / "notes.txt")}), text_step("ok")]) as up:
            s = session_in(h, up)
            evs = list(s.turn("read the notes"))
            reqs = up.requests
        sent = request_text(reqs[1]) if len(reqs) > 1 else ""
        ctx.check("the model sees the redacted result", "[held]" in sent and WORD not in sent)
        node = next(n for n in s.log.nodes() if n.get("type") == "tool_result")
        ctx.check("the transcript keeps the redacted one", WORD not in str(node.get("content")) and "[held]" in str(node.get("content")))
        res = [e for e in evs if e.kind == "tool_result"][0]
        ctx.check(f"the tool line, got {(res.data.get('policy') or {}).get('line')!r}", (res.data.get("policy") or {}).get("line")
                  == "policy: allow -- fence: not a write; policy after: redact -- fence: a held word was taken out")
        row = policy_rows("after")[-1]
        ctx.check(f"the audit row: redact, the rule, a sha256, got {row}", row["verdict"] == "redact" and row["rule"] == "redact-word"
                  and str(row.get("sha256", "")).startswith("sha256:") and len(row["sha256"]) == 71 and WORD not in str(row))
        out, item = _gate_after(h, f"one {WORD} two")
        ctx.check("the gate keeps the pack's result", out.content == "one [held] two")
        ctx.check("the hash is the original's", item["policy"][-1]["sha256"] == digest(f"one {WORD} two")
                  == policy_rows("after")[-1]["sha256"])


@test
def test_drop_the_result_is_the_packs_line(ctx: Ctx):
    with fenced_home(after=True, HALO_POLICY_TEST_DROP=1) as h:
        out, item = _gate_after(h, "a result the pack keeps out")
        want = "policy after: drop -- fence: the result stays out of the session (pack policy-fence, rule drop-all)"
        ctx.check(f"dropped, got {out.content!r}", out.content == want and "keeps out" not in out.content)
        ctx.check("the row is the winner", item["policy"][-1]["winner"] is True and item["policy"][-1]["at"] == "after")


@test
def test_a_late_answer_is_on_error(ctx: Ctx):
    from halo_harness.agent import policy_gate as G
    from halo_harness.packs import policy as P
    from halo_harness.tools.base import ToolResult
    with fenced_home(after=True, HALO_POLICY_TEST_SLOW_MS=1500) as h:
        out, item = _gate_after(h, "a slow pack's result", budget_ms=200)
        ctx.check(f"on_error deny reads as drop, got {out.content!r}",
                  out.content.startswith("policy after: drop -- fence: on_error deny (no answer within 200 ms)"))
        ctx.check("the error is on the row", item["policy"][-1].get("error") == "no answer within 200 ms")
        pol = dataclasses.replace(P.armed(cwd=h.repo)[0], on_error="allow")
        v, kept = P.ask_after(pol, P.request(pol, "Read", {}, cwd=h.repo), "text", 5, budget_ms=200)
        ctx.check(f"on_error allow reads as pass, got {v}", v.action == "pass" and v.error and kept is None)
        quick = dataclasses.replace(pol, after=False)
        s = SimpleNamespace(cwd=h.repo, agent_id=None, log=None, permission_engine=None)
        tr = ToolResult("kept as it is")
        ctx.check("a policy without after is not asked", G.after(s, {"name": "Read", "_policies": [quick]}, tr) is tr)
        ctx.check("a tool when.tools does not name is not asked",
                  G.after(s, {"name": "Grep", "_policies": [pol]}, tr) is tr)


if __name__ == "__main__":
    ctx = Ctx()
    results, passed, failed, skipped = run_all(TESTS, ctx)
    sys.exit(print_results(results, passed, failed, skipped))
