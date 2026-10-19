"""tests.test_init_wizard_round7 -- Halo 2.0.2 round 7 (init wizard brief):
pure-logic pieces that don't need a Textual pilot -- `roles.py`'s own mode
switch (`roles_mode_enabled`), the three shipped role presets
(`compute_builtin_role_presets`/`ensure_builtin_role_presets`) and the
wizard's step keys (3.1.4.0: the Organizations step is gone). The Textual
pilot tests (the wizard walking its steps, the roles editor's template
picker, `/setup`) live in test_tui.py, per house convention; the
integration pieces live in tests/test_init_wizard_round7_integration.py.
"""
from __future__ import annotations

import os
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from tests.helpers.runner import Ctx, new_registry, print_results, run_all

test, TESTS = new_registry()


def _fresh_state_dir(prefix: str) -> Path:
    d = Path(tempfile.mkdtemp(prefix=prefix))
    os.environ["BRIDGE_STATE_DIR"] = str(d)
    return d


def _clear_state_dir_env() -> None:
    os.environ.pop("BRIDGE_STATE_DIR", None)


# ---- roles_mode_enabled / resolve_role_table gating ------------------------

@test
def test_roles_mode_enabled_defaults_true_and_disables_the_table(ctx: Ctx):
    from halo_harness.roles import resolve_role_table, roles_mode_enabled
    from halo_harness.theme import set_config_value
    _fresh_state_dir("roles-mode-")
    try:
        ctx.check("defaults on", roles_mode_enabled() is True)
        set_config_value("roles.coder", "or:vendor/pinned")
        ctx.check("configured table resolves while enabled",
                  resolve_role_table().get("coder") == "or:vendor/pinned")
        set_config_value("roles.enabled", False)
        ctx.check("now reports disabled", roles_mode_enabled() is False)
        ctx.check(f"resolve_role_table is {{}} regardless of the configured table, "
                   f"got {resolve_role_table()}", resolve_role_table() == {})
        ctx.check("even the cost-aware databricks default is suppressed",
                  resolve_role_table(provider="databricks") == {})
    finally:
        _clear_state_dir_env()


# ---- the three shipped role presets ----------------------------------------

@test
def test_compute_builtin_role_presets_shapes(ctx: Ctx):
    from halo_harness.roles import BUILTIN_ROLE_PRESET_NAMES, compute_builtin_role_presets
    state_dir = Path(tempfile.mkdtemp(prefix="roles-presets-"))
    presets = compute_builtin_role_presets(default_model="or:vendor/strong", state_dir=state_dir)
    ctx.check(f"all three names present, got {sorted(presets)}",
              set(presets) == set(BUILTIN_ROLE_PRESET_NAMES))
    ctx.check(f"quality pins judge/reviewer to the given default model, got {presets['quality']['roles']}",
              presets["quality"]["roles"].get("judge") == "or:vendor/strong"
              and presets["quality"]["roles"].get("reviewer") == "or:vendor/strong")
    # No configured provider at all in this bare state_dir -- "balanced"/
    # "local-first" fall back to the given default model too (never crash
    # on an empty catalog).
    ctx.check(f"balanced falls back to the default model with no catalog, got {presets['balanced']['roles']}",
              presets["balanced"]["roles"].get("researcher") == "or:vendor/strong")
    ctx.check("every preset carries a human description",
              all(presets[n]["description"] for n in BUILTIN_ROLE_PRESET_NAMES))


@test
def test_cheapest_model_entry_skips_free_negative_and_toolless(ctx: Ctx):
    """2.0.2 review finding 28 pin: no price/tool-support floor at all
    used to mean a $0 `:free` model or a negative-priced router entry
    (OpenRouter's own `openrouter/auto` reports "-1") could win outright
    and become `researcher`/`small` -- which then fails every call."""
    import halo_harness.roles as roles_mod
    entries = [
        {"ref": "or:openrouter/auto", "price_in_per_m": -1, "supported_parameters": ["tools"]},
        {"ref": "or:vendor/free", "price_in_per_m": 0, "supported_parameters": ["tools"]},
        {"ref": "or:vendor/toolless", "price_in_per_m": 0.1, "supported_parameters": ["reasoning"]},
        {"ref": "or:vendor/real", "price_in_per_m": 0.5, "supported_parameters": ["tools"]},
        {"ref": "or:vendor/unknown-support", "price_in_per_m": 2.0},  # no field at all -- fail-open
    ]
    old = roles_mod._configured_model_entries
    roles_mod._configured_model_entries = lambda state_dir=None: entries
    try:
        ctx.check("picks the real, positively-priced, tool-capable entry (cheapest of the two valid ones)",
                  roles_mod._cheapest_model_entry() == "or:vendor/real")
    finally:
        roles_mod._configured_model_entries = old


