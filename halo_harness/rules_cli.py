"""halo_harness.rules_cli -- `halo rules` (Halo 2.0.5 round 3, deliverable
2): lists the learned PARAMETER-rejection rules `providers.learned_params`
has recorded (endpoint, field, action, age), or forgets one endpoint's
rules with `--forget`. `/rules` (`commands/builtins.py::_cmd_rules`)
renders the SAME listing, so the two surfaces never drift apart. This is
deliberately separate from `halo mcp learned` (`tools_rejected`/
`reasoning_effort_with_tools`, a different learned shape with its own
forget surface) -- `halo rules --forget` only ever clears a PARAM fix.

Bare `halo rules` never touches the network (reads whatever `learned-
rules.json` already has).
"""

from __future__ import annotations

import argparse

from halo_harness.config.paths import bridge_home


def format_rules_lines(rows: list) -> list:
    """`[{"endpoint","field","action","value","age_s"}, ...]` (`providers.
    learned_params.list_param_rules`'s own shape) -> display lines, one per
    rule, age rendered as whole days (or "<1d")."""
    if not rows:
        return ["No learned parameter rules yet."]
    lines = []
    for r in rows:
        days = r["age_s"] / 86400
        age = f"{days:.0f}d" if days >= 1 else "<1d"
        value = f" -> {r['value']!r}" if r.get("value") is not None else ""
        lines.append(f"{r['endpoint']:<44} {r['field']:<22} {r['action']:<6}{value:<16} {age}")
    return lines


def cmd_rules(argv) -> int:
    parser = argparse.ArgumentParser(prog="halo rules", add_help=True,
                                      description="List or forget learned parameter-rejection rules.")
    parser.add_argument("--forget", metavar="<provider:model>", default=None,
                         help="Clear every learned parameter rule for this endpoint, as printed with no --forget")
    args = parser.parse_args(argv)

    from halo_harness.providers.learned_params import forget_param_fixes, list_param_rules
    state_dir = bridge_home()
    if args.forget:
        if forget_param_fixes(state_dir, args.forget):
            print(f"halo rules: forgot the learned parameter rule(s) for {args.forget!r}.")
            return 0
        print(f"halo rules: no learned parameter rule for {args.forget!r} to forget.")
        return 1

    for line in format_rules_lines(list_param_rules(state_dir)):
        print(line)
    return 0
