"""tests.test_studio_pool -- Halo 3.3.8.0 R1 deliverable 6, the Chrome half: Local -> Pool in headless Chrome through
tests/helpers/studio_pool.py (skipped without one), over tests/helpers/host_rig.py's fake host and two rpc-server
stand-ins on 127.0.0.1:0; the scan's network layer faked; no model call, never a request beyond 127.0.0.1:

1. the page lists the two fixture members with their numbers (pc through its halo host: a 24 GB card, 24.0 GB free,
   2.5 GbE; worker1: 40 GB as stated), the recommendation table (Qwen3-Next fits the pool and ranks 1, gpt-oss does
   not fit) with the preview, and the line saying warm and stop arrive in R2; nothing opens over the page;
2. Scan is a button, not a load: nothing was scanned when the page opened; pressed, the two responders arrive, one is
   the member pc (its RTT now in its row), Add on the other makes a third member;
3. the Library's Pool preset: the three pool rows with their badges, the members line, no Save as role template.
Run: python -m tests.test_studio_pool
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
QWEN, OSS = "qwen3-next-80b-a3b-q4km", "gpt-oss-120b"


def _got(ctx: Ctx) -> dict:
    from tests.helpers.chrome_driver import driver_env, find_chrome
    if not find_chrome():
        raise SkipTest("no Chrome found (the Pool page checks need headless Chrome)")
    if "r" not in _RUN:
        r = subprocess.run([sys.executable, "-m", "tests.helpers.studio_pool"], capture_output=True, encoding="utf-8",
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
def test_the_page_lists_the_members_and_the_recommendation(ctx: Ctx):
    got = _got(ctx)
    m = {row[0]: row[1:] for row in got.get("members") or []}
    ctx.check(f"two members, pc through its card and worker1 as stated, got {m}", sorted(m) == ["pc", "worker1"]
              and m["pc"] == ["24.0 GB of 24.0 GB", "2.5 GbE", "a 24 GB card"]
              and m["worker1"][0] == "40.0 GB of 40.0 GB (as you stated it)")
    ctx.check(f"the head sums the free VRAM and gives the split, got {got.get('head')!r}", str(got.get("head")).startswith(
        "2 members, 2 with VRAM read: 64.0 GB free of 64.0 GB; split 0.38 / 0.62"))
    ctx.check(f"the recommendation: Qwen3-Next fits the pool (rank 1), gpt-oss does not, got {got.get('rec')}",
              got.get("rec") == [[QWEN, "pool", "1", "pool: fits (2 nodes, 32k Q8_0)"], [OSS, "no", None, "pool: no"]])
    ctx.check(f"the preview, got {got.get('preview')!r}", str(got.get("preview")).startswith(
        "needs 53.6 GB -- 64.0 GB free across 2 nodes; 32k Q8_0; one 2 GB routing table per node; download 46 GB")
              and str(got.get("preview")).endswith("nothing downloads until you press it"))
    ctx.check(f"what R1 cannot do yet, got {got.get('not_yet')!r}", "warm and stop arrive in R2" in str(got.get("not_yet")))
    ctx.check(f"nothing opens over the page, got {got.get('dialogs')}", got.get("dialogs") == 0)


@test
def test_scan_is_a_button_not_a_load(ctx: Ctx):
    got = _got(ctx)
    ctx.check(f"the page load scanned nothing, got {got.get('scanned_on_load')} {got.get('scan_line_before')!r}",
              got.get("scanned_on_load") is False and "not scanned yet" in str(got.get("scan_line_before")))
    ctx.check(f"Scan is a button, got {got.get('is_button')}", got.get("is_button") == "BUTTON")
    cands = got.get("cands") or []
    ctx.check(f"pressed: two responders, one the member pc (no Add), the other with Add, got {cands}", len(cands) == 2
              and sorted(x[1] for x in cands) == ["", "pc"] and [x[2] for x in cands if x[1] == "pc"] == [False]
              and [x[2] for x in cands if not x[1]] == [True])
    ctx.check(f"the scan was kept and pc's RTT is in its row, got {got.get('scan_file')} {got.get('rtt')!r}",
              got.get("scan_file") is True and str(got.get("rtt")).endswith("ms"))
    ctx.check(f"Add made a third member (by its address: pc-host is a member already), got {got.get('after_add')}",
              got.get("after_add") == ["pc", "worker1", "worker-1"])


@test
def test_the_librarys_pool_preset(ctx: Ctx):
    got = _got(ctx)
    ctx.check(f"three pool rows with their badges, got {got.get('lib')}", got.get("lib") == [
        ["pool/qwen3-next-80b-a3b-q4km", "pool"], ["pool/llama-3.3-70b-q4km", "pool"], ["pool/gpt-oss-120b", "no"]])
    ctx.check(f"the members line, no Save as role template, got {got.get('lib_head')!r} {got.get('lib_save')}",
              str(got.get("lib_head")).startswith("2 of 3 members with their VRAM read") and got.get("lib_save") is False)


if __name__ == "__main__":
    ctx = Ctx()
    results, passed, failed, skipped = run_all(TESTS, ctx)
    sys.exit(print_results(results, passed, failed, skipped))
