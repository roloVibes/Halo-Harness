"""tests.test_builder_outcome_frame -- Halo 3.6.0.2 R25: when a Builder card is answered, Studio gets ONE `builder_done`
frame AFTER the files are written: `{id, outcome: applied|left|failed, wrote: [{kind, name, added}], undo, next,
this_session, maps, t}` (crew/map_events.py `builder_done`, sent in a `finally` around crew/session_tool.py `finish` in
agent/loop.py's Builder branch). `map_card {done}` is still sent. The session's log keeps the same receipt without the
map bodies; a map over 64 KB is left out of `maps` (the page fetches it). The kind is in both kind lists.

A real interactive Session against the mock upstream; the model calls Builder once. Nothing calls a real model.
Run: python -m tests.test_builder_outcome_frame
"""
from __future__ import annotations

import json
import os
import shutil
import tempfile
import threading
import time
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from tests.helpers.crew_map_script import reviewer_calls  # noqa: E402
from tests.helpers.runner import Ctx, new_registry, print_results, run_all  # noqa: E402
from tests.test_builder_session_parity import _session, approve_all  # noqa: E402

test, TESTS = new_registry()
ROOT = Path(__file__).resolve().parent.parent
WORKFLOW_CALL = [{"tool": "workflow_make", "args": {"name": "review", "for": "review a change",
                                                    "steps": [{"name": "look", "agents": ["reviewer"]},
                                                              {"name": "fix", "agents": ["coder"]}]}}]


def _run(answer_fn, calls=None, *, before=None, inspect=None) -> dict:
    """A real Session whose model calls Builder once; `answer_fn(questions)` answers the card (None: dismiss).
    `before(state)` runs once the scratch home is set; `inspect(session, state)` before it is removed. Returns
    {frames: [(kind, data, reviewer file on disk then)], result, receipts, this_session, inspect, error}."""
    from tests.helpers.mock_openai import SCENARIOS, MockUpstream, ScriptedTurns
    from tests.helpers.session_rig import text_step, tool_step
    saved = {k: os.environ.get(k) for k in ("BRIDGE_TEST_HOME", "BRIDGE_OPENROUTER_BASE_URL", "BRIDGE_STATE_DIR")}
    home = Path(tempfile.mkdtemp(prefix="builder-done-"))
    os.environ.pop("BRIDGE_STATE_DIR", None)
    os.environ["BRIDGE_TEST_HOME"] = str(home)
    mock = MockUpstream().start()
    os.environ["BRIDGE_OPENROUTER_BASE_URL"] = mock.base_url
    SCENARIOS["builder-session"] = ScriptedTurns([tool_step(("Builder", {"changes": calls or reviewer_calls()}, "call_b")),
                                                  text_step("Done.")])
    out: dict = {"frames": [], "error": None}
    try:
        from halo_harness.agent.agent_registry import tree_for
        from halo_harness.providers.config import default_state_dir
        state = Path(default_state_dir())
        if before:
            before(state)
        s = _session(home, mock)
        reviewer = state / "crew" / "agents" / "my-reviewer.yaml"
        tree_for(s).add_listener(lambda kind, aid, data: out["frames"].append(
            (kind, json.loads(json.dumps(data, default=str)), reviewer.is_file()))
            if kind in ("builder_done", "map_card") else None)
        events: list = []
        done = threading.Event()

        def drive():
            try:
                events.extend(s.turn("make me a reviewer agent and hand reviews to it"))
            except Exception as e:  # the raising write: the turn ends with the error, as today
                out["error"] = e
            finally:
                done.set()
        threading.Thread(target=drive, daemon=True).start()
        end = time.monotonic() + 20
        while time.monotonic() < end and not done.is_set() and not any(e.kind == "question" for e in list(events)):
            time.sleep(0.02)
        q = next((e for e in list(events) if e.kind == "question"), None)
        if q is not None:
            out["question_id"] = q.data["id"]
            s.resolve_question(q.data["id"], answer_fn((q.data.get("input") or {}).get("questions") or []))
        out["ended"] = done.wait(20)
        out["result"] = str(next((n.get("content") for n in s.log.nodes() if n.get("type") == "tool_result"), ""))
        out["receipts"] = [n for n in s.log.nodes() if n.get("type") == "receipt" and n.get("event") == "builder_done"]
        tc = getattr(s, "team_control", None)
        out["this_session"] = getattr(tc, "map_name", None) if getattr(tc, "is_map", False) else None
        out["built"] = getattr(s, "_builder_built", None)
        out["inspect"] = inspect(s, state) if inspect else None
        return out
    finally:
        mock.stop()
        SCENARIOS.pop("builder-session", None)
        for k, v in saved.items():
            os.environ.pop(k, None) if v is None else os.environ.__setitem__(k, v)
        shutil.rmtree(home, ignore_errors=True)


