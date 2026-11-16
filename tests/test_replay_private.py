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
def test_an_excerpt_cut_inside_a_name(ctx: Ctx):
    from halo_harness.live.replay_private import scrub
    got = scrub({"t": f"as {USER[:7]}...", "u": f"on {MACHINE[:4]}...", "v": "the..."}, None, homes=[WIN_HOME],
                users=[USER], machines=[MACHINE])
    ctx.check(f"a name cut by the excerpt is still the name, got {got}",
              got == {"t": "as <user>...", "u": "on <machine>...", "v": "the..."})


@test
def test_an_excerpt_cut_inside_a_path(ctx: Ctx):
    """3.4.1.3: the 200-character cut can land inside a home or project path; the stub left is rewritten too."""
    from halo_harness.live.replay_private import scrub
    root = WIN_HOME + chr(92) + "work" + chr(92) + "secret-project"
    got = scrub({"a": f"read {NIX_HOME[:2]}...", "b": f"open {WIN_HOME[:7]}...", "c": f'see "{WIN_HOME[:-3]}...',
                 "d": f"in {root[:-4]}...", "e": "ratio 3/4...", "f": "/tmp/x..."}, root, homes=[WIN_HOME, NIX_HOME],
                users=[USER], machines=[MACHINE])
    ctx.check(f"a path cut by the excerpt is ~ or ., got {got}",
              got == {"a": "read ~...", "b": "open ~...", "c": 'see "~...', "d": "in ....", "e": "ratio 3/4...",
                      "f": "/tmp/x..."})


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


PROSE = ("the user asked for a list; open the admin panel; run the test suite; tests/test_a.py passed; go home; "
         "Ubuntu 24.04 is the CI image on ubuntu-latest; the test runner failed twice, as runners do; /usr/local/bin")


@test
def test_a_common_word_account_name_is_scrubbed_only_as_a_name(ctx: Ctx):
    """3.6.0.1 setup-words: with an account called `user`, `admin`, `test`, `home`, `ubuntu` or `runner` the scrub
    rewrote ordinary words ('the <user> asked', 'tests/<user>_a.py', '<user>-latest') and JSON keys. A common word is
    the name only where it stands as a home folder's segment; an uncommon name is replaced as a whole word anywhere
    (a digit, '_', '.', '@' or a quote beside it is a boundary; a letter is not)."""
    from halo_harness.live.replay_private import scrub
    bs = chr(92)
    for name in ("user", "admin", "test", "home", "ubuntu", "runner"):
        got = scrub({"t": PROSE, "k": {name: 1, "role": "user"}}, None, homes=[], users=[name], machines=[])
        ctx.check(f"[{name}] the prose is kept exactly, got {got['t']!r}", got["t"] == PROSE)
        ctx.check(f"[{name}] the dict keys and the role value are kept, got {got['k']!r}",
                  got["k"] == {name: 1, "role": "user"})
        for shape in ("/home/{n}/x", "/Users/{n}/x", "C:{b}Users{b}{n}{b}x", "C:/Users/{n}/x",
                      "c:{b}{b}users{b}{b}{n}{b}{b}x", "/mnt/c/Users/{n}/x", "/c/Users/{n}", "{b}{b}?{b}C:{b}Users{b}{n}"):
            path, want = shape.format(n=name, b=bs), "see " + shape.format(n="<user>", b=bs)
            out = scrub({"t": f"see {path}"}, None, homes=[], users=[name], machines=[])["t"]
            ctx.check(f"[{name}] the name as a home segment goes: {path!r} -> {want!r}, got {out!r}", out == want)
    word = "zedtester"
    for text, want in (("zedtester@box", "<user>@box"), ("zedtester_notes", "<user>_notes"), ("see zedtester.", "see <user>."),
                       ("1zedtester", "1<user>"), ("zedtester2", "<user>2"), ("zedtesterx", "zedtesterx"),
                       ("xzedtester", "xzedtester"), ("zedtesters", "zedtesters"), ('{"by": "zedtester"}', '{"by": "<user>"}')):
        out = scrub({"t": text}, None, homes=[], users=[word], machines=[])["t"]
        ctx.check(f"[{word}] {text!r} -> {want!r}, got {out!r}", out == want)
    out = scrub({"t": "open the admin..."}, None, homes=[], users=["administrator"], machines=[])["t"]
    ctx.check(f"a cut excerpt that begins a common name is kept, got {out!r}", out == "open the admin...")
    out = scrub({"t": "served on localhost and the desktop app"}, None, homes=[], users=[], machines=["localhost", "desktop"])["t"]
    ctx.check(f"a common machine name is no machine name in prose, got {out!r}", out == "served on localhost and the desktop app")


