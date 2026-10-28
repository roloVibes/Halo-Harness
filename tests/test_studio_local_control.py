"""tests.test_studio_local_control -- Halo 3.3.5.0 R3 "Ollama, controlled": Studio's Local tab in headless Chrome
through tests/helpers/studio_local_control.py (skipped without one), over R1's seeded home (hosts pc and samus on
192.0.2.x placeholders, `box` a fake Ollama on 127.0.0.1:0 that pulls, copies and deletes); no provider request, no
model call, nothing sent but to the fake:

1. Library -> Pull on gemma3:4b to box: the button's title is the CLI line; the progress bar moves (percent, speed,
   time left) on `pull` frames; "installed on box" after; the Jobs list says done;
2. the typed pull of an HF GGUF through Ollama; a slow pull cancelled from the Jobs list (the fake sees the hang-up);
3. Models -> a row's actions menu, every item titled with its `halo models` line; Show (the /api/show facts beside
   the model card); Load now, then Unload from the Loaded-now strip (another machine's host: Unload disabled with why);
4. the tuned twin (its name, what it costs, then made and listed); Copy and Rename;
5. Delete with the uses card (a role names it: Delete anyway, gone from the fake) and a live session keeping it.
Run: python -m tests.test_studio_local_control
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
        raise SkipTest("no Chrome found (the Local control checks need headless Chrome)")
    if "r" not in _RUN:
        r = subprocess.run([sys.executable, "-m", "tests.helpers.studio_local_control"], capture_output=True, encoding="utf-8",
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
def test_pull_from_a_library_row_to_installed(ctx: Ctx):
    got = _got(ctx)
    ctx.check(f"Pull's title is the CLI line, got {got.get('pull_title')!r}", got.get("pull_title") == "halo models pull gemma3:4b --host box")
    pct, speed, left = (got.get("moving") or ["", "", ""])[:3]
    ctx.check(f"the bar moves: a percent, a speed, the time left, got {got.get('moving')}",
              0 < float(pct or 0) < 100 and speed.endswith("/s") and left.endswith("left"))
    ctx.check(f"installed on box after, the job done, got {got.get('installed')!r} {got.get('job_done')!r}",
              got.get("installed") == "installed on box" and got.get("job_done") == "done")


@test
def test_the_typed_pull_and_a_cancel_from_the_jobs_list(ctx: Ctx):
    got = _got(ctx)
    hf = "hf.co/example-org/Some-8B-GGUF:Q4_K_M"
    ctx.check(f"the typed HF GGUF pulls through Ollama, got {got.get('typed')!r} {got.get('pulled')}",
              got.get("typed") == f"{hf} pulled on box" and hf in (got.get("pulled") or [])
              and got.get("go_title") == f"halo models pull {hf} --host box")
    state, said = (got.get("cancelled") or ["", ""])[:2]
    ctx.check(f"cancelled from the Jobs list, the fake saw the hang-up, got {got.get('cancelled')} {got.get('fake_cancelled')}",
              state == "cancelled" and "keeps the layers" in said and got.get("fake_cancelled") == ["llama3.2:3b"])


@test
def test_the_actions_menu_show_and_load(ctx: Ctx):
    got = _got(ctx)
    titles = dict(got.get("menu_titles") or [])
    ctx.check(f"every item titled with its line, got {titles}", titles.get("show") == "halo models show qwen3.5:9b --host box"
              and titles.get("load") == "halo models load qwen3.5:9b --host box" and titles.get("delete") == "halo models rm qwen3.5:9b --host box"
              and {"twin", "copy", "rename"} <= set(titles))
    ctx.check(f"Show: the /api/show facts beside the card, got {got.get('show')} {got.get('show_card')}",
              {"quant", "context", "capabilities"} <= set(got.get("show") or []) and got.get("show_card") is True
              and got.get("show_cli") == "halo models show qwen3.5:9b --host box")
    ctx.check(f"Load now shows in the strip with its VRAM share; Unload from it, got {got.get('loaded')} {got.get('unloaded')}",
              (got.get("loaded") or [""])[0] == "100% VRAM" and got.get("unloaded") == 0)
    disabled, why = (got.get("samus_unload") or [False, ""])[:2]
    ctx.check(f"another machine's host: Unload disabled with why, got {got.get('samus_unload')}", disabled is True and "another machine" in why)


@test
def test_the_twin_copy_and_rename(ctx: Ctx):
    got = _got(ctx)
    name, cost = (got.get("twin") or ["", ""])[:2]
    ctx.check(f"the twin's name and its cost, got {got.get('twin')}", name == "qwen3.5-halo:9b" and "no new blobs" in cost)
    ctx.check(f"made and listed, got {got.get('twin_said')!r} {got.get('twin_row')}",
              "made qwen3.5-halo:9b" in str(got.get("twin_said")) and got.get("twin_row") is True)
    ctx.check(f"copied, then renamed, got {got.get('copied')} {got.get('renamed')}", got.get("copied") is True and got.get("renamed") is True)


@test
def test_delete_with_the_uses_card(ctx: Ctx):
    got = _got(ctx)
    line, button, title = (got.get("uses") or ["", "", ""])[:3]
    ctx.check(f"the uses card names the role; Delete anyway; its line has --force, got {got.get('uses')}",
              "`reviewer` role" in line and button == "Delete anyway" and title.endswith("--force"))
    ctx.check(f"deleted from the fake and the list, got {got.get('deleted')} {got.get('fake_deleted')}",
              got.get("deleted") is True and "qwen3-coder:30b" in (got.get("fake_deleted") or []))
    text, disabled = (got.get("live") or ["", False])[:2]
    ctx.check(f"a live session keeps Delete disabled, got {got.get('live')}", "1 live session is on it" in text and disabled is True)


if __name__ == "__main__":
    ctx = Ctx()
    results, passed, failed, skipped = run_all(TESTS, ctx)
    sys.exit(print_results(results, passed, failed, skipped))
