"""tests.test_picker_columns -- Halo 2.0.4 round 3 (deliverable 1): the
picker's three columns (price per million in/out, context, speed), the
"?" (never a blank that looks like zero) convention, the sort-cycle key
(`s`) and the per-group/all-groups refresh keys (`r`/`R`) in
`tui/dialogs/model_picker.py`.

Hierarchical OpenRouter pick (vendor, then model) is NOT covered here --
see the hand-back's WHAT YOU FOUND for why that part of deliverable 1 is
left PARTIAL this round.
"""
import asyncio
import os
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

os.environ.setdefault("BRIDGE_TEST_HOME", tempfile.mkdtemp(prefix="picker-columns-"))
os.environ.setdefault("BRIDGE_TEST_NO_BACKGROUND_NET", "1")

from tests.helpers.runner import Ctx, new_registry, print_results, run_all

test, TESTS = new_registry()


# ---------------------------------------------------------------------------
# Pure: model_display.py's own new functions -- known, unknown and sentinel
# values ("blank that looks like zero" must never appear: unknown is
# always literally "?").
# ---------------------------------------------------------------------------

@test
def test_format_speed_known_unknown_and_one_sided(ctx: Ctx):
    from halo_harness.model_display import format_speed
    ctx.check("both known", format_speed(1.2, 48) == "1.2s · 48 t/s")
    ctx.check("ttft only", format_speed(0.8, None) == "0.8s")
    ctx.check("tok/s only", format_speed(None, 12) == "12 t/s")
    ctx.check("neither known -> blank, not a placeholder", format_speed(None, None) == "")
    ctx.check("a zero tok/s is unknown, not a real reading", format_speed(None, 0) == "")
    ctx.check("a negative ttft (never real) is treated as unknown", format_speed(-1, None) == "")


@test
def test_unknown_as_qmark(ctx: Ctx):
    from halo_harness.model_display import unknown_as_qmark
    ctx.check("blank becomes ?", unknown_as_qmark("") == "?")
    ctx.check("a real value is untouched", unknown_as_qmark("$1.00/M") == "$1.00/M")


@test
def test_format_picker_row_sentinels_never_blank(ctx: Ctx):
    """price -1 ("varies"), price 0 ("free") -- round 2's own fix pass,
    reused unchanged by the picker row -- and a totally empty entry still
    renders three "?" columns, never a blank field."""
    from halo_harness.model_display import format_picker_row
    router_row = format_picker_row({"ref": "or:openrouter/auto", "price_in_per_m": -1, "price_out_per_m": -1,
                                     "context_tokens": 2_000_000})
    ctx.check(f"a router's -1 price reads 'varies', got {router_row!r}", "varies" in router_row)
    free_row = format_picker_row({"ref": "xp:space-bunny-alpha", "price_in_per_m": 0, "price_out_per_m": 0,
                                   "context_tokens": 1_000_000})
    ctx.check(f"a $0 preview model reads 'free', got {free_row!r}", "free" in free_row)
    empty_row = format_picker_row({"ref": "dbx:some-endpoint"})
    ctx.check(f"every unknown column is '?', never blank, got {empty_row!r}",
              "in=?" in empty_row and "out=?" in empty_row and "ctx=?" in empty_row and "speed=?" in empty_row)
    ctx.check("no bare blank-looks-like-zero gap remains", "in= " not in empty_row and "out= " not in empty_row)
    # Fixpass finding (caught by the two-live-provider HF test): a real,
    # non-blank price must never show a doubled/misplaced "/M" --
    # format_price_per_m already appends its own, the row template must
    # not append a second one.
    priced_row = format_picker_row({"ref": "or:deepseek/x", "price_in_per_m": 0.8, "price_out_per_m": 2.4})
    ctx.check(f"exactly one '/M' per price column, got {priced_row!r}",
              "/M/" not in priced_row and priced_row.count("/M") == 2)


@test
def test_format_picker_row_is_the_same_layout_for_every_group_shape(ctx: Ctx):
    """"the same layout in every group" -- the row formatter never
    special-cases a provider; feeding it every group's own real-world
    shape (OpenRouter, Databricks w/ dbu+detail, cc:, local, xp:) proves
    none of those extra, provider-specific keys change the three-column
    contract."""
    from halo_harness.model_display import format_picker_row
    shapes = [
        {"ref": "or:deepseek/deepseek-chat", "price_in_per_m": 0.8, "price_out_per_m": 2.4, "context_tokens": 128000,
         "provider": "openrouter"},
        {"ref": "dbx:databricks-glm-5-3", "context_tokens": 128000, "dbu": "$0.015/1k", "detail": "glm · mlflow",
         "provider": "databricks"},
        {"ref": "cc:opus", "price_in_per_m": 4.0, "price_out_per_m": 20.0, "context_tokens": 1_000_000,
         "detail": "-> claude-opus-5-5", "provider": "cc"},
        {"ref": "ol:qwen3:30b", "provider": "ollama", "group": "Ollama (default)"},
        {"ref": "xp:space-bunny-alpha", "price_in_per_m": 0, "price_out_per_m": 0, "context_tokens": 1_000_000,
         "speed_ttft_s": 0.9, "speed_tokens_per_second": 55, "provider": "experiential"},
    ]
    for entry in shapes:
        row = format_picker_row(entry)
        ctx.check(f"{entry['ref']}: starts with the ref, got {row!r}", row.startswith(entry["ref"]))
        ctx.check(f"{entry['ref']}: has all three column labels, got {row!r}",
                  "in=" in row and "out=" in row and "ctx=" in row and "speed=" in row)
    # The one entry with real speed data shows it, not "?".
    xp_row = format_picker_row(shapes[-1])
    ctx.check(f"xp: row shows the real speed reading, got {xp_row!r}", "0.9s · 55 t/s" in xp_row)


