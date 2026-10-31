"""tests.test_studio_local_probe -- Halo 3.3.6.0 R1 "the battery": Studio's Local tab in headless Chrome through
tests/helpers/studio_local_probe.py (skipped without one), over R1's seeded home (`box` a fake Ollama on 127.0.0.1:0
answering the battery's probes); no provider request, no model call, nothing sent but to the fake:

1. a row not probed yet: "not probed", the card's blocks and placement chip marked declared or expected, never
   verified (3.3.6.0 R2: the three truths);
2. Probe: its title is the cost line and the `halo models probe` line; the progress strip shows the cost line and
   the step while it runs, then the result;
3. after: "probed <date> · re-probe", the placement chip verified, the four blocks (where it sits, use it for,
   don't use it for, limits) verified, the fit meter's word with the measured speed;
4. the no-tools model: "bulk worker · non-agentic" and "not interactive", its tool roles verified as no.
Run: python -m tests.test_studio_local_probe
"""
from __future__ import annotations

TIER = "full"  # headless Chrome: the full tier

import json
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from tests.helpers.runner import Ctx, SkipTest, new_registry, print_results, run_all  # noqa: E402

test, TESTS = new_registry()
REPO = Path(__file__).resolve().parent.parent
_RUN: dict = {}
COST = "about 8 requests to qwen3.5:9b on box, 1-3 minutes, no cost; it loads the model"


def _got(ctx: Ctx) -> dict:
    from tests.helpers.chrome_driver import driver_env, find_chrome
    if not find_chrome():
        raise SkipTest("no Chrome found (the Local probe checks need headless Chrome)")
    if "r" not in _RUN:
        r = subprocess.run([sys.executable, "-m", "tests.helpers.studio_local_probe"], capture_output=True, encoding="utf-8",
                           errors="replace", timeout=480, env=driver_env(REPO), cwd=str(REPO), stdin=subprocess.DEVNULL)
        try:
            info = json.loads(r.stdout.strip().splitlines()[-1])
        except (ValueError, IndexError):
            info = {}
        _RUN["r"] = (r, info)
    r, info = _RUN["r"]
    if info.get("skip"):
        raise SkipTest(info["skip"])
    ctx.check(f"the driver ran, got {r.returncode} {info.get('failed')!r} {r.stderr[-800:]!r}", r.returncode == 0 and "failed" not in info)
    return info


@test
def test_before_a_probe_everything_is_expected(ctx: Ctx):
    got = _got(ctx)
    ctx.check(f"not probed, got {got.get('mark_before')!r}", got.get("mark_before") == "no")
    ctx.check(f"the blocks and the chip declared or expected, never verified, got {got.get('marks_before')} {got.get('sits_before')!r}",
              set(got.get("marks_before") or []) <= {"expected", "declared"} and "expected" in (got.get("marks_before") or [])
              and got.get("sits_before") in ("expected", "declared"))
    ctx.check(f"the button says Probe, got {got.get('label_before')!r}", got.get("label_before") == "Probe")


@test
def test_probe_its_line_and_its_progress(ctx: Ctx):
    got = _got(ctx)
    ctx.check(f"the title: the cost line, then the CLI line, got {got.get('title')!r}",
              got.get("title") == f"{COST} -- halo models probe qwen3.5:9b --host box")
    running = got.get("running") or ["", ""]
    ctx.check(f"the strip while it runs: the cost line and a step, got {running}",
              running[0] == COST and running[1][:2] in ("1/", "2/", "3/", "4/", "5/", "6/"))
    ctx.check(f"the strip at the end, got {got.get('done')}", (got.get("done") or ["", ""])[0] == "true"
              and "full agent" in got["done"][1])


@test
def test_after_the_probe_the_card_says_it(ctx: Ctx):
    got = _got(ctx)
    ctx.check(f"probed <date> · re-probe, got {got.get('mark_after')!r}",
              (got.get("mark_after") or "").startswith("probed 20") and got["mark_after"].endswith("re-probe"))
    ctx.check(f"the chip verified, got {got.get('chip')}", got.get("chip") == ["full agent", "verified"])
    four = [b for b in got.get("blocks") or [] if b not in ("measured", "dialect", "fit", "kv")]  # 3.3.6.0 R3 / R4's blocks
    ctx.check(f"the four blocks, got {got.get('blocks')}", four == ["sits", "use_for", "dont_use_for", "limits"]
              or four == ["sits", "use_for", "limits"])
    ctx.check(f"every value verified, got {got.get('marks_after')}", got.get("marks_after") == ["verified"])
    ctx.check(f"Re-probe now, got {got.get('label_after')!r}", got.get("label_after") == "Re-probe")
    ctx.check(f"the fit meter's word with the speed, got {got.get('fit_word')!r}", "~188 tok/s at 32k" in (got.get("fit_word") or ""))


@test
def test_the_no_tools_model_is_a_step_model(ctx: Ctx):
    got = _got(ctx)
    chips = got.get("mute_chips") or []
    ctx.check(f"bulk worker and not interactive, got {chips}", chips[:1] == ["bulk worker · non-agentic"]
              and "not interactive" in chips)
    roles = {r[0]: (r[1], r[2]) for r in got.get("mute_roles") or []}
    ctx.check(f"its tool roles no, verified, got {roles}", roles.get("coder") == (False, "verified")
              and roles.get("orchestrator") == (False, "verified"))


if __name__ == "__main__":
    ctx = Ctx()
    results, passed, failed, skipped = run_all(TESTS, ctx)
    sys.exit(print_results(results, passed, failed, skipped))
