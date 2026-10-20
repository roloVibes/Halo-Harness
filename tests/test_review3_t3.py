"""tests.test_review3_t3 -- pins for the 3.0.2.0 review fix pass, round T-tui:

  * item 78  the model picker reads gym results once and reuses its rows
             (item 162, the game themes' plain bar, went with the themes in
             3.1.5.0; tests/test_removed_themes.py pins the one bar now)

Run: python -m tests.test_review3_t3
"""
from __future__ import annotations

TIER = "full"  # a TUI pilot (Textual run_test): the full tier

import asyncio
import json
import sys
from pathlib import Path

REPO_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_DIR))

from tests.helpers.provider_env_defaults import ensure_default_provider_credentials, ensure_scoped_state_dir_once

ensure_default_provider_credentials()
ensure_scoped_state_dir_once()

from tests.helpers.runner import Ctx, new_registry, print_results, run_all  # noqa: E402

test, TESTS = new_registry()


@test
def test_item78_picker_reads_gym_once_and_keeps_the_score_suffix(ctx: Ctx):
    from textual.app import App
    from halo_harness import gym as gym_mod
    from halo_harness.config.paths import bridge_home
    from halo_harness.tui.dialogs.model_picker import ModelPicker

    host = Path(bridge_home()) / "gym" / "host1"
    host.mkdir(parents=True, exist_ok=True)
    result = host / "r3t.json"
    result.write_text(json.dumps({"model": "vendor/m-0", "model_ref": "or:vendor/m-0", "finished_at": 1,
                                  "tokens_per_second": 40.0, "tool_call_accuracy": {"score": 0.9},
                                  "edit_success": {"score": 0.8}, "context_recall": {"score": 0.7},
                                  "instruction_adherence": {"score": 0.6}}), encoding="utf-8")
    models = [{"ref": f"or:vendor/m-{i}", "provider": "openrouter", "group": "OpenRouter (or:)",
               "context_tokens": 128000, "price_in_per_m": 1.0, "price_out_per_m": 2.0} for i in range(300)]
    reads = []
    real_iter = gym_mod.iter_results
    gym_mod.iter_results = lambda state_dir: reads.append(1) or real_iter(state_dir)

    async def body():
        app = App()
        async with app.run_test(size=(140, 40)) as pilot:
            picker = ModelPicker(models)
            app.push_screen(picker)
            await pilot.pause(0.3)
            for query in ("m", "m-", "m-1", ""):
                picker._refresh_list(query)
            ol = picker.query_one("#model-list")
            first = str(ol.get_option("or:vendor/m-0").prompt)
            ctx.check(f"gym results were read once for five refreshes, got {len(reads)}", len(reads) == 1)
            ctx.check(f"the score suffix still shows, got {first!r}", "gym" in first)
            ctx.check(f"every row is listed, got {ol.option_count}", ol.option_count == 301)
    try:
        asyncio.run(body())
    finally:
        gym_mod.iter_results = real_iter
        result.unlink()


if __name__ == "__main__":
    ctx = Ctx()
    results, passed, failed, skipped = run_all(TESTS, ctx)
    sys.exit(print_results(results, passed, failed, skipped))
