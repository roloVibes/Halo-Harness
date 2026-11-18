"""tests.test_privacy_scrub -- the redaction every export and the bug report stand on (halo_harness/privacy_scrub.py;
3.6.0.3 moved it out of live/replay_private.py and live/replay_cut.py with no change of behaviour). Paths inside the
project become project-relative, any other path under the home `~/...`, the user name and the machine name leave every
text but the owner's own (the title) and a project-relative path; a text cut short is still rewritten; a common-word
account name goes only where it stands as an account. Every name that moved is the same object through its old module
until the batch that deletes it, and the kept files import it from here. Run: python -m tests.test_privacy_scrub
"""
from __future__ import annotations

import ast
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from tests.helpers.runner import Ctx, new_registry, print_results, run_all  # noqa: E402

test, TESTS = new_registry()
USER, MACHINE = "zedtester", "boxname7"
WIN_HOME, NIX_HOME = "C:\\Users\\" + USER, "/home/" + USER


@test
def test_windows_style_paths_and_names(ctx: Ctx):
    from halo_harness.privacy_scrub import scrub
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
    from halo_harness.privacy_scrub import scrub
    root = NIX_HOME + "/proj"
    got = scrub({"marks": [{"text": f"{root}/b.txt, {root}, {root}2/c, {NIX_HOME}/.halo/x, {NIX_HOME}, /tmp/t/x, "
                                    f"{MACHINE}.lan said hi to {USER}"}], "id": f"{USER}-1"},
                root, homes=[NIX_HOME], users=[USER], machines=[MACHINE])
    ctx.check(f"relative, ~, untouched outside the home, names out, got {got['marks'][0]['text']!r}",
              got["marks"][0]["text"] == "b.txt, ., ~/proj2/c, ~/.halo/x, ~, /tmp/t/x, <machine>.lan said hi to <user>")
    ctx.check("an id is never rewritten (a file's own name)", got["id"] == f"{USER}-1")


@test
def test_an_excerpt_cut_inside_a_name(ctx: Ctx):
    from halo_harness.privacy_scrub import scrub
    got = scrub({"t": f"as {USER[:7]}...", "u": f"on {MACHINE[:4]}...", "v": "the..."}, None, homes=[WIN_HOME],
                users=[USER], machines=[MACHINE])
    ctx.check(f"a name cut by the excerpt is still the name, got {got}",
              got == {"t": "as <user>...", "u": "on <machine>...", "v": "the..."})


@test
def test_an_excerpt_cut_inside_a_path(ctx: Ctx):
    """3.4.1.3: the 200-character cut can land inside a home or project path; the stub left is rewritten too."""
    from halo_harness.privacy_scrub import scrub
    root = WIN_HOME + chr(92) + "work" + chr(92) + "secret-project"
    got = scrub({"a": f"read {NIX_HOME[:2]}...", "b": f"open {WIN_HOME[:7]}...", "c": f'see "{WIN_HOME[:-3]}...',
                 "d": f"in {root[:-4]}...", "e": "ratio 3/4...", "f": "/tmp/x..."}, root, homes=[WIN_HOME, NIX_HOME],
                users=[USER], machines=[MACHINE])
    ctx.check(f"a path cut by the excerpt is ~ or ., got {got}",
              got == {"a": "read ~...", "b": "open ~...", "c": 'see "~...', "d": "in ....", "e": "ratio 3/4...",
                      "f": "/tmp/x..."})


PROSE = ("the user asked for a list; open the admin panel; run the test suite; tests/test_a.py passed; go home; "
         "Ubuntu 24.04 is the CI image on ubuntu-latest; the test runner failed twice, as runners do; /usr/local/bin")


