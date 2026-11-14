"""tests.helpers.studio_room_seed -- the long-names seed of the room driver (Halo 3.6.0.0 R0a; the audit's room walk
made it): 24 agents with long names and long descriptions, a 20-card lineup `big-crew` in three tiers, a 40-row model
catalog with long refs, and the Local seed (tests/helpers/local_seed.py: the fake Ollama `box`, the hosts and the
ledger). Neutral names only; nothing is sent anywhere but the fake."""
from __future__ import annotations

import json

LONG = ("storefront-checkout-regression-reviewer", "payments-and-refunds-integration-tester", "release-notes-and-changelog-writer",
        "database-migration-safety-checker", "accessibility-and-keyboard-auditor", "api-contract-and-openapi-verifier",
        "translation-strings-and-locale-checker", "performance-budget-and-bundle-watcher", "security-headers-and-csp-reviewer",
        "docs-site-screenshots-refresher", "dependency-upgrade-and-lockfile-bot", "flaky-test-quarantine-keeper",
        "customer-support-macro-drafter", "analytics-events-schema-guard", "image-and-pdf-receipt-reader", "voice-memo-transcriber",
        "search-index-rebuilder", "feature-flag-cleanup-sweeper", "error-budget-and-alert-tuner", "inventory-sync-reconciler",
        "shipping-label-and-tracking-helper", "coupon-and-discount-rules-auditor", "warehouse-webhook-replayer", "tax-rate-table-updater")
VENDORS = ("anthropic", "openai", "google", "mistralai", "deepseek", "qwen", "moonshotai", "z-ai", "meta-llama", "nvidia")


def seed_long_names(rig) -> str:
    """Write the seed into the rig's home; returns a word for the driver's output ("local seed ok" or why not)."""
    import yaml
    st = rig.state
    (st / "agents").mkdir(parents=True, exist_ok=True)
    (st / "teams").mkdir(parents=True, exist_ok=True)
    pref = "or:mistralai/mistral-medium-3.5-instruct-2611-preview"
    for n in LONG:
        desc = f"{n.replace('-', ' ').capitalize()}: reads the task, does the part named here and hands back one short report with links."
        (st / "agents" / f"{n}.yaml").write_text(yaml.safe_dump({"name": n, "description": desc, "kind": "subagent", "models": {"preference": pref}}),
                                                  encoding="utf-8")
    agents = [{"agent": "orchestrator", "role": "main", "as": "boss"}] + [{"agent": n, "role": "subagent", "as": n, "use_for": n.split("-")[:2]} for n in LONG[:20]]
    crew = {"name": "big-crew", "description": "Twenty cards with long names", "agents": agents,
            "tiers": [{"name": "top", "members": ["boss"]}, {"name": "build", "purpose": "the builders", "members": list(LONG[:10])},
                      {"name": "check", "purpose": "the checkers", "members": list(LONG[10:20])}], "workflows": ["media", "review"]}
    (st / "teams" / "big-crew.yaml").write_text(yaml.safe_dump(crew, sort_keys=False), encoding="utf-8")
    models = {}
    for i in range(40):
        v = VENDORS[i % len(VENDORS)]
        models[f"{v}/{v}-flagship-reasoning-{i:02d}-instruct-long-context-preview-2611"] = {
            "price_in_per_m": 0.5 + i / 10, "context_length": 131072 * (1 + i % 4),
            "pricing": {"prompt": f"{(0.5 + i / 10) / 1e6:.9f}", "completion": f"{(2 + i / 5) / 1e6:.9f}"}}
    (st / "models.json").write_text(json.dumps(models), encoding="utf-8")
    try:
        from tests.helpers import local_seed
        mock = local_seed.start_box()
        local_seed.seed(st, mock)
        rig.closers.append(getattr(mock, "stop", lambda: None))
        return "local seed ok"
    except Exception as e:  # Local then draws its empty states; the driver says so
        return f"local seed failed: {type(e).__name__}: {e}"
