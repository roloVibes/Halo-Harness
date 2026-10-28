"""tests.test_studio_ollama -- Halo 3.3.4.0 R5 "the steward in Studio": Fleet's Ollama panel, Settings -> Ollama's
steward block and Setup's steward line, in headless Chrome through tests/helpers/studio_ollama.py (skipped without
one), over a scratch home with tests/helpers/ollama_panel_seed.py's fixture (a ledger, an event, the cards from
fixtures, a steward note, review mode); no provider request, no model call:

1. the quiet Fleet opens with nothing over it and without the panel; the "+" menu's Ollama row adds it;
2. the steward's attention row (O) opens it;
3. the host picker: pc, samus and the local server; each model row's numbers are the fixture's hour; the eye on
   the vision model, the VRAM share of the loaded one, the card line;
4. the timeline draws a bucket a minute with the hour's calls, the trim and the cut marked;
5. Apply on a finding: config.json's ollama.profiles has it and the row says applied; Dismiss: gone, and gone
   after a reload; Copy on the KV hint carries the exact env line;
6. Settings -> Ollama: the block sits above the rows; its model picker writes ollama.steward.model, its mode
   writes ollama.steward.apply; its button opens the panel;
7. Setup -> Providers: the Ollama card's "steward: <the note's first line>" and its link to the panel.
Run: python -m tests.test_studio_ollama
"""
from __future__ import annotations

TIER = "full"  # headless Chrome: the full tier

import json
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from tests.helpers import ollama_panel_seed as S  # noqa: E402
from tests.helpers.runner import Ctx, SkipTest, new_registry, print_results, run_all  # noqa: E402

test, TESTS = new_registry()
REPO = Path(__file__).resolve().parent.parent
_RUN: dict = {}


def _got(ctx: Ctx) -> dict:
    from tests.helpers.chrome_driver import driver_env, find_chrome
    if not find_chrome():
        raise SkipTest("no Chrome found (the Ollama panel checks need headless Chrome)")
    if "r" not in _RUN:
        r = subprocess.run([sys.executable, "-m", "tests.helpers.studio_ollama"], capture_output=True, encoding="utf-8",
                           errors="replace", timeout=420, env=driver_env(REPO), cwd=str(REPO), stdin=subprocess.DEVNULL)
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


def _hour(host: str) -> list:
    return sorted([m, v["calls"], v["trims"], v["cuts"], v["errors"]] for (h, m), v in S.HOUR.items() if h == host)


@test
def test_the_plus_menu_and_the_attention_row_open_it(ctx: Ctx):
    got = _got(ctx)
    ctx.check(f"the quiet Fleet: nothing over it, the panel not in the layout, got {got.get('quiet_open')} {got.get('quiet_has_panel')}",
              got.get("quiet_open") == [False, 0] and got.get("quiet_has_panel") is False)
    ctx.check(f"the + menu's row adds it, got {got.get('plus_word')} {got.get('plus_opened')}",
              got.get("plus_word") == "add" and got.get("plus_opened") == "pc")
    ctx.check(f"the steward's attention row names the note, got {got.get('attn_row')!r}",
              str(got.get("attn_row") or "").startswith(S.NOTE[:40]) and got.get("attn_before") is False)
    ctx.check(f"O opens the panel, got {got.get('attn_opened')}", got.get("attn_opened") == "pc")


