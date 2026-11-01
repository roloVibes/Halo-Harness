"""tests.test_steward_rules_servers -- Halo 3.3.8.0 R2: rules.gather takes the local servers beside the Ollama hosts
(ollama_steward/rules_servers.py): an hf:local call's lines group under the server's name, its window per slot is the
cap, and a server finding names its server and runtime; an Ollama host's group is as before. In-process, a fresh
home (tests/helpers/steward_seed.py), background reads off: no server.
Run: python -m tests.test_steward_rules_servers
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from tests.helpers.provider_env_defaults import ensure_default_provider_credentials  # noqa: E402
ensure_default_provider_credentials()

from tests.helpers.runner import Ctx, new_registry, print_results, run_all  # noqa: E402
from tests.helpers.steward_seed import Home, event, line  # noqa: E402

test, TESTS = new_registry()


def _found(home, **kw) -> list:
    from halo_harness.ollama_steward.rules import findings
    return findings(home.state, **kw)


def _one(found, rule) -> dict:
    hits = [f for f in found if f["rule"] == rule]
    return hits[0] if hits else {}


@test
def test_a_local_servers_calls_group_under_its_name_beside_the_hosts(ctx: Ctx):
    """3.3.8.0 R2: rules.gather takes the local servers beside the Ollama hosts (rules_servers.py)."""
    from halo_harness.ollama_steward.rules import gather
    box = {"name": "box", "url": "http://127.0.0.1:8080/v1"}
    with Home(extra={"huggingface": {"local_servers": [box]}}) as h:
        from halo_harness.ollama_steward import servers_hf
        servers_hf.reset()
        hf = {"name": "127.0.0.1:8080", "url": box["url"]}
        h.calls(line(), *[line(host=hf, model="qwen3-8b", dialect="openai", num_ctx_sent=None, prompt_eval_count=7900)
                          for _ in range(3)])
        h.events({**event("load-result", model="qwen3-8b", window=8192)}, host="box")
        g = {x["key"]: x for x in gather(h.state, cards={}, catalogs={})["groups"]}
        found = _found(h, cards={}, catalogs={})
        servers_hf.reset()
    ctx.check(f"the host's group and the server's, got {sorted(g)}", sorted(g) == ["box|qwen3-8b", "pc|qwen3.8:27b"])
    s = g["box|qwen3-8b"]
    ctx.check("the server's group: its runtime, its window per slot as the cap", s.get("server") == "box"
              and s["cap"] == 8192 and s["stats"]["p95"] == 7900)
    ctx.check("the host's group is as before", not g["pc|qwen3.8:27b"].get("server"))
    w = _one(found, "window-small")
    ctx.check(f"a server finding names its server, got {w.get('key')}", w.get("server") == "box" and w.get("runtime"))


if __name__ == "__main__":
    ctx = Ctx()
    results, passed, failed, skipped = run_all(TESTS, ctx)
    sys.exit(print_results(results, passed, failed, skipped))