@test
def test_a_common_word_account_name_is_scrubbed_only_as_a_name(ctx: Ctx):
    """3.6.0.1 setup-words: with an account called `user`, `admin`, `test`, `home`, `ubuntu` or `runner` the scrub
    rewrote ordinary words ('the <user> asked', 'tests/<user>_a.py', '<user>-latest') and JSON keys. A common word is
    the name only where it stands as a home folder's segment; an uncommon name is replaced as a whole word anywhere
    (a digit, '_', '.', '@' or a quote beside it is a boundary; a letter is not)."""
    from halo_harness.privacy_scrub import scrub
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
    from halo_harness.privacy_scrub import scrub
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
    from halo_harness.privacy_scrub import scrub
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


def _login_and_share_shapes(name: str) -> list:
    """jf-words batch 2: (text, the scrubbed text) for the login form `name@host` and the UNC share segment, the shapes
    3.6.0.0 scrubbed for any account name (made-up hosts only, built from parts: no address of any kind)."""
    bs, host = chr(92), "gpu-box"
    unc = bs * 2
    v6 = ":".join([format(0xFE80, "x"), "", "7"])  # a bracketed host, never written as a literal
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
            (f"{unc}{host}{bs}home{bs}{name}", f"{unc}<machine>{bs}home{bs}<user>"),
            # batch 2 repair: a bracketed host (built at run time), a share written as a URL, the account's slots
            (f"{name}@[{v6}]", f"<user>@[{v6}]"), (f"ssh {name}@[{v6}]:~/x", f"ssh <user>@[{v6}]:~/x"),
            (f"smb://{host}/{name}/x", "smb://<machine>/<user>/x"), (f"file://{host}/{name}/x", "file://<machine>/<user>/x"),
            (f"afp://{host}/{name}", "afp://<machine>/<user>"),
            (f"git clone ssh://git@{host}:22/{name}/repo.git", "git clone ssh://git@<machine>:22/<user>/repo.git"),
            (f"git@{host}:{name}/repo.git", "git@<machine>:<user>/repo.git"),
            (f"ssh -l {name} {host}", "ssh -l <user> <machine>"), (f"mysql -u {name} -p", "mysql -u <user> -p"),
            (f"psql --username={name} -h {host}", "psql --username=<user> -h <machine>"),
            (f"user={name} host={host}", "user=<user> host=<machine>"), (f"export USER={name}", "export USER=<user>"),
            (f'{{"username": "{name}"}}', '{"username": "<user>"}'), (f"DB_USER: {name}", "DB_USER: <user>"),
            (f"owner={name}", "owner=<user>"), (f"su - {name}", "su - <user>"), (f"sudo su {name}", "sudo su <user>"),
            (f"chown -R {name}:staff f", "chown -R <user>:staff f"), (f"id {name}", "id <user>"),
            (f"runas /user:{name} cmd", "runas /user:<user> cmd"), (f"passwd {name}", "passwd <user>")]


@test
def test_a_common_word_account_never_keeps_a_login_or_a_share_3600_scrubbed(ctx: Ctx):
    """3.6.0.1 jf-words batch 2: a common-word account name (admin, user, dev, build) was replaced only as a home
    folder's segment, so `admin@gpu-box:~$` (a prompt), `ssh admin@gpu-box` (an ssh, scp or git target) and the
    account's share `\\\\gpu-box\\admin\\share` kept it: 3.6.0.0 removed them all. The name right before `@` and a
    host, and the share right after a UNC server, are the account name again; a longer name and prose are kept."""
    from halo_harness.privacy_scrub import scrub
    for name in ("admin", "user", "dev", "build", "zedtester"):
        def run(text):
            return scrub({"t": text}, None, homes=[], users=[name], machines=["gpu-box"])["t"]
        for text, want in _login_and_share_shapes(name):
            ctx.check(f"[{name}] {text!r} -> {want!r}, got {run(text)!r}", run(text) == want)
    keep = ("the admin said hi", "user input", "a dev build", "open the admin panel", "sysadmin@<machine>",
            "x.admin@<machine>", "my-admin@<machine>", "admin_x@<machine>", "ping @admin please", "admin @ noon",
            "admin@", "<user>@<machine>", "git push -u origin", "sort -u admins.txt", "the admin: hi")
    for name in ("admin", "user"):
        for text in keep:
            text = text.replace("admin", name) if "<user>" not in text else text
            out = scrub({"t": text.replace("<machine>", "gpu-box")}, None, homes=[], users=[name],
                        machines=["gpu-box"])["t"]
            ctx.check(f"[{name}] not the account as a login or a share: {text!r} kept, got {out!r}", out == text)


