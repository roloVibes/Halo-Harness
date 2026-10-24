"""tests.test_outcomes_learned_cli -- see and reset what Auto learned (Halo
3.1.9.0 R3, outcomes/learn_cli.py), over a fresh home seeded with the
outcomes fixture tests/fixtures/outcomes/learn-roster.jsonl:

1. `halo outcomes learned`: per model and kind the window's n, passes, rate,
   the pick's weight, how many were its own picks, dropped; `--kind`,
   `--model`; `--json` (the settings and the rows); learning off says so;
2. `halo outcomes forget`: without --yes (stdin not a terminal) nothing is
   removed; with --yes the matching rows go, the rest stay as they were, the
   file before is kept as outcomes.jsonl.bak-<time> (one line says so), and
   the best-at cache is marked stale; --before; no match; a bad date;
3. `halo models --measured` (text and --json) and `halo models analyze`
   mark a dropped model.
No model call. Run: python -m tests.test_outcomes_learned_cli
"""
from __future__ import annotations

import contextlib
import io
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from tests.helpers.provider_env_defaults import ensure_scoped_state_dir_once  # noqa: E402
from tests.helpers.runner import Ctx, new_registry, print_results, run_all  # noqa: E402
from tests.helpers import catalog_facts_seed as S  # noqa: E402
from tests.helpers import outcomes_rig as R  # noqa: E402

ensure_scoped_state_dir_once()
test, TESTS = new_registry()


def _run(fn, argv) -> "tuple[int, str]":
    buf, saved = io.StringIO(), sys.stdin
    sys.stdin = io.StringIO("")  # not a terminal: forget never asks
    try:
        with contextlib.redirect_stdout(buf):
            code = fn(argv)
    finally:
        sys.stdin = saved
    return code, buf.getvalue()


def _outcomes(argv):
    from halo_harness.outcomes.cli import cmd_outcomes
    return _run(cmd_outcomes, argv)


def _row(text: str, model: str, kind: str) -> str:
    return next((l for l in text.splitlines() if l.startswith(model + " ") and f" {kind} " in l), "")


@test
def test_learned_lists_the_numbers_the_weight_and_the_drops(ctx: Ctx):
    from halo_harness.theme import set_config_value
    with R.home("learned-") as state:
        code, empty = _outcomes(["learned"])
        R.seed_fixture(state, "learn-roster")
        code2, text = _outcomes(["learned"])
        _c, only = _outcomes(["learned", "--kind", "code", "--model", "or:v/eyes"])
        _c, raw = _outcomes(["learned", "--json"])
        set_config_value("models.learn", False)
        _c, off = _outcomes(["learned"])
    ctx.check(f"nothing yet says how rows get there, got {empty!r}", code == 0 and "Nothing learned yet" in empty)
    head = text.splitlines()[0]
    ctx.check(f"the rule's numbers head the table, got {head!r}",
              code2 == 0 and head == "Learning on; the last 30 days; weighed from 3 checked tasks (weight 0.5 + 0.5 x rate); "
                                     "dropped below 34%.")
    ears = _row(text, "or:v/ears", "code")
    ctx.check(f"or:v/ears code: 1/4, 25%, weight 0.625, 4 own picks, dropped (the stopped row is not rated), got {ears!r}",
              ears.split() == ["or:v/ears", "code", "4", "1/4", "25%", "0.625", "4/4", "dropped", "for", "code"])
    eyes = _row(text, "or:v/eyes", "code")
    ctx.check(f"or:v/eyes code: the 40-day-old failure is out of the window, 3 of 4 its own picks, got {eyes!r}",
              eyes.split() == ["or:v/eyes", "code", "4", "4/4", "100%", "1.000", "3/4"])
    cheap = _row(text, "or:v/cheap", "code")
    ctx.check(f"under 3 tasks: not weighed, got {cheap!r}", cheap.endswith("(fewer than 3: not weighed)") and " 1.000 " in cheap)
    ctx.check("ant:fable research 0/3 is dropped and none were picks",
              _row(text, "ant:fable", "research").split()[3:8] == ["0/3", "0%", "0.500", "0/3", "dropped"])
    ctx.check(f"--kind and --model narrow it, got {only!r}",
              [l.split()[0] for l in only.splitlines()[2:-1]] == ["or:v/eyes"])
    data = json.loads(raw)
    rows = {(r["model"], r["kind"]): r for r in data["rows"]}
    ctx.check(f"--json: the settings, the window's start and the rows, got {data['learn']}",
              data["learn"] == {"enabled": True, "min_tasks": 3, "window_days": 30, "drop_below": 0.34}
              and isinstance(data["since"], float) and rows[("or:v/ears", "code")]["weight"] == 0.625
              and rows[("or:v/ears", "code")]["dropped"] is True and rows[("or:v/eyes", "code")]["picked"] == 3
              and rows[("or:v/cheap", "code")]["counted"] is False)
    ctx.check(f"learning off says the numbers are not used, got {off.splitlines()[0]!r}",
              off.startswith("Learning off (models.learn: false") and "dropped for" not in off
              and " 1.000 " in _row(off, "or:v/ears", "code"))


