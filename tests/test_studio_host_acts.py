"""tests.test_studio_host_acts -- Halo 3.3.7.0 R2 deliverable 5, Studio's Local section acting through a paired
`halo host` in headless Chrome through tests/helpers/studio_host_acts.py (skipped without one), over
tests/helpers/host_act_rig.PeerRig; no model call, no real ssh, never a request beyond 127.0.0.1:

1. Local -> Hosts: pc's grants line; Load goes through the host (the fake saw it), "through halo host at ...";
   the server setting's stated line (the exact line for the host's OS, applied false; no POST reached the server);
   nothing opens over the page;
2. Local -> Models: Probe on a host-served model runs the battery on the host and its frames come back here.
Run: python -m tests.test_studio_host_acts
"""
from __future__ import annotations

TIER = "full"  # headless Chrome: the full tier

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from tests.helpers.runner import Ctx, new_registry, print_results, run_all  # noqa: E402
from tests.helpers.driver_got import got as driver_got  # noqa: E402

test, TESTS = new_registry()
REPO = Path(__file__).resolve().parent.parent
_RUN: dict = {}


def _got(ctx: Ctx) -> dict:
    info = driver_got(ctx, "tests.helpers.studio_host_acts", why="the host-acting checks need headless Chrome",
                      cache=_RUN, timeout=400)
    ctx.check(f"nothing left 127.0.0.1, got {info.get('blocked')}", not info.get("blocked"))
    return info


@test
def test_the_hosts_card_acts_through_the_host(ctx: Ctx):
    got = _got(ctx)
    ctx.check(f"the grants line, got {got.get('grants')!r}", "grants there: view, control" in str(got.get("grants")))
    ctx.check(f"Load is on and went through the host, got {got.get('load_said')!r} {got.get('loaded_on_fake')}",
              got.get("load_enabled") is True and "qwen3-coder:30b" in (got.get("loaded_on_fake") or [])
              and "loaded on pc" in str(got.get("load_said")))
    ctx.check(f"through the halo host, got {got.get('via')!r}", "through halo host at 127.0.0.1" in str(got.get("via")))
    stated = str(got.get("stated"))
    ctx.check(f"the stated line: the variable, never applied, got {stated!r}", "OLLAMA_KV_CACHE_TYPE=q8_0" in stated
              and "never applies" in stated)
    ctx.check(f"nothing opens over the page, got {got.get('dialogs')}", got.get("dialogs") == 0)


@test
def test_a_probe_runs_on_the_host_and_its_frames_come_here(ctx: Ctx):
    got = _got(ctx)
    ctx.check(f"Probe is on for a host-served model, got {got.get('probe_enabled')}", got.get("probe_enabled") is True)
    ctx.check(f"the strip ran with the host's steps, got {got.get('running')!r}", bool(got.get("running")))
    ctx.check(f"it ended here, got {got.get('done')}", isinstance(got.get("done"), list) and got["done"][0] == "true")
    ctx.check(f"the battery ran on the host, got {got.get('host_jobs')}", "rerun_battery" in (got.get("host_jobs") or []))


if __name__ == "__main__":
    ctx = Ctx()
    results, passed, failed, skipped = run_all(TESTS, ctx)
    sys.exit(print_results(results, passed, failed, skipped))
