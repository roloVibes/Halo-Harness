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
    seed_crew(st, pref)
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


def seed_crew(st, pref: str) -> None:
    """3.6.0.0 R1: the Agents tab's list -- six crew agents with long names (one with every kind of tool, a skill and a
    connected tool, its More filled), so the room rules measure a full form (`&view=crew&agent=<LONG[0]>`)."""
    from halo_harness.crew import store
    for i, n in enumerate(LONG[:6]):
        raw = {"format": "agent/1", "name": n, "does": f"{n.replace('-', ' ').capitalize()}: reads the task, does the part named here and hands back one short report.",
               "model": pref if i % 2 else "auto", "uses": ["read", "edit", "bash", "web", "skill:release-notes", "mcp:issue-tracker"] if i == 0 else ["read"],
               "careful": ("ask-changes", "ask-commands", "own")[i % 3],
               "more": {"max_turns": 40, "max_usd": 2.5, "reads": ["SECURITY.md", "docs/CONTRIBUTING.md"], "worktree": True} if i == 0 else {}}
        if i == 0:
            raw["instructions"] = chr(10).join(f"{k}. Step {k} of how it works, in one plain line that is long enough to wrap in a narrow box." for k in range(1, 9))
        store.write_text(store.path_for("agent", n, state_dir=st), store.dump(raw))
    seed_flows(st)


FLOW = "storefront-checkout-release-and-regression-flow"


def seed_flows(st) -> None:
    """3.6.0.0 R2: the Workflows tab's list -- four workflows with long names; the first (`&view=flows&workflow=<FLOW>`)
    with four steps: two agents side by side, a when of each kind, a repeat, long words everywhere."""
    from halo_harness.crew import store
    steps = [{"name": "Make the change the task asks for, in the checkout code", "agents": [LONG[0]], "gets": "the task and the files it names",
              "hands": "the diff and a one-line summary of what changed"},
             {"name": "Check it from both sides at the same time", "agents": [LONG[1], LONG[4]], "gets": "the diff",
              "hands": "failures and problems, one line each", "repeat": {"until": "the tests pass and the audit finds nothing", "max": 3}},
             {"name": "Read the receipts", "agents": [LONG[5]], "when": {"needs": ["pdf", "images"]}, "gets": "the attachments", "hands": "items and totals"},
             {"name": "Write the release notes", "agents": [LONG[2]], "when": {"says": ["release", "ship"]}, "gets": "the diff", "hands": "the notes"}]
    for i, n in enumerate((FLOW, "payments-refunds-and-chargebacks-review", "docs-and-screenshots-refresh-weekly", "inventory-sync-nightly")):
        raw = {"format": "workflow/1", "name": n, "for": f"{n.replace('-', ' ').capitalize()}: what comes in, what each step does, what it hands back.",
               "steps": steps if i == 0 else steps[:1 + i % 2], "own_copy": False}
        store.write_text(store.path_for("workflow", n, state_dir=st), store.dump(raw))
