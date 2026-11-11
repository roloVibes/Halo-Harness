"""halo_harness.workflows.when_route -- the router's explicit rules (Halo 3.3.16.3, docs/WORKFLOWS-squares.md "When"
and "The order"): a hand-off that names no need goes first to a square whose rule is `always`, then to one whose
`words` the task says; then a square whose rule names `needs` that meet the gaps (router.py picks among the
`explicit` squares with `covers`). All of these come before a lineup role that covers the need; a square with a
plain ref comes after it.

    by_rule(route, task, squares, rules) -> bool   True when one fired: route.square / .rule / .why are set
    explicit(rules, wf) -> bool                   the square carries a rule that is not the plain one
    covers(rules, wf) -> [need]                   what it covers for the router: its rule's needs, else its contract's
"""

from __future__ import annotations

from halo_harness.workflows.when import word_hit


def by_rule(r, task: str, squares: list, rules: dict) -> bool:
    for wf in squares:
        rule = rules.get(wf.ref)
        if rule is not None and rule.mode == "always":
            r.square, r.rule = wf, "always first"
            r.why = f"handing the task to {wf.ref}: always first"
            return True
    for wf in squares:
        word = word_hit(rules.get(wf.ref), task)
        if word:
            r.square, r.rule = wf, f'when the task says "{word}"'
            r.why = f"handing the task to {wf.ref}: {r.rule}"
            return True
    return False


def explicit(rules: dict, wf) -> bool:
    rule = rules.get(wf.ref)
    return rule is not None and not rule.plain


def covers(rules: dict, wf) -> list:
    """A rule's `needs` narrow what the square covers; a words-only rule covers no need; otherwise its covers."""
    rule = rules.get(wf.ref)
    if rule is None or rule.plain:
        return list(wf.contract.covers)
    return list(rule.needs) if rule.needs else ([] if rule.words else list(wf.contract.covers))
