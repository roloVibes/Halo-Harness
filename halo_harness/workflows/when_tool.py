"""halo_harness.workflows.when_tool -- what the Workflow tool's description says of each enabled square, its "when"
included (Halo 3.3.16.3, docs/WORKFLOWS-squares.md "When"). A square with no rule reads as before ("media (covers
pdf, vision, ...)"); a rule says itself: by name only, always first (main hands it the task before it answers), the
words; a square that is not connected is left out.

    squares_tail(squares, rules) -> str
    has_reach(rules) -> bool   a rule main acts on whatever its model takes (always, or words)
"""

from __future__ import annotations


def _one(wf, rule) -> str:
    covers = ", ".join(wf.contract.covers) or "-"
    if rule is None:
        return f"{wf.ref} (covers {covers})"
    if rule.mode == "named":
        return f"{wf.ref} (only when you name it)"
    if rule.mode == "always":
        return f"{wf.ref} (always first: hand it the task before you answer)"
    bits = [f"covers {', '.join(rule.needs)}"] if rule.needs else ([] if rule.words else [f"covers {covers}"])
    bits += [f"when the task says {', '.join(rule.words)}"] if rule.words else []
    return f"{wf.ref} ({'; '.join(bits)})"


def squares_tail(squares: list, rules: dict) -> str:
    live = [wf for wf in squares if not (wf.ref in rules and rules[wf.ref].mode == "off")]
    if not live:
        return (" No square is connected for this lineup (Studio: draw its line)." if squares
                else " No square is enabled for this lineup yet (halo workflows enable media).")
    return " Enabled squares: " + "; ".join(_one(wf, rules.get(wf.ref)) for wf in live) + "."


def has_reach(rules: dict) -> bool:
    return any(r.mode == "always" or (r.mode == "auto" and r.words) for r in rules.values())
