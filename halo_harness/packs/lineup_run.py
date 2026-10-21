"""halo_harness.packs.lineup_run -- what a lineup says about the runs that
use it (Halo 3.2.0.0 R2, docs/PACKS.md "A pack's lineups").

A lineup's `acceptance` section already holds the smoke prompt `halo doctor
--teams` runs (`prompt`, `expect`). It also holds the Orchestra defaults a
run with this lineup starts with, under the Orchestra's own field names:

    acceptance:
      test: python -m pytest -q   # the goal's `test`: the command the gate runs
      review: true                # the goal's `plan: review`: pause after the split for the plan's review

`halo orchestra new --lineup L` takes them when you give no `--test` (and the
plan is still `auto`); what you type wins. `workflows: [<name>, ...]` names
the pack workflows the lineup runs (R5 runs them; in a pack's lineup each
name is one its pack.yaml declares, packs/bio_rules.py).

    acceptance_problems(data)               # one line per bad value (teams_yaml.validate_team_template)
    run_defaults(name, cwd=..., state_dir=...)  # {"test": "...", "review": True} (only what the lineup sets)
    goal_defaults(goal, cwd=..., explicit_test=False)  # fills an Orchestra Goal; the lines saying what it took
"""

from __future__ import annotations


def acceptance_problems(data) -> "list[str]":
    if not isinstance(data, dict):
        return []
    out: "list[str]" = []
    flows = data.get("workflows")
    if flows is not None and not (isinstance(flows, list) and all(isinstance(f, str) and f.strip() for f in flows)):
        out.append('"workflows" must be a list of workflow names')
    acc = data.get("acceptance") if isinstance(data.get("acceptance"), dict) else {}
    if acc.get("test") is not None and not isinstance(acc.get("test"), str):
        out.append('"acceptance.test" must be a command (a string), the one the Orchestra gate runs')
    if acc.get("review") is not None and not isinstance(acc.get("review"), bool):
        out.append('"acceptance.review" must be true or false (pause for the plan\'s review)')
    return out


def run_defaults(name: str, *, cwd=None, state_dir=None) -> dict:
    """The Orchestra defaults lineup `name` sets: `test` and `review`, each only when set."""
    from halo_harness.teams_yaml import resolve_team_template
    if not isinstance(name, str) or not name.strip():
        return {}
    lineup = resolve_team_template(name.strip(), cwd=cwd, state_dir=state_dir) or {}
    acc = lineup.get("acceptance") if isinstance(lineup.get("acceptance"), dict) else {}
    out: dict = {}
    if isinstance(acc.get("test"), str) and acc["test"].strip():
        out["test"] = acc["test"].strip()
    if isinstance(acc.get("review"), bool):
        out["review"] = acc["review"]
    return out


def goal_defaults(goal, *, cwd=None, state_dir=None, explicit_test: bool = False) -> "list[str]":
    """Fill an Orchestra `Goal` from its lineup's acceptance; what you gave wins. The lines say what was taken."""
    defaults = run_defaults(getattr(goal, "lineup", "") or "", cwd=cwd, state_dir=state_dir)
    lines: "list[str]" = []
    if defaults.get("test") and not explicit_test and not str(goal.test or "").strip():
        goal.test = defaults["test"]
        lines.append(f"test: {goal.test} (from lineup {goal.lineup}'s acceptance.test)")
    if defaults.get("review") and getattr(goal, "plan", "auto") == "auto":
        goal.plan = "review"
        lines.append(f"plan: review (lineup {goal.lineup}'s acceptance.review: the run pauses for the plan)")
    return lines