@test
def test_the_name_patterns_stay_linear_on_a_long_run_of_name_colons(ctx: Ctx):
    """3.6.0.1 jf-words batch 2 repair: the login pattern looked ahead to the end of `admin:admin:admin...` from every
    name (quadratic: minutes at 200 KB); the audit runs these patterns over whole replay texts. Each pattern alone on
    180 KB of it is a few milliseconds when linear; the budget is set for a slow CI runner."""
    import time
    from halo_harness.privacy_scrub import _name_patterns
    # batch 3: the `machine\name` login and the command-position slots get runs of their own lead too
    texts = ("admin:" * 30000, "gpu-box" + chr(92) + "gpu-box" * 22000, "ssh -x " * 26000, "; sudo " * 26000)
    for text in texts:
        for pat in _name_patterns(["admin"], machines=["gpu-box"]):
            t0 = time.perf_counter()
            pat.sub("", text)
            took = time.perf_counter() - t0
            ctx.check(f"{pat.pattern[:60]!r} took {took:.2f} s on {text[:12]!r}...", took < 8.0)


def _machine_login_shapes(name: str) -> list:
    """jf-words batch 3: (text, the scrubbed text) for a Windows account written `machine\\name` (whoami, runas, net
    use, an ACL's owner column), single and JSON-doubled backslash, after the machine already became `<machine>`.
    Made-up host only, built from parts."""
    bs, host = chr(92), "gpu-box"
    return [(f"{host}{bs}{name}", f"<machine>{bs}<user>"), (f"{host}{bs * 2}{name}", f"<machine>{bs * 2}<user>"),
            (f"<machine>{bs}{name}", f"<machine>{bs}<user>"), (f"$ whoami\n{host}{bs}{name}\n", f"$ whoami\n<machine>{bs}<user>\n"),
            (f"runas /user:{host}{bs}{name} cmd", f"runas /user:<machine>{bs}<user> cmd"),
            (f"net use {bs * 2}{host}{bs}x /user:{host}{bs}{name}", f"net use {bs * 2}<machine>{bs}x /user:<machine>{bs}<user>"),
            (f"f.txt GPU-BOX{bs}{name}:(OI)(CI)(F)", f"f.txt <machine>{bs}<user>:(OI)(CI)(F)"),
            (f"Owner  : GPU-BOX{bs}{name}", f"Owner  : <machine>{bs}<user>"),
            (f'{{"owner": "{host}{bs * 2}{name}"}}', f'{{"owner": "<machine>{bs * 2}<user>"}}'),
            (f"{host}{bs}{name}{bs}x", f"<machine>{bs}<user>{bs}x")]