@test
def test_a_home_path_before_closing_punctuation_is_scrubbed(ctx: Ctx):
    """3.6.0.1 setup-words batch 2: the home-folder rule ended a name only at a slash, a quote, whitespace or the end,
    so '/home/user.' at the end of a sentence and '/home/user:' in a PATH-like list kept a common-word account name.
    Punctuation no account name can hold ends it; a '.', '-' or ')' that runs on into more name does not."""
    from halo_harness.live.replay_private import scrub
    bs = chr(92)
    for name in ("user", "zedtester"):
        def run(text):
            return scrub({"t": text}, None, homes=[], users=[name], machines=[])["t"]
        line = f"see /home/{name}, then /home/{name}. and (/home/{name}) and /home/{name}: and /home/{name}/x"
        want = "see /home/<user>, then /home/<user>. and (/home/<user>) and /home/<user>: and /home/<user>/x"
        ctx.check(f"[{name}] every home path in the line goes, got {run(line)!r}", run(line) == want)
        for tail in (".", ":", ";", ",", ")", "]", ">", "...", ".)", ":/usr/bin", ";C:" + bs + "x", "'", "|"):
            for lead in ("/home/", "/Users/", f"C:{bs}Users{bs}", "C:/Users/"):
                text = f"at {lead}{name}{tail}"
                ctx.check(f"[{name}] {text!r} -> the name goes, got {run(text)!r}",
                          run(text) == f"at {lead}<user>{tail}")
    home = "/" + "home" + "/"  # built from parts: the repo's privacy scan reads a longer made-up name as a real home path
    for text in (f"{home}user.name/x", f"{home}username", f"{home}user-2", f"{home}user_x", f"C:{bs}Users{bs}user.name{bs}x",
                 f"{home}user.2/x"):
        out = scrub({"t": text}, None, homes=[], users=["user"], machines=[])["t"]
        ctx.check(f"another, longer account name is not 'user': {text!r} kept, got {out!r}", out == text)


def _home_shapes(name: str, lead: str) -> list:
    """jf-words: (text, the scrubbed text) for the home-folder shapes 3.6.0.0 scrubbed for any account name."""
    return [(f"${{HOME:-{lead}{name}}}", f"${{HOME:-{lead}<user>}}"), (f"{lead}{name}#frag", f"{lead}<user>#frag"),
            (f"?p={lead}{name}&x=1", f"?p={lead}<user>&x=1"), (f"{lead}{name}!", f"{lead}<user>!"),
            (f"{lead}{name}~", f"{lead}<user>~"), (f"{lead}{name}{{x}}", f"{lead}<user>{{x}}"),
            (f"{lead}{name}@x", f"{lead}<user>@x"), (f"{lead}{name}$", f"{lead}<user>$")]


@test
def test_a_common_word_account_never_keeps_a_home_folder_3600_scrubbed(ctx: Ctx):
    """3.6.0.1 jf-words: the home-folder rule ended a name only at a closed list of characters and knew no `~name`, so
    a common-word account (admin, dev, build, user) kept its name in `${HOME:-/home/admin}`, `/home/admin#frag`,
    `?p=/home/admin&x=1`, `/home/admin!`, `/home/admin~`, `/home/admin{x}` and `~admin/notes`: 3.6.0.0 removed
    them all. The name now ends at anything that is not more name, and `~name` is a home folder too."""
    from halo_harness.live.replay_private import scrub
    bs = chr(92)
    for name in ("admin", "dev", "build", "user", "zedtester"):
        def run(text):
            return scrub({"t": text}, None, homes=[], users=[name], machines=[])["t"]
        for lead in ("/" + "home/", "/" + "Users/", f"C:{bs}Users{bs}", "C:/Users/"):
            for text, want in _home_shapes(name, lead):
                ctx.check(f"[{name}] {text!r} -> {want!r}, got {run(text)!r}", run(text) == want)
        for text, want in ((f"~{name}/notes", "~<user>/notes"), (f"~{name}", "~<user>"),
                           (f"cd ~{name} && ls", "cd ~<user> && ls"), (f"(~{name}/x)", "(~<user>/x)")):
            ctx.check(f"[{name}] the ~name form {text!r} -> {want!r}, got {run(text)!r}", run(text) == want)
    # the decided limits stay: a common word in prose, a longer name, a letter glued to the name
    home = "/" + "home" + "/"
    for text in ("the admin panel", "admin~1 is a short name", f"x~admin/notes", f"~~admin", f"{home}admin-2/x",
                 f"{home}admin.name/x", f"{home}adminx/x", f"{home}admin_x", "~administrators/x"):
        out = scrub({"t": text}, None, homes=[], users=["admin"], machines=[])["t"]
        ctx.check(f"not the account 'admin' as a home folder: {text!r} kept, got {out!r}", out == text)


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


