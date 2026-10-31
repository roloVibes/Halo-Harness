"""tests.test_studio_search -- Halo 3.3.6.0 R2 "the page": Studio's Local -> Library search in headless Chrome
through tests/helpers/studio_search.py (skipped without one), over R1's seeded home (`box` a fake Ollama on
127.0.0.1:0) with the library's fixture sources, a seeded profile, a seeded crash and a pullable model the fake
answers the battery for; no provider request, no model call, nothing pulled but from the fake:

1. the resource strip pinned on top names box with its usable and free VRAM; the Coder preset shows its bundle;
2. moving the window re-reads every row against the strip (the strip's window, the rows and their fits change);
3. a row's capabilities carry the three marks (verified, declared, expected) with titles; the verdicts side by side;
4. the cost line (download and eta, VRAM, tok/s, what it evicts, each source in its title);
5. the crashed model shows its line, and Exclude crashed greys it and puts it last;
6. Download and verify: one job, the pull then the probe, to the role offer; Assign; Save as role template.
Run: python -m tests.test_studio_search
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
        raise SkipTest("no Chrome found (the search checks need headless Chrome)")
    if "r" not in _RUN:
        r = subprocess.run([sys.executable, "-m", "tests.helpers.studio_search"], capture_output=True, encoding="utf-8",
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
def test_the_strip_and_a_preset_with_its_bundle(ctx: Ctx):
    got = _got(ctx)
    card, text = (got.get("strip") or ["", ""])[:2]
    ctx.check(f"the strip: box, its usable and free VRAM, what is resident, got {text!r}",
              card == "yes" and "usable 24.0 GB" in text and "free" in text and "resident:" in text and "disk free" in text)
    ctx.check(f"the Coder bundle, expanded: tools and coder with their floors, got {got.get('bundle')}",
              ["tools", "declared"] in (got.get("bundle") or []) and ["coder", "expected"] in (got.get("bundle") or []))
    ctx.check(f"every row is a coder, got {got.get('coder_rows')}", (got.get("coder_rows") or 0) >= 3)


@test
def test_the_window_moves_and_every_row_reads_again(ctx: Ctx):
    got = _got(ctx)
    ctx.check(f"the strip follows the window, got {got.get('win_strip')}", got.get("win_strip") == "131072")
    a, b = got.get("fit_8k") or [], got.get("fit_128k") or []
    ctx.check(f"fits at 131,072 keeps fewer rows, each fits or tight, got {len(a)} -> {len(b)} {b}",
              0 < len(b) < len(a) and all(x in ("fits", "tight") for x in b))


@test
def test_the_three_marks_and_the_verdicts(ctx: Ctx):
    got = _got(ctx)
    truths = {t for _c, t, _g in got.get("marks") or []}
    glyph = {c: g for c, _t, g in got.get("marks") or []}
    ctx.check(f"qwen3.5:9b's chips: verified, declared and expected, got {got.get('marks')}",
              {"verified", "declared", "expected"} <= truths and glyph.get("tools") == "✓")
    ctx.check(f"the mark's title says what it means, got {got.get('mark_title')!r}", "verified: the battery probed it on this host" in str(got.get("mark_title")))
    ctx.check(f"fits and role-ready side by side, got {got.get('verdicts')!r}",
              str(got.get("verdicts")).startswith("fits: yes") and "role-ready: yes" in str(got.get("verdicts")))


@test
def test_the_cost_line(ctx: Ctx):
    got = _got(ctx)
    text, title = (got.get("cost") or ["", ""])[:2]
    ctx.check(f"download, VRAM at the window, cold load, tok/s, got {text!r}",
              text.startswith("cost: ") and " GB, ~" in text and "GiB at 32,768" in text and "tok/s" in text)
    ctx.check(f"each number's source in the title, got {title!r}", "download: assumed 50 MB/s" in title and "cold load:" in title and "speed:" in title)


@test
def test_a_crashed_row_is_greyed(ctx: Ctx):
    got = _got(ctx)
    ctx.check(f"the crash line, got {got.get('crash_line')!r}",
              str(got.get("crash_line")).startswith("crashed here on ") and "illegal memory access" in str(got.get("crash_line"))
              and "after a spill at 65,536" in str(got.get("crash_line")))
    ctx.check(f"the filters in three groups, got {got.get('groups')}", got.get("groups") == ["capability", "fit", "supply"])
    ctx.check(f"Exclude crashed: greyed and last, got {got.get('greyed')}", got.get("greyed") == ["true", "qwen3-coder:30b"])


@test
def test_download_and_verify_to_the_role_offer(ctx: Ctx):
    got = _got(ctx)
    ctx.check(f"the button says what it does and that nothing downloads before, got {got.get('verify_title')!r}",
              "run the battery" in str(got.get("verify_title")) and "verify role" in str(got.get("verify_title")))
    ctx.check(f"the job: pull, then probe, then the offer, got {got.get('first_stage')} {got.get('stages')} {got.get('pull_bar')}",
              got.get("first_stage") in ("pull", "probe") and "offer" in (got.get("stages") or []) and ["pull", "done"] in (got.get("pull_bar") or []))
    ctx.check(f"the offer, got {got.get('offer')!r}", "assign `verify` to ol:qwen3:8b@box?" in str(got.get("offer")))
    ctx.check(f"Assign writes the active lineup and applies it again, got {got.get('assigned')!r}",
              "verify is ol:qwen3:8b@box in " in str(got.get("assigned")) and "roles.verify follows" in str(got.get("assigned")))
    ctx.check(f"pulled from the fake only, got {got.get('pulled')}", got.get("pulled") == ["qwen3:8b"])
    ctx.check(f"Save as role template, got {got.get('template')!r}", "lineup local-verifier written (not active)" in str(got.get("template")))


if __name__ == "__main__":
    ctx = Ctx()
    results, passed, failed, skipped = run_all(TESTS, ctx)
    sys.exit(print_results(results, passed, failed, skipped))