@test
def test_a_common_word_account_never_keeps_a_windows_machine_login_3600_scrubbed(ctx: Ctx):
    """3.6.0.1 jf-words batch 3: the Windows counterpart of `name@machine` is `machine\\name` (`whoami`, `runas
    /user:`, `net use /user:`, the owner of `icacls` / `Get-Acl`): a common-word name kept it, 3.6.0.0 removed it. The
    name right after a machine of the scrub's list (or `<machine>`) and a backslash is the account; a folder named
    like the word under another folder is a path word and stays, and a UNC share is batch 2's rule (no double match)."""
    from halo_harness.privacy_scrub import scrub
    bs = chr(92)
    for name in ("admin", "user", "dev", "build", "zedtester"):
        def run(text):
            return scrub({"t": text}, None, homes=[], users=[name], machines=["gpu-box"])["t"]
        for text, want in _machine_login_shapes(name):
            ctx.check(f"[{name}] {text!r} -> {want!r}, got {run(text)!r}", run(text) == want)
    for name in ("admin", "build"):
        for text in (f"tools{bs}{name}{bs}x", f"see tools{bs}{name}", f"C:{bs}tools{bs}{name}{bs}x", f"the {name} said"):
            out = scrub({"t": text}, None, homes=[], users=[name], machines=["gpu-box"])["t"]
            ctx.check(f"[{name}] a path word or prose stays: {text!r}, got {out!r}", out == text)
        unc = f"{bs * 2}gpu-box{bs}{name}{bs}share"
        out = scrub({"t": unc}, None, homes=[], users=[name], machines=["gpu-box"])["t"]
        ctx.check(f"[{name}] a UNC share is replaced once, got {out!r}", out == f"{bs * 2}<machine>{bs}<user>{bs}share")


@test
def test_a_common_word_is_an_account_only_in_a_command_s_account_slot(ctx: Ctx):
    """3.6.0.1 jf-words batch 3: batch 2 took `-u` / `-U` / `-l` / `--user` after ANY command and `id`, `groups`,
    `passwd`, `finger`, `su` anywhere in a sentence as an account slot, so `pip install -U build` lost `build`. A
    command word counts only at a command position (a line's start, a quote's start, after a prompt mark, `sudo`, `;`,
    `&&`, `||`, `|`, `(`), and an account flag only after a command that takes an account there."""
    from halo_harness.privacy_scrub import scrub
    for name in ("build", "dev"):
        def run(text):
            return scrub({"t": text}, None, homes=[], users=[name], machines=["gpu-box"])["t"]
        keep = (f"pip install -U {name}", f"pip install --user {name}", f"python -m {name}", f"python -u {name}",
                f"the id {name} number", f"su {name}-essential", f"npm run {name}", f"git checkout {name}",
                f"two groups {name} and qa", f"the passwd {name} database", f"a finger {name} pointing",
                f"rsync -u {name}/ out/", f"docker run -l {name}=x img", f"git push -u origin {name}",
                f"sort -u {name}.txt")
        for text in keep:
            ctx.check(f"[{name}] not an account slot: {text!r} kept, got {run(text)!r}", run(text) == text)
        gone = ((f"$ groups {name}", "$ groups <user>"), (f"groups {name}", "groups <user>"),
                (f"sudo -u {name} ls", "sudo -u <user> ls"), (f"sudo -E -u {name} ls", "sudo -E -u <user> ls"),
                (f"sudo --user={name} ls", "sudo --user=<user> ls"), (f"sudo --user {name} ls", "sudo --user <user> ls"),
                (f"ssh -p 22 -l {name} gpu-box", "ssh -p 22 -l <user> <machine>"),
                (f"docker exec -it -u {name} c sh", "docker exec -it -u <user> c sh"),
                (f"docker exec --user={name} c sh", "docker exec --user=<user> c sh"),
                (f"psql -U {name} -d x", "psql -U <user> -d x"), (f"cd x && id {name}", "cd x && id <user>"),
                (f"x; sudo passwd {name}", "x; sudo passwd <user>"), (f"ls | finger {name}", "ls | finger <user>"),
                (f"out=$(id {name})", "out=$(id <user>)"), (f"run 'su - {name}' now", "run 'su - <user>' now"),
                (f"PS C:/x> runas /user:{name} cmd", "PS C:/x> runas /user:<user> cmd"))
        for text, want in gone:
            ctx.check(f"[{name}] an account slot: {text!r} -> {want!r}, got {run(text)!r}", run(text) == want)


