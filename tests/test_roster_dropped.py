"""tests.test_roster_dropped -- the roster drops a failing model (Halo 3.1.9.0
R3, providers/roster.py over outcomes/learn.py), on R1's seeded catalog
(tests/helpers/catalog_facts_seed.py) and the seeded outcomes fixture
tests/fixtures/outcomes/learn-roster.jsonl (dbx:databricks-gemini-9-flash
media 0/5, ant:fable research 0/3, or:v/ears code 1/4, or:v/cheap plan 1/3:
all below 34%; or:v/eyes code 4/4 is not):

1. a dropped model leaves the leaders of the kinds its task kind maps to
   (code -> code, research -> research, media -> visual, audio, video), and
   one line after them names it with its numbers, worst first, at most 3
   models, "+1 more" for the rest;
2. the block is byte-stable while the numbers do not move: the same file
   twice, a new unrated row (stopped, unchecked), a new row for another kind
   under min_tasks; it moves when a number does;
3. nothing dropped (no outcomes, or `models.learn: false`): no drop line and
   R1's leaders; the block stays within 40 lines and names only models.
No model call. Run: python -m tests.test_roster_dropped
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from tests.helpers.runner import Ctx, new_registry, print_results, run_all  # noqa: E402
from tests.helpers import catalog_facts_seed as S  # noqa: E402
from tests.helpers import outcomes_rig as R  # noqa: E402

test, TESTS = new_registry()
DROP = ("- dropped for media: dbx:databricks-gemini-9-flash (0/5 checked tasks); dropped for research: ant:fable "
        "(0/3 checked tasks); dropped for code: or:v/ears (1/4 checked tasks) (+1 more: `halo outcomes learned`)")


def _block(state, env) -> str:
    from halo_harness.providers.roster import roster_block
    return roster_block(state, list(S.rows_by_ref(state, env).values()))


def _leaders(text: str) -> dict:
    out = {}
    for line in text.splitlines():
        if line.startswith("- ") and ": " in line and not line.startswith("- dropped") and "  " not in line:
            kind, rest = line[2:].split(": ", 1)
            out[kind] = rest
    return out


@test
def test_a_dropped_model_leaves_the_leaders_and_is_named_once(ctx: Ctx):
    with S.home("roster-dropped-") as (_root, state):
        env = S.seed(state)
        before = _block(state, env)
        R.seed_fixture(state, "learn-roster")
        after = _block(state, env)
    lines = after.splitlines()
    drop = [line for line in lines if line.startswith("- dropped")]
    ctx.check(f"one drop line, worst first, at most 3 models, the rest counted, got {drop}", drop == [DROP])
    ctx.check("it sits after the per-kind leaders, before the model lines",
              lines.index(DROP) == lines.index("Models:") - 1)
    was, now = _leaders(before), _leaders(after)
    ctx.check(f"R1's code line named or:v/ears the cheapest, got {was.get('code')!r}", was.get("code") == "ant:fable; cheapest or:v/ears")
    ctx.check(f"code: or:v/ears is out of the leaders, got {now.get('code')!r}",
              "or:v/ears" not in now.get("code", "") and now.get("code", "").startswith("ant:fable"))
    ctx.check(f"research: ant:fable is out (it stays the code leader), got {now.get('research')!r}",
              "ant:fable" not in now.get("research", "x") and now.get("research"))
    for kind in ("visual", "audio", "video"):
        ctx.check(f"media -> {kind}: dbx:databricks-gemini-9-flash is out, got {now.get(kind)!r}",
                  "databricks-gemini-9-flash" not in now.get(kind, ""))
    ctx.check(f"a model's own measured line still says what it did, got {[l for l in lines if l.startswith('- or:v/ears ')]}",
              any(l.startswith("- or:v/ears ") and "code 1/4" in l for l in lines))
    ctx.check("the kinds no task kind maps to are R1's", all(now.get(k) == was.get(k) for k in ("image", "design", "pdf", "bulk")))
    ctx.check(f"still within 40 lines, got {len(lines)}", len(lines) <= 40)
    ctx.check("names only: no URL, no path", "http" not in after and "\\" not in after and str(state) not in after)


@test
def test_the_block_is_byte_stable_until_a_number_moves(ctx: Ctx):
    from halo_harness.outcomes.records import append, make_row
    with S.home("roster-stable-") as (_root, state):
        env = S.seed(state)
        R.seed_fixture(state, "learn-roster")
        first, second = _block(state, env), _block(state, env)
        append([make_row(run="later", task="agent s1", source="session", model="or:v/ears", kind="code", outcome="stopped"),
                make_row(run="later", task="agent s2", source="session", model="or:v/ears", kind="code", outcome="passed",
                         check=""),
                make_row(run="later", task="agent s3", source="session", model="or:v/eyes", kind="review",
                         outcome="failed", check="acceptance")], state)
        third = _block(state, env)
        append([make_row(run="later", task="agent s4", source="session", model="or:v/ears", kind="code", outcome="passed",
                         check="acceptance")], state)
        moved = _block(state, env)
    ctx.check("the same outcomes file twice: byte-identical", first == second)
    ctx.check("an unrated row, an unchecked one and one under min_tasks change nothing", third == first)
    drop = [line for line in moved.splitlines() if line.startswith("- dropped")]
    ctx.check(f"a checked pass lifts or:v/ears to 2/5 (40%, over 34%): off the drop line, back among the leaders, "
              f"the fourth now shown, got {drop}",
              moved != first and drop == ["- dropped for media: dbx:databricks-gemini-9-flash (0/5 checked tasks); "
                                          "dropped for research: ant:fable (0/3 checked tasks); dropped for plan: "
                                          "or:v/cheap (1/3 checked tasks)"]
              and "- code: ant:fable; cheapest or:v/ears" in moved.splitlines())


@test
def test_nothing_dropped_keeps_r1s_roster(ctx: Ctx):
    from halo_harness.theme import set_config_value
    with S.home("roster-none-") as (_root, state):
        env = S.seed(state)
        plain = _block(state, env)
        R.seed_fixture(state, "learn-roster")
        set_config_value("models.learn", False)
        off = _block(state, env)
        set_config_value("models.learn", {"drop_below": 0.0})
        never = _block(state, env)
    ctx.check("no outcomes: no drop line", "dropped for" not in plain)
    ctx.check("models.learn false: no drop line and R1's leaders", "dropped for" not in off and _leaders(off) == _leaders(plain))
    ctx.check("drop_below 0: nothing is below it", "dropped for" not in never and _leaders(never) == _leaders(plain))


if __name__ == "__main__":
    ctx = Ctx()
    results, passed, failed, skipped = run_all(TESTS, ctx)
    sys.exit(print_results(results, passed, failed, skipped))
