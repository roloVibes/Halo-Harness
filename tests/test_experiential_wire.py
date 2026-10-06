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


@test
def test_round5_zdr_provider_constraint_config_key(ctx: Ctx):
    """Halo 2.0.4 round 5 (xp: contract alignment, llms.txt "Zero data
    retention"): `experiential.zdr` drives the per-request `"provider":
    {"zdr": true}` constraint -- off by default (an existing session's
    request body is byte-identical to before this key existed)."""
    from halo_harness.providers.experiential import zdr_provider_constraint
    ctx.check("default (no config) is off", zdr_provider_constraint(config=False) is None)
    ctx.check(f"on when configured, got {zdr_provider_constraint(config=True)!r}",
              zdr_provider_constraint(config=True) == {"zdr": True})


@test
def test_round5_zdr_constraint_reaches_both_request_builders(ctx: Ctx):
    """Integration: BOTH request builders `xp:` can use (the OpenAI-chat
    dialect for most slugs, the Anthropic-passthrough dialect for Claude
    slugs) add the constraint when `experiential.zdr` is on, and NEITHER
    does when it's off -- and a bare `ant:`/Databricks-Claude-passthrough
    body (never experiential) is untouched either way, since an
    unrecognized "provider" field on THOSE hosts is a real 400 risk."""
    import halo_harness.theme as theme_mod
    from halo_harness.providers.profiles import ProviderProfile
    from halo_harness.providers.request import build_request_body, build_anthropic_request_body
    from halo_harness.providers.routing import Route

    real_get_config_value = theme_mod.get_config_value

    def _fake_get_config_value(key, default=None):
        if key == "experiential.zdr":
            return True
        return real_get_config_value(key, default=default)

    xp_route = Route(provider="experiential", upstream_model="m", dialect="openai-chat")
    ant_route = Route(provider="anthropic", upstream_model="claude-x", dialect="anthropic-passthrough")
    profile = ProviderProfile(model_id="m")
    messages = [{"role": "user", "content": "hi"}]

    body_off = build_request_body(system_text="sys", messages=messages, route=xp_route, profile=profile)
    ctx.check("off by default: no provider key on the chat-dialect body", "provider" not in body_off)
    ant_body_off = build_anthropic_request_body(system_text="sys", messages=messages, route=xp_route, profile=profile)
    ctx.check("off by default: no provider key on the Anthropic-shaped body either",
              "provider" not in ant_body_off)

    theme_mod.get_config_value = _fake_get_config_value
    try:
        body_on = build_request_body(system_text="sys", messages=messages, route=xp_route, profile=profile)
        ctx.check(f"provider.zdr on the chat-dialect body once configured, got {body_on.get('provider')!r}",
                  body_on.get("provider") == {"zdr": True})
        ant_body_on = build_anthropic_request_body(system_text="sys", messages=messages, route=xp_route,
                                                     profile=profile)
        ctx.check(f"provider.zdr on the Anthropic-shaped xp: body too, got {ant_body_on.get('provider')!r}",
                  ant_body_on.get("provider") == {"zdr": True})
        ant_body_bare = build_anthropic_request_body(system_text="sys", messages=messages, route=ant_route,
                                                       profile=profile)
        ctx.check("a bare ant: body NEVER picks up the field, even with the config key on",
                  "provider" not in ant_body_bare)
    finally:
        theme_mod.get_config_value = real_get_config_value


@test
def test_round5_append_usage_carries_experiential_meta_on_the_usage_node(ctx: Ctx):
    """Halo 2.0.4 round 5 (xp: contract alignment): "the per-response
    headers ... captured and shown on the transcript line" -- the
    session's own transcript log is where every other piece of per-call
    metadata (latency, retries, the responding provider, ...) already
    lives (`agent/log.py`'s own H10 Part A fields), so this is the SAME
    mechanism, one more field. A non-experiential call never carries the
    key at all (`None`/`{}` is dropped, not written as an empty dict)."""
    from halo_harness.agent.log import SessionLog

    cwd = Path(tempfile.mkdtemp(prefix="xp-round5-usage-node-"))
    log = SessionLog(cwd, session_id="xp-round5-usage-node")
    log.append_meta(model="xp:space-bunny-alpha", cwd=str(cwd), system_prompt_bytes=1, tools=[])
    log.append_usage(
        {"input_tokens": 10, "output_tokens": 5}, cost_usd=0.0001, model="xp:space-bunny-alpha", route="xp",
        experiential_meta={
            "request_id": "req_abc123", "is_byok": False, "gateway_provider": "experiential_cloud",
            "gateway_zdr": "false", "gateway_route_depth": "1", "gateway_route_reason": "primary",
        },
    )
    log.append_usage({"input_tokens": 1, "output_tokens": 1}, cost_usd=0.0, model="or:some/model", route="or")
    nodes = [n for n in log.nodes() if n.get("type") == "usage"]
    ctx.check(f"two usage nodes written, got {len(nodes)}", len(nodes) == 2)
    xp_node, or_node = nodes
    ctx.check(f"request_id on the xp: node, got {xp_node.get('experiential_meta')!r}",
              xp_node["experiential_meta"]["request_id"] == "req_abc123")
    ctx.check(f"gateway_route_reason on the xp: node, got {xp_node.get('experiential_meta')!r}",
              xp_node["experiential_meta"]["gateway_route_reason"] == "primary")
    ctx.check("the or: node never carries the key at all (never an empty dict either)",
              "experiential_meta" not in or_node)


if __name__ == "__main__":
    ctx = Ctx()
    results, passed, failed, skipped = run_all(TESTS, ctx)
    sys.exit(print_results(results, passed, failed, skipped))