@test
def test_a_listed_account_slot_counts_behind_a_path_a_prefix_or_a_trace(ctx: Ctx):
    """3.6.0.1 jf-words batch 3 repair: batch 3 took an account flag only when its command stood at a command line's
    very start, so `ssh.exe -l name`, `/usr/bin/ssh -l name`, `PGPASSWORD=x psql -U name`, `sudo -u postgres psql -U
    name`, `env X=1 sudo -u name ls`, `timeout 5 ssh -l name` and a `set -x` trace (`+ ssh -l name`) kept the name
    (3.6.0.0 removed it). A command of the flag list counts wherever it stands as a whole word (a path before it, `.exe`
    after it); a command of the word list (`id`, `chown` ...) after a trace mark, `VAR=value` / `env`, `sudo` and its
    options, or a folder. The group of `name:name` (`chown`, `--user`) goes with the name. The audit shares this."""
    from halo_harness.privacy_scrub import _name_patterns, scrub
    win = "C:\\Windows\\System32\\OpenSSH\\ssh.exe"
    for name in ("admin", "build"):
        def run(text):
            return scrub({"t": text}, None, homes=[], users=[name], machines=["gpu-box"])["t"]
        gone = ((f"ssh.exe -l {name} gpu-box", "ssh.exe -l <user> <machine>"),
                (f"{win} -l {name} gpu-box", f"{win} -l <user> <machine>"),
                (f"/usr/bin/ssh -l {name} gpu-box", "/usr/bin/ssh -l <user> <machine>"),
                (f"PGPASSWORD=x psql -U {name} -d db", "PGPASSWORD=x psql -U <user> -d db"),
                (f"sudo -u postgres psql -U {name}", "sudo -u postgres psql -U <user>"),
                (f"env X=1 sudo -u {name} ls", "env X=1 sudo -u <user> ls"),
                (f"timeout 5 ssh -l {name} gpu-box", "timeout 5 ssh -l <user> <machine>"),
                (f"+ ssh -l {name} gpu-box", "+ ssh -l <user> <machine>"),
                (f"++ id {name}", "++ id <user>"), (f"env LANG=C id {name}", "env LANG=C id <user>"),
                (f"/usr/bin/id {name}", "/usr/bin/id <user>"), (f"sudo -u root chown {name} f", "sudo -u root chown <user> f"),
                (f"docker run --user {name}:{name} img", "docker run --user <user>:<user> img"),
                (f"chown -R {name}:{name} f", "chown -R <user>:<user> f"),
                (f"gpu-box.local\\{name}", "<machine>.local\\<user>"))
        for text, want in gone:
            ctx.check(f"[{name}] an account slot: {text!r} -> {want!r}, got {run(text)!r}", run(text) == want)
            pats = _name_patterns([name], machines=["gpu-box"])
            ctx.check(f"[{name}] the audit finds {text!r}", any(p.search(text) for p in pats))
        keep = (f"sudo pip install -U {name}", f"env X=1 python -m {name}", f"+ git push -u origin {name}",
                f"/usr/bin/sort -u {name}.txt", f"the ssh {name} key", f"x=1 git checkout {name}",
                f"chown -R root:{name} f")
        for text in keep:
            ctx.check(f"[{name}] not an account slot: {text!r} kept, got {run(text)!r}", run(text) == text)


@test
def test_a_generic_word_outside_home_folders_and_logins_is_the_documented_limit(ctx: Ctx):
    """3.6.0.1 jf-words batch 3, the coordinator's ruling (docs/REPLAY.md): for an account named by a common word the
    scrub removes the name in home folders and logins only; in an `ls -l` owner column, a process list, an ssh config
    `User` line or a `role:` value it cannot be told from the ordinary word and stays. An uncommon name goes there as
    in 3.6.0.0. Pinned so the limit is not 'fixed' by accident."""
    from halo_harness.privacy_scrub import scrub
    lines = ("-rw-r--r--  1 {n} staff  0 Nov 16 a.txt", "role: {n}", "{n}      4242  0.0  0.1 python x.py",
             "Host gpu-box\n  User {n}")
    for line in lines:
        out = scrub({"t": line.format(n="admin")}, None, homes=[], users=["admin"], machines=[])["t"]
        ctx.check(f"a common word stays: {line!r}, got {out!r}", out == line.format(n="admin"))
        out = scrub({"t": line.format(n="zedtester")}, None, homes=[], users=["zedtester"], machines=[])["t"]
        ctx.check(f"an uncommon name goes: {line!r}, got {out!r}", out == line.format(n="<user>"))


