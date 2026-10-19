"""tests.test_shipped_bios_default_model -- Halo 3.1.4.0: no shipped bio
sends a role to a provider you did not set up.

The owner's live check (2026-10-19, a Databricks / GLM session on his
Kali box) found the built-in `orchestrator` bio pinning
`or:anthropic/claude-fable-5.1`: a lineup that put the orchestrator in the
boss slot silently routed the boss through OpenRouter to Anthropic. Every
shipped bio that names a model now says `default`, the one literal
`agents_yaml.resolve_agent_bio` substitutes with the session's own model
at resolve time, and carries no provider-pinned fallback. Pinned here:

- every shipped bio's `models.preference` is `default` or absent, and no
  `models.fallback` names a cloud provider;
- the orchestrator resolves to whatever `model` the config holds.

Run: python -m tests.test_shipped_bios_default_model
"""

from __future__ import annotations

import sys
from pathlib import Path

REPO_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_DIR))

from tests.helpers.provider_env_defaults import ensure_default_provider_credentials, ensure_scoped_state_dir_once

ensure_default_provider_credentials()
ensure_scoped_state_dir_once()

from tests.helpers.runner import Ctx, new_registry, print_results, run_all  # noqa: E402

test, TESTS = new_registry()

CLOUD = ("or:", "dbx:", "xp:", "cc:", "hf:", "anthropic/", "openrouter")


def _names_a_cloud(ref) -> bool:
    return isinstance(ref, str) and ref.strip().lower().startswith(CLOUD)


@test
def test_every_shipped_bio_prefers_the_sessions_default_model(ctx: Ctx):
    from halo_harness.agents_yaml import list_bundled_agent_templates, load_agent_bio_raw
    names = list_bundled_agent_templates()
    ctx.check(f"the shipped bios are there, got {names}", "orchestrator" in names and "media" in names)
    pinned, bad_fallback = [], []
    for name in names:
        raw = load_agent_bio_raw(name) or {}
        models = raw.get("models") or {}
        pref = models.get("preference")
        if pref is not None and pref != "default":
            pinned.append(f"{name}={pref}")
        if _names_a_cloud(models.get("fallback")):
            bad_fallback.append(f"{name}={models.get('fallback')}")
    ctx.check(f"no shipped bio pins a model (preference is `default` or absent), got {pinned}", not pinned)
    ctx.check(f"no shipped bio's fallback names a cloud provider, got {bad_fallback}", not bad_fallback)


@test
def test_the_orchestrator_resolves_to_the_configured_model(ctx: Ctx):
    from halo_harness.agents_yaml import resolve_agent_bio
    from halo_harness.theme import set_config_value
    set_config_value("model", "dbx:databricks-glm-5-3")
    resolved = resolve_agent_bio("orchestrator") or {}
    models = resolved.get("models") or {}
    ctx.check(f"the orchestrator runs on the session's model, got {models.get('preference')!r}",
              models.get("preference") == "dbx:databricks-glm-5-3")
    ctx.check(f"and falls back to no cloud provider of its own, got {models.get('fallback')!r}",
              not _names_a_cloud(models.get("fallback")))
    set_config_value("model", "ol:qwen3:8b")
    again = (resolve_agent_bio("reviewer") or {}).get("models") or {}
    ctx.check(f"changing the session model moves every shipped role at once, got {again.get('preference')!r}",
              again.get("preference") == "ol:qwen3:8b")


if __name__ == "__main__":
    ctx = Ctx()
    results, passed, failed, skipped = run_all(TESTS, ctx)
    print_results(results, passed, failed, skipped)
    sys.exit(1 if failed else 0)
