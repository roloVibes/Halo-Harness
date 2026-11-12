"""halo_harness.live.replay_private -- a saved replay is safe to hand to someone else (Halo 3.4.1.1, defect 56).

A replay's texts are the model's own words (a sub-agent's task, a hand-back, a tool line), and models write absolute
paths: `C:\\Users\\<you>\\project\\a.txt`, `/home/<you>/project/b.txt`. Applied when the file is written (and when it
is built, so the Save dialog shows what the file will hold), to every string of the payload:

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
"""

from __future__ import annotations

import os
import re
from pathlib import Path
from typing import Iterable, Optional

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
    """Windows 8.3 spellings of each home (`C:\\Users\\JSMITH~1`), when the file system has them."""
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


def _name_rule(names: list, word: str):
    """3.4.1.2 (PACKS-5): a name of 6+ characters is replaced wherever it stands, even glued to a word (`1jsmith`,
    `jsmith_notes`); a shorter one only between non-letters; a name of 7+ letters also as its 8.3 short form
    (`JSMITH~1`)."""
    if not names:
        return None
    ordered = sorted(names, key=len, reverse=True)
    glued = [re.escape(n) for n in ordered if len(n) >= 6]
    alts = [re.escape(n) for n in ordered if len(n) < 6]
    alts += [re.escape(re.sub(r"[\s.]", "", n)[:6]) + r"~\d+" for n in names if len(re.sub(r"[\s.]", "", n)) > 6]
    parts = (["(?:" + "|".join(glued) + ")"] if glued else []) + \
        ([r"(?<![^\W_])(?:" + "|".join(alts) + r")(?![^\W_])"] if alts else [])  # a letter or digit is no boundary
    pat = re.compile(r"(?i)" + "|".join(parts))
    return lambda s: pat.sub(word, s)


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
    names = [r for r in (_name_rule(list(users) if users is not None else _users(homes), "<user>"),
                         _name_rule(list(machines) if machines is not None else _machines(), "<machine>")) if r]

    def rules(s: str, owner: bool) -> str:
        for rule in path_rules:
            s = rule(s)
        if not owner and names:
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


def audit(state_dir) -> list:
    """`halo audit privacy --replays`: every saved replay of this home (`<state>/replays/*.halo-replay`) checked by the
    audit's own rules (privacy_scan.scan_text_content) and for this machine's home path (any spelling), user name
    and machine name outside the owner's own text; `{kind, path, line, excerpt, commit}` rows, the value masked."""
    import json
    from halo_harness.live.replay_file import SUFFIX, replays_dir
    from halo_harness.privacy_scan import _masked_excerpt, scan_text_content
    homes = _homes()
    own = [(re.compile(_LEAD + src), "home-path") for src in filter(None, map(_prefix, homes))]
    own += [(re.compile(r"(?i)(?<![\w.-])" + re.escape(n) + r"(?![\w-])"), kind)
            for names, kind in ((_users(homes), "user-name"), (_machines(), "machine-name")) for n in names]
    folder = replays_dir(state_dir)
    out: list = []
    for path in sorted(folder.glob(f"*{SUFFIX}")) if folder.is_dir() else []:
        try:
            text = path.read_text(encoding="utf-8")
            data = json.loads(text)
        except (OSError, ValueError):
            continue
        rel = f"replays/{path.name}"
        rows = scan_text_content(text, rel_path=rel, allowlist=set())
        if isinstance(data, dict):  # the owner's own text (the title, the lineup's names) may name them
            text = json.dumps({k: v for k, v in data.items() if k not in OWNER_KEYS}, ensure_ascii=False, indent=0)
        for pat, kind in own:
            rows += [{"kind": kind, "line": text.count("\n", 0, m.start()) + 1,
                      "excerpt": _masked_excerpt(text, m.start(), m.end())} for m in pat.finditer(text)]
        for r in rows:  # an excerpt's context may hold another of them: masked too
            for pat, _kind in own:
                r["excerpt"] = pat.sub("<redacted>", r["excerpt"])
        out += [dict(r, path=rel, commit=None) for r in rows]
    return out
