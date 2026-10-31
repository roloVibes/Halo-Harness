"""tests.test_changes -- Halo 3.3.6.0 R5 deliverable 6, scopes and revert (ollama_steward/changes.py) in a scratch
home (no server, no model call):

1. a change under each scope (agent_proposals.land_user): `session` goes back when THAT session ends and no other,
   `until-restart` on the exit path, `keep` survives both; the revert line's words; nothing written when nothing is due;
2. the exit path: this process's until-restart rows, a halo that is gone (a dead pid), a home this process moved off
   is left alone; the loop's `_fire_session_end` runs the session revert;
3. the steward: an auto change is a row (until-restart, its journal id), its undo marks the row reverted, a revert of
   the row writes the journal's undo (the steward's in-place list drops it); the ledger's dialect refinement as a row;
4. stacked changes revert newest first; a field changed again is left as it is; a new scope; the CLI's
   `halo local changes` and `halo local revert`.
Run: python -m tests.test_changes
"""
from __future__ import annotations

import contextlib
import io
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from tests.helpers.runner import Ctx, new_registry, print_results, run_all  # noqa: E402
from tests.helpers.steward_seed import Home  # noqa: E402

test, TESTS = new_registry()
KEY = "pc|qwen3-coder:30b"


def _prof(key: str = KEY) -> dict:
    from halo_harness.ollama_steward.profiles import all_profiles
    return all_profiles().get(key) or {}


def _size(h) -> int:
    from halo_harness.ollama_steward import changes as C
    p = C.path(h.state)
    return p.stat().st_size if p.exists() else -1


@test
def test_a_change_under_each_scope(ctx: Ctx):
    from halo_harness.ollama_steward import changes as C
    from halo_harness.ollama_steward.agent_proposals import land_user
    from halo_harness.ollama_steward.profiles import set_field
    with Home() as h:
        set_field(KEY, "num_ctx", 32768, by="user")
        a = land_user(h.state, {"key": KEY, "field": "num_ctx", "to": 16384}, scope="session", session_id="s1",
                      why="the bench's trial")
        b = land_user(h.state, {"key": KEY, "field": "num_predict", "to": 512}, scope="until-restart")
        c = land_user(h.state, {"key": KEY, "field": "keep_alive", "to": "30m"})
        ctx.check(f"each landed with its scope's words, got {[a['line'], b['line'], c['line']]}",
                  a["line"] == "num_ctx 32,768 -> 16,384 on pc|qwen3-coder:30b (undone when the session ends)"
                  and b["line"].endswith("(undone when this halo exits)") and c["line"].endswith("(kept)"))
        ctx.check(f"a user's own defaults to keep, got {[r['scope'] for r in C.read(h.state)]}",
                  [r["scope"] for r in C.read(h.state)] == ["session", "until-restart", "keep"])
        no = land_user(h.state, {"key": KEY, "field": "num_ctx", "to": 8192}, scope="session")
        ctx.check(f"session with no session to end with says so, got {no}", not no["ok"] and "session" in no["line"])
        before = _size(h)
        ctx.check("another session's end: nothing due, nothing written", C.revert_scope(h.state, "session", "s2") == []
                  and _size(h) == before)
        said = C.revert_scope(h.state, "session", "s1")
        ctx.check(f"that session's end puts its change back and says so, got {said}",
                  said == ["put num_ctx back to 32,768 on pc|qwen3-coder:30b (the session ended)"]
                  and _prof()["num_ctx"] == 32768 and _prof()["num_predict"] == 512)
        said = C.revert_scope(h.state, "until-restart")
        ctx.check(f"the exit path: the until-restart change goes, got {said}",
                  said == ["took num_predict on pc|qwen3-coder:30b away: it had none before (this halo exited)"]
                  and "num_predict" not in _prof())
        before = _size(h)
        ctx.check("again: nothing due, nothing written", C.revert_scope(h.state, "until-restart") == [] and _size(h) == before)
        ctx.check(f"keep survives both, got {_prof()}", _prof().get("keep_alive") == "30m"
                  and [r["id"] for r in C.in_force(h.state)] == [c["id"]])
        ctx.check("a home with no changes file: nothing, nothing written",
                  C.revert_scope(h.state / "nowhere", "until-restart") == [] and not (h.state / "nowhere").exists())


