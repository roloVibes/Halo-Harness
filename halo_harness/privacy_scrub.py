"""halo_harness.privacy_scrub -- the paths and names part of the redaction of what leaves this machine (Halo 3.4.1.1,
defect 56; privacy_redact.redact runs it after the key shapes).

What leaves holds the model's own words (a sub-agent's task, a hand-back, a tool line), and models write absolute
paths: `C:\\Users\\<you>\\project\\a.txt`, `/home/<you>/project/b.txt`. Applied to every string of the payload:

    paths inside the project       -> project-relative (`a.txt`, `src/b.py`; the project itself `.`)
    any other path under the home  -> `~/...` (the home itself `~`)
    the user name, the machine name -> `<user>`, `<machine>` -- except inside a project-relative path and in the
                                       session's own text the owner typed (its title: the first words), and the
                                       lineup's blocks (names the owner gave them)

Every spelling of a path is caught: either separator (or both, or doubled as JSON text spells them), any case of a
Windows path, Git Bash's `/c/Users/...` and WSL's `/mnt/c/...`, the `\\\\?\\` long-path prefix. Nothing is added to the
format: a file written before still opens, a reader sees only strings.

    scrub(payload, root=None, *, homes=None, users=None, machines=None) -> payload
    project_root(cwd) -> the git top folder that holds `cwd`, else `cwd` (None for none)

3.6.0.3: moved here, with no change of behaviour, from live/replay_private.py (all but `halo audit privacy
--replays`' audit) and live/replay_cut.py, the rules for a text that was CUT SHORT before the redactor saw it:

live/history.py cuts a task to 200 characters and closes it with "..." before a record is built, so the cut can
land inside a name ("... as zedteste...") or inside a path ("... and /h...", or a Windows home cut after its
first letters), where the
whole-name and whole-path rules above cannot match. These rules look only at the last run of
characters before a closing "..." (or the one-character ellipsis):

    cut_name_rule(names, word) -> rule(s)   a word of 3+ letters there that BEGINS a name is that name -> `word`
    cut_path_rule(homes, root) -> rule(s)   a run there that BEGINS the project folder -> ".", a home folder -> "~"

Both err towards rewriting: an ordinary word that happens to begin the user's name, right before the cut, is
replaced too. That is the right side to err on for a file meant to be handed to someone else.
"""

from __future__ import annotations

import os
import re
from pathlib import Path
from typing import Iterable, Optional


_CUT_WORD = re.compile(r"([^\W_]{3,})(\.\.\.|…)$")
_CUT_RUN = re.compile(r"(\S{2,})(\.\.\.|…)$")

#: 3.6.0.1: account and machine names that are also ordinary words (and the accounts of CI runners and cloud images):
#: such a name is replaced only where it stands as a home folder's segment, never as a word in a text
COMMON_NAMES = frozenset({
    "user", "users", "admin", "administrator", "root", "home", "test", "tester", "guest", "owner", "default", "public",
    "dev", "developer", "ubuntu", "debian", "runner", "vagrant", "docker", "pi", "ec2-user", "server", "desktop",
    "laptop", "localhost", "build", "builder", "jenkins", "app", "www", "data", "local", "work"})


def cut_name_rule(names: list, word: str):
    low = [str(n).lower() for n in names if n and str(n).lower() not in COMMON_NAMES]

    def rule(s: str) -> str:
        m = _CUT_WORD.search(s)
        if m and any(n.startswith(m.group(1).lower()) and n != m.group(1).lower() for n in low):
            return s[:m.start(1)] + word + m.group(2)
        return s
    return rule


def _forms(path) -> set:
    """Every spelling a folder can have in a text: both slash kinds, and backslashes doubled (a JSON or code string)."""
    p = str(path or "").rstrip("\\/")
    if len(p) < 2:
        return set()
    fwd, back = p.replace("\\", "/"), p.replace("/", "\\")
    return {v.lower() for v in (p, fwd, back, back.replace("\\", "\\\\"))}


def _starts_a_path(run: str, i: int) -> bool:
    return run[i] in "/\\~" or run[i + 1:i + 2] == ":"


