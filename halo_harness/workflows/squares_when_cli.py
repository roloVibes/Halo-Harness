"""halo_harness.workflows.squares_when_cli -- `halo workflows enable <ref> --when ...` and `halo workflows when <ref>`
(Halo 3.3.16.3, docs/COMMANDS-workflows.md): a square's "when" on a lineup (workflows/when.py; when_store.py writes
it into the lineup's `workflows:` item, or config `workflows.when.<ref>` on the auto lineup).

    halo workflows enable media --when needs=pdf,audio      on, wired with the rule (enabled first when it is off)
    halo workflows enable review --when words=review,audit
    halo workflows enable plan --when named | always | off | auto
    halo workflows when media [--lineup <name>]             the rule: its label and the sentence
"""

from __future__ import annotations

import sys
from pathlib import Path

from halo_harness.workflows import registry
from halo_harness.workflows import when as W


def when_fields(lineup, repo: Path):
    """For `rows()`: (ref, covers) -> {when, when_label, when_sentence} on the lineup."""
    from halo_harness.workflows.when_store import rules_for
    try:
        rules = rules_for(lineup, cwd=repo)
    except Exception:
        rules = {}

    def one(ref: str, covers) -> dict:
        rule = rules.get(ref)
        return {"when": rule.to_json() if rule is not None else {}, "when_mode": rule.mode if rule else "auto",
                "when_label": W.label(rule, covers), "when_sentence": W.sentence(rule, ref, covers)}
    return one


def print_when(wf, lineup, repo: Path) -> int:
    from halo_harness.workflows.when_store import rule_of
    lineup = lineup if lineup is not None else registry.active_lineup()
    where = "the auto lineup" if registry.uses_config(lineup) else f"lineup {lineup}"
    if wf.ref not in registry.enabled_refs(lineup, cwd=repo):
        print(f"{wf.ref} is not on {where}: halo workflows enable {wf.ref} [--when ...]")
        return 1
    rule = rule_of(wf.ref, lineup, cwd=repo)
    print(f"{wf.ref} on {where}: {W.when_line(rule, wf.contract.covers)}")
    print(f"  {W.sentence(rule, wf.ref, wf.contract.covers)}")
    print(f"  written: {rule.to_json() if rule is not None and not rule.plain else 'a plain ref (its covers)'}")
    return 0


def enable_when(wf, text: str, lineup, repo: Path) -> int:
    raw, bad = W.parse(text)
    if raw is None:
        print(f"halo workflows enable: {bad}", file=sys.stderr)
        return 2
    ok, line = registry.enable(wf.ref, lineup, cwd=repo)
    if not ok:
        print(f"halo workflows enable: {line}", file=sys.stderr)
        return 1
    from halo_harness.workflows.when_store import set_rule
    ok2, line2 = set_rule(wf.ref, raw, lineup, cwd=repo)
    if "already on" not in line:
        print(line)
    print(line2 if ok2 else f"halo workflows enable: {line2}", file=sys.stdout if ok2 else sys.stderr)
    return 0 if ok2 else 1
