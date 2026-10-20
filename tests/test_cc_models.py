"""tests.test_cc_models -- the `ant:` Claude aliases (3.1.5.0 R1: the API-key
half of the old cc:/ant: alias module, now `providers/anthropic_aliases.py`):
alias resolution with routes.json hops and [1m] pass-through, bare-word
routing to `ant:` (or an error naming it), the alias display detail, and the
vendored profile fields. The claude.ai login checks the connectors bridge
uses are tests/test_mcp_claude_auth.py.
"""
import os
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from tests.helpers.runner import Ctx, new_registry, print_results, run_all

# This module's own scratch home, set once at import (never the real ~/.halo).
os.environ["BRIDGE_TEST_HOME"] = tempfile.mkdtemp(prefix="ant-aliases-scratchhome-")

test, TESTS = new_registry()


def _clear_env():
    for k in ("BRIDGE_TEST_CC_AUTH_STATUS", "ANTHROPIC_API_KEY", "BRIDGE_CLAUDE_EXE",
              "ANTHROPIC_BASE_URL", "ANTHROPIC_AUTH_TOKEN"):
        os.environ.pop(k, None)


# ---- ant: alias table -------------------------------------------------------

@test
def test_ant_prefix_resolves_the_alias_names(ctx: Ctx):
    from halo_harness.model import parse_model_ref
    _clear_env()
    try:
        os.environ["ANTHROPIC_API_KEY"] = "sk-ant-test"
        expected = {
            "ant:fable": "claude-fable-5-1", "ant:opus": "claude-opus-5-5",
            "ant:opus-5": "claude-opus-5", "ant:opus-4.8": "claude-opus-4-8",
            "ant:opus-4.6": "claude-opus-4-6", "ant:sonnet-5": "claude-sonnet-5",
        }
        for raw, model in expected.items():
            ref = parse_model_ref(raw)
            ctx.check(f"{raw} -> provider anthropic", ref.provider == "anthropic")
            ctx.check(f"{raw} -> model {model!r}, got {ref.model!r}", ref.model == model)
            ctx.check(f"{raw} -> dialect anthropic-passthrough", ref.dialect == "anthropic-passthrough")
    finally:
        _clear_env()


@test
def test_ant_prefix_sonnet_and_haiku_resolve_to_concrete_ids_not_bare_aliases(ctx: Ctx):
    """ant: hits the real API directly and needs a concrete id."""
    from halo_harness.model import parse_model_ref
    _clear_env()
    try:
        os.environ["ANTHROPIC_API_KEY"] = "sk-ant-test"
        ref_sonnet = parse_model_ref("ant:sonnet")
        ref_haiku = parse_model_ref("ant:haiku")
        ctx.check(f"ant:sonnet is a real id, got {ref_sonnet.model!r}", ref_sonnet.model == "claude-sonnet-5-5")
        ctx.check(f"ant:haiku is a real id, got {ref_haiku.model!r}", ref_haiku.model == "claude-haiku-4-5-20251001")
    finally:
        _clear_env()


@test
def test_ant_prefix_existing_behavior_unaffected_for_unknown_names(ctx: Ctx):
    """Regression guard: test_model.py's own test_parse_ant_prefix case."""
    from halo_harness.model import parse_model_ref
    _clear_env()
    try:
        os.environ["ANTHROPIC_API_KEY"] = "sk-ant-test"
        ref = parse_model_ref("ant:claude-opus-4")
        ctx.check("provider anthropic", ref.provider == "anthropic")
        ctx.check("model bare (ant: stripped, no alias applied)", ref.model == "claude-opus-4")
        ref1m = parse_model_ref("ant:sonnet-5[1m]")
        ctx.check(f"[1m] reattached after the alias lookup, got {ref1m.model!r}",
                  ref1m.model == "claude-sonnet-5[1m]")
    finally:
        _clear_env()


@test
def test_routes_json_alias_hop_into_ant_prefix(ctx: Ctx):
    from halo_harness.model import parse_model_ref
    _clear_env()
    try:
        os.environ["ANTHROPIC_API_KEY"] = "sk-ant-test"
        ref = parse_model_ref("my-opus", {"aliases": {"my-opus": "ant:opus"}})
        ctx.check("provider anthropic via routes.json alias hop", ref.provider == "anthropic")
        ctx.check(f"model resolved, got {ref.model!r}", ref.model == "claude-opus-5-5")
    finally:
        _clear_env()