def cut_path_rule(homes: list, root=None):
    home_forms = [f for h in homes for f in _forms(h)]
    root_forms = set(_forms(root))
    for h in home_forms:  # the home rules ran first: a project under a home already reads "~/..." or "~\..."
        for r in list(root_forms):
            if r.startswith(h) and len(r) > len(h):
                root_forms.add("~" + r[len(h):])
    # a stub that begins a home is "~" (it begins the project too, when the project is under that home); a longer
    # one that only begins the project is "."
    targets = [(f, "~") for f in home_forms] + [(f, ".") for f in sorted(root_forms, key=len, reverse=True)]

    def rule(s: str) -> str:
        m = _CUT_RUN.search(s)
        if not m:
            return s
        run = m.group(1)
        low = run.lower()
        for i in range(0, len(run) - 1):  # the path may follow a quote or a bracket inside the run
            if not _starts_a_path(run, i):
                continue
            stub = low[i:]
            for form, to in targets:
                if len(stub) >= 2 and form.startswith(stub) and form != stub:
                    return s[:m.start(1) + i] + to + m.group(2)
            break  # the run's first path-like position is the only candidate
        return s
    return rule


SEP = r"[\\/]+"
_LEAD = r"(?<![\w.~-])"  # a POSIX path starts here: not inside a word or another path
_TAIL = r"(?:(?P<sep>[\\/]+)(?P<rest>[^\s\"'`<>|;,]+)|(?![\w-]|\.\w))"
OWNER_KEYS = {"title"}  # the owner's own text (its first words); 3.4.1.2 (SERVERS-6): the plan's names are scrubbed
#: machine-made values a reader matches on (3.4.1.2: `to`, `agent_id`, `parent` are scrubbed like any text)
ID_KEYS = {"id", "session_id", "run_id", "format", "halo", "kind", "state", "phase", "version", "upgraded_from"}
_MARK = "\ue000"  # wraps a path the root rule made project-relative while the name rules run (never in the output)


def _prefix(path: str) -> Optional[str]:
    """A regex for every spelling of the absolute `path` (None for a relative or empty one)."""
    p = str(path or "").strip()
    win = re.match(r"^(?:\\\\\?\\)?([A-Za-z]):[\\/]", p)
    parts = [x for x in re.split(r"[\\/]+", p) if x]
    if win:
        drive = win.group(1)
        rest = parts[next(i for i, x in enumerate(parts) if x.endswith(":")) + 1:]
        heads = [r"(?:\\\\\?\\)?" + re.escape(drive) + ":", "/mnt/" + re.escape(drive.lower()), "/" + re.escape(drive.lower())]
        return "(?i:(?:" + "|".join(heads) + ")" + "".join(SEP + re.escape(x) for x in rest) + ")"
    if p.startswith("/") and parts:
        return "".join(SEP + re.escape(x) for x in parts)
    return None


def _rule(path: str, short: str, long: str, mark: bool = False):
    """3.4.1.2 (PACKS-5): a drive-letter path needs no word boundary before it (`x_C:\\Users\\...`); `mark` wraps what
    the root rule writes, so the name rules know a project-relative path the rule made."""
    src = _prefix(path)
    if not src:
        return None
    pat = re.compile(("" if re.match(r"^(?:\\\\\?\\)?[A-Za-z]:", str(path).strip()) else _LEAD) + src + _TAIL)
    m0 = _MARK if mark else ""
    return lambda s: pat.sub(lambda m: m0 + (long + re.sub(r"[\\/]+", "/", m.group("rest")) if m.group("sep")
                                             else short) + m0, s)


def _short_paths(homes: list) -> list:
    """Windows 8.3 spellings of each home (the `NAME~1` form of the user folder), when the file system has them."""
    if os.name != "nt":
        return []
    out = []
    try:
        import ctypes
        for h in homes:
            buf = ctypes.create_unicode_buffer(1024)
            if ctypes.windll.kernel32.GetShortPathNameW(str(h), buf, 1024) and buf.value and buf.value != str(h):
                out.append(buf.value)
    except Exception:
        pass
    return out


def project_root(cwd) -> Optional[Path]:
    if not cwd:
        return None
    here = Path(str(cwd))
    for d in (here, *here.parents):
        try:
            if (d / ".git").exists():
                return d
        except OSError:
            break
    return here


def _homes() -> list:
    from halo_harness.config.paths import home
    out = [str(home())] + [os.environ.get(k, "") for k in ("USERPROFILE", "HOME")]  # paths.home(), and the real one
    return [h for h in dict.fromkeys(out) if h and len(h) > 3]


def _users(homes: Iterable[str]) -> list:
    names = [os.environ.get(k, "") for k in ("USERNAME", "USER", "LOGNAME")]
    try:
        import getpass
        names.append(getpass.getuser())
    except Exception:
        pass
    names += [re.split(r"[\\/]+", h.rstrip("\\/"))[-1] for h in homes]
    return [n for n in dict.fromkeys(names) if len(n) >= 3]


