"""tests.test_pack_test -- `halo pack test` and `halo_harness.ext.testing` (Halo 3.3.12.0 R4, docs/PACK-AUTHORING.md
"Testing"): green on the --all scaffold, doc-review, concord (its MCP server and its `concord` hooks skipped with the
line when the binary is absent), studio-bundle, policy-fence, setup-blocks and shell-hook; red with the right lines
on studio-outside, wf-unknown-role, bad-yaml, a hook that exits 1, an MCP server that never answers (the timeout
line) and a policy that answers out of shape; the entry command run, the integration skip line, the bundle check;
the --json shape; the scaffold's own tests/pack_test.py green through `python -m`. Every run is ext.testing's own
scratch home; no model, no network; each child process is waited for.
"""

from __future__ import annotations

import io
import json
import os
import subprocess
import sys
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from tests.helpers.pack_kit import KitHome  # noqa: E402
from tests.helpers.packs_home import fixture  # noqa: E402
from tests.helpers.runner import Ctx, new_registry, print_results, run_all  # noqa: E402

test, TESTS = new_registry()
REPO = Path(__file__).resolve().parent.parent


def _run(folder, **kw):
    from halo_harness.ext import testing
    return testing.run(folder, **kw)


def _failed(report) -> "list[str]":
    return [ln for ln in report.lines() if not ln.startswith("skip ")]


@test
def test_green_on_the_scaffold_and_the_shipped_and_fixture_packs(ctx: Ctx):
    from halo_harness.packs.sources import shipped_dir
    with KitHome() as k:
        demo = k.new("demo", all_kinds=True)
        for folder in (demo, fixture("doc-review"), fixture("studio-bundle"), fixture("policy-fence"),
                       fixture("setup-blocks"), fixture("shell-hook")):
            report = _run(folder)
            ctx.check(f"{folder.name}: green, got {report.text()}", report.ok and report.exit_code == 0)
        with k.path():
            report = _run(shipped_dir() / "concord")
        skips = [ln for ln in report.lines() if ln.startswith("skip ")]
        ctx.check(f"concord without concord on PATH: green, got {report.text()}", report.ok)
        ctx.check(f"concord: its MCP server and its concord hooks skipped with the line, got {skips}",
                  any("MCP server concord: skipped, concord-mcp is not on PATH here" in s for s in skips)
                  and sum("skipped, concord is not on PATH here" in s for s in skips) == 4)


@test
def test_the_entry_command_the_integration_skip_and_the_bundle(ctx: Ctx):
    with KitHome() as k:
        demo = k.new("demo", "integration", "bundle", "workflows")
        with k.path():
            report = _run(demo)
        by = {c["what"]: c for c in report.checks}
        entry = next((c for w, c in by.items() if w.startswith("/demo runs in a fake session")), None)
        ctx.check(f"the entry command ran and listed the parts, got {entry}", entry and entry["ok"] is True)
        skip = [ln for ln in report.lines() if ln.startswith("skip ") and "rg is not on PATH" in ln]
        ctx.check(f"no rg: the parts it gates are skipped with one line each, got {skip}", report.ok and any(
            "MCP server rg: skipped" in s for s in skip) and any("rg_todos.py: skipped" in s for s in skip)
            and any("install it:" in s for s in skip))
        ctx.check("the bundle block and the fake card", any(w.startswith("the bundle: block reads clean") and c["ok"]
                                                             for w, c in by.items())
                  and any("fits a fake 24 GB card" in w and c["ok"] for w, c in by.items()))
        with k.path(fake_rg=True):
            report = _run(demo, kinds=["integration"])
        ctx.check(f"a fake rg on PATH: the requirement passes, got {report.text()}", report.ok and any(
            c["what"].startswith("rg (command) is here") for c in report.checks))


@test
def test_red_with_the_right_lines(ctx: Ctx):
    cases = {"studio-outside": "pack.yaml: pack.yaml line 9: contributes.studio.panels[0].source "
                               "'../doc-review/studio/notes.md' is outside the pack's folder",
             "wf-unknown-role": "workflows/flow.yaml: workflows/flow.yaml line 6: stages.audit.role 'auditor' is not a bio",
             "bad-yaml": "pack.yaml: it does not read as a YAML mapping (key: value)"}
    for name, line in cases.items():
        report = _run(fixture(name))
        ctx.check(f"{name}: red with its line, got {report.text()}", report.exit_code == 1
                  and any(f.startswith(line) for f in _failed(report)) and " -- " in _failed(report)[0])


def _rewrite(folder: Path, rel: str, text: str) -> None:
    (folder / rel).write_text(text, encoding="utf-8")