# ---- bare alias routing (ant: vs error) ---------------------------------------

@test
def test_bare_alias_routes_to_ant_when_key_set(ctx: Ctx):
    from halo_harness.model import parse_model_ref
    _clear_env()
    try:
        os.environ["ANTHROPIC_API_KEY"] = "sk-ant-test"
        ref = parse_model_ref("opus")
        ctx.check(f"bare opus -> anthropic when key set, got provider={ref.provider!r}", ref.provider == "anthropic")
        ctx.check("bare opus -> claude-opus-5-5", ref.model == "claude-opus-5-5")
    finally:
        _clear_env()


@test
def test_bare_alias_ignores_a_claude_login(ctx: Ctx):
    """A claude.ai login no longer routes anything: with no key a bare
    alias is the error naming ant:, logged in or not."""
    import json
    from halo_harness.model import parse_model_ref
    from halo_harness.providers.routing import InvalidModelError
    _clear_env()
    try:
        os.environ["BRIDGE_TEST_CC_AUTH_STATUS"] = json.dumps({"loggedIn": True, "authMethod": "claude.ai"})
        try:
            parse_model_ref("sonnet-5")
            ctx.check("must raise without ANTHROPIC_API_KEY", False)
        except InvalidModelError as e:
            ctx.check(f"the error names ant:sonnet-5, got {e}", "ant:sonnet-5" in str(e))
    finally:
        _clear_env()


@test
def test_bare_alias_error_names_the_ant_form_when_no_key(ctx: Ctx):
    from halo_harness.model import parse_model_ref
    from halo_harness.providers.routing import InvalidModelError
    _clear_env()
    try:
        parse_model_ref("opus")
        ctx.check("must raise when no ANTHROPIC_API_KEY is set", False)
    except InvalidModelError as e:
        msg = str(e)
        ctx.check(f"error names ant:, got {msg!r}", "ant:opus" in msg and "ANTHROPIC_API_KEY" in msg)
        ctx.check(f"error never names cc:, got {msg!r}", "cc:" not in msg)
    finally:
        _clear_env()


@test
def test_bare_non_alias_word_still_raises_invalid_model_error(ctx: Ctx):
    """Regression guard: test_model.py's own test_parse_invalid_raises case."""
    from halo_harness.model import parse_model_ref
    from halo_harness.providers.routing import InvalidModelError
    _clear_env()
    try:
        parse_model_ref("totally-unrecognized-form")
        ctx.check("must raise", False)
    except InvalidModelError as e:
        ctx.check(f"the accepted forms no longer list cc:/cx:, got {e}", "cc:" not in str(e) and "cx:" not in str(e))


@test
def test_default_bare_alias_route_reads_only_the_key(ctx: Ctx):
    from halo_harness.providers.anthropic_aliases import default_bare_alias_route
    ctx.check("a key -> ant", default_bare_alias_route(api_key="sk-ant-test") == "ant")
    ctx.check("no key -> none", default_bare_alias_route(api_key="") == "none")


# ---- profile fields -------------------------------------------------------------

@test
def test_profile_fields_known_for_every_alias_target_and_alias_word(ctx: Ctx):
    from halo_harness.providers.anthropic_aliases import ANT_ALIASES, profile_fields_for_ant_model
    for model_id in list(ANT_ALIASES.values()) + ["sonnet", "haiku", "claude-sonnet-5[1m]"]:
        fields = profile_fields_for_ant_model(model_id)
        ctx.check(f"{model_id} has fields", fields is not None)
        ctx.check(f"{model_id} has context_tokens", isinstance((fields or {}).get("context_tokens"), int))
        ctx.check(f"{model_id} has max_output_tokens", isinstance((fields or {}).get("max_output_tokens"), int))


@test
def test_profile_fields_unknown_model_returns_none(ctx: Ctx):
    from halo_harness.providers.anthropic_aliases import profile_fields_for_ant_model
    ctx.check("unknown id -> None", profile_fields_for_ant_model("claude-totally-made-up") is None)