def _machines() -> list:
    names = [os.environ.get("COMPUTERNAME", "")]
    try:
        import platform
        import socket
        names += [socket.gethostname(), platform.node()]
    except Exception:
        pass
    names += [n.split(".", 1)[0] for n in names if n]
    return [n for n in dict.fromkeys(names) if len(n) >= 3]


#: a home folder's prefix right before the account name: /home/, /Users/, C:\Users\ (either slash, a JSON-doubled
#: backslash), /c/Users/ (Git Bash), /mnt/c/Users/ (WSL), \\?\C:\Users\; or the shell's `~name` (not glued to a word
#: or another `~`); or a UNC server, the account's share right after it (`\\server\name`, `\\<machine>\name`, JSON-
#: doubled (twice over in the audit's JSON text), `//server/name`, `\\?\UNC\server\name`; a URL's first segment
#: after its host (`smb://`, `file://`, `ssh://git@host:22/name`) but not a web page's (http, https, ws, wss: a route
#: word); an scp / git target's `@host:name`); group 1 is kept
_SEGMENT_LEAD = (r"((?<=[\\/])(?:home|users)(?:\\+|/)"
                 r"|(?:(?<![\w:/\\])(?:\\{2,}|//)|(?<=[\w+.-]:)(?<!https:)(?<!http:)(?<!wss:)(?<!ws:)//)"
                 r"(?:\?\\+UNC\\+)?(?:[^\W_][\w.-]*@)?(?:<machine>|[^\W_][\w.-]*)(?::\d+)?(?:\\+|/)"
                 r"|@(?:<machine>|[^\W_][\w.-]*):"
                 r"|(?<![\w~])~)")
#: a login right after the name (`name@host`, `name@<machine>`, `name@[an IPv6 literal]`: a prompt, an ssh / scp / git
#: target; a URL's `name:secret@host`, the secret bounded so a long `name:name:...` is not read to its end from every
#: name); a letter, digit, `_`, `.` or `-` before the name makes it another, longer name (`sysadmin@box`)
_LOGIN_AT = r"(?=(?::[^\s@/\\]{0,256})?@(?:<machine>|[^\W_]|\[[\da-f:]))"


#: jf-words batch 3: the commands that take an account after a flag of theirs, and those flags (case matters: `ssh -L`
#: forwards a port). Not scp / sftp / rsync: their `-l` is a bandwidth limit or links, rsync's `-u` is "update".
_ACCOUNT_FLAGS = (("ssh", "-l"), ("sudo", "-u|--user"), ("docker", "-u|--user"), ("psql", "-U|--username"),
                  ("mysql", "-u|--user"), ("runas", "(?i:/user:)"), ("net", "(?i:/user:)"))
#: the commands whose argument is an account (`su - name`, `chown -R name:staff`, `id name` ...)
_ACCOUNT_COMMANDS = r"(?:su(?:[^\S\n]+-l?)?|chown(?:[^\S\n]+-\w+)*|id|passwd|finger|groups|useradd|userdel|adduser|deluser)"
#: a command position: a line's start (a JSON text's `\n` too), a quote's or `(`'s start, after `;` `&` `|`, after a
#: prompt mark and a space (`$ `, `# `, `% `, `> `); then a `set -x` trace's `+`, `env` and `VAR=value`s, `sudo` and
#: its options (`-u root`), a folder (`/usr/bin/`) may come first (each bounded: linear time from every position)
_CMD_AT = (r"(?:(?<![^\n\"'`(;&|])|(?<=\\n)|(?<=[$#%>] ))[^\S\n]*(?:\++[^\S\n]+)?"
           r"(?:(?:env[^\S\n]+)?(?:\w{1,64}=[^\s;&|]{0,256}[^\S\n]+){1,8})?"
           r"(?:sudo(?:[^\S\n]+-(?:[ughCpU]|-user|-group)[^\S\n]+[^\s;&|-][^\s;&|]{0,255}|[^\S\n]+-[\w-]+){0,8}"
           r"[^\S\n]+)?(?:[^\s;&|\"'`]{0,256}[/\\])?")
#: a command of the flag list stands as a whole word anywhere on a line (`timeout 5 ssh`, `PGPASSWORD=x psql`, `sudo
#: -u postgres psql`), a folder before it, `.exe` after it
_CMD_WORD = r"(?:(?<![\w.-])|(?<=\\[nrt]))"
#: a command's other arguments before its account flag: a few, each bounded (linear time from every position)
_ARGS = r"(?:[^\S\n]+[^\s;&|]{1,256}){0,16}?[^\S\n]+"


