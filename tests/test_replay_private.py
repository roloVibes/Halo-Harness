"""tests.test_replay_private -- Halo 3.4.1.1 defect 56: a saved replay is safe to hand to someone else
(live/replay_private.py). Paths inside the project are stored project-relative, any other path under the home as
`~/...`, the user name and the machine name only in the owner's own text (the title) or a project-relative path; a
seeded home path, user name and key never reach the file, on Windows-style and POSIX paths; `halo audit privacy
--replays` knows the replay folder. 3.6.0.3: the scrub's own tests moved with it to tests/test_privacy_scrub.py;
what is left here is the audit's and the saved file's (they leave with them). Run: python -m tests.test_replay_private
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
from tests.test_privacy_scrub import (MACHINE, NIX_HOME, USER, WIN_HOME, _home_shapes,  # noqa: E402
                                      _login_and_share_shapes, _machine_login_shapes)
ENV = {"USERPROFILE": WIN_HOME, "HOME": NIX_HOME, "USERNAME": USER, "USER": USER, "LOGNAME": USER,
       "COMPUTERNAME": MACHINE}


@contextlib.contextmanager
def _home(where=None):
    """A scratch home in `where` (the temp folder when None: under the real home, inside a repo, an 8.3 spelling)."""
    keys = ("BRIDGE_TEST_HOME", "BRIDGE_STATE_DIR") + tuple(ENV)
    saved = {k: os.environ.get(k) for k in keys}
    with tempfile.TemporaryDirectory(prefix="halo-private-", dir=where) as d:
        os.environ["BRIDGE_TEST_HOME"] = d
        os.environ.pop("BRIDGE_STATE_DIR", None)
        os.environ.update(ENV)
        try:
            from halo_harness.config.paths import bridge_home
            yield bridge_home()
        finally:
            for k, v in saved.items():
                os.environ.pop(k, None) if v is None else os.environ.__setitem__(k, v)


def _seeded(ctx: Ctx, where=None, label: str = "") -> None:
    from halo_harness.live import replay_file as RF
    with _home(where) as state:
        sub = seed(state).parent / SID / "subagents"
        proj = str(state.parent / "work" / "secret-project")  # the session's cwd (seed's meta)
        (Path(proj) / ".git").mkdir(parents=True, exist_ok=True)  # its own repo, wherever the scratch home lies (inside one, too)
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
        for bad in (FAKE_KEY, USER, USER[:6], MACHINE, "Users\\\\" + USER, "/home/" + USER, proj,
                    proj.replace("\\", "\\\\"), str(state.parent).replace("\\", "\\\\"), "secret-project"):
            ctx.check(f"{label}{bad[:40]!r} is not in the file", bad not in raw)
        back = json.loads(raw)
        task = next(a["task"] for a in back["agents"] if a["agent_id"] == "scout1")
        want = "count lines of a.txt; read ~/Documents/plan.md and ~/notes, as <user> on <machine>"
        # the task is an excerpt (200 characters of the model's words, live/history.py): how much of `want` it holds
        # depends on how long the scratch home's path was; it is `want` or a cut of it ending in "..."
        cut = task[:-3] if task.endswith("...") else None
        ctx.check(f"{label}the task (the model's words) reads project-relative, ~ and no names, got {task!r}",
                  task.startswith(want) or (cut is not None and (want.startswith(cut) or (
                      cut.endswith(("<user>", "<machine>")) and want.startswith(cut.rsplit(" ", 1)[0] + " ")))))
        ctx.check(f"{label}a text added after build is rewritten at write time, got {back['marks'][-1]['text']!r}",
                  back["marks"][-1]["text"].startswith(want.split("; ", 1)[1]))
        back = RF.load(path)
        ctx.check("the file opens as before (format, version 1, no new key a reader needs)",
                  back["format"] == "halo-replay" and back["version"] == 1)
        ctx.check("the dialog's includes line says the limit",
                  any("relative to the project" in x and "where you typed it" in x for x in back["includes"]))


@test
def test_a_seeded_home_path_user_name_and_key_never_reach_the_file(ctx: Ctx):
    _seeded(ctx)


@test
def test_the_scratch_home_inside_a_repo_and_under_an_8_3_spelling(ctx: Ctx):
    """3.4.1.2: the gate puts TEMP under the real home (and a run may put it inside the project): the redaction does not
    depend on where the scratch home lies, nor on a short (8.3) spelling of its folder."""
    inside = Path(__file__).resolve().parent.parent / ".prepush" / "replay-private-inside"
    inside.mkdir(parents=True, exist_ok=True)
    try:
        _seeded(ctx, str(inside), "inside the working tree: ")
    finally:
        import shutil
        shutil.rmtree(inside, ignore_errors=True)
    long_dir = Path(tempfile.mkdtemp(prefix="halo private long folder name "))
    short = str(long_dir)
    if os.name == "nt":
        import ctypes
        buf = ctypes.create_unicode_buffer(1024)
        if ctypes.windll.kernel32.GetShortPathNameW(str(long_dir), buf, 1024):
            short = buf.value
    _seeded(ctx, short, f"under {'an 8.3 spelling' if short != str(long_dir) else 'a long folder name'}: ")


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


@test
def test_audit_finds_a_common_word_account_in_every_home_shape(ctx: Ctx):
    """3.6.0.1 jf-words: `halo audit privacy --replays` shares the scrub's patterns, so the shapes the scrub missed
    were not findings either: an unscrubbed `${HOME:-/home/admin}` replay was called clean."""
    from halo_harness.live.replay_private import audit
    name = "admin"
    env = dict(ENV, USERNAME=name, USER=name, LOGNAME=name)
    saved = {k: os.environ.get(k) for k in env}
    try:
        with _home() as state:
            os.environ.update(env)
            folder = state / "replays"
            folder.mkdir(parents=True, exist_ok=True)
            texts = [t for t, _w in _home_shapes(name, "/" + "home/")] + [f"~{name}/notes"]
            for i, t in enumerate(texts):
                rid = f"raw{i}-20261116-000000"
                (folder / f"{rid}.halo-replay").write_text(json.dumps({
                    "format": "halo-replay", "version": 1, "id": rid, "title": "t", "marks": [{"text": t}]}),
                    encoding="utf-8")
            rows = [r for r in audit(state) if r["kind"] == "user-name"]
            found = {r["path"] for r in rows}
            for i, t in enumerate(texts):
                ctx.check(f"the audit finds the name in {t!r}, rows {sorted(found)}",
                          f"replays/raw{i}-20261116-000000.halo-replay" in found)
            ctx.check(f"no excerpt shows the name, got {[r['excerpt'] for r in rows]}",
                      all(name not in r["excerpt"].replace("<user>", "") for r in rows))
    finally:
        for k, v in saved.items():
            os.environ.pop(k, None) if v is None else os.environ.__setitem__(k, v)


@test
def test_audit_finds_no_leak_in_a_scrubbed_replay_of_a_common_word_account(ctx: Ctx):
    """3.6.0.1 setup-words: `halo audit privacy --replays` matched its own placeholder ('<user>' holds 'user') and the
    ordinary words a common-word account name shares; it uses the scrub's own name rules now."""
    from halo_harness.live.replay_private import audit, scrub
    for name in ("user", "admin"):
        env = dict(ENV, USERNAME=name, USER=name, LOGNAME=name)
        saved = {k: os.environ.get(k) for k in env}
        try:
            with _home() as state:
                os.environ.update(env)
                folder = state / "replays"
                folder.mkdir(parents=True, exist_ok=True)
                clean = scrub({"marks": [{"text": f"the {name} panel; the user asked; /home/{name}/x"}]}, None,
                              homes=[], users=[name], machines=[])
                (folder / "clean-20261116-000000.halo-replay").write_text(json.dumps(dict(
                    clean, format="halo-replay", version=1, id="clean-20261116-000000", title="t")), encoding="utf-8")
                rows = [r for r in audit(state) if r["kind"] == "user-name"]
                ctx.check(f"[{name}] a scrubbed replay holds no user name, got {rows}", not rows)
                (folder / "raw-20261116-000000.halo-replay").write_text(json.dumps({
                    "format": "halo-replay", "version": 1, "id": "raw-20261116-000000", "title": "t",
                    "marks": [{"text": f"/home/{name}/x"}]}), encoding="utf-8")
                rows = [r for r in audit(state) if r["kind"] in ("user-name", "home-path")]
                ctx.check(f"[{name}] an unscrubbed home path still is a finding, got {rows}", len(rows) >= 1)
        finally:
            for k, v in saved.items():
                os.environ.pop(k, None) if v is None else os.environ.__setitem__(k, v)