def _done(out) -> list:
    return [(d, disk) for k, d, disk in out["frames"] if k == "builder_done"]


@test
def test_done_after_the_write_with_files_and_undo(ctx: Ctx):
    out = _run(approve_all)
    got = _done(out)
    ctx.check(f"exactly one builder_done frame, got {len(got)} (frames {[(k, d.get('done')) for k, d, _ in out['frames']]})",
              len(got) == 1)
    if not got:
        return
    d, on_disk = got[0]
    ctx.check(f"its id is the card's question id, got {d.get('id')!r} vs {out.get('question_id')!r}",
              d.get("id") == out.get("question_id"))
    ctx.check(f"outcome applied, got {d.get('outcome')!r}", d.get("outcome") == "applied")
    wrote = d.get("wrote") or []
    ctx.check(f"wrote names the new agent, got {wrote}", {"kind": "agent", "name": "my-reviewer", "added": True} in wrote)
    ctx.check(f"wrote names the map starter, got {wrote}",
              any(w.get("kind") == "map" and w.get("name") == "starter" and isinstance(w.get("added"), bool) for w in wrote))
    undo = out["result"].split("Undo id ", 1)[-1].split(" ", 1)[0] if "Undo id " in out["result"] else ""
    ctx.check(f"undo is the id the tool result names, got {d.get('undo')!r} vs {undo!r}", bool(undo) and d.get("undo") == undo)
    ctx.check(f"next is config crew.map (unset: None), got {d.get('next')!r}", "next" in d and d["next"] is None)
    ctx.check(f"this_session is the session's map, got {d.get('this_session')!r} vs {out['this_session']!r}",
              "this_session" in d and d["this_session"] == out["this_session"])
    ctx.check("the files were on disk when the frame was sent", on_disk is True)
    ctx.check("map_card {done} is still sent, before builder_done",
              [k for k, dd, _ in out["frames"] if k == "builder_done" or dd.get("done")] == ["map_card", "builder_done"])
    ctx.check(f"the session keeps the last outcome without bodies, got {out['built']}",
              isinstance(out["built"], dict) and out["built"].get("outcome") == "applied" and "maps" not in out["built"])
    ctx.check(f"the tool result text is unchanged, got {out['result'][:120]!r}", "Applied 5 line(s)" in out["result"])


@test
def test_left_card_frames_left(ctx: Ctx):
    for label, fn in (("Leave them", lambda qs: {qs[0]["question"]: "Leave them"}), ("dismissed", lambda qs: None)):
        out = _run(fn)
        got = _done(out)
        ctx.check(f"{label}: one builder_done, got {len(got)}", len(got) == 1)
        if got:
            d = got[0][0]
            ctx.check(f"{label}: outcome left, nothing written, no undo, got {d}",
                      d.get("outcome") == "left" and d.get("wrote") == [] and d.get("undo") is None and d.get("maps") == {})
        ctx.check(f"{label}: nothing was written, got {out['result'][-80:]!r}", "nothing was written" in out["result"])


@test
def test_failed_write_still_frames_failed(ctx: Ctx):
    from halo_harness.crew import changes
    real = changes.apply

    def raising(*a, **k):
        raise OSError("disk gone")

    def refusing(*a, **k):
        return {"ok": False, "undo_id": "", "wrote": [], "removed": [], "skipped": [], "problems": ["disk full"], "filled": []}
    for label, fake in (("raises", raising), ("refuses", refusing)):
        changes.apply = fake
        try:
            out = _run(approve_all)
        finally:
            changes.apply = real
        got = _done(out)
        ctx.check(f"{label}: one builder_done, got {len(got)}", len(got) == 1)
        if got:
            d = got[0][0]
            ctx.check(f"{label}: outcome failed, nothing written, got {d}",
                      d.get("outcome") == "failed" and d.get("wrote") == [] and d.get("undo") is None)
        ctx.check(f"{label}: the turn ended", out.get("ended") is True)
        if label == "raises":
            ctx.check(f"raises: the error still reaches the turn, got {out['error']!r}", isinstance(out["error"], OSError))
        else:
            ctx.check(f"refuses: the result says so, got {out['result'][-60:]!r}", "Nothing was written: disk full" in out["result"])


