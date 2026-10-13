"""tests.test_review3_m -- pins for the 3.0.2.0 review fix pass, round M-data-misc,
secret redaction (review items 88, 157, 158):

  * 88   `--sanitize` kept dropping whole nodes when an object/array sat under a
         TOKEN/SECRET/PASSWORD/API_KEY-named key
  * 157  the bug-report known-secret harvest ignored lowercase/camelCase names
  * 158  Cookie / Set-Cookie / Proxy-Authorization header values were never redacted
"""
from __future__ import annotations

import json
import sys
from pathlib import Path
from types import SimpleNamespace

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from tests.helpers.runner import Ctx, new_registry, print_results, run_all

test, TESTS = new_registry()

_GH = "ghp" + "_lowercasekey1234567890"  # built at runtime: not a literal key-shaped fragment


# ---- 88 ------------------------------------------------------------------------

@test
def test_sanitize_keeps_a_meta_node_whose_tool_schema_has_a_password_property(ctx: Ctx):
    from halo_harness.redact import sanitize_node
    node = {"type": "meta", "model": "or:x", "tools": [
        {"name": "mcp__db__connect", "input_schema": {"properties": {
            "password": {"type": "string"}, "api_key": {"type": "string", "description": "key"}}}}]}
    out = sanitize_node(node)
    ctx.check(f"the node survives untouched, got {out}", out == node)


@test
def test_sanitize_keeps_a_list_or_dict_under_a_secret_named_key(ctx: Ctx):
    from halo_harness.redact import sanitize_node
    node = {"type": "assistant", "content": [{"type": "tool_use", "name": "T", "input": {
        "tokens": [1, 2, 3], "secrets": {"a": 1}, "password": ["x"]}}]}
    out = sanitize_node(node)
    ctx.check(f"no _sanitize_error, got {out}", "_sanitize_error" not in out)
    ctx.check("the structure is intact", out["content"][0]["input"]["tokens"] == [1, 2, 3]
              and out["content"][0]["input"]["secrets"] == {"a": 1})


@test
def test_sanitize_still_redacts_scalar_secrets_next_to_a_structured_value(ctx: Ctx):
    from halo_harness.redact import sanitize_node, sanitize_text
    out = sanitize_node({"type": "meta", "tools": {"password": {"type": "string"}},
                         "env": {"OPENAI_API_KEY": "sk" + "-abcdefghijklmnopqrstuvwxyz"}})
    ctx.check(f"the schema stays, got {out}", out.get("tools") == {"password": {"type": "string"}})
    ctx.check("the key value is redacted", "abcdefghijklmnop" not in json.dumps(out))
    ctx.check("a shell assignment of the same name is still redacted",
              "hunter2" not in sanitize_text("export PASSWORD=hunter2"))


# ---- 157 -----------------------------------------------------------------------

@test
def test_known_secret_harvest_matches_names_in_any_case(ctx: Ctx):
    from halo_harness.bugreport import _collect_known_secret_values
    cfg = SimpleNamespace(env={"github_token": _GH, "apiKey": "camelValue-123",
                               "api_key": "snake-value-456", "PATH": "/usr/bin:/bin"}, headers=None)
    vals = _collect_known_secret_values(settings=None, mcp_servers={"srv": cfg})
    for expected in (_GH, "camelValue-123", "snake-value-456"):
        ctx.check(f"{expected!r} was harvested", expected in vals)
    ctx.check("a non-secret name is still left out", "/usr/bin:/bin" not in vals)


# ---- 158 -----------------------------------------------------------------------

@test
def test_cookie_style_headers_are_redacted(ctx: Ctx):
    from halo_harness.redact import sanitize_node, sanitize_text
    for line, leak in (
            ("Cookie: session=abcdef0123456789abcdef0123456789; theme=dark", "abcdef0123456789"),
            ("Set-Cookie: sid=zzTOPsecret99; Path=/; HttpOnly", "zzTOPsecret99"),
            ("Proxy-Authorization: Basic dXNlcjpwYXNzd29yZA==", "dXNlcjpwYXNzd29yZA"),
            ("> cookie: a=b1b1b1b1; c=d2d2d2d2\n> Accept: */*", "b1b1b1b1"),
            ('{"Cookie": "a=jsonsecret77; b=2"}', "jsonsecret77")):
        out = sanitize_text(line)
        ctx.check(f"{line[:20]!r} is redacted, got {out!r}", leak not in out and "<redacted>" in out)
    ctx.check("an unrelated header line is untouched", sanitize_text("Accept: */*") == "Accept: */*")
    node = sanitize_node({"type": "tool_result", "content": "Cookie: a=bbbbbb; c=d\nnext line"})
    ctx.check(f"a node round-trips with the header redacted once, got {node}",
              node["content"] == "Cookie: <redacted>\nnext line")


if __name__ == "__main__":
    ctx = Ctx()
    results, passed, failed, skipped = run_all(TESTS, ctx)
    sys.exit(print_results(results, passed, failed, skipped))