@test
def test_the_exit_path_and_a_halo_that_is_gone(ctx: Ctx):
    from halo_harness.ollama_steward import changes as C
    from halo_harness.ollama_steward.profiles import set_field
    with Home() as h:
        set_field(KEY, "num_ctx", 65536, by="steward")
        C.record(h.state, by="steward", key=KEY, field="num_ctx", before=32768, after=65536, scope="until-restart",
                 why="a test")
        rows = C.read(h.state)
        C._append(h.state, {**rows[0], "id": "gone-1", "pid": 4194301, "field": "keep_alive", "before": None, "after": "1h"})
        set_field(KEY, "keep_alive", "1h", by="steward")
        said = C.at_exit()
        ctx.check(f"at exit: this process's change and the gone halo's, got {said}",
                  "put num_ctx back to 32,768 on pc|qwen3-coder:30b (this halo exited)" in said
                  and any("the halo that made it is gone" in s for s in said) and "keep_alive" not in _prof())
        with Home() as other:
            C.record(other.state, by="user", key=KEY, field="num_ctx", before=None, after=4096, scope="until-restart")
            set_field(KEY, "num_ctx", 4096, by="user")
            first = Path(other.state)
        ctx.check(f"a home this process moved off is left alone at exit, got {C.at_exit()}",
                  len(C.in_force(first)) == 1)
        from halo_harness.agent.loop import Session
        C.record(h.state, by="bench", key=KEY, field="num_predict", before=None, after=256, scope="session",
                 session_id="sess-9")
        set_field(KEY, "num_predict", 256, by="user")

        class _Log:
            session_id = "sess-9"
        fake = type("S", (), {"state_dir": h.state, "log": _Log(), "hook_runner": None})()
        Session._fire_session_end(fake, "quit")
        ctx.check(f"the loop's session end reverts that session's change, got {fake.session_end_reverts}",
                  fake.session_end_reverts and "num_predict" not in _prof())


@test
def test_the_steward_rows_and_their_undo(ctx: Ctx):
    from halo_harness.ollama_steward import changes as C
    from halo_harness.ollama_steward import steward
    with Home() as h:
        f = {"id": "w-1", "rule": "window-small", "key": KEY, "host": "pc", "model": "qwen3-coder:30b"}
        row = steward.apply_change(h.state, f, {"field": "num_ctx", "from": None, "to": 65536, "why": "a test"},
                                   mode_name="auto")
        ch = C.in_force(h.state)
        ctx.check(f"an auto change is a row: until-restart, its journal id, got {ch}",
                  len(ch) == 1 and ch[0]["scope"] == "until-restart" and ch[0]["journal_id"] == row["id"] and ch[0]["by"] == "steward")
        steward.undo_last(h.state)
        ctx.check("the steward's undo marks the row reverted", C.in_force(h.state) == [])
        steward.apply_change(h.state, {**f, "id": "w-2"}, {"field": "num_ctx", "from": None, "to": 49152, "why": "x"},
                             mode_name="review")
        ch = C.in_force(h.state)
        ctx.check(f"an Apply of a proposal keeps, got {[r['scope'] for r in ch]}", [r["scope"] for r in ch] == ["keep"])
        said = C.revert(h.state, ch[0]["id"], "reverted by hand")
        ctx.check(f"a revert of the row puts it back and the steward's list drops it, got {said}",
                  said[0].startswith("took num_ctx on pc|qwen3-coder:30b away") and steward._in_place(steward.read_journal(h.state)) == []
                  and "num_ctx" not in _prof())
        from halo_harness.providers import dialect as D
        D.set_fields("pc", "qwen3-coder:30b", {"reply_reserve": 2048}, by="ledger")
        C.record(h.state, by="ledger", key=KEY, field="dialect.reply_reserve", before=None, after=2048, scope="until-restart")
        said = C.revert_scope(h.state, "until-restart")
        ctx.check(f"a dialect refinement goes back too, got {said} {D.stored('pc', 'qwen3-coder:30b')}",
                  said and "reply_reserve" not in D.stored("pc", "qwen3-coder:30b"))


