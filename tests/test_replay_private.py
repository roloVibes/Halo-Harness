"""tests.test_replay_private -- Halo 3.4.1.1 defect 56: a saved replay is safe to hand to someone else
(live/replay_private.py). Paths inside the project are stored project-relative, any other path under the home as
`~/...`, the user name and the machine name only in the owner's own text (the title) or a project-relative path; a
seeded home path, user name and key never reach the file, on Windows-style and POSIX paths; `halo audit privacy
--replays` knows the replay folder. Run: python -m tests.test_replay_private
"""
from __future__ import annotations

import contextlib
import io
import json
import os
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from tests.helpers.replay_seed import FAKE_KEY, SID, T0, seed  # noqa: E402
from tests.helpers.runner import Ctx, new_registry, print_results, run_all  # noqa: E402

test, TESTS = new_registry()
USER, MACHINE = "zedtester", "boxname7"
WIN_HOME, NIX_HOME = "C:\\Users\\" + USER, "/home/" + USER
ENV = {"USERPROFILE": WIN_HOME, "HOME": NIX_HOME, "USERNAME": USER, "USER": USER, "LOGNAME": USER,
       "COMPUTERNAME": MACHINE}


@contextlib.contextmanager
def _home():
    keys = ("BRIDGE_TEST_HOME", "BRIDGE_STATE_DIR") + tuple(ENV)
    saved = {k: os.environ.get(k) for k in keys}
    with tempfile.TemporaryDirectory(prefix="halo-private-") as d:
        os.environ["BRIDGE_TEST_HOME"] = d
        os.environ.pop("BRIDGE_STATE_DIR", None)
        os.environ.update(ENV)
        try:
            from halo_harness.config.paths import bridge_home
            yield bridge_home()
        finally:
            for k, v in saved.items():
                os.environ.pop(k, None) if v is None else os.environ.__setitem__(k, v)


@test
def test_windows_style_paths_and_names(ctx: Ctx):
    from halo_harness.live.replay_private import scrub
    root = WIN_HOME + "\\work\\trepo"
    got = scrub({"title": f"fix {USER}'s basket in {root}\\a.txt",
                 "agents": [{"agent_id": "main", "task": f"count lines of {root}\\a.txt and C:/Users/{USER}/work/trepo/sub/b.txt"}],
                 "marks": [{"text": f"Read /c/Users/{USER}/notes.md, /mnt/c/users/{USER.upper()}/x and c:\\\\users\\\\{USER}\\\\y.txt"},
                           {"text": f"ran on {USER}@{MACHINE}; cd {root}; {root}2\\z; \\\\?\\{root}\\q.py"},
                           {"text": f"{USER}/notes.txt stays (a path inside the project); D:\\data\\{USER}\\k"}]},
                root, homes=[WIN_HOME], users=[USER], machines=[MACHINE])
    a, m = got["agents"][0]["task"], [x["text"] for x in got["marks"]]
    ctx.check(f"project paths are relative, got {a!r}", a == "count lines of a.txt and sub/b.txt")
    ctx.check(f"other home paths are ~, any spelling, got {m[0]!r}", m[0] == "Read ~/notes.md, ~/x and ~/y.txt")
    ctx.check(f"names out, the project itself '.', a sibling folder is no project path, got {m[1]!r}",
              m[1] == "ran on <user>@<machine>; cd .; ~/work/trepo2/z; q.py")
    # 3.4.1.2 (SERVERS-6): only a path the root rule made project-relative keeps its words; a relative path the model
    # wrote may name anything (`..\\..\\Users\\<you>`), so the name goes there too
    ctx.check(f"a relative path the model wrote loses the name, as a path outside the home does, got {m[2]!r}",
              m[2] == "<user>/notes.txt stays (a path inside the project); D:\\data\\<user>\\k")
    kept = scrub({"t": f"{root}\\{USER}\\notes.txt"}, root, homes=[WIN_HOME], users=[USER], machines=[MACHINE])["t"]
    ctx.check(f"a project path the root rule made keeps its words, got {kept!r}", kept == f"{USER}/notes.txt")
    ctx.check(f"the title (the owner's own words) keeps the name, its path is relative, got {got['title']!r}",
              got["title"] == f"fix {USER}'s basket in a.txt")


@test
def test_posix_paths_and_names(ctx: Ctx):
    from halo_harness.live.replay_private import scrub
    root = NIX_HOME + "/proj"
    got = scrub({"marks": [{"text": f"{root}/b.txt, {root}, {root}2/c, {NIX_HOME}/.halo/x, {NIX_HOME}, /tmp/t/x, "
                                    f"{MACHINE}.lan said hi to {USER}"}], "id": f"{USER}-1"},
                root, homes=[NIX_HOME], users=[USER], machines=[MACHINE])
    ctx.check(f"relative, ~, untouched outside the home, names out, got {got['marks'][0]['text']!r}",
              got["marks"][0]["text"] == "b.txt, ., ~/proj2/c, ~/.halo/x, ~, /tmp/t/x, <machine>.lan said hi to <user>")
    ctx.check("an id is never rewritten (a file's own name)", got["id"] == f"{USER}-1")


