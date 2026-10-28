"""tests.test_studio_library -- Halo 3.3.5.0 R2 "the library browser and the fit badge": Studio's Local -> Library in
headless Chrome through tests/helpers/studio_library.py (skipped without one), over R1's seeded home (hosts pc and
samus on 192.0.2.x placeholders, `box` a fake Ollama on 127.0.0.1:0) with the fixture sources (the shipped snapshot,
the hub's fixtures); no provider request, no model call, nothing pulled:

1. the page lists the library, its source line names the snapshot's date with Refresh, each size says its source;
2. the source switch (Hugging Face only, then both) and a typed search;
3. the host picker and the window control move gemma3:27b's fit badge: fits at 8,192, tight at 16,384, no at
   131,072, the numbers as its title; "fits this host" keeps fits and tight;
4. the unfold: the card's how lines ("once pulled") and the other tags, each with its fit meter;
5. Pull is enabled with its CLI line (R3 pulls: tests/test_studio_local_control.py); Copy takes the pull line; the embed intent leaves embedding models only.
Run: python -m tests.test_studio_library
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
        raise SkipTest("no Chrome found (the Library checks need headless Chrome)")
    if "r" not in _RUN:
        r = subprocess.run([sys.executable, "-m", "tests.helpers.studio_library"], capture_output=True, encoding="utf-8",
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
def test_the_page_and_where_its_rows_came_from(ctx: Ctx):
    got = _got(ctx)
    ctx.check(f"the library's rows, got {got.get('rows')}", (got.get("rows") or 0) >= 300)
    ollama, hf, snap, text = (got.get("sources") or [None, None, False, ""])[:4]
    ctx.check(f"the source line: the snapshot with its date and Refresh, the hub's fixtures, got {got.get('sources')}",
              str(ollama).startswith("snapshot 20") and hf == "fixtures" and snap is True and "snapshot from 20" in text and "Refresh" in text)
    ctx.check(f"a size says where it came from, got {got.get('size_title')!r}", "model layer" in str(got.get("size_title")) or "tags page" in str(got.get("size_title")))
    ctx.check(f"each page names its ideas, got {got.get('ideas')!r}", "fit meter" in str(got.get("ideas")) and "intents" in str(got.get("ideas")))


@test
def test_the_source_switch_and_the_search(ctx: Ctx):
    got = _got(ctx)
    ctx.check(f"Hugging Face only: the hub's repos, got {(got.get('hf_rows') or [])[:3]}",
              len(got.get("hf_rows") or []) >= 10 and all("/" in n for n in got.get("hf_rows") or []))
    ctx.check(f"a typed search narrows the rows, got {got.get('searched')}",
              got.get("searched") and all("gemma3" in n for n in got["searched"]) and "gemma3:27b" in got["searched"])


@test
def test_the_fit_badge_follows_the_host_and_the_window(ctx: Ctx):
    got = _got(ctx)
    w = got.get("windows") or {}
    levels = [(w.get(k) or [None])[0] for k in ("8192", "16384", "131072")]
    ctx.check(f"on box: fits, tight, no as the window grows, got {levels}", levels == ["fits", "tight", "no"])
    title = (w.get("8192") or ["", ""])[1]
    ctx.check(f"the numbers are the badge's title, got {title!r}", title.startswith("weights ") and "GiB free" in title and "KV" in title)
    ctx.check(f"no says what it needs against the card and the RAM, got {(w.get('131072') or ['', ''])[1][-160:]!r}",
              "the card has 24.0 GiB and the RAM 64.0 GiB" in (w.get("131072") or ["", ""])[1])
    fits = got.get("fits_only") or []
    ctx.check(f"fits this host keeps fits and tight, got {fits}", fits and all(lv in ("fits", "tight") for _n, lv in fits))


@test
def test_the_unfold_pull_copy_and_the_intent(ctx: Ctx):
    got = _got(ctx)
    how = got.get("how") or []
    ctx.check(f"the card's how lines, each once pulled, got {how}", how and all(h.endswith("(once pulled)") for h in how))
    others = got.get("others") or []
    ctx.check(f"the other tags, each with its fit meter, got {others[:4]}",
              len(others) >= 3 and all(meter for _n, _f, meter in others) and any(n == "gemma3:27b" for n, _f, _m in others))
    ctx.check(f"Pull (3.3.5.0 R3) onto the host picked, its CLI line as its title, got {got.get('pull')}",
              got.get("pull") == [False, "halo models pull gemma3:27b --host box"])
    said, line = (got.get("copied") or ["", ""])[:2]
    ctx.check(f"Copy takes the pull line (or says to copy it by hand), got {got.get('copied')} {got.get('clipboard')!r}",
              line == "ollama pull gemma3:27b" and said in ("copied", "by-hand") and (said != "copied" or got.get("clipboard") in (line, "unreadable")))
    ctx.check(f"embed: embedding models only, got {got.get('embed')}", got.get("embed") and all(
        any(w in n for w in ("embed", "bge", "minilm", "paraphrase", "nomic", "mxbai", "granite-embedding", "snowflake")) for n in got["embed"]))


if __name__ == "__main__":
    ctx = Ctx()
    results, passed, failed, skipped = run_all(TESTS, ctx)
    sys.exit(print_results(results, passed, failed, skipped))
