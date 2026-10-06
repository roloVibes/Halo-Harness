"""tests.test_experiential_wire -- Halo 2.0.4 round 2: the smaller, pure-
unit-test pieces of the `xp:` route split out of tests/
test_experiential_provider.py to keep each file under the house ~400-line
convention -- tool search (research doc section 3.5), the `gateway`
request object (section 3.4), the structured-output capability gate
(section 3.1), `experiential.dialect_overrides`, the ignored-parameters
learned rule, and the init wizard tab. No network.
"""
from __future__ import annotations

import os
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from tests.helpers.runner import Ctx, new_registry, print_results, run_all

test, TESTS = new_registry()


@test
def test_tool_search_wire_shape(ctx: Ctx):
    from halo_harness.providers.experiential import apply_tool_search
    anthropic_tools = [{"name": "Read"}, {"name": "Glob", "defer_loading": True}]
    oai_tools = [{"type": "function", "function": {"name": "Read", "parameters": {}}},
                 {"type": "function", "function": {"name": "Glob", "parameters": {}}}]
    out = apply_tool_search(oai_tools, anthropic_tools)
    ctx.check(f"sentinel prepended, got {out[0]!r}", out[0] == {"type": "openrouter:tool_search"})
    glob_entry = next(t for t in out if t.get("function", {}).get("name") == "Glob")
    ctx.check("the deferred tool is marked defer_loading", glob_entry.get("defer_loading") is True)
    read_entry = next(t for t in out if t.get("function", {}).get("name") == "Read")
    ctx.check("the non-deferred tool is untouched", "defer_loading" not in read_entry)

    # Nothing deferred -- the sentinel is dropped entirely (unchanged list).
    none_deferred = apply_tool_search(oai_tools, [{"name": "Read"}, {"name": "Glob"}])
    ctx.check("no sentinel when nothing is deferred", none_deferred == oai_tools)
    ctx.check("empty/None tools pass through unchanged", apply_tool_search(None, anthropic_tools) is None)


@test
def test_tool_search_off_by_default_in_request_body(ctx: Ctx):
    """`experiential.tool_search` defaults False -- `build_request_body`
    must not apply the convention unless the config explicitly turns it
    on, even when a tool def carries `defer_loading`."""
    from halo_harness.providers.profiles import ProviderProfile
    from halo_harness.providers.request import build_request_body
    from halo_harness.providers.routing import Route
    route = Route(provider="experiential", upstream_model="space-bunny-alpha", dialect="openai-chat")
    profile = ProviderProfile(model_id="space-bunny-alpha")
    tools = [{"name": "Read", "input_schema": {"type": "object", "properties": {}}},
             {"name": "Glob", "defer_loading": True, "input_schema": {"type": "object", "properties": {}}}]
    body = build_request_body(system_text="sys", messages=[{"role": "user", "content": "hi"}],
                               tools=tools, route=route, profile=profile)
    tool_types = [t.get("type") for t in body.get("tools") or []]
    ctx.check(f"no tool_search sentinel when the config flag is off, got {tool_types!r}",
              "openrouter:tool_search" not in tool_types)


@test
def test_gateway_object_defaults_and_overrides(ctx: Ctx):
    from halo_harness.providers.experiential import build_gateway_object
    default = build_gateway_object(config={})
    ctx.check(f"default is retry-only, max_attempts_per_route=1, got {default!r}",
              default == {"retry": {"max_attempts_per_route": 1}})

    with_routing = build_gateway_object(config={"routing": {"allow_fallbacks": False, "route_id": "rt_123"}})
    ctx.check(f"routing included when configured, got {with_routing!r}",
              with_routing["routing"] == {"allow_fallbacks": False, "route_id": "rt_123"})
    ctx.check("retry default still present", with_routing["retry"] == {"max_attempts_per_route": 1})

    with_retry_override = build_gateway_object(config={"retry": {"max_attempts_per_route": 3, "max_total_attempts": 6}})
    ctx.check(f"explicit retry override wins, got {with_retry_override!r}",
              with_retry_override["retry"] == {"max_attempts_per_route": 3, "max_total_attempts": 6})
    ctx.check("no routing key when nothing configured", "routing" not in default)