def _defined(path: Path) -> list:
    """The names a module defines at its top level (functions, classes, assignments), never what it imports."""
    out = []
    for node in ast.parse(path.read_text(encoding="utf-8")).body:
        if isinstance(node, (ast.FunctionDef, ast.ClassDef)):
            out.append(node.name)
        elif isinstance(node, ast.Assign):
            out += [t.id for t in node.targets if isinstance(t, ast.Name)]
        elif isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name):
            out.append(node.target.id)
    return out


def _imports(path: Path) -> list:
    """(module, name) for every import of a file, at any depth (a function-local one too)."""
    out = []
    for node in ast.walk(ast.parse(path.read_text(encoding="utf-8"))):
        if isinstance(node, ast.ImportFrom) and node.module:
            out += [(node.module, a.name) for a in node.names]
        elif isinstance(node, ast.Import):
            out += [(a.name, "") for a in node.names]
    return out


LIVE_PKG = "halo_harness.live"
OLD_SCRUB = tuple(f"{LIVE_PKG}.{name}" for name in ("replay_private", "replay_cut"))  # deleted in 3.6.0.3 B file 06


@test
def test_the_scrub_lives_in_its_own_module(ctx: Ctx):
    """3.6.0.3 (R-B6, Z5): the scrub left its old names as a pure move, private names too; file 06 deleted the old
    modules that re-exported it (and audit(), with `halo audit privacy --replays`)."""
    import importlib.util
    names = _defined(ROOT / "halo_harness" / "privacy_scrub.py")
    for must in ("scrub", "project_root", "_homes", "_CONTROLS", "_SEGMENT_END", "_name_patterns", "COMMON_NAMES",
                 "cut_name_rule", "cut_path_rule"):
        ctx.check(f"{must} lives in privacy_scrub.py", must in names)
    ctx.check("audit() is not in it", "audit" not in names)
    for old in OLD_SCRUB:
        ctx.check(f"{old} is gone", importlib.util.find_spec(old) is None)


@test
def test_the_kept_files_import_the_scrub_from_its_own_module(ctx: Ctx):
    """3.6.0.3 (R-B6): privacy_redact.py (the export's, `halo export --sanitize`'s and the bug report's redaction),
    the card's build (live/card_data.py) and realcheck's prompt step import the scrub from halo_harness.privacy_scrub; the
    new module imports no old one."""
    for rel in ("halo_harness/privacy_redact.py", "halo_harness/live/card_data.py", "scripts/realcheck/steps_prompt.py",
                "halo_harness/privacy_scrub.py"):
        old = [f"{m}.{n}" for m, n in _imports(ROOT / rel) if m in OLD_SCRUB or m == LIVE_PKG and f"{m}.{n}" in OLD_SCRUB]
        ctx.check(f"{rel} imports nothing from the old modules, got {old}", not old)
    for rel in ("halo_harness/privacy_redact.py", "scripts/realcheck/steps_prompt.py"):
        ctx.check(f"{rel} imports from halo_harness.privacy_scrub",
                  any(m == "halo_harness.privacy_scrub" for m, _n in _imports(ROOT / rel)))
    lines = len((ROOT / "halo_harness" / "privacy_scrub.py").read_text(encoding="utf-8").splitlines())
    ctx.check(f"one file of at most 400 lines, got {lines}", lines <= 400)


if __name__ == "__main__":
    ctx = Ctx()
    results, passed, failed, skipped = run_all(TESTS, ctx)
    sys.exit(print_results(results, passed, failed, skipped))
