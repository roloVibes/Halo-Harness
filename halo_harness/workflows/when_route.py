"""halo_harness.workflows.when_route -- the router's two rules that come before the needs (Halo 3.3.16.3, docs/
WORKFLOWS-squares.md "When"): a hand-off that names no need goes first to a square whose rule is `always`, then to
one whose `words` the task says. The needs rule stays router.py's pick.

    by_rule(route, task, squares, rules) -> bool   True when one fired: route.square / .rule / .why are set
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