@test
def test_the_host_picker_and_the_model_rows(ctx: Ctx):
    got = _got(ctx)
    ctx.check(f"pc, samus and the local server, got {got.get('hosts')}", got.get("hosts") == ["pc", "samus", "llama-box"])
    for host, key in (("pc", "pc_rows"), ("samus", "samus_rows"), ("llama-box", "local_rows")):
        ctx.check(f"{host}: each row's calls / trims / cuts / errors are the fixture's hour, got {got.get(key)}",
                  sorted(got.get(key) or []) == _hour(host))
    ctx.check("the local server says what comes next for Hugging Face", got.get("local_label") is True)
    ctx.check(f"the eye on the vision model only, got {got.get('eye')}", dict(got.get("eye") or []) == {S.BIG: True, S.CODER: False})
    ctx.check(f"the loaded model's VRAM share, got {got.get('vram')}", "90% VRAM" in (got.get("vram") or []))
    card = str(got.get("card") or "")
    ctx.check(f"the card line: the GPU, the server's settings, ComfyUI, got {card!r}",
              "GPU 0: a 24 GB card" in card and "KV cache f16" in card and "ComfyUI" in card)


@test
def test_the_timeline_draws(ctx: Ctx):
    got = _got(ctx)
    buckets, calls = (got.get("tl") or [0, 0])[:2]
    ctx.check(f"a bucket a minute, pc's 10 calls of the hour, got {got.get('tl')}", 60 <= buckets <= 62 and calls == 10)
    ctx.check(f"the trim, the cut and the error marked, got {got.get('tl_marks')}", got.get("tl_marks") == ["cut", "error", "trim"])
    ctx.check(f"one point a bucket, got {got.get('tl_line')}", got.get("tl_line") == buckets)


@test
def test_apply_dismiss_and_copy(ctx: Ctx):
    got = _got(ctx)
    ctx.check("review mode: the window finding has Apply", got.get("review_apply") is True)
    prof = got.get("applied_config") or {}
    ctx.check(f"Apply: ollama.profiles has the window, the row says applied, got {prof} {got.get('applied_row')!r}",
              prof.get("num_ctx") == 65536 and prof.get("by") == "steward" and got.get("applied_row") == "applied")
    ctx.check(f"the model row shows the profile and who set it, got {got.get('profile_cell')!r}",
              "window 65,536" in str(got.get("profile_cell")) and "by steward" in str(got.get("profile_cell")))
    ctx.check(f"Dismiss: the finding is gone, and still gone after a reload, got {got.get('dismissed')} "
              f"{got.get('dismiss_gone')} {got.get('dismiss_after_reload')}",
              str(got.get("dismissed") or "").startswith("reply-cut-") and got.get("dismiss_gone") is True
              and got.get("dismiss_after_reload") is True)
    ctx.check(f"Copy carries the exact env line, got {got.get('hint_line')!r} {got.get('copied')!r}",
              got.get("hint_line") == "OLLAMA_KV_CACHE_TYPE=q8_0" and got.get("copied") == "OLLAMA_KV_CACHE_TYPE=q8_0")


@test
def test_settings_block_and_setup_line(ctx: Ctx):
    got = _got(ctx)
    ctx.check(f"the steward's block sits above the rows with the job's status, got {got.get('settings_first')} "
              f"{str(got.get('settings_status'))[:80]!r}", got.get("settings_first") == "settings-ollama-block"
              and "steward job: not running" in str(got.get("settings_status")))
    ctx.check(f"the picker: automatic and none (no local model listed here), got {got.get('settings_models')}",
              got.get("settings_models") == ["", "none"])
    ctx.check(f"it writes ollama.steward.model and apply, got {got.get('model_config')!r} {got.get('mode_config')!r}",
              got.get("model_config") == "none" and got.get("mode_config") == "auto")
    ctx.check(f"the status says the model is none, got {str(got.get('model_says'))[:160]!r}", "is none" in str(got.get("model_says")))
    ctx.check("Open the Ollama panel lands on Fleet's panel", got.get("settings_open") is True)
    ctx.check(f"Setup's Ollama card: the steward's line, got {got.get('setup_line')!r}", got.get("setup_line") == f"steward: {S.NOTE}")
    ctx.check("its link opens the panel", got.get("setup_open") is True)


if __name__ == "__main__":
    ctx = Ctx()
    results, passed, failed, skipped = run_all(TESTS, ctx)
    sys.exit(print_results(results, passed, failed, skipped))
