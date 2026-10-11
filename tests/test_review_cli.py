"""tests.test_review_cli -- Halo 2.0.10 round 1: `halo review` in print mode
(real `python -m halo_harness review ...` subprocesses against the mock
upstream): the text form, the `--json` shape in the ReportFindings field names,
the PR form through a fake `gh`, `--fix`, and the usage errors. Every role
resolves to the one `--model`, so a single scripted router answers reviewer,
judge and fixer prompts alike (told apart by their prompt text).
"""
from __future__ import annotations

import json
import os
import re
import subprocess
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from tests.helpers.runner import Ctx, new_registry, print_results, run_all
from tests.helpers.mock_openai import MockUpstream, SCENARIOS
from tests.helpers import review_mock as rm

REPO_DIR = Path(__file__).resolve().parent.parent
test, TESTS = new_registry()

_SCRUB = ("OPENROUTER_", "DATABRICKS_", "ANTHROPIC_", "HALO_", "ROLO_CLAUDE_", "TYPESAFE_", "OPENAI_", "BRIDGE_")


def _env(mock, extra_path: "Path | None" = None) -> dict:
    env = {k: v for k, v in os.environ.items()
           if k.startswith("BRIDGE_TEST_") or not k.startswith(_SCRUB)}
    env.pop("BRIDGE_STATE_DIR", None)
    env.update({"BRIDGE_TEST_HOME": tempfile.mkdtemp(prefix="rv-cli-home-"), "BRIDGE_TEST_NO_BACKGROUND_NET": "1",
                "BRIDGE_OPENROUTER_BASE_URL": mock.base_url, "OPENROUTER_API_KEY": "test-key",
                "PYTHONPATH": str(REPO_DIR), "OLLAMA_HOST": "http://127.0.0.1:1", "PYTHONIOENCODING": "utf-8"})
    if extra_path is not None:
        env["PATH"] = str(extra_path) + os.pathsep + env.get("PATH", "")
    return env


def _halo(mock, args, cwd, extra_path=None, timeout=240):
    cmd = [sys.executable, "-m", "halo_harness", "review", *args, "--model", "or:mock/rv-all", "--cwd", str(cwd)]
    return subprocess.run(cmd, env=_env(mock, extra_path), cwd=str(REPO_DIR), capture_output=True, text=True,
                          encoding="utf-8", timeout=timeout)


def _scripted(repo: Path):
    """One model for every role: the prompt says which part it is."""
    items = [rm.finding_json(severity="high", short="subtracts instead of adds"),
             rm.finding_json(file="util.py", line=2, severity="low", category="crash", short="empty list crash"),
             rm.finding_json(file="util.py", line=1, severity="medium", category="phantom", short="not real")]

    def reply(p: str) -> str:
        if "CONFIRMED finding to fix:" in p:
            (repo / "a.py").write_text("def add(a, b):\n    return a + b\n", encoding="utf-8")
            return '```json\n{"outcome": "fixed", "note": "restored the plus"}\n```'
        if "Finding to judge:" in p:
            if "A fix was just applied" in p:
                return '```json\n{"verdict": "DISMISSED", "reason": "the plus is back"}\n```'
            if "not real" in p:
                return '```json\n{"verdict": "DISMISSED", "reason": "guarded by the caller"}\n```'
            if "empty list crash" in p:
                return '```json\n{"verdict": "PLAUSIBLE", "reason": "depends on callers"}\n```'
            return '```json\n{"verdict": "CONFIRMED", "reason": "traced"}\n```'
        return rm.fenced(items) if "Dimension: correctness" in p else "```json\n[]\n```"
    return rm.Router(reply)


@test
def test_text_output_ranked_with_header(ctx: Ctx):
    mock = MockUpstream().start()
    try:
        repo = rm.make_repo()
        SCENARIOS["rv-all"] = _scripted(repo)
        r = _halo(mock, [], repo)
        ctx.check(f"exit 0, got {r.returncode} stderr={r.stderr[-400:]!r}", r.returncode == 0)
        out = r.stdout
        ctx.check(f"header line, got {out[:300]!r}",
                  re.search(r"2 findings \(1 confirmed, 1 plausible\) from 5 reviewers in \d+ s, \$\d", out) is not None)
        ctx.check("confirmed high finding first, with file:line and verdict",
                  out.index("a.py:2") < out.index("util.py:2") and "CONFIRMED" in out and "PLAUSIBLE" in out)
        ctx.check("failure scenario and judge reason shown", "Failure scenario: add(1, 2) returns -1" in out and "Judge: traced" in out)
        ctx.check("dismissed finding is not listed", "not real" not in out and "1 finding(s) dismissed" in out)
        ctx.check("progress goes to stderr, not stdout", "reviewer(s) on" in r.stderr and "reviewer(s) on" not in out)
    finally:
        mock.stop()