def _account_slots(names: list) -> list:
    """jf-words: where a word stands as an account, read over the whole text (the scrub splits text at quotes,
    whitespace and `=`; the audit reads whole texts anyway), group 1 kept: a database account `'name'@'host'` (any
    quote), a login flag of a command that takes an account there (`ssh -l name`, `mysql -u name`, `docker exec
    --user=name`, `psql --username=name`, `runas /user:name`; `pip install -U build` is no account), a command at a
    command position whose argument is an account (`su - name`, `chown -R name:staff`, `id name`, `passwd name`; not
    "the id build number") and a key (`user=name`, `USER=name`, `DB_USER: name`, `"username": "name"`, `owner=name`,
    JSON-escaped too)."""
    names = sorted((str(n) for n in names if n), key=len, reverse=True)
    if not names:
        return []
    either = "(" + "|".join(map(re.escape, names)) + ")"
    flags = "|".join(re.escape(cmd) + r"(?:\.exe)?" + _ARGS + r"(?-i:" + fl + r")(?:(?<=:)|[^\S\n]+|=)"
                     for cmd, fl in _ACCOUNT_FLAGS)
    return [re.compile(r"(?i)([\"'`])" + either + r"(?=\1@)"),
            re.compile(r"(?i)((?:" + _CMD_WORD + r"(?:" + flags + r")|" + _CMD_AT + _ACCOUNT_COMMANDS
                       + r"[^\S\n]+))" + either + _SEGMENT_END),
            re.compile(r"(?i)((?<![\w-])\w*?(?:user(?:_?name)?|login|logname|owner)\\*[\"'`]?\s*[=:]\s*\\*[\"'`]?)"
                       + either + _SEGMENT_END)]
#: where the name's segment ends: anything that does not run on into more name, as the path rule's _TAIL ends a home
#: (`}` `#` `&` `!` `~` `,` `:` a slash, a quote, whitespace, the end ...; after the home prefix, `user.` ends a
#: sentence; `user.name`, `user-2` and `user_x` are other, longer names)
_SEGMENT_END = r"(?![\w-]|\.[\w-])"


def _name_patterns(names: list, *, segments: bool = True, machines: Iterable[str] = ()) -> list:
    """3.6.0.1 (setup-words): the patterns that find a name, shared by `scrub` and `audit`. Every name where it stands as
    a home folder's segment (`segments`; any length, group 1 the prefix kept), a login (`name@host`, jf-words batch 3:
    `machine\\name` after one of `machines` or `<machine>`) or an account slot; a name of 3+ characters that is not a
    common word (COMMON_NAMES: `user`, `admin`, `runner` ...) as a whole word: not glued to a LETTER (a
    digit, `_`, `.`, `-`, `@` or a quote is a boundary: `1jsmith`, `jsmith_notes`, `jsmith@box` go; `jsmithx`,
    `xjsmith` stay); a name of 7+ letters also as its 8.3 short form (`JSMITH~1`)."""
    names = [str(n) for n in names if n]
    if not names:
        return []
    ordered = sorted(names, key=len, reverse=True)
    out = []
    if segments:
        either = "(" + "|".join(map(re.escape, ordered)) + ")"
        out.append(re.compile(r"(?i)" + _SEGMENT_LEAD + either + _SEGMENT_END))
        out.append(re.compile(r"(?i)()(?<![\w.-])" + either + _LOGIN_AT))  # jf-words: the login form, group 1 empty
        # jf-words batch 3: Windows' `machine\name` (whoami, runas / net use `/user:`, an ACL's owner), one backslash
        # or JSON-doubled; not after a slash or backslash (a UNC share is the segment rule's), nor glued to a word
        hosts = "|".join(["<machine>"] + [re.escape(str(m)) for m in machines if m])
        out.append(re.compile(r"(?i)((?:(?<![\w.\\/-])|(?<=\\[nrt]))(?:" + hosts + r")(?:\.[\w-]{1,64}){0,8}\\+)"
                              + either + _SEGMENT_END))  # repair: this machine's full name too (`gpu-box.local\name`)
        out += _account_slots(ordered)
    alts = [re.escape(n) for n in ordered if len(n) >= 3 and n.lower() not in COMMON_NAMES]
    alts += [re.escape(re.sub(r"[\s.]", "", n)[:6]) + r"~\d+" for n in names if len(re.sub(r"[\s.]", "", n)) > 6]
    if alts:
        out.append(re.compile(r"(?i)(?<![^\W\d_])(?:" + "|".join(alts) + r")(?![^\W\d_])"))  # a letter is no boundary
    return out