def _login_and_share_shapes(name: str) -> list:
    """jf-words batch 2: (text, the scrubbed text) for the login form `name@host` and the UNC share segment, the shapes
    3.6.0.0 scrubbed for any account name (made-up hosts only, built from parts: no address of any kind)."""
    bs, host = chr(92), "gpu-box"
    unc = bs * 2
    return [(f"{name}@{host}", "<user>@<machine>"), (f"{name}@{host}:~/x", "<user>@<machine>:~/x"),
            (f"ssh {name}@{host}", "ssh <user>@<machine>"), (f"{name}@{host}:~$ ls", "<user>@<machine>:~$ ls"),
            (f"scp a.txt {name}@nas-01.example:/srv", "scp a.txt <user>@nas-01.example:/srv"),
            (f"git clone ssh://{name}@{host}/srv/repo.git", "git clone ssh://<user>@<machine>/srv/repo.git"),
            (f"[{name}@{host} ~]$", "[<user>@<machine> ~]$"), (f"{name}@<machine>:~$", "<user>@<machine>:~$"),
            (f"https://{name}:pw@{host}/", "https://<user>:pw@<machine>/"),
            (f"'{name}'@'{host}'", "'<user>'@'<machine>'"), (f"GRANT ALL TO `{name}`@`%`;", "GRANT ALL TO `<user>`@`%`;"),
            (f"{unc}{host}{bs}{name}{bs}share", f"{unc}<machine>{bs}<user>{bs}share"),
            (f"{unc}<machine>{bs}{name}{bs}x", f"{unc}<machine>{bs}<user>{bs}x"),
            (f"{unc}{host}{bs}{name}", f"{unc}<machine>{bs}<user>"),
            (f"{unc}{host}{bs}{name}$", f"{unc}<machine>{bs}<user>$"),
            (f"{bs * 4}{host}{bs * 2}{name}{bs * 2}x", f"{bs * 4}<machine>{bs * 2}<user>{bs * 2}x"),
            (f"//{host}/{name}/x", "//<machine>/<user>/x"),
            (f"{unc}?{bs}UNC{bs}{host}{bs}{name}{bs}x", f"{unc}?{bs}UNC{bs}<machine>{bs}<user>{bs}x"),
            (f"{unc}{host}{bs}Users{bs}{name}{bs}x", f"{unc}<machine>{bs}Users{bs}<user>{bs}x"),
            (f"{unc}{host}{bs}home{bs}{name}", f"{unc}<machine>{bs}home{bs}<user>")]


@test
def test_a_common_word_account_never_keeps_a_login_or_a_share_3600_scrubbed(ctx: Ctx):
    """3.6.0.1 jf-words batch 2: a common-word account name (admin, user, dev, build) was replaced only as a home
    folder's segment, so `admin@gpu-box:~$` (a prompt), `ssh admin@gpu-box` (an ssh, scp or git target) and the
    account's share `\\\\gpu-box\\admin\\share` kept it: 3.6.0.0 removed them all. The name right before `@` and a
    host, and the share right after a UNC server, are the account name again; a longer name and prose are kept."""
    from halo_harness.live.replay_private import scrub
    for name in ("admin", "user", "dev", "build", "zedtester"):
        def run(text):
            return scrub({"t": text}, None, homes=[], users=[name], machines=["gpu-box"])["t"]
        for text, want in _login_and_share_shapes(name):
            ctx.check(f"[{name}] {text!r} -> {want!r}, got {run(text)!r}", run(text) == want)
    keep = ("the admin said hi", "user input", "a dev build", "open the admin panel", "sysadmin@<machine>",
            "x.admin@<machine>", "my-admin@<machine>", "admin_x@<machine>", "ping @admin please", "admin @ noon",
            "https://<machine>/admin/login", "admin@", "<user>@<machine>")
    for name in ("admin", "user"):
        for text in keep:
            text = text.replace("admin", name) if "<user>" not in text else text
            out = scrub({"t": text.replace("<machine>", "gpu-box")}, None, homes=[], users=[name],
                        machines=["gpu-box"])["t"]
            ctx.check(f"[{name}] not the account as a login or a share: {text!r} kept, got {out!r}", out == text)


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


if __name__ == "__main__":
    ctx = Ctx()
    results, passed, failed, skipped = run_all(TESTS, ctx)
    sys.exit(print_results(results, passed, failed, skipped))