@test
def test_json_output_has_the_report_findings_shape(ctx: Ctx):
    mock = MockUpstream().start()
    try:
        repo = rm.make_repo()
        SCENARIOS["rv-all"] = _scripted(repo)
        r = _halo(mock, ["--json", "--level", "low", "--dimensions", "correctness,tests"], repo)
        ctx.check(f"exit 0, got {r.returncode} stderr={r.stderr[-400:]!r}", r.returncode == 0)
        obj = json.loads(r.stdout)
        ctx.check(f"top-level keys, got {sorted(obj)}",
                  sorted(obj) == ["cost_usd", "dismissed", "elapsed_s", "findings", "reviewers", "target"])
        ctx.check("target block", obj["target"]["kind"] == "branch" and obj["target"]["head"] == "feature"
                  and sorted(obj["target"]["files"]) == ["a.py", "util.py"])
        f0 = obj["findings"][0]
        need = {"file", "line", "short_summary", "summary", "failure_scenario", "verdict", "category", "severity", "outcome"}
        ctx.check(f"finding has the ReportFindings fields, got {sorted(f0)}", need <= set(f0))
        ctx.check("field values", (f0["file"], f0["line"], f0["verdict"], f0["severity"], f0["outcome"])
                  == ("a.py", 2, "CONFIRMED", "high", None))
        ctx.check("second finding is the plausible low one", obj["findings"][1]["verdict"] == "PLAUSIBLE")
        ctx.check("dismissed kept with its reason",
                  [(d["short_summary"], d["reason"]) for d in obj["dismissed"]] == [("not real", "guarded by the caller")])
        ctx.check(f"two reviewers listed, got {[r['dimension'] for r in obj['reviewers']]}",
                  [r["dimension"] for r in obj["reviewers"]] == ["correctness", "tests"])
        ctx.check("cost and elapsed are numbers",
                  isinstance(obj["cost_usd"], (int, float)) and isinstance(obj["elapsed_s"], (int, float)))
    finally:
        mock.stop()


@test
def test_pr_form_with_a_fake_gh(ctx: Ctx):
    mock = MockUpstream().start()
    try:
        repo = rm.make_repo()
        SCENARIOS["rv-all"] = _scripted(repo)
        diff = ("diff --git a/a.py b/a.py\n--- a/a.py\n+++ b/a.py\n@@ -1,2 +1,2 @@\n def add(a, b):\n"
                "-    return a + b\n+    return a - b\n")
        meta = json.dumps({"number": 7, "title": "Change add", "headRefName": "feature", "baseRefName": "main",
                           "files": [{"path": "a.py"}]})
        gh = rm.fake_gh(diff, meta)
        r = _halo(mock, ["#7", "--json", "--dimensions", "correctness"], repo, extra_path=gh)
        ctx.check(f"exit 0, got {r.returncode} stderr={r.stderr[-400:]!r}", r.returncode == 0)
        obj = json.loads(r.stdout)
        ctx.check(f"target is the PR, got {obj['target']}", obj["target"]["kind"] == "pr"
                  and obj["target"]["label"] == "PR #7: Change add" and obj["target"]["files"] == ["a.py"])
        ctx.check("findings came back", len(obj["findings"]) >= 1)
        calls = (gh / "calls.txt").read_text(encoding="utf-8")
        ctx.check(f"gh pr diff 7 was called, got {calls!r}", "pr diff 7" in calls)
    finally:
        mock.stop()


@test
def test_fix_flag_reports_outcomes_and_leaves_changes_uncommitted(ctx: Ctx):
    mock = MockUpstream().start()
    try:
        repo = rm.make_repo()
        # Revert the working tree to the broken version so the scripted coder has something to fix.
        SCENARIOS["rv-all"] = _scripted(repo)
        log_before = rm.git(repo, "log", "--oneline")
        (repo / "a.py").write_text("def add(a, b):\n    return a - b\n", encoding="utf-8")
        r = _halo(mock, ["--json", "--fix", "--dimensions", "correctness"], repo)
        ctx.check(f"exit 0, got {r.returncode} stderr={r.stderr[-400:]!r}", r.returncode == 0)
        obj = json.loads(r.stdout)
        top = obj["findings"][0]
        ctx.check(f"the confirmed finding was fixed, got {top['outcome']}", top["outcome"] == "fixed")
        ctx.check("the plausible one has no outcome", obj["findings"][1]["outcome"] is None)
        ctx.check("the file now has the plus", "a + b" in (repo / "a.py").read_text(encoding="utf-8"))
        ctx.check("no commit was made", rm.git(repo, "log", "--oneline") == log_before)
    finally:
        mock.stop()


