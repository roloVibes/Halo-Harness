"""tests.test_steward_called_wrong -- Halo 3.3.5.0 R0b (e): the steward knows
the model card. The ledger line carries `body_flags` {think, tools, images}
(`ledger_call.body_flags`); rule `called-wrong` (ollama_steward/rules_card.py)
holds each line against the model's card and says the fix in the card's own
`how` words; a line that matches the card is no finding; a model with no
catalog row is not judged; symptoms.md has its row. Fixture ledger lines and
catalog rows (tests/helpers/model_card_fixtures.py), a scratch home: no
server, no model call.
Run: python -m tests.test_steward_called_wrong
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from tests.helpers.provider_env_defaults import ensure_default_provider_credentials  # noqa: E402
ensure_default_provider_credentials()

from tests.helpers.model_card_fixtures import ROWS, write_probes  # noqa: E402
from tests.helpers.runner import Ctx, new_registry, print_results, run_all  # noqa: E402
from tests.helpers.steward_seed import Home, line  # noqa: E402

test, TESTS = new_registry()


def _found(h, catalogs) -> list:
    from halo_harness.ollama_steward.rules import findings
    return [f for f in findings(h.state, catalogs=catalogs) if f["rule"] == "called-wrong"]


@test
def test_the_body_flags_on_a_ledger_line(ctx: Ctx):
    from halo_harness.ollama_steward.ledger import FIELDS
    from halo_harness.ollama_steward.ledger_call import body_flags
    got = body_flags({"think": True, "tools": [{"type": "function"}],
                      "messages": [{"role": "user", "content": "x", "images": ["aGk="]}]})
    ctx.check(f"think, tools and images read off the body, got {got}", got == {"think": True, "tools": True, "images": True})
    ctx.check("an OpenAI-dialect body's reasoning_effort counts as think",
              body_flags({"reasoning_effort": "low", "messages": []}) == {"think": "low", "tools": False, "images": False})
    ctx.check("the ledger has the field", "body_flags" in FIELDS)


@test
def test_a_tool_catalog_and_a_think_flag_against_the_card(ctx: Ctx):
    with Home() as h:
        write_probes(h.state)
        h.calls(line(model="qwen3-coder:30b", body_flags={"think": True, "tools": True, "images": False}),
                line(model="qwen3-coder:30b", body_flags={"think": None, "tools": True, "images": False}),
                line(model="qwen3-coder:30b", body_flags={"think": None, "tools": False, "images": False}))
        found = _found(h, {"pc": {"qwen3-coder:30b": dict(ROWS["qwen3-coder:30b"])}})
    f = found[0] if found else {}
    ctx.check(f"one finding for the two calls that went wrong, got {[x.get('finding') for x in found]}",
              len(found) == 1 and f["evidence"]["numbers"]["calls"] == 2)
    ctx.check(f"it names what was sent and why, got {f.get('finding')!r}",
              f.get("finding", "").startswith("2 calls to qwen3-coder:30b sent a think value and a tool catalog, which its card "
                                              "says it cannot take (it does not think; it has no tool calling here)"))
    ctx.check(f"the fix is the card's how line, got {f.get('fix')!r}",
              "no think field (the model does not think)" in f.get("fix", "")
              and "no tools: answers only" in f.get("fix", "") and f.get("fix", "") in f.get("finding", ""))
    ctx.check(f"counted per part, got {f.get('evidence', {}).get('numbers')}",
              f.get("evidence", {}).get("numbers", {}).get("think") == 1 and f["evidence"]["numbers"]["tools"] == 2)
    ctx.check("a warning with no profile change", f.get("severity") == "warn" and f.get("proposal") is None)


@test
def test_images_to_a_model_without_vision(ctx: Ctx):
    with Home() as h:
        h.calls(line(model="qwen3.5:9b", body_flags={"think": None, "tools": True, "images": True}))
        found = _found(h, {"pc": {"qwen3.5:9b": dict(ROWS["qwen3.5:9b"])}})
    ctx.check(f"images to a model with no vision, got {[x['finding'] for x in found]}",
              len(found) == 1 and "sent images" in found[0]["finding"] and "images as captions" in found[0]["fix"])


@test
def test_a_call_that_matches_the_card_and_a_model_with_no_row(ctx: Ctx):
    with Home() as h:
        h.calls(line(model="qwen3.8:27b", body_flags={"think": True, "tools": True, "images": True}),
                line(model="unknown:7b", body_flags={"think": True, "tools": True, "images": True}),
                line(model="qwen3.8:27b"))
        found = _found(h, {"pc": {"qwen3.8:27b": dict(ROWS["qwen3.8:27b"])}})
    ctx.check(f"the 27B thinks, calls tools and sees; the unknown model is not judged, got {found}", not found)


@test
def test_the_symptoms_row(ctx: Ctx):
    from halo_harness.ollama_steward.explain import symptom_rows
    rows = symptom_rows()
    ctx.check(f"symptoms.md has the called-wrong row, got {sorted(rows)[:3]}...", "called-wrong" in rows)


if __name__ == "__main__":
    results, passed, failed, skipped = run_all(TESTS, Ctx())
    sys.exit(print_results(results, passed, failed, skipped))