@test
def test_picker_footer_documents_sort_and_filter_keys(ctx: Ctx):
    """Deliverable 1: "sort and filter keys documented in the picker
    footer."""
    from halo_harness.model_display import PICKER_FOOTER
    # Chords, not bare letters: a bare letter forwarded from the filter could
    # no longer be typed into it (orchestrator follow-up, 2026-10-05).
    for token in ("Ctrl+O:", "Ctrl+S:", "Ctrl+G:", "F5:", "filter", "Enter", "Esc"):
        ctx.check(f"footer mentions {token!r}, got {PICKER_FOOTER!r}", token in PICKER_FOOTER)


# ---------------------------------------------------------------------------
# Pilot: the real ModelPicker dialog -- sort cycling and refresh keys.
# ---------------------------------------------------------------------------

async def _mounted(controller, **kwargs):
    from halo_harness.tui.app import BridgeApp
    return BridgeApp(controller, cwd=kwargs.pop("cwd", tempfile.mkdtemp(prefix="picker-pilot-")), **kwargs)


@test
def test_s_cycles_sort_and_reorders_rows_within_a_group(ctx: Ctx):
    from halo_harness.testing.fake_controller import FakeController
    from halo_harness.tui.dialogs.model_picker import ModelPicker, _SORT_KEYS

    models = [
        {"ref": "or:expensive/model", "provider": "openrouter", "price_in_per_m": 50.0, "context_tokens": 8000},
        {"ref": "or:cheap/model", "provider": "openrouter", "price_in_per_m": 0.1, "context_tokens": 2000},
    ]

    async def body():
        fake = FakeController()
        app = await _mounted(fake)
        async with app.run_test(size=(100, 40)) as pilot:
            picker = ModelPicker(models, current="")
            app.push_screen(picker)
            await pilot.pause(0.1)
            ctx.check(f"starts on 'name', got {_SORT_KEYS[picker._sort_index]}", picker._sort_index == 0)
            picker.action_cycle_sort()
            ctx.check(f"advances to 'price', got {_SORT_KEYS[picker._sort_index]}",
                      _SORT_KEYS[picker._sort_index] == "price")
            option_list = picker.query_one("#model-list")
            # Cheapest first once sorted by price (ascending).
            first_real_option = next(o for o in option_list._options if not o.disabled)
            ctx.check(f"cheapest model sorts first, got {first_real_option.id!r}",
                      first_real_option.id == "or:cheap/model")
            for _ in range(len(_SORT_KEYS) - 1):
                picker.action_cycle_sort()
            ctx.check("cycling wraps back to 'name'", picker._sort_index == 0)
    asyncio.run(body())


@test
def test_refresh_group_calls_the_registry_for_the_highlighted_rows_provider(ctx: Ctx):
    from halo_harness.testing.fake_controller import FakeController
    from halo_harness.tui.dialogs.model_picker import ModelPicker

    calls = []

    def _fake_refresh_one_catalog(provider, state_dir, *, env=None, force=True):
        calls.append(provider)
        return {"name": "OpenRouter", "provider": "openrouter", "attempted": True, "ok": True, "count": 1}

    import halo_harness.providers.catalog_refresh as catalog_refresh_mod
    real_fn = catalog_refresh_mod.refresh_one_catalog
    catalog_refresh_mod.refresh_one_catalog = _fake_refresh_one_catalog

    models = [{"ref": "or:deepseek/x", "provider": "openrouter"}]

    async def body():
        fake = FakeController()
        fake.state_dir = Path(tempfile.mkdtemp(prefix="picker-refresh-"))
        app = await _mounted(fake)
        async with app.run_test(size=(100, 40)) as pilot:
            picker = ModelPicker(models, current="")
            app.push_screen(picker)
            await pilot.pause(0.1)
            picker.action_refresh_group()
            for _ in range(30):
                await pilot.pause(0.05)
                if calls:
                    break
            ctx.check(f"refresh_one_catalog called with the highlighted row's provider, got {calls}",
                      calls == ["openrouter"])
    try:
        asyncio.run(body())
    finally:
        catalog_refresh_mod.refresh_one_catalog = real_fn