@test
def test_a_seeded_home_path_user_name_and_key_never_reach_the_file(ctx: Ctx):
    from halo_harness.live import replay_file as RF
    with _home() as state:
        sub = seed(state).parent / SID / "subagents"
        proj = str(state.parent / "work" / "secret-project")  # the session's cwd (seed's meta)
        said = f"read {WIN_HOME}\\Documents\\plan.md and {NIX_HOME}/notes, as {USER} on {MACHINE} {FAKE_KEY}"
        task = f"count lines of {proj}{os.sep}a.txt; {said}"
        for name in ("agent-scout1.meta.json", "agent-scout1.jsonl"):  # the task: the meta's and the first user line
            rows = [json.loads(x) for x in (sub / name).read_text(encoding="utf-8").splitlines() if x.strip()]
            rows[0].update({"description": task} if name.endswith(".meta.json") else {"content": task})
            (sub / name).write_text("".join(json.dumps(r) + "\n" for r in rows), encoding="utf-8")
        p = RF.build(state, SID)
        p["marks"].append({"t": T0 + 72, "kind": "ask", "agent_id": "main", "name": "main", "text": said})  # after build
        from halo_harness.redact import sanitize_node
        path = RF.save(state, sanitize_node(p))
        raw = path.read_text(encoding="utf-8")
        for bad in (FAKE_KEY, USER, MACHINE, "Users\\\\" + USER, "/home/" + USER, proj, proj.replace("\\", "\\\\"),
                    str(state.parent).replace("\\", "\\\\"), "secret-project"):
            ctx.check(f"{bad[:40]!r} is not in the file", bad not in raw)
        back = json.loads(raw)
        task = next(a["task"] for a in back["agents"] if a["agent_id"] == "scout1")
        want = "read ~/Documents/plan.md and ~/notes, as <user> on <machine>"
        ctx.check(f"the task (the model's words) reads project-relative, ~ and no names, got {task!r}",
                  task.startswith("count lines of a.txt; " + want))
        ctx.check(f"a text added after build is rewritten at write time, got {back['marks'][-1]['text']!r}",
                  back["marks"][-1]["text"].startswith(want))
        back = RF.load(path)
        ctx.check("the file opens as before (format, version 1, no new key a reader needs)",
                  back["format"] == "halo-replay" and back["version"] == 1)
        ctx.check("the dialog's includes line says the limit",
                  any("relative to the project" in x and "where you typed it" in x for x in back["includes"]))


@test
def test_audit_privacy_knows_the_replay_folder(ctx: Ctx):
    from halo_harness.audit_cli import cmd_audit
    from halo_harness.live import replay_file as RF
    with _home() as state:
        seed(state)
        RF.save(state, RF.build(state, SID))
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            rc = cmd_audit(["privacy", "--replays", "--json"])
        got = json.loads(out.getvalue())
        ctx.check(f"a saved replay is clean, got {rc} {got['findings']}", rc == 0 and got["mode"] == "replays" and got["clean"])
        own = state / "replays" / "owner-words-20261112-000000.halo-replay"
        own.write_text(json.dumps({"format": "halo-replay", "version": 1, "id": "owner-words-20261112-000000",
                                   "title": f"{USER} asks on {MACHINE}", "marks": []}), encoding="utf-8")
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            rc = cmd_audit(["privacy", "--replays", "--json"])
        ctx.check(f"names in the title alone (the owner's own words) are no finding, got {rc} {out.getvalue()[-300:]!r}", rc == 0)
        raw = state / "replays" / "by-hand-20261112-000000.halo-replay"
        raw.write_text(json.dumps({"format": "halo-replay", "version": 1, "id": "by-hand-20261112-000000", "title": USER,
                                   "marks": [{"text": f"{NIX_HOME}/x by {USER} on {MACHINE}"}]}), encoding="utf-8")
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            rc = cmd_audit(["privacy", "--replays", "--json"])
        got = json.loads(out.getvalue())
        kinds = sorted({f["kind"] for f in got["findings"]})
        ctx.check(f"a file written by hand is caught: home path, user and machine name, got {rc} {kinds}",
                  rc == 1 and {"home-path", "user-name", "machine-name"} <= set(kinds))
        ctx.check("no excerpt holds a value", all(USER not in f["excerpt"] and MACHINE not in f["excerpt"]
                                                 for f in got["findings"]))


if __name__ == "__main__":
    ctx = Ctx()
    results, passed, failed, skipped = run_all(TESTS, ctx)
    sys.exit(print_results(results, passed, failed, skipped))