@test
def test_stacked_changed_again_a_new_scope_and_the_cli(ctx: Ctx):
    from halo_harness.local_bench_cli import cmd_changes, cmd_revert
    from halo_harness.ollama_steward import changes as C
    from halo_harness.ollama_steward.agent_proposals import land_user
    from halo_harness.ollama_steward.profiles import set_field
    with Home() as h:
        set_field(KEY, "num_ctx", 32768, by="user")
        land_user(h.state, {"key": KEY, "field": "num_ctx", "to": 16384})
        land_user(h.state, {"key": KEY, "field": "num_ctx", "to": 8192})
        said = C.revert(h.state, "all")
        ctx.check(f"stacked: newest first, back to the first value, got {said} {_prof()}", _prof()["num_ctx"] == 32768
                  and said[0].startswith("put num_ctx back to 16,384") and said[1].startswith("put num_ctx back to 32,768"))
        got = land_user(h.state, {"key": KEY, "field": "num_predict", "to": 1024})
        set_field(KEY, "num_predict", 2048, by="user")
        said = C.revert(h.state, got["id"])
        ctx.check(f"changed again since: left as it is and said, got {said}", said[0].startswith(
            "left num_predict on pc|qwen3-coder:30b as it is (2,048)") and _prof()["num_predict"] == 2048)
        got = land_user(h.state, {"key": KEY, "field": "tools_max", "to": 12})
        line = C.rescope(h.state, got["id"], "until-restart")
        ctx.check(f"a new scope, got {line!r}", line == "tools_max on pc|qwen3-coder:30b: undone when this halo exits"
                  and C.in_force(h.state)[0]["scope"] == "until-restart")
        ctx.check("session needs a session", C.rescope(h.state, got["id"], "session").startswith("session needs"))
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            cmd_changes([])
            cmd_revert(["--all"])
            cmd_changes([])
        text = out.getvalue()
        ctx.check(f"halo local changes lists it with its scope, revert --all says what went back, got {text!r}",
                  f"[{got['id']}] tools_max unset -> 12 on {KEY} (by user, until-restart" in text
                  and "took tools_max on pc|qwen3-coder:30b away: it had none before (reverted by hand)" in text
                  and text.strip().endswith("no change in force"))
        ctx.check("no pid of another process was recorded", all(r["pid"] == os.getpid() for r in C.read(h.state)))


@test
def test_a_settings_edit_is_a_change(ctx: Ctx):
    from halo_harness.ollama_steward import changes as C
    from halo_harness.studio.api import Request, dispatch
    with Home() as h:
        def api(path, body):
            return dispatch(Request(method="POST", path=path, query={}, body=body, cwd=h.root, state_dir=h.state, server=None))
        st, _a = api("settings/set", {"key": "ollama.profiles", "value": {KEY: {"num_ctx": 24576, "by": "user"}}})
        rows = C.in_force(h.state)
        ctx.check(f"Settings' edit of ollama.profiles is a row: by settings, keep, got {st} {rows}", st == 200 and len(rows) == 1
                  and rows[0]["by"] == "settings" and rows[0]["scope"] == "keep" and rows[0]["after"] == 24576)
        st, _a = api("settings/unset", {"key": "ollama.profiles"})
        ctx.check(f"its reset is one too, got {[r['after'] for r in C.in_force(h.state)]}", st == 200
                  and [r["after"] for r in C.in_force(h.state)] == [24576, None])


if __name__ == "__main__":
    ctx = Ctx()
    results, passed, failed, skipped = run_all(TESTS, ctx)
    sys.exit(print_results(results, passed, failed, skipped))