@test
def test_usage_errors_exit_2_with_a_message(ctx: Ctx):
    mock = MockUpstream().start()
    try:
        repo = rm.make_repo()
        r = _halo(mock, ["--dimensions", "bogus"], repo)
        ctx.check(f"unknown dimension: rc 2 naming it, got rc={r.returncode} {r.stderr[-200:]!r}",
                  r.returncode == 2 and "bogus" in r.stderr)
        r = _halo(mock, ["--fix", "--no-verify"], repo)
        ctx.check(f"--fix with --no-verify: rc 2, got rc={r.returncode} {r.stderr[-200:]!r}",
                  r.returncode == 2 and "--no-verify" in r.stderr)
        r = _halo(mock, ["--level", "extreme"], repo)
        ctx.check("bad level: rc 2", r.returncode == 2)
        rm.git(repo, "checkout", "-q", "main")
        r = _halo(mock, [], repo)
        ctx.check(f"clean default branch: rc 2 'nothing to review', got rc={r.returncode} {r.stderr[-200:]!r}",
                  r.returncode == 2 and "nothing to review" in r.stderr)
        r = _halo(mock, ["no-such-file.py"], repo)
        ctx.check("unknown target: rc 2", r.returncode == 2 and "no-such-file.py" in r.stderr)
    finally:
        mock.stop()


@test
def test_role_flag_picks_the_model_for_each_part(ctx: Ctx):
    mock = MockUpstream().start()
    try:
        repo = rm.make_repo()
        router = _scripted(repo)
        for name in ("rv-all", "rv-part-reviewer", "rv-part-judge"):
            SCENARIOS[name] = router
        r = _halo(mock, ["--json", "--dimensions", "correctness", "--role", "reviewer=or:mock/rv-part-reviewer",
                         "--role", "judge=or:mock/rv-part-judge"], repo)
        ctx.check(f"exit 0, got {r.returncode} stderr={r.stderr[-300:]!r}", r.returncode == 0)
        def model_of(body):
            return ((body or {}).get("model") or "")
        by_kind = {"reviewer": set(), "judge": set()}
        for req in mock.requests:
            body = req.get("body") or {}
            text = json.dumps(body.get("messages") or [])
            kind = "judge" if "Finding to judge:" in text else "reviewer"
            by_kind[kind].add(model_of(body))
        ctx.check(f"reviewer requests used the reviewer role's model, got {by_kind}",
                  by_kind["reviewer"] == {"mock/rv-part-reviewer"})
        ctx.check("judge requests used the judge role's model", by_kind["judge"] and by_kind["judge"] == {"mock/rv-part-judge"})
        bad = _halo(mock, ["--role", "nonsense"], repo)
        ctx.check(f"a bad --role is a usage error, got rc={bad.returncode}", bad.returncode == 2)
    finally:
        mock.stop()


@test
def test_paths_target_and_help(ctx: Ctx):
    mock = MockUpstream().start()
    try:
        repo = rm.make_repo()
        SCENARIOS["rv-all"] = _scripted(repo)
        r = _halo(mock, ["util.py", "--json", "--dimensions", "correctness", "--no-verify"], repo)
        ctx.check(f"exit 0, got {r.returncode} stderr={r.stderr[-300:]!r}", r.returncode == 0)
        obj = json.loads(r.stdout)
        ctx.check("kind paths", obj["target"]["kind"] == "paths" and obj["target"]["files"] == ["util.py"])
        ctx.check("--no-verify leaves PLAUSIBLE and no dismissed",
                  {f["verdict"] for f in obj["findings"]} == {"PLAUSIBLE"} and obj["dismissed"] == [])
        h = subprocess.run([sys.executable, "-m", "halo_harness", "review", "--help"], env=_env(mock),
                           cwd=str(REPO_DIR), capture_output=True, text=True, timeout=60)
        ctx.check("--help lists the options", all(x in h.stdout for x in ("--level", "--dimensions", "--fix", "--no-verify", "--json")))
    finally:
        mock.stop()


if __name__ == "__main__":
    ctx = Ctx()
    results, passed, failed, skipped = run_all(TESTS, ctx)
    sys.exit(print_results(results, passed, failed, skipped))