@test
def test_resolve_model_profile_ant_uses_the_table(ctx: Ctx):
    from halo_harness.model import parse_model_ref, resolve_model_profile
    _clear_env()
    try:
        os.environ["ANTHROPIC_API_KEY"] = "sk-ant-test"
        ref = parse_model_ref("ant:opus")
        profile = resolve_model_profile(ref, Path(tempfile.mkdtemp(prefix="ant-profile-")), {})
        ctx.check(f"context_tokens 1M, got {profile.context_tokens}", profile.context_tokens == 1_000_000)
        ctx.check("reasoning native", profile.reasoning == "native")
        ctx.check("vision on", profile.vision is True)
        ctx.check("has real pricing, not None", profile.price_in is not None and profile.price_out is not None)
    finally:
        _clear_env()


# ---- H15 addendum 2: explicit opus-5.5/sonnet-5.5 aliases and the detail -------

@test
def test_opus_5_5_and_sonnet_5_5_aliases_resolve_the_same_as_the_bare_latest_pointer(ctx: Ctx):
    from halo_harness.providers.anthropic_aliases import ANT_ALIASES
    ctx.check(f"ANT_ALIASES['opus-5.5'], got {ANT_ALIASES.get('opus-5.5')!r}",
              ANT_ALIASES.get("opus-5.5") == "claude-opus-5-5" == ANT_ALIASES.get("opus"))
    ctx.check(f"ANT_ALIASES['sonnet-5.5'], got {ANT_ALIASES.get('sonnet-5.5')!r}",
              ANT_ALIASES.get("sonnet-5.5") == "claude-sonnet-5-5" == ANT_ALIASES.get("sonnet"))


@test
def test_ant_prefix_resolves_the_dotted_five_five_aliases(ctx: Ctx):
    from halo_harness.model import parse_model_ref
    _clear_env()
    try:
        os.environ["ANTHROPIC_API_KEY"] = "sk-ant-test"
        ref3 = parse_model_ref("ant:opus-5.5")
        ctx.check(f"ant:opus-5.5 -> claude-opus-5-5, got {ref3.model!r}", ref3.model == "claude-opus-5-5")
        ref4 = parse_model_ref("ant:sonnet-5.5")
        ctx.check(f"ant:sonnet-5.5 -> claude-sonnet-5-5, got {ref4.model!r}", ref4.model == "claude-sonnet-5-5")
    finally:
        _clear_env()


@test
def test_alias_display_detail_shows_resolved_id_with_a_latest_note_for_opus_and_sonnet(ctx: Ctx):
    from halo_harness.providers.anthropic_aliases import alias_display_detail
    ctx.check(f"opus -> resolved id + latest note, got {alias_display_detail('opus')!r}",
              alias_display_detail("opus") == "-> claude-opus-5-5 (latest Opus)")
    ctx.check(f"sonnet -> resolved id + latest note, got {alias_display_detail('sonnet')!r}",
              alias_display_detail("sonnet") == "-> claude-sonnet-5-5 (latest Sonnet)")


@test
def test_alias_display_detail_has_no_note_for_an_already_versioned_name(ctx: Ctx):
    from halo_harness.providers.anthropic_aliases import alias_display_detail
    ctx.check(f"opus-5.5 -> no parenthetical, got {alias_display_detail('opus-5.5')!r}",
              alias_display_detail("opus-5.5") == "-> claude-opus-5-5")
    ctx.check(f"haiku -> no parenthetical, got {alias_display_detail('haiku')!r}",
              alias_display_detail("haiku") == "-> claude-haiku-4-5-20251001")
    ctx.check(f"opus-4.6 -> no parenthetical, got {alias_display_detail('opus-4.6')!r}",
              alias_display_detail("opus-4.6") == "-> claude-opus-4-6")


@test
def test_ant_entries_carry_the_display_detail_field(ctx: Ctx):
    """The shared helper `/model`'s ant: group AND the init picker both go
    through (`init_providers._ant_entries`) wires `detail` onto every row."""
    from halo_harness.init_providers import _ant_entries
    entries = {e["ref"]: e for e in _ant_entries()}
    ctx.check(f"ant:opus carries a detail, got {entries['ant:opus']}",
              entries["ant:opus"]["detail"] == "-> claude-opus-5-5 (latest Opus)")
    ctx.check(f"ant:opus-5.5 carries a detail, got {entries['ant:opus-5.5']}",
              entries["ant:opus-5.5"]["detail"] == "-> claude-opus-5-5")
    ctx.check("no cc: row", not [r for r in entries if not r.startswith("ant:")])


if __name__ == "__main__":
    ctx = Ctx()
    results, passed, failed, skipped = run_all(TESTS, ctx)
    sys.exit(print_results(results, passed, failed, skipped))
