"""tests.test_capabilities -- which model for what (Halo 3.0.1.0 round D1):
capability profiles come only from catalog facts (modalities, image
output, context, price, speed), unknown stays unknown, the rankings for
visual / audio / video / image / design pick the right rows with a reason,
the preflight canaries demote a lane, and `halo models --capabilities` /
`--best-for` print them.
"""

from __future__ import annotations

import io
import sys
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from tests.helpers.provider_env_defaults import ensure_default_provider_credentials, ensure_scoped_state_dir_once

ensure_default_provider_credentials()
ensure_scoped_state_dir_once()

from tests.helpers.runner import Ctx, new_registry, print_results, run_all  # noqa: E402

test, TESTS = new_registry()

ROWS = [
    {"ref": "or:v/see-all", "provider": "openrouter", "context_tokens": 1_000_000, "price_in_per_m": 1.0, "price_out_per_m": 5.0,
     "modalities_in": ["text", "image", "video", "audio", "file"], "modalities_out": ["text"], "image_output": False, "speed_tokens_per_second": 90},
    {"ref": "or:v/painter", "provider": "openrouter", "context_tokens": 65_536, "price_in_per_m": 1.5, "price_out_per_m": 7.5,
     "modalities_in": ["text", "image"], "modalities_out": ["text", "image"], "image_output": True},
    {"ref": "or:v/cheap-eyes", "provider": "openrouter", "context_tokens": 128_000, "price_in_per_m": 0.1, "price_out_per_m": 0.4,
     "modalities_in": ["text", "image"], "modalities_out": ["text"], "image_output": False, "speed_tokens_per_second": 40},
    {"ref": "or:v/text-only", "provider": "openrouter", "context_tokens": 200_000, "price_in_per_m": 0.5, "price_out_per_m": 2.0,
     "modalities_in": ["text"], "modalities_out": ["text"], "image_output": False},
    {"ref": "ol:mystery", "provider": "ollama", "context_tokens": 32_000, "price_in_per_m": 0, "price_out_per_m": 0},
    {"ref": "ol:local-eyes", "provider": "ollama", "context_tokens": 32_000, "price_in_per_m": 0, "price_out_per_m": 0,
     "modalities_in": ["text", "image"]},
    {"ref": "cc:opus", "provider": "cc", "context_tokens": 1_000_000, "price_in_per_m": None, "modalities_in": ["text", "image"]},
    {"ref": "alias-row", "provider": "alias", "target": "or:v/see-all"},
    {"hint": "something"},
]


@test
def test_profiles_come_from_facts_and_unknown_stays_unknown(ctx: Ctx):
    from halo_harness.capabilities import capability_profile
    p = capability_profile(ROWS[0])
    ctx.check("every stated input modality is read", p["vision"] and p["audio"] and p["video"] and p["files"] and p["known"])
    ctx.check("image output comes from the catalog flag", capability_profile(ROWS[1])["image_out"] is True and p["image_out"] is False)
    u = capability_profile(ROWS[4])
    ctx.check("a row without modality data is unknown, not false", u["known"] is False and u["vision"] is None and u["chips"] == "?")
    ctx.check("a text-only row says text", capability_profile(ROWS[3])["chips"] == "text")
    ctx.check("chips name what the model does", capability_profile(ROWS[0])["chips"] == "vision audio video files")


@test
def test_rankings_pick_the_right_rows_with_reasons(ctx: Ctx):
    from halo_harness.capabilities import KINDS, best_for
    audio = best_for(ROWS, "audio")
    ctx.check("audio ranks only the row that accepts audio", [r["ref"] for r in audio] == ["or:v/see-all"] and "accepts audio" in audio[0]["reason"])
    video = best_for(ROWS, "video")
    ctx.check("video likewise", [r["ref"] for r in video] == ["or:v/see-all"])
    image = best_for(ROWS, "image")
    ctx.check("image ranks only the image-output row", [r["ref"] for r in image] == ["or:v/painter"] and "makes images" in image[0]["reason"])
    visual = best_for(ROWS, "visual")
    refs = [r["ref"] for r in visual]
    ctx.check("visual excludes text-only and unknown rows and never lists aliases or hints",
              "or:v/text-only" not in refs and "ol:mystery" not in refs and "alias-row" not in refs and len(refs) == 5)
    ctx.check("visual prefers big context and low price (see-all and cheap-eyes lead)", set(refs[:2]) == {"or:v/see-all", "or:v/cheap-eyes"} or refs[0] == "or:v/see-all")
    ctx.check("every ranked row has a plain reason", all(r["reason"] and "reads images" in r["reason"] for r in visual))
    design = best_for(ROWS, "design")
    ctx.check("design ranks vision rows and weighs speed and tools", design[0]["ref"] == "or:v/see-all" and "tok/s" in design[0]["reason"])
    ctx.check("limit applies", len(best_for(ROWS, "visual", limit=2)) == 2)
    ctx.check("an unknown kind raises", _raises(lambda: best_for(ROWS, "smell")) and set(KINDS) >= {"visual", "audio", "video", "image", "design"})