@test
def test_audit_finds_a_common_word_account_in_a_login_or_a_share(ctx: Ctx):
    """3.6.0.1 jf-words batch 2: the audit shares the scrub's patterns; an unscrubbed `admin@gpu-box:~$` or
    `\\\\gpu-box\\admin\\share` replay was called clean, and a scrubbed one must stay clean."""
    from halo_harness.live.replay_private import audit, scrub
    name = "admin"
    env = dict(ENV, USERNAME=name, USER=name, LOGNAME=name)
    saved = {k: os.environ.get(k) for k in env}
    try:
        with _home() as state:
            os.environ.update(env)
            folder = state / "replays"
            folder.mkdir(parents=True, exist_ok=True)
            texts = [t for t, _w in _login_and_share_shapes(name)]
            for i, t in enumerate(texts):
                rid = f"raw{i}-20261116-000000"
                (folder / f"{rid}.halo-replay").write_text(json.dumps({
                    "format": "halo-replay", "version": 1, "id": rid, "title": "t", "marks": [{"text": t}]}),
                    encoding="utf-8")
            rows = [r for r in audit(state) if r["kind"] == "user-name"]
            found = {r["path"] for r in rows}
            for i, t in enumerate(texts):
                ctx.check(f"the audit finds the name in {t!r}, rows {sorted(found)}",
                          f"replays/raw{i}-20261116-000000.halo-replay" in found)
            ctx.check(f"no excerpt shows the name, got {[r['excerpt'] for r in rows]}",
                      all(name not in r["excerpt"].replace("<user>", "") for r in rows))
            for p in folder.glob("raw*"):
                p.unlink()
            clean = scrub({"marks": [{"text": t} for t in texts]}, None, homes=[], users=[name], machines=["gpu-box"])
            (folder / "clean-20261116-000000.halo-replay").write_text(json.dumps(dict(
                clean, format="halo-replay", version=1, id="clean-20261116-000000", title="t")), encoding="utf-8")
            rows = [r for r in audit(state) if r["kind"] == "user-name"]
            ctx.check(f"a scrubbed replay of these shapes holds no user name, got {rows}", not rows)
    finally:
        for k, v in saved.items():
            os.environ.pop(k, None) if v is None else os.environ.__setitem__(k, v)