@test
def test_workflow_only_card_frames(ctx: Ctx):
    def before(state):
        from halo_harness.crew.changes_map import config_text, write_config
        write_config(config_text("ship-it"))
    out = _run(approve_all, WORKFLOW_CALL, before=before)
    ctx.check(f"no map_card ghosts for a card with no map row (only its `done`, as today), got {out['frames']}",
              not any(k == "map_card" and not d.get("done") for k, d, _ in out["frames"]))
    got = _done(out)
    ctx.check(f"one builder_done, got {len(got)}", len(got) == 1)
    if got:
        d = got[0][0]
        ctx.check(f"applied, the workflow added, no maps, got {d}",
                  d.get("outcome") == "applied" and d.get("wrote") == [{"kind": "workflow", "name": "review", "added": True}]
                  and d.get("maps") == {})
        ctx.check(f"next is config crew.map, got {d.get('next')!r}", d.get("next") == "ship-it")


@test
def test_frame_carries_bodies_receipt_does_not(ctx: Ctx):
    def inspect(s, state):
        from halo_harness.crew import store
        return store.clean(store.load("map", "starter", scope="yours") or {})
    out = _run(approve_all, inspect=inspect)
    got = _done(out)
    ctx.check(f"one builder_done, got {len(got)}", len(got) == 1)
    if got:
        d = got[0][0]
        ctx.check(f"maps['starter'] is the map as written, got keys {sorted((d.get('maps') or {}))}",
                  bool(out["inspect"]) and (d.get("maps") or {}).get("starter") == out["inspect"])
        rec = out["receipts"]
        ctx.check(f"exactly one builder_done receipt in the log, got {len(rec)}", len(rec) == 1)
        if rec:
            data = rec[0].get("data") or {}
            ctx.check(f"the receipt is the frame minus maps, got keys {sorted(data)}",
                      sorted(data) == sorted(k for k in d if k != "maps") and "maps" not in data
                      and all(data[k] == d[k] for k in data))
    # a map over 64 KB is left out of `maps`; the frame is still sent
    from tests.helpers.workflow_fakes import FakeSession
    from halo_harness.agent.agent_registry import tree_for
    from halo_harness.crew import map_events, store
    saved = os.environ.get("BRIDGE_TEST_HOME")
    home = Path(tempfile.mkdtemp(prefix="builder-big-"))
    os.environ["BRIDGE_TEST_HOME"] = str(home)
    try:
        small = {"format": "map/1", "name": "small", "main": {"agent": "main"}, "boxes": [], "lines": []}
        big = dict(small, name="big", does="x" * 70000)
        for body in (small, big):
            p = store.path_for("map", body["name"])
            p.parent.mkdir(parents=True, exist_ok=True)
            store.write_text(p, store.dump(body))
        s = FakeSession(home, "or:vendor/text-only")
        from types import SimpleNamespace
        s.team_control = SimpleNamespace(is_map=True, map_name="small")
        seen: list = []
        tree_for(s).add_listener(lambda kind, aid, data: seen.append(data) if kind == "builder_done" else None)
        map_events.builder_done(s, "q1", {"outcome": "applied", "undo": "u1",
                                          "wrote": [{"kind": "map", "name": "big", "added": True},
                                                    {"kind": "map", "name": "small", "added": True}]})
        ctx.check(f"the big map's frame is still sent, got {len(seen)}", len(seen) == 1)
        if seen:
            ctx.check(f"over 64 KB: no body (the page fetches it); the small one has its body, got {sorted(seen[0].get('maps') or {})}",
                      sorted(seen[0].get("maps") or {}) == ["small"] and [w["name"] for w in seen[0]["wrote"]] == ["big", "small"])
            ctx.check(f"this_session is the session's map control's map, got {seen[0].get('this_session')!r}",
                      seen[0].get("this_session") == "small")
        rec = [n for n in s.log.receipts() if n.get("event") == "builder_done"]
        ctx.check(f"its receipt has no bodies, got {[sorted(n.get('data') or {}) for n in rec]}",
                  len(rec) == 1 and "maps" not in rec[0]["data"])
    finally:
        os.environ.pop("BRIDGE_TEST_HOME", None) if saved is None else os.environ.__setitem__("BRIDGE_TEST_HOME", saved)
        shutil.rmtree(home, ignore_errors=True)