def _raises(fn) -> bool:
    try:
        fn()
    except ValueError:
        return True
    return False


@test
def test_preflight_results_demote_and_promote(ctx: Ctx):
    from halo_harness.capabilities import best_for
    pf = {"or:v/see-all": {"vision": False, "tools": True}, "or:v/cheap-eyes": {"vision": True, "tools": True}}
    design = best_for(ROWS, "design", preflight=pf)
    refs = [r["ref"] for r in design]
    ctx.check("a lane that failed the image canary drops to the bottom", refs[-1] == "or:v/see-all" and "failed the preflight image canary" in design[-1]["reason"])
    ctx.check("a lane that passed the canary says so", any(r["ref"] == "or:v/cheap-eyes" and "passed the preflight" in r["reason"] for r in design))


@test
def test_catalog_rows_carry_modalities(ctx: Ctx):
    """build_model_rows reads input_modalities / output_modalities /
    pricing.image_output from a models.json fixture."""
    import json
    from halo_harness.providers.config import default_state_dir
    from halo_harness.providers.model_enumeration import build_model_rows
    state = Path(default_state_dir())
    state.mkdir(parents=True, exist_ok=True)
    (state / "models.json").write_text(json.dumps({
        "v/eyes": {"context_length": 100000, "input_modalities": ["text", "image"], "pricing": {"prompt": "0.000001", "completion": "0.000002"}},
        "v/painter": {"context_length": 50000, "input_modalities": ["text"], "pricing": {"prompt": "0.000001", "completion": "0.000002", "image_output": "0.00003"}},
        "v/plain": {"context_length": 50000, "pricing": {"prompt": "0.000001", "completion": "0.000002"}},
    }), encoding="utf-8")
    rows = {r["ref"]: r for r in build_model_rows(state, env={"OPENROUTER_API_KEY": "x"}) if r.get("ref")}
    ctx.check("an OpenRouter row carries its input modalities", rows.get("or:v/eyes", {}).get("modalities_in") == ["text", "image"])
    ctx.check("image_output pricing marks image output", rows.get("or:v/painter", {}).get("image_output") is True and "image" in (rows["or:v/painter"].get("modalities_out") or []))
    ctx.check("a row without the field stays None (unknown), never an empty list", rows.get("or:v/plain", {}).get("modalities_in") is None)


@test
def test_cli_capabilities_and_best_for(ctx: Ctx):
    from halo_harness.catalog_cli import cmd_models
    buf = io.StringIO()
    with redirect_stdout(buf):
        rc = cmd_models(["--capabilities"])
    out = buf.getvalue()
    ctx.check(f"--capabilities prints in:/out: columns, got {out[:120]!r}", rc == 0 and "in: " in out and "out: " in out)
    buf = io.StringIO()
    with redirect_stdout(buf):
        rc = cmd_models(["--best-for", "visual"])
    out = buf.getvalue()
    ctx.check(f"--best-for visual prints a ranked list with reasons, got {out[:160]!r}", rc == 0 and "or:v/eyes" in out and "reads images" in out)
    buf = io.StringIO()
    with redirect_stdout(buf), redirect_stderr(buf):
        rc = cmd_models(["--best-for", "smell"])
    ctx.check("an unknown kind is refused with the list of kinds", rc != 0 and "visual" in buf.getvalue())


if __name__ == "__main__":
    ctx = Ctx()
    results, passed, failed, skipped = run_all(TESTS, ctx)
    sys.exit(print_results(results, passed, failed, skipped, label="capabilities tests"))