@test
def test_a_failing_hook_a_silent_server_and_a_policy_out_of_shape(ctx: Ctx):
    with KitHome() as k:
        hook = k.new("bad-hook", "hooks")
        _rewrite(hook, "hooks/log_write.py", "import sys\nsys.stderr.write('the hook broke\\n')\nsys.exit(1)\n")
        report = _run(hook)
        ctx.check(f"a hook that exits 1: red, its exit and its last line, got {report.text()}", report.exit_code == 1
                  and any(f.startswith("hooks/hooks.json: PostToolUse hook") and "exit 1 (want 0): the hook broke" in f
                          for f in _failed(report)))
        mcp = k.new("silent-mcp", "mcp")
        _rewrite(mcp, "mcp/words_server.py", "import sys\nfor line in sys.stdin:\n    pass\n")
        report = _run(mcp, timeout_s=2)
        ctx.check(f"an MCP server that never answers: the timeout line, got {report.text()}", report.exit_code == 1
                  and any("MCP server words starts" in f and "no answer to initialize within 2 s" in f
                          for f in _failed(report)))
        pol = k.new("odd-policy", "policy")
        _rewrite(pol, "policy/guard.py", "import json, sys\nfor line in sys.stdin:\n    req = json.loads(line)\n"
                 "    print(json.dumps({'id': req['id'], 'verdict': 'maybe'}), flush=True)\n")
        report = _run(pol)
        ctx.check(f"a policy that answers out of shape: red with the line, got {report.text()}", report.exit_code == 1
                  and any("policy guard answers a Write call in shape" in f and "verdict 'maybe' is not allow, deny or ask"
                          in f for f in _failed(report)))


@test
def test_the_cli_and_the_json_shape(ctx: Ctx):
    from halo_harness.packs.cli import cmd_pack
    with KitHome() as k:
        demo = k.new("demo", "commands")
        out, err = io.StringIO(), io.StringIO()
        with redirect_stdout(out), redirect_stderr(err):
            code = cmd_pack(["test", str(demo), "--json"])
        data = json.loads(out.getvalue())
        ctx.check(f"--json: {{pack, ok, checks, passed, failed, skipped, result}}, got {sorted(data)}", code == 0
                  and set(data) == {"pack", "ok", "checks", "passed", "failed", "skipped", "result"}
                  and data["pack"] == "demo" and data["result"].startswith("RESULT: ")
                  and all(set(c) == {"kind", "file", "what", "ok", "fix"} for c in data["checks"]))
        out = io.StringIO()
        with redirect_stdout(out), redirect_stderr(io.StringIO()):
            code = cmd_pack(["test", str(fixture("bad-yaml"))])
        last = out.getvalue().strip().splitlines()[-1]
        ctx.check(f"the text: the RESULT line last, exit 1, got {last}", code == 1
                  and last == "RESULT: 1 checks, 0 passed, 1 failed")
        with redirect_stdout(io.StringIO()), redirect_stderr(err := io.StringIO()):
            code = cmd_pack(["test", "no-such-pack"])
        ctx.check(f"a target that is neither: one line, exit 1, got {err.getvalue()}", code == 1
                  and "is neither a pack folder, a pack installed here nor one Halo ships" in err.getvalue())


@test
def test_the_scaffolds_own_test_runs_through_python_m(ctx: Ctx):
    with KitHome() as k:
        demo = k.new("demo", all_kinds=True)
        env = {kk: v for kk, v in os.environ.items()}
        env["PYTHONPATH"] = os.pathsep.join([str(REPO)] + [p for p in env.get("PYTHONPATH", "").split(os.pathsep) if p])
        done = subprocess.run([sys.executable, "-m", "tests.pack_test"], cwd=str(demo), env=env, capture_output=True,
                              text=True, encoding="utf-8", errors="replace", timeout=300)
        ctx.check(f"python -m tests.pack_test: green, its own policy check too, got {done.stdout[-600:]} {done.stderr[-400:]}",
                  done.returncode == 0 and "0 failed" in done.stdout and "RESULT:" in done.stdout)
        from halo_harness.ext import testing
        verdict = testing.ask_policy(demo, "guard", "Write", {"file_path": ".git/config"})
        ctx.check(f"ext.testing.ask_policy: the guard denies a write under .git/, got {verdict}",
                  verdict.get("verdict") == "deny" and verdict.get("rule") == "no-git-dir")


if __name__ == "__main__":
    ctx = Ctx()
    results, passed, failed, skipped = run_all(TESTS, ctx)
    sys.exit(print_results(results, passed, failed, skipped))