@test
def test_undo_card_outcomes(ctx: Ctx):
    """An undo card is a Builder card too: left when not confirmed, failed when there is nothing to undo."""
    from halo_harness.crew.session_tool import finish
    pv = {"undo": "20990101-000000-abcdef", "rows": [], "text": ""}
    finish(pv, {"Undo it?": "No"}, None)
    ctx.check(f"not confirmed: left, got {pv.get('outcome')}", (pv.get("outcome") or {}).get("outcome") == "left")
    saved = os.environ.get("BRIDGE_TEST_HOME")
    home = Path(tempfile.mkdtemp(prefix="builder-undo-"))
    os.environ["BRIDGE_TEST_HOME"] = str(home)
    try:
        pv = {"undo": "20990101-000000-abcdef", "rows": [], "text": ""}
        finish(pv, {"Undo it?": "Yes"}, None)
        ctx.check(f"no such change: failed, got {pv.get('outcome')}", (pv.get("outcome") or {}).get("outcome") == "failed")
    finally:
        os.environ.pop("BRIDGE_TEST_HOME", None) if saved is None else os.environ.__setitem__("BRIDGE_TEST_HOME", saved)
        shutil.rmtree(home, ignore_errors=True)


@test
def test_change_and_applied_undo_say_what_each_file_was(ctx: Ctx):
    """R25 (P2 batch 8): `added` is true only for a file that was not there before the card's write. A card that changes
    your existing map says added:false for it (and added:true for the agent it makes); an applied Undo of that card says
    added:false for the map it puts back and added:false, removed:true for the agent file it takes away."""
    from halo_harness.crew import store
    from halo_harness.crew.session_tool import finish

    def before(state):  # yours `starter` already there: the card's box and line CHANGE it
        mine = state / "crew" / "maps" / "starter.yaml"
        mine.parent.mkdir(parents=True, exist_ok=True)
        mine.write_bytes((store.SHIPPED / "maps" / "starter.yaml").read_bytes())

    def inspect(s, state):
        text = str(next((n.get("content") for n in s.log.nodes() if n.get("type") == "tool_result"), ""))
        undo = text.split("Undo id ", 1)[-1].split(" ", 1)[0] if "Undo id " in text else ""
        pv = {"undo": undo, "rows": [], "text": ""}
        said = finish(pv, {"Undo it?": "Yes"}, s)
        return {"undo": undo, "outcome": pv.get("outcome"), "said": said,
                "agent_gone": not (state / "crew" / "agents" / "my-reviewer.yaml").is_file()}
    out = _run(approve_all, before=before, inspect=inspect)
    got = _done(out)
    ctx.check(f"one builder_done for the card, got {len(got)}", len(got) == 1)
    wrote = (got[0][0].get("wrote") or []) if got else []
    ctx.check(f"the card: your map starter changed (added false), the agent new (added true), got {wrote}",
              {"kind": "map", "name": "starter", "added": False} in wrote
              and {"kind": "agent", "name": "my-reviewer", "added": True} in wrote)
    u = out["inspect"] or {}
    o = u.get("outcome") or {}
    ctx.check(f"the undo was applied and took the agent away, got {o} {u.get('said')!r}",
              o.get("outcome") == "applied" and u.get("agent_gone") is True)
    ctx.check(f"the undo: the map put back (added false, not removed), got {o.get('wrote')}",
              {"kind": "map", "name": "starter", "added": False} in (o.get("wrote") or []))
    ctx.check(f"the undo: the agent removed (added false, removed true), got {o.get('wrote')}",
              {"kind": "agent", "name": "my-reviewer", "added": False, "removed": True} in (o.get("wrote") or []))
    ctx.check(f"nothing in an undo is marked added, got {o.get('wrote')}",
              bool(o.get("wrote")) and not any(w.get("added") for w in o.get("wrote") or []))


@test
def test_builder_done_in_both_kind_lists(ctx: Ctx):
    from halo_harness.studio.feed_kinds import DEFAULT_KINDS
    ctx.check("Studio asks every session for builder_done frames", "builder_done" in DEFAULT_KINDS)
    known = (ROOT / "halo_harness" / "studio" / "ui" / "src" / "lib" / "events.ts").read_text(encoding="utf-8")
    block = known.split("export const KNOWN_KINDS = [", 1)[-1].split("]", 1)[0]
    ctx.check("the UI binds builder_done (inside KNOWN_KINDS)", '"builder_done"' in block)


if __name__ == "__main__":
    ctx = Ctx()
    results, passed, failed, skipped = run_all(TESTS, ctx)
    sys.exit(print_results(results, passed, failed, skipped))