@test
def test_audit_finds_a_common_word_account_in_a_windows_machine_login(ctx: Ctx):
    """3.6.0.1 jf-words batch 3: the audit shares the scrub's patterns, so an unscrubbed `gpu-box\\admin` replay was
    called clean; a scrubbed one stays clean."""
    from halo_harness.live.replay_private import audit, scrub
    name = "admin"
    env = dict(ENV, USERNAME=name, USER=name, LOGNAME=name, COMPUTERNAME="gpu-box")
    saved = {k: os.environ.get(k) for k in env}
    try:
        with _home() as state:
            os.environ.update(env)
            folder = state / "replays"
            folder.mkdir(parents=True, exist_ok=True)
            texts = [t for t, _w in _machine_login_shapes(name)]
            for i, t in enumerate(texts):
                rid = f"raw{i}-20261116-000000"
                (folder / f"{rid}.halo-replay").write_text(json.dumps({
                    "format": "halo-replay", "version": 1, "id": rid, "title": "t", "marks": [{"text": t}]}),
                    encoding="utf-8")
            rows = [r for r in audit(state) if r["kind"] == "user-name"]
            found = {r["path"] for r in rows}
            for i, t in enumerate(texts):
                ctx.check(f"the audit finds the name in {t!r}, rows {sorted(found)}",
                          f"replays/raw{i}-20261116-000000.halo-replay" in found)
            ctx.check(f"no excerpt shows the name, got {[r['excerpt'] for r in rows]}",
                      all(name not in r["excerpt"].replace("<user>", "") for r in rows))
            for p in folder.glob("raw*"):
                p.unlink()
            clean = scrub({"marks": [{"text": t} for t in texts]}, None, homes=[], users=[name], machines=["gpu-box"])
            (folder / "clean-20261116-000000.halo-replay").write_text(json.dumps(dict(
                clean, format="halo-replay", version=1, id="clean-20261116-000000", title="t")), encoding="utf-8")
            rows = [r for r in audit(state) if r["kind"] == "user-name"]
            ctx.check(f"a scrubbed replay of these shapes holds no user name, got {rows}", not rows)
    finally:
        for k, v in saved.items():
            os.environ.pop(k, None) if v is None else os.environ.__setitem__(k, v)


if __name__ == "__main__":
    ctx = Ctx()
    results, passed, failed, skipped = run_all(TESTS, ctx)
    sys.exit(print_results(results, passed, failed, skipped))
