"""tests.test_studio_model_card -- Halo 3.3.5.0 R0b in the page. Headless
Chrome through the driver base (tests/helpers/studio_model_card.py; skipped
without one), over a seeded home whose Ollama host `pc` (a placeholder,
never asked) has the fixture catalog and hardware card in the server
process's caches; no provider request, no model call:

1. the Roles picker's rows carry the card's chips and the fit meter
   (`data-level`), and the picked row unfolds the card's `how` lines;
2. Setup -> Default model: the chips and meters; the coder picked shows the
   main-model line and the offer, whose button writes the lineup (active),
   the coder role on the model and `model` on the orchestrator;
3. Settings' `model` row shows the saved model's card (no offer: it can
   orchestrate) and its list rows carry the chips and the meter;
4. the Session header's effort control lists think on / off / default for a
   thinking local model and a pick writes `models.think`.
Run: python -m tests.test_studio_model_card
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
LINE = ("qwen3-coder:30b is a coding model with no tool calling on this server: it can write and answer but cannot act; "
        "as the main agent it would not run tools")


def _got(ctx: Ctx) -> dict:
    from tests.helpers.chrome_driver import driver_env, find_chrome
    if not find_chrome():
        raise SkipTest("no Chrome found (these checks need headless Chrome)")
    if "r" not in _RUN:
        r = subprocess.run([sys.executable, "-m", "tests.helpers.studio_model_card"], capture_output=True, encoding="utf-8",
                           errors="replace", timeout=400, env=driver_env(REPO), cwd=str(REPO), stdin=subprocess.DEVNULL)
        try:
            info = json.loads(r.stdout.strip().splitlines()[-1])
        except (ValueError, IndexError):
            info = {}
        _RUN["r"] = (r, info)
    r, info = _RUN["r"]
    if info.get("skip"):
        raise SkipTest(info["skip"])
    ctx.check(f"the driver ran, got {r.returncode} {info.get('failed')!r} {r.stderr[-600:]!r}", r.returncode == 0 and "failed" not in info)
    return info


@test
def test_the_roles_picker_rows_carry_the_card_and_the_meter(ctx: Ctx):
    got = _got(ctx)
    ctx.check(f"the chips per row, got {got.get('picker_chips')}",
              got.get("picker_chips") == ["no tools coder 64k", "tools instruct 128k", "thinks tools vision instruct 64k"])
    ctx.check(f"a meter per row with its level, got {got.get('picker_levels')}", got.get("picker_levels") == ["tight", "fits", "fits"])
    detail = got.get("picker_detail") or []
    ctx.check(f"the picked row's card: how Halo calls it, got {detail}",
              len(detail) == 5 and detail[1].startswith("no tools: answers only") and detail[-1].startswith("dialect: native"))


@test
def test_setup_default_model_shows_the_card_and_the_offer_writes_the_lineup(ctx: Ctx):
    got = _got(ctx)
    ctx.check(f"Setup's rows carry chips and meters, got {got.get('setup_chips')} {got.get('setup_levels')}",
              len(got.get("setup_chips") or []) == 3 and sorted(got.get("setup_levels") or []) == ["fits", "fits", "tight"])
    ctx.check(f"the one plain line, got {got.get('setup_line')!r}", got.get("setup_line") == LINE)
    ctx.check(f"the offer names the orchestrator, got {got.get('setup_offer')!r}",
              got.get("setup_offer") == "Keep it as the coder lane under ol:qwen3.8:27b")
    ctx.check(f"the button wrote the lineup and moved main, got {got.get('setup_said')!r}",
              (got.get("setup_said") or "").startswith("lineup 'local-coder' applied"))
    ctx.check(f"active, the coder role on the model, main on the orchestrator, got {got.get('team')} {got.get('coder_role')} "
              f"{got.get('model')}", got.get("team") == "local-coder" and got.get("coder_role") == "ol:qwen3-coder:30b"
              and got.get("model") == "ol:qwen3.8:27b")


@test
def test_the_settings_model_row(ctx: Ctx):
    got = _got(ctx)
    ctx.check(f"the saved model's card under the row, no offer, got {got.get('settings_panel')} {got.get('settings_offer')}",
              got.get("settings_panel") == "ol:qwen3.8:27b" and got.get("settings_offer") is False)
    ctx.check(f"the list rows carry the meter and the chips, got {got.get('settings_levels')} {got.get('settings_chips')}",
              got.get("settings_levels") == ["tight", "fits", "fits"] and all((n or 0) >= 3 for n in got.get("settings_chips") or [0]))


@test
def test_the_session_headers_effort_control(ctx: Ctx):
    got = _got(ctx)
    ctx.check(f"the word, then this model's options, got {got.get('effort_word')!r} {got.get('effort_options')}",
              got.get("effort_word") == "think default" and got.get("effort_options") == ["on", "off", "default"])
    ctx.check(f"a pick writes models.think and the word follows, got {got.get('effort_after')!r} {got.get('effort_saved')!r}",
              got.get("effort_after") == "think off" and got.get("effort_saved") == "off")


if __name__ == "__main__":
    results, passed, failed, skipped = run_all(TESTS, Ctx())
    sys.exit(print_results(results, passed, failed, skipped))
