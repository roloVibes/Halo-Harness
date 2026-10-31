"""tests.test_studio_hosts_host -- Halo 3.3.7.0 R1 deliverable 4, Studio's Local section over a paired `halo host` in
headless Chrome through tests/helpers/studio_hosts_host.py (skipped without one), over tests/helpers/host_rig.py's
fake host; no model call, no real ssh, never a request beyond 127.0.0.1:

1. Local -> Hosts: pc sits first, under SERVED BY HALO HOST; its card's line "served by halo host at 127.0.0.1 --
   running since ..., last seen ..., N requests in its audit"; its log line says "via host"; Load's reason names the
   control grant and 3.3.7.0 R2; nothing opens over the page;
2. Local -> Logs with pc: the status says "via host", the tail arrives from the host with its groups, the cut prompt's
   sizes there and no request body.
Run: python -m tests.test_studio_hosts_host
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


def _got(ctx: Ctx) -> dict:
    from tests.helpers.chrome_driver import driver_env, find_chrome
    if not find_chrome():
        raise SkipTest("no Chrome found (the Hosts page checks need headless Chrome)")
    if "r" not in _RUN:
        r = subprocess.run([sys.executable, "-m", "tests.helpers.studio_hosts_host"], capture_output=True, encoding="utf-8",
                           errors="replace", timeout=300, env=driver_env(REPO), cwd=str(REPO), stdin=subprocess.DEVNULL)
        try:
            info = json.loads(r.stdout.strip().splitlines()[-1])
        except (ValueError, IndexError):
            info = {}
        _RUN["r"] = (r, info)
    r, info = _RUN["r"]
    if info.get("skip"):
        raise SkipTest(info["skip"])
    ctx.check(f"the driver ran, got {r.returncode} {info.get('failed')!r} {r.stderr[-800:]!r}", r.returncode == 0 and "failed" not in info)
    ctx.check(f"nothing left 127.0.0.1, got {info.get('blocked')}", not info.get("blocked"))
    return info


@test
def test_the_hosts_card_says_served_by_halo_host(ctx: Ctx):
    got = _got(ctx)
    line = str(got.get("host_line"))
    ctx.check(f"the host line: address, running since, last seen, the audit, got {line!r}",
              line.startswith("served by halo host at 127.0.0.1") and "running since" in line and "last seen" in line
              and "in its audit" in line)
    ctx.check(f"pc first, under the host group, got {got.get('group')} {got.get('first_group')}",
              got.get("group") == "host" and got.get("first_group") == "host")
    ctx.check(f"its log line reads through the host, got {got.get('log_line')!r}", "via host" in str(got.get("log_line")))
    ctx.check(f"Load says why not yet, got {got.get('why')!r}", "`control` grant" in str(got.get("why"))
              and "3.3.7.0 R2" in str(got.get("why")))
    ctx.check(f"nothing opens over the page, got {got.get('dialogs')}", got.get("dialogs") == 0)


@test
def test_the_logs_page_tail_comes_from_the_host(ctx: Ctx):
    got = _got(ctx)
    ctx.check(f"the status says via host, got {got.get('status')!r}", "via host" in str(got.get("status")))
    lines = got.get("lines") or []
    ctx.check(f"the tail's lines arrived, the cut prompt's sizes there, got {lines}", any("prompt=41104" in x for x in lines))
    ctx.check("no request body", not any("the secret plan" in x for x in lines)
              and any("stays on this machine" in x for x in lines))
    ctx.check(f"with their groups, got {got.get('groups')}", {"fit", "truncation"} <= set(got.get("groups") or []))


if __name__ == "__main__":
    ctx = Ctx()
    results, passed, failed, skipped = run_all(TESTS, ctx)
    sys.exit(print_results(results, passed, failed, skipped))