@test
def test_forget_removes_with_a_backup_and_marks_the_cache_stale(ctx: Ctx):
    from halo_harness.models_best_at import is_fresh, load, rebuild
    from halo_harness.outcomes.records import path
    with R.home("forget-") as state:
        R.seed_fixture(state, "learn-roster")
        rebuild(state, [])  # a best-at cache to invalidate
        fresh = is_fresh(load(state), state)
        original = path(state).read_text(encoding="utf-8")
        ask, asked = _outcomes(["forget", "--model", "or:v/ears", "--kind", "code"])
        unchanged = path(state).read_text(encoding="utf-8") == original
        code, said = _outcomes(["forget", "--model", "or:v/ears", "--kind", "code", "--yes"])
        backups = sorted(path(state).parent.glob("outcomes.jsonl.bak-*"))
        after = path(state).read_text(encoding="utf-8")
        cache = load(state) or {}
        _c, learned = _outcomes(["learned", "--json"])
        none_code, none_said = _outcomes(["forget", "--kind", "nothing-like-this", "--yes"])
        old_code, old_said = _outcomes(["forget", "--before", "7d", "--yes"])
        old_after = path(state).read_text(encoding="utf-8")
        bad, bad_said = _outcomes(["forget", "--before", "someday"])
    ctx.check(f"without --yes and no terminal: nothing removed, saying how, got {asked!r}",
              ask == 1 and unchanged and "5 outcome row(s) match (model or:v/ears, kind code)" in asked and "--yes" in asked)
    ctx.check(f"with --yes: one line, the backup named, got {said!r}",
              code == 0 and len(said.strip().splitlines()) == 1 and said.startswith("Removed 5 outcome row(s) "
                                                                                   "(model or:v/ears, kind code), 18 kept;")
              and len(backups) == 1 and str(backups[0]) in said)
    ctx.check("the backup is the file before", backups and backups[0].read_text(encoding="utf-8") == original)
    kept = [l for l in original.splitlines() if not ('"model": "or:v/ears"' in l and '"kind": "code"' in l)]
    ctx.check("every other row stays as it was, in order", after.splitlines() == kept)
    ctx.check(f"the best-at cache was fresh and is now stale (built 0), got {cache.get('built')}",
              fresh and cache.get("built") == 0 and not is_fresh(cache, state))
    models = {r["model"] for r in json.loads(learned)["rows"] if r["kind"] == "code"}
    ctx.check(f"learned starts or:v/ears over, got {sorted(models)}", "or:v/ears" not in models and "or:v/eyes" in models)
    ctx.check(f"no match: nothing removed, got {none_said!r}", none_code == 0 and none_said.startswith("No outcome row matches"))
    ctx.check(f"--before 7d removes only the old rows, got {old_said!r}",
              old_code == 0 and old_said.startswith("Removed 1 outcome row(s) (before 7d)") and len(old_after.splitlines()) == 17)
    ctx.check(f"a date that does not read, got {bad_said!r}", bad == 2 and "does not read" in bad_said)


@test
def test_models_measured_and_analyze_mark_the_dropped(ctx: Ctx):
    from halo_harness.catalog_cli import cmd_models
    from halo_harness.models_analyze_cli import summary_lines
    from halo_harness.models_best_at import index
    with S.home("learned-marks-") as (_root, state):
        env = S.seed(state)
        R.seed_fixture(state, "learn-roster")
        _c, text = _run(cmd_models, ["--measured"])
        _c, raw = _run(cmd_models, ["--measured", "--json"])
        lines = summary_lines(index(state, list(S.rows_by_ref(state, env).values())), state)
    ears = _row(text, "or:v/ears", "code")
    ctx.check(f"--measured marks or:v/ears for code, got {ears!r}", ears.endswith("dropped for code (1/4 in the last 30 days)"))
    eyes = _row(text, "or:v/eyes", "code")
    ctx.check(f"all-time numbers stay all-time (4/5), and no mark, got {eyes!r}", "4/5" in eyes and "dropped" not in eyes)
    rows = {(r["model"], r["kind"]): r for r in json.loads(raw)}
    ctx.check("--json carries the mark", rows[("or:v/ears", "code")]["dropped"] == "dropped for code (1/4 in the last 30 days)"
              and rows[("or:v/eyes", "code")]["dropped"] == "")
    line = next((l for l in lines if l.strip().startswith("ant:fable ")), "")
    ctx.check(f"analyze marks the model's line, got {line[-80:]!r}", line.endswith(" -- dropped for research (0/3 in the last 30 days)"))
    ctx.check("and its measured table", any("or:v/cheap" in l and " plan " in l and "dropped for plan" in l for l in lines))


if __name__ == "__main__":
    ctx = Ctx()
    results, passed, failed, skipped = run_all(TESTS, ctx)
    sys.exit(print_results(results, passed, failed, skipped))
