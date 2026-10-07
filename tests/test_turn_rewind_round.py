"""tests.test_turn_rewind_round -- Halo 2.0.6 round 6: turn checkpoints,
the file-state `/rewind turn <N>`.

The v2.0.4 model review's item 5: "snapshot the changed files at each
turn boundary (stash-style or a file history) so one key rolls back a
turn's edits after a bad agent run." The git-shadow store already
snapshots per STEP; this round groups those steps by the TURN their
tool_result event carried, so `/rewind turn <N>` restores the tree to
the START of that turn -- the last step of the previous turn, or the
session's own start (every created file deleted, nothing restored)
when there is no previous one.
"""

from __future__ import annotations

import json
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from tests.helpers.runner import Ctx, new_registry, print_results, run_all

test, TESTS = new_registry()


def _store(tmp: Path):
    from halo_harness.shadow import ShadowStore
    return ShadowStore(tmp / "shadow")


def _work(tmp: Path, name: str, content: str) -> Path:
    p = tmp / name
    p.write_text(content, encoding="utf-8")
    return p


@test
def test_checkpoints_group_steps_by_turn(ctx: Ctx):
    tmp = Path(tempfile.mkdtemp(prefix="tc-group-"))
    store = _store(tmp)
    a = _work(tmp, "a.txt", "v1")
    b = _work(tmp, "b.txt", "v1")
    c = _work(tmp, "c.txt", "v1")
    # turn 1: two steps; turn 2: one step; then an untagged (old-log) step
    store.record_step({str(a): "v2"}, label="Edit(a)", turn=1)
    store.record_step({str(b): "v2"}, label="Write(b)", turn=1, created=[str(b)])
    store.record_step({str(c): "v2"}, label="Edit(c)", turn=2, created=[str(c)])
    store.record_step({str(a): "v3"}, label="Edit(a-legacy)")
    cps = store.turn_checkpoints()
    ctx.check(f"two turn checkpoints (the legacy step never groups), got {[c['turn'] for c in cps]}",
              [c["turn"] for c in cps] == [1, 2])
    cp1, cp2 = cps
    ctx.check(f"turn 1 has no rewind_to (session start), got {cp1['rewind_to']!r}",
              cp1["rewind_to"] is None)
    ctx.check(f"turn 1 counts its steps/files, got {cp1['steps']}/{len(cp1['files'])}",
              (cp1["steps"], len(cp1["files"])) == (2, 2))
    ctx.check(f"turn 2 rewinds to turn 1's LAST step, got {cp2['rewind_to']!r}",
              cp2["rewind_to"] is not None)
    if cp2["rewind_to"]:
        last_t1 = next(s for s in store.steps if s.get("turn") == 1 and s["label"] == "Write(b)")
        ctx.check("and that step id is the real one", cp2["rewind_to"] == last_t1["id"])


@test
def test_rewind_to_turn_start_restores_previous_state(ctx: Ctx):
    tmp = Path(tempfile.mkdtemp(prefix="tc-restore-"))
    store = _store(tmp)
    a = _work(tmp, "a.txt", "v1")
    new_file = tmp / "made-in-t2.txt"
    # turn 1 edits a.txt to v2 (recorded); turn 2 edits it to v3 AND creates a file
    store.record_step({str(a): "v2"}, label="Edit(a) t1", turn=1)
    store.record_step({str(a): "v3"}, label="Edit(a) t2", turn=2)
    new_file.write_text("born in turn 2", encoding="utf-8")
    store.record_step({str(new_file): "born in turn 2"}, label="Write(new) t2", turn=2,
                       created=[str(new_file)])
    result = store.rewind_to_turn_start(2)
    ctx.check("the rewind produced a result", result is not None)
    ctx.check(f"a.txt is back to END-of-turn-1 content (v2), got {a.read_text(encoding='utf-8')!r}",
              a.read_text(encoding="utf-8") == "v2")
    ctx.check(f"the file CREATED in turn 2 is deleted, exists={new_file.exists()}",
              not new_file.exists())
    ctx.check(f"the result names the deleted file, got {result.get('deleted')}",
              str(new_file) in (result.get("deleted") or []))


@test
def test_rewind_first_turn_is_the_session_start(ctx: Ctx):
    tmp = Path(tempfile.mkdtemp(prefix="tc-start-"))
    store = _store(tmp)
    a = _work(tmp, "a.txt", "v1")           # pre-session content v1
    born = tmp / "born.txt"
    # turn 1 is the FIRST with steps: rewinding it = the session's start
    store.record_step({str(a): "v2"}, label="Edit(a) t1", turn=1)
    born.write_text("born in turn 1", encoding="utf-8")
    store.record_step({str(born): "born"}, label="Write(born) t1", turn=1, created=[str(born)])
    result = store.rewind_to_turn_start(1)
    ctx.check("the session-start rewind produced a result", result is not None)
    ctx.check(f"a.txt is back to its PRE-SESSION content (v1 -- nothing to restore, "
              f"but created-file deletion ran), got {a.read_text(encoding='utf-8')!r}",
              a.read_text(encoding="utf-8") == "v1")
    ctx.check(f"the turn-1 created file is deleted, exists={born.exists()}", not born.exists())
    ctx.check(f"the pseudo-step is named for the turn, got {(result or {}).get('step', {}).get('label')!r}",
              (result or {}).get("step", {}).get("label") == "start of turn 1")


@test
def test_unknown_turn_and_empty_store(ctx: Ctx):
    tmp = Path(tempfile.mkdtemp(prefix="tc-none-"))
    store = _store(tmp)
    ctx.check("an empty store has no checkpoints", store.turn_checkpoints() == [])
    ctx.check("rewinding any turn on an empty store is None", store.rewind_to_turn_start(1) is None)
    a = _work(tmp, "a.txt", "v1")
    store.record_step({str(a): "v2"}, label="Edit", turn=3)
    ctx.check(f"only turn 3 exists, got {[c['turn'] for c in store.turn_checkpoints()]}",
              [c["turn"] for c in store.turn_checkpoints()] == [3])
    ctx.check("rewinding a turn with no steps is None", store.rewind_to_turn_start(2) is None)


@test
def test_steps_carry_the_turn_for_the_dispatch_path(ctx: Ctx):
    """Structural pin: the dispatch threads the event's own turn into
    both shadow record paths (Write/Edit directly, Bash through its
    worker), so real sessions group into checkpoints."""
    src = (Path(__file__).resolve().parent.parent / "halo_harness" / "tui" / "dispatch.py") \
        .read_text(encoding="utf-8")
    ctx.check("the Write/Edit record passes turn",
              "created=created, turn=turn" in src)
    ctx.check("the Bash worker record passes turn",
              "created=created, turn=turn" in src.replace("created=created, turn=turn", "", 1)
              or src.count("turn=turn") >= 2)
    ctx.check("the tool_result call site passes the event's turn",
              "data.get(\"bash_shadow_before\"), turn=turn" in src)


if __name__ == "__main__":
    ctx = Ctx()
    results, passed, failed, skipped = run_all(TESTS, ctx)
    sys.exit(print_results(results, passed, failed, skipped))
