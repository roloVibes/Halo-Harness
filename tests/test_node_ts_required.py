"""tests.test_node_ts_required -- 3.6.0.2 P8 (judge E, must 3): the node halves of this release's pure-rule tests
(layout, truth sentences, the session pick, the prompt's words) skip on a box with no node or no TypeScript, and a
skip does not fail a run. So CI's `studio-ui` job, after its `npm ci`, runs every module that uses
tests/helpers/node_ts.py with HALO_NODE_TS_REQUIRED=1, which turns "cannot run" into a FAILURE. Also the realcheck
step's and job's time limits (judge A, must 3: the steps' budgets add up past the old 40-minute step).
Runs anywhere; no node needed (the helper's two "cannot run" paths are fed their inputs).
Run: python -m tests.test_node_ts_required
"""
from __future__ import annotations

import os
import re
import subprocess
import sys
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from tests.helpers.runner import Ctx, SkipTest, new_registry, print_results, run_all  # noqa: E402

test, TESTS = new_registry()
REPO = Path(__file__).resolve().parent.parent
SWITCH = "HALO_NODE_TS_REQUIRED"


def _raised(fn) -> "BaseException | None":
    try:
        fn()
    except BaseException as e:  # noqa: BLE001 -- the kind of what it raised is the point
        return e
    return None


@test
def test_a_node_half_that_cannot_run_fails_with_the_switch_and_skips_without(ctx: Ctx):
    """No node on the box, and a node without TypeScript with no `npm ci`: SkipTest without the switch (as before),
    an AssertionError naming the switch with HALO_NODE_TS_REQUIRED=1. Red on fc214582: both were SkipTest."""
    from tests.helpers import node_ts
    no_ts = subprocess.CompletedProcess([], 1, "", "Error [ERR_NO_TYPESCRIPT]: no TypeScript")
    cases = {
        "no node": [mock.patch.object(node_ts.shutil, "which", return_value=None)],
        "no TypeScript": [mock.patch.object(node_ts.shutil, "which", return_value="node"),
                          mock.patch.object(node_ts, "_exec", return_value=no_ts),
                          mock.patch.object(node_ts.subprocess, "run",
                                            return_value=subprocess.CompletedProcess([], 0, "v24.0.0\n", "")),
                          mock.patch.object(node_ts, "TSC", REPO / "no-such-folder" / "typescript")],
    }
    for name, patches in cases.items():
        for required in (None, "1"):
            env = {k: v for k, v in os.environ.items() if k != SWITCH}
            if required:
                env[SWITCH] = required
            with mock.patch.dict(os.environ, env, clear=True):
                for p in patches:
                    p.start()
                try:
                    e = _raised(lambda: node_ts.run("console.log('null')"))
                finally:
                    for p in reversed(patches):
                        p.stop()
            if required:
                ctx.check(f"{name}, {SWITCH}=1: a failure naming the switch, got {type(e).__name__}: {e}",
                          isinstance(e, AssertionError) and not isinstance(e, SkipTest) and SWITCH in str(e))
            else:
                ctx.check(f"{name}, no switch: a skip, as before, got {type(e).__name__}: {e}",
                          isinstance(e, SkipTest))


@test
def test_ci_runs_every_node_half_with_the_switch_and_realcheck_has_its_time(ctx: Ctx):
    """suites.yml: the studio-ui job, after `npm ci`, runs every module that imports tests/helpers/node_ts.py with
    HALO_NODE_TS_REQUIRED=1 (its grep finds every such module on this tree); the realcheck STEP has 60 minutes and its
    JOB 65 (3.6.0.5: room for the budgets of auto-groups and auto-ready-lines; 3.6.0.7: + copy-drag's 2 on Windows;
    3.6.0.8: + the browser step's 180 s, 3 minutes more; 3.6.0.14: + live-scene's 180 s and idle-cpu's 90 s more); the names of the jobs are as they were. docs/DEVELOPMENT.md
    names the switch. Red on fc214582."""
    yml = (REPO / ".github" / "workflows" / "suites.yml").read_text(encoding="utf-8")
    jobs = re.split(r"\n(?=  [a-z][a-z0-9-]*:\n)", yml)
    ui = next((j for j in jobs if j.startswith("  studio-ui:")), "")
    rc = next((j for j in jobs if j.startswith("  realcheck:")), "")
    npm, step = ui.find("npm ci"), ui.find(f'{SWITCH}: "1"')
    ctx.check("the studio-ui job sets HALO_NODE_TS_REQUIRED=1 on a step after its npm ci", 0 <= npm < step)
    grep = re.search(r'grep -l "([^"]+)" tests/test_\*\.py', ui[step:])
    ctx.check("that step finds the modules by their import of the helper", grep is not None)
    if grep:
        pats = [p.replace("\\.", ".") for p in grep.group(1).split("\\|")]
        found = {f.stem for f in (REPO / "tests").glob("test_*.py")
                 if any(p in f.read_text(encoding="utf-8", errors="replace") for p in pats)}
        users = {f.stem for f in (REPO / "tests").glob("test_*.py")
                 if re.search(r"helpers(\.| import )node_ts", f.read_text(encoding="utf-8", errors="replace"))}
        ctx.check(f"its grep finds every module that uses node_ts (missed {sorted(users - found)})",
                  users and users <= found)
        ctx.check("the pure-rule modules are among them",
                  {"test_map_layout", "test_map_truth", "test_map_s13_three_places", "test_studio_session_map_down",
                   "test_agents_door", "test_studio_door_kept", "test_api_limit", "test_studio_prompt_words"} <= found)
    step_rc = re.search(r"- name: realcheck\n\s+timeout-minutes: (\d+)", rc)
    job_rc = re.search(r"\n    timeout-minutes: (\d+)", rc)
    ctx.check(f"the realcheck step has 60 minutes, got {step_rc and step_rc.group(1)}",
              step_rc is not None and step_rc.group(1) == "60")
    ctx.check(f"the realcheck job has 65 minutes, got {job_rc and job_rc.group(1)}",
              job_rc is not None and job_rc.group(1) == "65")
    ctx.check("the job names are as they were",
              "name: studio-ui (build + drift gate)" in ui
              and "name: realcheck (${{ matrix.os }}${{ matrix.install == 'installed' && ', installed' || '' }})" in rc)
    dev = (REPO / "docs" / "DEVELOPMENT.md").read_text(encoding="utf-8")
    ctx.check("docs/DEVELOPMENT.md names the switch", SWITCH in dev)


if __name__ == "__main__":
    ctx = Ctx()
    results, passed, failed, skipped = run_all(TESTS, ctx)
    sys.exit(print_results(results, passed, failed, skipped, label="node_ts required tests"))
