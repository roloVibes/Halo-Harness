"""tests.test_review3_p -- pins for the 3.0.2.0 review fix pass, round
P-design-paperclip, the design-turn item (review item 43; the Paperclip
items 39 and 42 went with Paperclip in 3.1.4.0; the design items are in
test_review3_p2):

  * 43  run_turn enforces its timeout while the child holds stdout open
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from tests.helpers.provider_env_defaults import ensure_default_provider_credentials, ensure_scoped_state_dir_once

ensure_default_provider_credentials()
ensure_scoped_state_dir_once()

from tests.helpers.runner import Ctx, new_registry, print_results, run_all  # noqa: E402

test, TESTS = new_registry()


# ---- 43 -----------------------------------------------------------------------

@test
def test_i43_run_turn_kills_a_child_that_hangs_with_stdout_open(ctx: Ctx):
    import subprocess
    import time
    from halo_harness.design import session
    from halo_harness.design.store import Project
    p = Project.create("Hang turn")
    real = subprocess.Popen
    script = "import time; print('{\"type\": \"system\"}', flush=True); time.sleep(120)"

    def popen(cmd, **kw):
        return real([sys.executable, "-c", script], **kw)
    subprocess.Popen = popen
    started = time.monotonic()
    try:
        out = session.run_turn(p, "hang", entries={}, registered=set(), timeout=2)
    finally:
        subprocess.Popen = real
    ctx.check(f"returned near the deadline, took {time.monotonic() - started:.1f}s", time.monotonic() - started < 30)
    ctx.check(f"code 124, got {out['code']}", out["code"] == 124)
    ctx.check("lines read before the deadline were handled", any(e.get("type") == "system" for e in out["events"]))


@test
def test_i43_a_normal_child_still_returns_its_exit_code_and_lines(ctx: Ctx):
    import subprocess
    from halo_harness.design import session
    from halo_harness.design.store import Project
    p = Project.create("Quick turn")
    real = subprocess.Popen
    script = "import sys; print('{\"type\": \"result\", \"result\": \"hi\"}'); print('plain text'); sys.exit(3)"
    subprocess.Popen = lambda cmd, **kw: real([sys.executable, "-c", script], **kw)
    try:
        out = session.run_turn(p, "go", entries={}, registered=set(), timeout=30)
    finally:
        subprocess.Popen = real
    ctx.check(f"exit code kept, got {out['code']}", out["code"] == 3)
    ctx.check("result text and a plain line both arrive", out["text"] == "hi" and any(e.get("text") == "plain text" for e in out["events"]))


if __name__ == "__main__":
    ctx = Ctx()
    results, passed, failed, skipped = run_all(TESTS, ctx)
    sys.exit(print_results(results, passed, failed, skipped, label="review3 p tests"))
