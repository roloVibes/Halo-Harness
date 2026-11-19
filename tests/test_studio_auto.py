"""tests.test_studio_auto -- Auto and groups in a real browser (Halo 3.6.0.5, design section 6, the VM browser tests;
headless Chrome through tests/helpers/studio_auto.py and tests/helpers/studio_auto_map.py, skipped without one). Run on
the Linux VM only; browser modules never run on the PC.

Scene 4: over this harness's real session on Auto, after a build that wrote the agent checker and the workflow review
(no map), Studio's head over Session's Live drawing says "Just built: the workflow review. Ready in this session now,
by name." with [Open in Workflows] and the two true lines under it, nothing moves and no pair appears; the run of that
workflow shows as the group "workflow review · step 1 of 2": in view, or (when it does not fit under the head) named by
the slot and brought up by one press; the head and main hold still; the room is on record. In a home with no workflow (its own driver
process) the head says it waits for the next session, with two "Saved for your next session" lines.

Scene 5: the map picker (Agents -> 3 · Map) and Setup's Map step list Auto (the default) first, his maps (his old file
named starter as "starter · your copy from before"), "shop (this project's)", "ship-it (ships with Halo)"; the old row
opens HIS file read-only and its one button makes my-map holding his boxes and lines, his file untouched; with no
session on Auto, Auto's Map tab says "Nothing runs on Auto right now."

Run: python -m tests.test_studio_auto   (the Linux VM)
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
_RUNS: dict = {}


def _run(module: str, *argv: str) -> "tuple[subprocess.CompletedProcess, dict]":
    """One driver process, waited for with a timeout (subprocess.run ends it on a timeout); its last line's JSON."""
    from tests.helpers.chrome_driver import driver_env, find_chrome
    if not find_chrome():
        raise SkipTest("no Chrome found (Studio's drawings need headless Chrome)")
    key = (module, *argv)
    if key not in _RUNS:
        try:
            r = subprocess.run([sys.executable, "-m", module, *argv], capture_output=True, encoding="utf-8",
                               errors="replace", timeout=300, env=driver_env(REPO), cwd=str(REPO))
        except subprocess.TimeoutExpired as e:
            r = subprocess.CompletedProcess(e.cmd, -9, str(e.stdout or ""), "timed out after 300 s")
        try:
            info = json.loads(r.stdout.strip().splitlines()[-1])
        except (ValueError, IndexError):
            info = {}
        _RUNS[key] = (r, info)
    r, info = _RUNS[key]
    if info.get("skip"):
        raise SkipTest(info["skip"])
    return r, info


def _driver() -> "list[tuple[subprocess.CompletedProcess, dict]]":
    """Scene 4's two runs, one after the other: ready then use, then waits in a process of its own (a StudioSessionRig
    sets process-wide variables)."""
    return [_run("tests.helpers.studio_auto"), _run("tests.helpers.studio_auto", "waits")]


def _map_driver() -> "tuple[subprocess.CompletedProcess, dict]":
    return _run("tests.helpers.studio_auto_map")


@test
def test_scene4_true_lines_then_use_it_runs_as_a_group(ctx: Ctx):
    from tests.helpers.studio_auto import verdicts
    runs = _driver()
    for r, got in runs:
        ctx.check(f"the driver ran, got {r.returncode} {got.get('failed')!r} {r.stderr[-600:]!r}",
                  r.returncode == 0 and "failed" not in got)
        says = verdicts(got)
        ctx.check(f"what a person sees: {says} -- {json.dumps(got)[:1200]}", says == [])
    seconds = sum(float(got.get("seconds") or 0) for _r, got in runs)
    ctx.check(f"the two runs took under 90 s together, got {seconds:.1f} s", 0 < seconds < 90)
    # k/batch02 entry 3: the room on record (a known limit at 1280 x 800: the drawing's visible box under the head)
    use = runs[0][1].get("use") or {}
    room, way = use.get("room") or {}, "pressed up from the slot" if use.get("press") is not None else "in view"
    print(f"  use it now: the drawing's visible box {room.get('visible_h')} px, the workflow's group {room.get('group_h')} px, {way}")
    ctx.check(f"the room is on record: the visible box {room.get('visible_h')} px, the group {room.get('group_h')} px ({way})",
              isinstance(room.get("visible_h"), int) and isinstance(room.get("group_h"), int))


@test
def test_scene5_picker_reads_ships_with_halo_and_your_copy_from_before(ctx: Ctx):
    from tests.helpers.studio_auto_map import verdicts
    r, got = _map_driver()
    ctx.check(f"the driver ran, got {r.returncode} {got.get('failed')!r} {r.stderr[-600:]!r}",
              r.returncode == 0 and "failed" not in got)
    says = verdicts(got)
    ctx.check(f"what a person sees: {says} -- {json.dumps(got)[:1200]}", says == [])
    ctx.check(f"the run took under 60 s, got {got.get('seconds')}", 0 < float(got.get("seconds") or 0) < 60)


@test
def test_watch_it_in_live_says_nothing_runs_without_a_session(ctx: Ctx):
    """A14's other half: with no session on Auto, Auto's Map tab says "Nothing runs on Auto right now." and shows no
    [Watch it in Live]. The half where the button lands in Agents -> 4 · Live with the Auto session picked is
    tests/test_studio_controls_change_something.py `test_every_control_changes_something` (a/batch02 entry 5)."""
    from tests.helpers.studio_auto_map import m1_verdicts
    r, got = _map_driver()
    ctx.check(f"the driver ran, got {r.returncode} {got.get('failed')!r}", r.returncode == 0 and "failed" not in got)
    says = m1_verdicts(got)
    ctx.check(f"Auto's plan line with no session: {says} -- {json.dumps(got.get('picker'))[:600]}", says == [])


if __name__ == "__main__":
    ctx = Ctx()
    results, passed, failed, skipped = run_all(TESTS, ctx)
    sys.exit(print_results(results, passed, failed, skipped))