# ---------------------------------------------------------------------------
# Halo 2.0.4 round 5 ("new labs coverage" deliverable 2): "`:free` variants
# sort beside their paid row."
# ---------------------------------------------------------------------------

@test
def test_place_free_variants_beside_base_survives_a_price_resort(ctx: Ctx):
    """A direct, fast unit test of the fixup pass itself (no pilot/asyncio
    needed) -- a `:free` row's own $0 price would otherwise sort it far
    from its paid sibling once a numeric key reorders the group; the
    fixup must put it right back beside that sibling, with every OTHER
    row's relative order left untouched."""
    from halo_harness.tui.dialogs.model_picker import _place_free_variants_beside_base, _sort_value

    members = [
        {"ref": "nvidia/nemotron-3-super-120b-a12b", "price_in_per_m": 0.5},
        {"ref": "nvidia/nemotron-3.5-lightning:free", "price_in_per_m": 0.0},
        {"ref": "nvidia/nemotron-3.5-lightning", "price_in_per_m": 0.06},
        {"ref": "nvidia/nemotron-3-super-120b-a12b:free", "price_in_per_m": 0.0},
    ]
    resorted = sorted(members, key=lambda m: _sort_value(m, "price"))
    resort_refs = [m["ref"] for m in resorted]
    ctx.check(f"fixture drift guard: a bare price sort SCATTERS the two free rows together at the "
              f"front, away from their own paid siblings (else this proves nothing), got {resort_refs}",
              resort_refs[0].endswith(":free") and resort_refs[1].endswith(":free"))

    fixed = _place_free_variants_beside_base(resorted)
    fixed_refs = [m["ref"] for m in fixed]
    ctx.check(f"nemotron-3.5-lightning:free sits immediately after its paid row, got {fixed_refs}",
              fixed_refs.index("nvidia/nemotron-3.5-lightning:free")
              == fixed_refs.index("nvidia/nemotron-3.5-lightning") + 1)
    ctx.check(f"nemotron-3-super-120b-a12b:free sits immediately after ITS paid row, got {fixed_refs}",
              fixed_refs.index("nvidia/nemotron-3-super-120b-a12b:free")
              == fixed_refs.index("nvidia/nemotron-3-super-120b-a12b") + 1)
    ctx.check("no row lost or duplicated", sorted(fixed_refs) == sorted(resort_refs))


@test
def test_place_free_variants_with_no_paid_sibling_left_alone(ctx: Ctx):
    """A `:free`-only model (no paid row in this group at all) is never
    moved -- there is nothing to glue it beside."""
    from halo_harness.tui.dialogs.model_picker import _place_free_variants_beside_base

    members = [{"ref": "a"}, {"ref": "only-free:free"}, {"ref": "b"}]
    fixed = _place_free_variants_beside_base(members)
    ctx.check(f"order unchanged, got {[m['ref'] for m in fixed]}",
              [m["ref"] for m in fixed] == ["a", "only-free:free", "b"])


@test
def test_s_cycles_to_price_keeps_free_variant_beside_its_paid_row(ctx: Ctx):
    """End-to-end through the real ModelPicker dialog: cycling to "price"
    sort must not separate a `:free` row from its paid sibling, even
    though the free row's own $0 price would otherwise sort it to the
    very front of the group."""
    from halo_harness.testing.fake_controller import FakeController
    from halo_harness.tui.dialogs.model_picker import ModelPicker

    models = [
        {"ref": "or:nvidia/nemotron-3.5-lightning", "provider": "openrouter", "price_in_per_m": 0.06},
        {"ref": "or:nvidia/nemotron-3.5-lightning:free", "provider": "openrouter", "price_in_per_m": 0.0},
        {"ref": "or:cheap/model", "provider": "openrouter", "price_in_per_m": 0.01},
    ]

    async def body():
        fake = FakeController()
        app = await _mounted(fake)
        async with app.run_test(size=(100, 40)) as pilot:
            picker = ModelPicker(models, current="")
            app.push_screen(picker)
            await pilot.pause(0.1)
            picker.action_cycle_sort()  # "name" -> "price"
            option_list = picker.query_one("#model-list")
            real_ids = [o.id for o in option_list._options if not o.disabled]
            ctx.check(f"the free row immediately follows its own paid row under price sort, got {real_ids}",
                      real_ids.index("or:nvidia/nemotron-3.5-lightning:free")
                      == real_ids.index("or:nvidia/nemotron-3.5-lightning") + 1)
    asyncio.run(body())


if __name__ == "__main__":
    ctx = Ctx()
    results, passed, failed, skipped = run_all(TESTS, ctx)
    sys.exit(print_results(results, passed, failed, skipped))
