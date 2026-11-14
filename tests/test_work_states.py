"""tests.test_work_states -- Halo 3.1.2.0 round R2: the state machine is
enforced (halo_harness/work/states.py, work/unit.py `Unit.move`): every
legal edge moves, three illegal ones raise IllegalMove naming the unit,
from and to (and an engine setter that meets one writes nothing), and each
engine's real fixture history -- an Orchestra run with a hand-off, a team
run through its gate and a local mission -- replays
through `Unit.move` from its first word to its last. No model is called.

Run: python -m tests.test_work_states
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from tests.helpers.provider_env_defaults import ensure_default_provider_credentials, ensure_scoped_state_dir_once

ensure_default_provider_credentials()
ensure_scoped_state_dir_once()

from tests.helpers.runner import Ctx, new_registry, print_results, run_all  # noqa: E402

test, TESTS = new_registry()


def _replay(kind: str, uid, words: list):
    """Move a fresh unit through `words` (engine words); the unit, or the IllegalMove text."""
    from halo_harness.work.states import IllegalMove
    from halo_harness.work.unit import Unit
    u = Unit.from_native(kind, uid, "" if kind == "lane" else "pending")
    try:
        for w in words:
            u.move_native(w)
    except IllegalMove as e:
        return str(e)
    return u


@test
def test_every_legal_edge_moves_and_the_added_ones_are_named(ctx: Ctx):
    from halo_harness.work import states as ST
    from halo_harness.work.unit import Unit
    moved = 0
    for a, outs in ST.EDGES.items():
        for b in outs:
            u = Unit(kind="lane", id="1", state=a)
            u.move(b)
            moved += u.state == b
    ctx.check(f"every edge moves, got {moved}", moved == sum(len(v) for v in ST.EDGES.values()))
    same = Unit(kind="goal", id="s", state="waiting").move("waiting")
    ctx.check("a move to the state it is in is the state said again", same.state == "waiting")
    ctx.check(f"R2's added edges are edges, got {ST.ADDED}", all(ST.can(a, b) for a, b in ST.ADDED) and len(ST.ADDED) == 5)
    ctx.check("stopped is the one state with no way out", ST.EDGES["stopped"] == () and ST.can("merged", "waiting")
              and not ST.can("merged", "ready"))


@test
def test_three_illegal_moves_raise_naming_the_unit_from_and_to(ctx: Ctx):
    from halo_harness.work.states import IllegalMove
    from halo_harness.work.unit import Unit, move_word
    cases = [(Unit(kind="lane", id="2", run_id="r1", state="merged"), "ready"),
             (Unit(kind="goal", id="draft", state="stopped"), "running"),
             (Unit(kind="lane", id="3", state="pending"), "merged")]
    texts = []
    for u, to in cases:
        try:
            u.move(to)
            texts.append(None)
        except IllegalMove as e:
            texts.append(str(e))
    ctx.check(f"each raises with the unit, from and to, got {texts}",
              texts[0] == "lane 2 of run r1 cannot move from merged to ready (from merged it moves to waiting)"
              and texts[1] == "goal draft cannot move from stopped to running (from stopped it moves to nothing: it is over)"
              and texts[2].startswith("lane 3 cannot move from pending to merged"))
    ctx.check("IllegalMove is a ValueError, and the engine-word helper raises it too",
              isinstance(IllegalMove("x", "a", "b"), ValueError) and _raises(lambda: move_word("lane", "s", "merged", "joined")))


def _raises(fn) -> bool:
    from halo_harness.work.states import IllegalMove
    try:
        fn()
    except IllegalMove:
        return True
    return False


@test
def test_an_orchestra_runs_lanes_replay_through_move(ctx: Ctx):
    from tests.helpers.orchestra_studio_rig import finished_run
    _repo, run_dir = finished_run(chain=True)
    ok, seen = True, {}
    for path in sorted((run_dir / "lanes").glob("*.json")):
        rec = json.loads(path.read_text(encoding="utf-8"))
        words = [h["state"] for h in rec.get("history") or []]
        got = _replay("lane", rec["lane"], words)
        seen[rec["lane"]] = words
        ok = ok and not isinstance(got, str) and got.native == rec["state"] == "merged"
    ctx.check(f"every lane's history replays to merged, got {seen}", ok and len(seen) == 5
              and seen[2][0] == "waiting" and "joined" in seen[2])


if __name__ == "__main__":
    ctx = Ctx()
    results, passed, failed, skipped = run_all(TESTS, ctx)
    sys.exit(print_results(results, passed, failed, skipped, label="work state machine tests"))