def _name_rule(names: list, word: str, *, segments: bool = True, machines: Iterable[str] = ()):
    pats = _name_patterns(names, segments=segments, machines=machines)
    if not pats:
        return None
    if segments:  # jf-words batch 3 repair: the name's own group right after it (`chown name:name`, `--user name:name`)
        pats.append(re.compile(r"(?i)(" + re.escape(word) + r":)(" + "|".join(
            re.escape(str(n)) for n in sorted(names, key=len, reverse=True) if n) + r")" + _SEGMENT_END))

    def rule(s: str) -> str:
        for pat in pats:
            s = pat.sub((lambda m: m.group(1) + word) if pat.groups else word, s)
        return s
    return rule


def _json_unescape(s: str) -> str:
    """A JSON text's escapes (`\\t`, `\\n`, `\\"`, `\\\\`, `\\u00e9`) as the characters they stand for."""
    simple = {"n": "\n", "r": "\r", "t": "\t", "b": "\b", "f": "\f", '"': '"', "\\": "\\", "/": "/"}
    return re.sub(r"\\(?:u([0-9a-fA-F]{4})|([nrtbf\"\\/]))",
                  lambda m: chr(int(m.group(1), 16)) if m.group(1) else simple[m.group(2)], s)


_TOKEN = re.compile(r"(\s+|[\"'`(),;=])")
_CONTROLS = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f-\x9f]")  # 3.4.1.2 (PACKS-7): no terminal escapes survive


def _variants(s: str) -> list:
    """`s` as a reader would see it: percent-decoded (twice encoded too) and NFKC-folded (full-width look-alikes)."""
    import unicodedata
    from urllib.parse import unquote
    out, cur = [], s
    for _ in range(3):
        nxt = unquote(cur)
        if nxt == cur:
            break
        out.append(nxt)
        cur = nxt
    folded = unicodedata.normalize("NFKC", cur)
    out += [folded] if folded != cur else []
    unescaped = _json_unescape(folded)  # a JSON text inside a string: `\tname` is a tab and the name
    return out + ([unescaped, unicodedata.normalize("NFKC", unescaped)] if unescaped != folded else [])


def scrub(payload, root=None, *, homes=None, users=None, machines=None):
    """The payload with its paths and names rewritten (see the module's doc); `root` is the project folder. 3.4.1.2:
    the names everywhere but in a path the root rule made project-relative (URLs, `user@host`, `..` and other
    relative paths, `to` / `agent_id` /
    `parent`, the plan, dict keys); 8.3 short homes and names; a text that holds one only once decoded (`%5C`, a
    full-width look-alike) is stored decoded and rewritten; control characters dropped everywhere."""
    homes = list(homes) if homes is not None else _homes()
    homes = homes + [h for h in _short_paths(homes) if h not in homes]
    path_rules = [r for r in [_rule(str(root), ".", "", mark=True) if root else None]
                  + [_rule(h, "~", "~/") for h in sorted(homes, key=len, reverse=True)] if r]
    users = list(users) if users is not None else _users(homes)
    machines = list(machines) if machines is not None else _machines()
    names = [r for r in (_name_rule(users, "<user>", machines=machines), _name_rule(machines, "<machine>", segments=False))
             if r]
    names += [cut_name_rule(users, "<user>"), cut_name_rule(machines, "<machine>")]
    path_rules.append(cut_path_rule(homes, root))
    slots = _account_slots(users)

    def rules(s: str, owner: bool) -> str:
        for rule in path_rules:
            s = rule(s)
        if not owner and names:
            for pat in slots:  # jf-words: `'name'@'host'`, `-l name`, `user=name` span tokens
                s = pat.sub(lambda m: m.group(1) + "<user>", s)
            out = []
            for tok in _TOKEN.split(s):
                if tok and _MARK not in tok:  # 3.4.1.2 (SERVERS-6): only a path the root rule made keeps its words
                    for rule in names:
                        tok = rule(tok)
                out.append(tok)
            s = "".join(out)
        return s.replace(_MARK, "")

    def text(s: str, owner: bool) -> str:
        got = rules(_CONTROLS.sub("", s), owner)
        for v in _variants(got):
            if rules(v, owner) != v:  # it still holds a path or a name once decoded: keep the decoded, rewritten text
                return rules(_CONTROLS.sub("", v), owner)
        return got

    def walk(obj, owner: bool, key: str = ""):
        if isinstance(obj, str):
            return _CONTROLS.sub("", obj) if key in ID_KEYS else text(obj, owner)
        if isinstance(obj, list):
            return [walk(v, owner, key) for v in obj]
        if isinstance(obj, dict):
            return {(text(k, False) if isinstance(k, str) else k): walk(v, owner or k in OWNER_KEYS, k)
                    for k, v in obj.items()}
        return obj

    return walk(payload, False)
