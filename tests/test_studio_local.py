"""tests.test_studio_local -- Halo 3.3.5.0 R1 "the Local tab": Studio's Local section in headless Chrome through
tests/helpers/studio_local.py (skipped without one), over a scratch home with tests/helpers/local_seed.py's fixture
(the Ollama panel's hosts, ledger, cards and catalogs, and `box`, a fake Ollama on 127.0.0.1:0); the sampler reads
the fixture's nvidia-smi and /proc answers; no provider request, no model call:

1. Alt+0 opens Local with nothing open over it, on Resources;
2. the eight pages in the rail's order (3.3.6.0 R3: Logs), each titled; Benchmarks and Steward framed (what they
   will hold, the commands today; Library is built in R2: tests/test_studio_library.py); Steward shows the job's status and the last note; each page names its ideas;
3. Resources: a strip per sampled host, moving on `resources` frames; every number titled with its source;
4. the traffic view's rows match the fixture ledger, its sparklines per host; a line written now arrives at the foot;
5. Hosts: the cards' numbers (pc's 90% VRAM, who calls it, why it has no control from here); Load and Unload on box
   reach the fake (a generate, then keep_alive 0); Make it fit writes the plan's profile change and Undo takes it back;
6. Models: every row with the card's chips and the fit meter; the intent filter's order (embed: the embedding model;
   code: the coder first) and its why line; the coder-lane button only where it applies, and it writes the lineup.
Run: python -m tests.test_studio_local
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
PAGES = ["resources", "hosts", "models", "library", "huggingface", "logs", "benchmarks", "steward"]  # 3.3.6.0 R3: Logs


def _got(ctx: Ctx) -> dict:
    from tests.helpers.chrome_driver import driver_env, find_chrome
    if not find_chrome():
        raise SkipTest("no Chrome found (the Local tab checks need headless Chrome)")
    if "r" not in _RUN:
        r = subprocess.run([sys.executable, "-m", "tests.helpers.studio_local"], capture_output=True, encoding="utf-8",
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
def test_alt0_and_the_seven_pages(ctx: Ctx):
    got = _got(ctx)
    ctx.check(f"Alt+0 opens Local with nothing over it, on Resources, got {got.get('alt0')} {got.get('alt0_open')} {got.get('alt0_page')}",
              got.get("alt0") == "Local" and got.get("alt0_open") == [0, 0] and got.get("alt0_page") == "resources")
    ctx.check(f"the rail's eight pages in order, got {got.get('rail')}", got.get("rail") == PAGES)
    titles = got.get("titles") or {}
    ctx.check(f"each page titled, got {titles}", [titles.get(p) for p in PAGES] ==
              ["Resources", "Hosts", "Models", "Library", "Hugging Face", "Logs", "Benchmarks", "Steward"])
    framed = got.get("framed") or {}
    ctx.check(f"the framed page says what it will hold and the commands today (Library is built, 3.3.5.0 R2; Hugging "
              f"Face, R5; Benchmarks, 3.3.6.0 R5), got {framed}", sorted(framed) == ["steward"]
              and all(n > 200 and k >= 3 for n, k in framed.values()))
    ctx.check(f"Steward: the job's status line and the last note, got {str(got.get('steward_status'))[:80]!r}",
              "steward job" in str(got.get("steward_status")) and str(got.get("steward_note") or "").startswith("The 27B spills"))
    ctx.check(f"each page names its ideas, got {got.get('ideas')!r}", str(got.get("ideas") or "").startswith("ideas here: "))


@test
def test_the_resources_strip_moves_and_says_where_each_number_came_from(ctx: Ctx):
    got = _got(ctx)
    ctx.check(f"a strip per sampled host, got {got.get('strips')}", got.get("strips") == ["box", "pc"])
    t0, t1 = (got.get("moved") or [0, 0])[:2]
    ctx.check(f"it moves on resources frames, got {got.get('moved')}", t1 > t0 > 0)
    ctx.check(f"the VRAM bar's figure and its holder (/api/ps: the driver names no bytes), got {got.get('vram')!r} {got.get('holder')!r}",
              str(got.get("vram") or "").startswith("VRAM ") and "of 24.0 GiB" in str(got.get("vram")) and got.get("holder") == "held by qwen3.8:27b")
    titles = dict(got.get("res_titles") or [])
    ctx.check(f"every number titled with its source, got {titles}",
              all(k in titles for k in ("local-res-vram", "local-res-holder", "local-res-gpu", "local-res-ram", "local-res-cpu", "local-res-temp"))
              and "nvidia-smi" in titles["local-res-gpu"] and "/proc/meminfo" in titles["local-res-ram"] and "/api/ps" in titles["local-res-holder"])
    ctx.check(f"the GPU sparkline draws the last minute, got {got.get('spark')}", (got.get("spark") or 0) >= 2)


@test
def test_the_traffic_view_follows_the_ledger(ctx: Ctx):
    got = _got(ctx)
    rows = got.get("trows") or []
    hosts = sorted({h for h, _m, _s in rows})
    ctx.check(f"the fixture ledger's 13 calls of the last 15 minutes, got {len(rows)} on {hosts}", len(rows) == 13
              and hosts == ["box", "llama-box", "pc"])
    states = sorted(s for _h, _m, s in rows if s != "ok")
    ctx.check(f"the trim, the cuts and the 500 marked, got {states}", states == ["500", "cut", "cut", "trimmed"])
    ctx.check(f"a sparkline per host, got {got.get('sparks')}", sorted(map(tuple, got.get("sparks") or [])) == [("box", 3), ("llama-box", 3), ("pc", 7)])
    ctx.check(f"a line written now arrives at the foot as a traffic frame, got {got.get('live_row')!r}", got.get("live_row") == "box")
    ctx.check("Follow keeps the newest row in view", got.get("follow_at_foot") is True)


@test
def test_the_hosts_page_and_its_controls(ctx: Ctx):
    got = _got(ctx)
    ctx.check(f"every host as a card, the controls where they apply, got {got.get('cards')}", (got.get("cards") or [])[:4] ==
              [["pc", "configured", "no"], ["samus", "configured", "no"], ["box", "configured", "yes"], ["llama-box", "local server", "no"]])
    ctx.check(f"pc's numbers: 90% VRAM, who calls it, got {got.get('pc_vram')!r} {got.get('pc_users')!r}",
              got.get("pc_vram") == "90% VRAM" and got.get("pc_users") == "who calls it: this machine 12")
    ctx.check(f"pc: why there is no Load from here, got {got.get('pc_why')!r}", "served by another machine" in str(got.get("pc_why")))
    ctx.check(f"Load reached the fake (a generate), Unload sent keep_alive 0, got {got.get('loaded')} {got.get('unloaded')!r}",
              got.get("loaded") == ["qwen3.5:9b"] and got.get("unloaded") == 0)
    prof = got.get("fit_profiles") or {}
    ctx.check(f"Make it fit: the plan's chosen option as a steward profile, got {prof}",
              list(prof) == ["pc|qwen3-coder:30b"] and prof["pc|qwen3-coder:30b"].get("keep_alive") == "0"
              and prof["pc|qwen3-coder:30b"].get("by") == "steward")
    ctx.check(f"Undo takes it back, got {got.get('after_undo')}", got.get("after_undo") == {})


@test
def test_the_models_page_and_the_intent_filter(ctx: Ctx):
    got = _got(ctx)
    rows = got.get("mrows") or []
    ctx.check(f"every installed model per host, each with its chips and its meter, got {rows}", len(rows) == 6
              and all(chips and meter for *_x, chips, meter in rows) and [r[1] for r in rows if r[0] == "box"] ==
              ["qwen3.5:9b", "qwen3-coder:30b", "nomic-embed-text"])
    ctx.check(f"embed: the embedding model only, got {got.get('embed')}", got.get("embed") == ["nomic-embed-text"])
    ctx.check(f"code: the coder first on box, got {got.get('code_box')}", got.get("code_box") == ["qwen3-coder:30b", "qwen3.5:9b"])
    ctx.check(f"and one line says why this order, got {got.get('why')!r}", str(got.get("why") or "").startswith("why this order: coding models first"))
    lanes = got.get("lane_buttons") or []
    ctx.check(f"the coder lane offered where the model cannot orchestrate but can code (not the embedding model), got {lanes}",
              "qwen3-coder:30b" in lanes and "nomic-embed-text" not in lanes)
    ctx.check(f"the button writes the lineup and the main model, got {got.get('lane_said')!r} {got.get('lane_config')}",
              "local-coder" in str(got.get("lane_said")) and got.get("lane_config") == ["local-coder", "ol:qwen3.5:9b@box"])


if __name__ == "__main__":
    ctx = Ctx()
    results, passed, failed, skipped = run_all(TESTS, ctx)
    sys.exit(print_results(results, passed, failed, skipped))
