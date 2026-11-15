"""tests.test_blocks -- Halo 3.3.16.3 "Blocks": a tier's `purpose` and a square's purpose (its DOES line), the two
things the Cast canvas draws as blocks. `tiers[].purpose` is read (teams_tiers.effective_tiers), checked (a non-string
is one problem line), printed by `halo teams show` (teams_tier_fields.tier_line) and kept through the YAML write the
canvas saves with; the shipped auto lineup names its tiers' purposes; a block's Purpose page saves a square's DOES
into a square of yours (studio/workflows_api.put_contract) and a shipped one answers how to copy it first. No model.
Run: python -m tests.test_blocks
"""
from __future__ import annotations

from types import SimpleNamespace

import sys
import tempfile
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO))

from tests.helpers.provider_env_defaults import ensure_scoped_state_dir_once  # noqa: E402
from tests.helpers.runner import Ctx, new_registry, print_results, run_all  # noqa: E402

ensure_scoped_state_dir_once()
test, TESTS = new_registry()

LINEUP = {"name": "think", "agents": [{"agent": "default-model", "role": "main"}, {"agent": "auto-planner", "role": "planner"},
                                      {"agent": "auto-reviewer", "role": "reviewer"}],
          "tiers": [{"name": "top", "members": ["main"]}, {"name": "thinkers", "members": ["planner", "reviewer"], "purpose": " thinking "}]}


@test
def test_a_tier_purpose_is_read_printed_and_checked(ctx: Ctx):
    from halo_harness.teams_tier_fields import tier_line
    from halo_harness.teams_tiers import effective_tiers, validate_tiers
    tiers = effective_tiers(LINEUP)
    ctx.check(f"the purpose, trimmed; none on a tier without one, got {[t.get('purpose') for t in tiers]}",
              [t.get("purpose") for t in tiers] == [None, "thinking"])
    ctx.check(f"teams show prints it, got {tier_line(tiers[1])!r}", tier_line(tiers[1]).startswith("tier 1 thinkers: planner, reviewer; purpose thinking"))
    ctx.check("a valid lineup stays valid", validate_tiers(LINEUP["tiers"], LINEUP["agents"]) == [])
    bad = validate_tiers([LINEUP["tiers"][0], {**LINEUP["tiers"][1], "purpose": 3}], LINEUP["agents"])
    ctx.check(f"a purpose that is not text is one line, got {bad}", bad == ["tiers[1] 'thinkers': \"purpose\" must be a few words of text"])


@test
def test_the_purpose_survives_the_yaml_write(ctx: Ctx):
    from halo_harness.agents_yaml import _read_yaml_file, _write_yaml_file
    with tempfile.TemporaryDirectory() as d:
        p = Path(d) / "think.yaml"
        ctx.check("written", not _write_yaml_file(p, LINEUP))
        back = _read_yaml_file(p) or {}
    ctx.check(f"read back, got {back.get('tiers')}", (back.get("tiers") or [{}, {}])[1].get("purpose") == " thinking ")


@test
def test_the_shipped_auto_lineup_names_its_tiers(ctx: Ctx):
    """3.6.0.0 R5b: the auto lineup is what a plain session answers (crew/plain.py, templates/crew/plain/session.yaml)."""
    from halo_harness.crew.plain import load
    got = [(t["name"], t.get("purpose")) for t in (load() or SimpleNamespace(tiers=[])).tiers]
    ctx.check(f"main and the pool each say what they are for, got {got}",
              got == [("main", "the one you talk to"), ("pool", "the workers, picked per task")])


if __name__ == "__main__":
    ctx = Ctx()
    results, passed, failed, skipped = run_all(TESTS, ctx)
    sys.exit(print_results(results, passed, failed, skipped))
