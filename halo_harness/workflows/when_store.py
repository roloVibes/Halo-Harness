"""halo_harness.workflows.when_store -- where a square's "when" rule lives (Halo 3.3.16.3; 3.6.0.0 R5d: config only).

A session's squares and their rules are config's: `workflows.when.<ref>` beside `workflows.enabled` (when.py reads a
rule). Lineups were the other place until 3.6; no session reads one, so their `workflows:` lists are not read.

    rules_for(lineup=None, cwd=, state_dir=)        -> {ref: Rule} (only the refs that carry one)
    rule_of(ref, lineup=None, ...)                  -> Rule | None

`lineup` is kept in the signatures for the callers that pass the session's name; it changes nothing.
"""

from __future__ import annotations

from typing import Optional

from halo_harness.workflows import when as W

CONFIG_KEY = "workflows.when"


def config_rules() -> dict:
    from halo_harness.theme import get_config_value
    try:
        got = get_config_value(CONFIG_KEY, None)
    except Exception:
        got = None
    return dict(got) if isinstance(got, dict) else {}


def rules_for(lineup=None, *, cwd=None, state_dir=None) -> dict:
    return {ref: rule for ref, raw in config_rules().items() if (rule := W.read(raw)) is not None}


def rule_of(ref: str, lineup=None, *, cwd=None, state_dir=None) -> Optional[W.Rule]:
    return rules_for(lineup, cwd=cwd, state_dir=state_dir).get(ref)