@test
def test_ensure_builtin_role_presets_never_overwrites(ctx: Ctx):
    from halo_harness.roles import ensure_builtin_role_presets, load_role_template, save_role_template
    state_dir = Path(tempfile.mkdtemp(prefix="roles-presets-noclobber-"))
    ensure_builtin_role_presets(default_model="or:vendor/x", state_dir=state_dir)
    first = load_role_template("balanced", state_dir=state_dir)
    ctx.check("balanced was written on first use", first is not None)
    save_role_template("balanced", {"description": "edited by the user", "roles": {}}, state_dir=state_dir)
    ensure_builtin_role_presets(default_model="or:vendor/y", state_dir=state_dir)  # a second "first use"
    reread = load_role_template("balanced", state_dir=state_dir)
    ctx.check("the user's edit survived a second ensure call", reread["description"] == "edited by the user")


# ---- default_org_name / set_default_org ------------------------------------

# ---- init_wizard.py: pure (Textual-free) pieces ----------------------------

@test
def test_resolve_start_index_accepts_ordinal_or_key(ctx: Ctx):
    from halo_harness.tui.dialogs.init_wizard import ALL_STEP_KEYS, _resolve_start_index
    # Halo 2.0.3 round 5c inserted "local_models" right after "providers",
    # shifting "roles" from the 5th to the 6th 1-based ordinal; Halo 2.0.5
    # round 2 then inserted "agents" right before "roles", shifting it to
    # the 7th; round 2c merged "agents"+"roles" into one "team" step,
    # shifting it back to the 6th -- the KEY form (tested right below,
    # plus the alias form just after it) is what actually stays correct
    # across a step-list change like any of these; this ordinal is
    # updated to match.
    ctx.check('start_step=6 (1-based ordinal) resolves to "team"',
              ALL_STEP_KEYS[_resolve_start_index(6, ALL_STEP_KEYS)] == "team")
    ctx.check('start_step="summary" (the key itself) resolves to "summary"',
              ALL_STEP_KEYS[_resolve_start_index("summary", ALL_STEP_KEYS)] == "summary")
    ctx.check('start_step="orgs" (a removed step, 3.1.4.0) falls back to step 1',
              "orgs" not in ALL_STEP_KEYS and _resolve_start_index("orgs", ALL_STEP_KEYS) == 0)
    # Round 2c: "agents"/"roles" (no longer real keys) still resolve, as
    # `--step` aliases, to wherever "team" now sits.
    ctx.check('start_step="agents" (alias) resolves to "team"',
              ALL_STEP_KEYS[_resolve_start_index("agents", ALL_STEP_KEYS)] == "team")
    ctx.check('start_step="roles" (alias) resolves to "team"',
              ALL_STEP_KEYS[_resolve_start_index("roles", ALL_STEP_KEYS)] == "team")
    ctx.check("an out-of-range ordinal falls back to step 1", _resolve_start_index(99, ALL_STEP_KEYS) == 0)
    ctx.check("an unknown key falls back to step 1", _resolve_start_index("not-a-step", ALL_STEP_KEYS) == 0)
    ctx.check("None falls back to step 1", _resolve_start_index(None, ALL_STEP_KEYS) == 0)


@test
def test_linux_fixes_step_key_never_shifts_team(ctx: Ctx):
    """Whether or not `linux_fixes` survives into `full_step_keys()`,
    "team" must stay at the SAME 1-based ordinal (6, after Halo 2.0.3
    round 5c's "local_models" insertion right after "providers" and Halo
    2.0.5 round 2c's "agents"+"roles" merge into one "team" step) --
    `linux_fixes` sits AFTER it; 3.1.4.0: no "orgs" step any more."""
    from halo_harness.tui.dialogs.init_wizard import ALL_STEP_KEYS
    ctx.check(f"team is step 6, got {ALL_STEP_KEYS}", ALL_STEP_KEYS[5] == "team")
    ctx.check(f"no orgs step, summary last, got {ALL_STEP_KEYS}", "orgs" not in ALL_STEP_KEYS and ALL_STEP_KEYS[-1] == "summary")
    without_linux_fixes = tuple(k for k in ALL_STEP_KEYS if k != "linux_fixes")
    ctx.check("still true with linux_fixes dropped", without_linux_fixes[5] == "team"
              and without_linux_fixes[6] == "summary")


if __name__ == "__main__":
    ctx = Ctx()
    results, passed, failed, skipped = run_all(TESTS, ctx)
    sys.exit(print_results(results, passed, failed, skipped))