@test
def test_structured_output_gate_on_force_response_format(ctx: Ctx):
    from halo_harness.providers.profiles import ProviderProfile
    from halo_harness.providers.request import build_request_body
    from halo_harness.providers.routing import Route
    route = Route(provider="experiential", upstream_model="m", dialect="openai-chat")
    schema = {"type": "object", "properties": {"answer": {"type": "string"}}}
    messages = [{"role": "user", "content": "hi"}]

    supported = ProviderProfile(model_id="m", supports_structured_output=True)
    body_ok = build_request_body(system_text="sys", messages=messages, route=route, profile=supported,
                                  force_response_format=schema)
    ctx.check("response_format sent when the catalog says yes", "response_format" in body_ok)

    unsupported = ProviderProfile(model_id="m", supports_structured_output=False)
    body_skip = build_request_body(system_text="sys", messages=messages, route=route, profile=unsupported,
                                    force_response_format=schema)
    ctx.check("response_format withheld when the catalog says no", "response_format" not in body_skip)


@test
def test_resolve_experiential_dialect_overrides(ctx: Ctx):
    from halo_harness.providers.experiential import resolve_experiential_dialect
    ctx.check("default is openai-chat", resolve_experiential_dialect("space-bunny-alpha", overrides={}) == "openai-chat")
    ctx.check("an override can select responses",
              resolve_experiential_dialect("some-model", overrides={"some-model": "responses"}) == "openai-responses")
    ctx.check("an unrecognized override value falls back to the table, never raises",
              resolve_experiential_dialect("some-model", overrides={"some-model": "not-a-real-dialect"}) == "openai-chat")


@test
def test_ignored_params_learned_rule_round_trip(ctx: Ctx):
    from halo_harness.providers.learned_rules import learn_ignored_params, learned_ignored_params
    state_dir = Path(tempfile.mkdtemp(prefix="xp-learned-"))
    ctx.check("nothing learned yet", learned_ignored_params(state_dir, "experiential", "space-bunny-alpha") is None)
    learn_ignored_params(state_dir, "experiential", "space-bunny-alpha", "top_p->dropped(...)")
    ctx.check("learned value round-trips",
              learned_ignored_params(state_dir, "experiential", "space-bunny-alpha") == "top_p->dropped(...)")
    ctx.check("a different model's row is untouched",
              learned_ignored_params(state_dir, "experiential", "other-model") is None)


@test
def test_init_wizard_tab_save_round_trip(ctx: Ctx):
    d = Path(tempfile.mkdtemp(prefix="xp-tab-"))
    saved = {k: os.environ.get(k) for k in ("BRIDGE_TEST_HOME", "BRIDGE_STATE_DIR", "BRIDGE_ENV_FILE", "EXPLABS_API_KEY")}
    os.environ["BRIDGE_TEST_HOME"] = str(d)
    os.environ["BRIDGE_STATE_DIR"] = str(d / ".halo")
    os.environ["BRIDGE_ENV_FILE"] = str(d / "env-file")
    os.environ.pop("EXPLABS_API_KEY", None)
    try:
        from halo_harness.init_providers import TAB_LABEL, TAB_PROVIDERS, save_tab_credentials, tab_credential_state
        ctx.check("experiential is a registered tab", "experiential" in TAB_PROVIDERS)
        ctx.check(f"tab label, got {TAB_LABEL['experiential']!r}", TAB_LABEL["experiential"] == "Experiential Labs")

        state_before = tab_credential_state("experiential")
        ctx.check("not configured before Save", state_before["configured"] is False)
        ctx.check(f"one key field offered, got {state_before['fields']!r}",
                  len(state_before["fields"]) == 1 and state_before["fields"][0]["name"] == "key"
                  and state_before["fields"][0]["label"] == "EXPLABS_API_KEY")

        ok, msg = save_tab_credentials("experiential", {"key": "xpl_" + "d" * 40})
        ctx.check(f"Save succeeds, got ok={ok!r} msg={msg!r}", ok is True and "EXPLABS_API_KEY" in msg)

        state_after = tab_credential_state("experiential")
        ctx.check("configured after Save", state_after["configured"] is True)
        ctx.check(f"masked value doesn't leak the real key, got {state_after['masked']!r}",
                  state_after["masked"] is not None and "xpl_" + "d" * 40 not in state_after["masked"])
    finally:
        for k, v in saved.items():
            if v is None:
                os.environ.pop(k, None)
            else:
                os.environ[k] = v


if __name__ == "__main__":
    ctx = Ctx()
    results, passed, failed, skipped = run_all(TESTS, ctx)
    sys.exit(print_results(results, passed, failed, skipped))
