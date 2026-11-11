"""tests.test_packs_contrib -- the 3.4.0.0 B draft contributions (extension API 1.3): `contributes.cli`, `.slash`,
`.doctor` and `.settings`, their manifest rules (one line per problem, each naming the entry), the grants they take
(`cli:<verb>`, `doctor`), and that `permissions:` takes `cli:<verb>` and `doctor`. The verbs at work: tests/
test_pack_first_run.py (the first-run pack's `halo start` and `/start`). Run: python -m tests.test_packs_contrib
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from tests.helpers.runner import Ctx, new_registry, print_results, run_all  # noqa: E402

test, TESTS = new_registry()
BASE = {"id": "demo", "name": "Demo", "version": "1.0.0", "halo_api": {"min": "1.2"}}


def _lines(contributes: dict, permissions=None) -> "list[str]":
    from halo_harness.packs.manifest import validate_manifest
    data = dict(BASE, contributes=contributes, permissions=permissions or [])
    return validate_manifest(data)


@test
def test_good_entries_validate_and_name_their_grants(ctx: Ctx):
    from halo_harness.packs import contrib_lines as CL
    c = {"cli": [{"verb": "start", "module": "cli/start.py", "help": "the run"}],
         "slash": [{"name": "start", "module": "cli/slash.py"}],
         "doctor": [{"id": "library", "module": "doctor.py"}],
         "settings": [{"key": "probe.k", "title": "Probe pairs", "type": "integer", "default": 1}]}
    lines = _lines(c, ["cli:start", "doctor"])
    ctx.check(f"a good manifest has no problem, got {lines}", lines == [])
    needs = CL.needs({"contributes": c})
    ctx.check(f"the grants: cli:start (the verb and the slash), doctor, got {needs}",
              ("cli:start", "CLI verb start") in needs and ("cli:start", "slash command /start") in needs
              and ("doctor", "doctor rows library") in needs)


@test
def test_each_problem_is_one_line_naming_the_entry(ctx: Ctx):
    c = {"cli": [{"verb": "Start", "module": "cli/start.txt"}, {"verb": "go", "module": "../x.py", "extra": 1}],
         "slash": [{"name": "a", "module": "s.py"}, {"name": "a", "module": "s.py"}],
         "doctor": [{"id": "", "module": "d.py"}],
         "settings": [{"key": "Bad Key", "title": "", "type": "list", "default": 3},
                      {"key": "n", "title": "N", "type": "integer", "default": True}]}
    lines = _lines(c)
    want = ["contributes.cli[0].verb: 'Start' is not a verb", "contributes.cli[0].module: 'cli/start.txt' is not a .py file",
            "contributes.cli[1]: unknown key 'extra'", "contributes.cli[1].module: '../x.py' is outside the pack",
            "contributes.slash[1].name: 'a' is used twice", "contributes.doctor[0].id: '' is not an id",
            "contributes.settings[0].key: 'Bad Key' is not a settings key", "contributes.settings[0].title: required",
            "contributes.settings[0].type: 'list' is not one of", "contributes.settings[1].default: True is not of type integer"]
    missing = [w for w in want if not any(ln.startswith(w) for ln in lines)]
    ctx.check(f"every problem named, got {lines}; missing {missing}", not missing)


@test
def test_permissions_take_cli_verbs_and_doctor(ctx: Ctx):
    lines = _lines({}, ["cli:start", "doctor", "cli:", "cli-start"])
    ctx.check(f"cli:<verb> and doctor are names; `cli:` and `cli-start` are not, got {lines}",
              not any("'cli:start'" in ln or "'doctor'" in ln for ln in lines)
              and any("'cli:'" in ln for ln in lines) and any("'cli-start'" in ln for ln in lines))


@test
def test_a_verb_that_left_says_its_line(ctx: Ctx):
    from halo_harness.left import LEFT, PACKED, line
    ctx.check("team left, start is the first-run pack's", "team" in LEFT and PACKED.get("start", ("",))[0] == "first-run")
    ctx.check("any other word says nothing", line("teams") == "" and line("orchestra") == "")


if __name__ == "__main__":
    ctx = Ctx()
    results, passed, failed, skipped = run_all(TESTS, ctx)
    sys.exit(print_results(results, passed, failed, skipped, label="pack contribution tests"))
