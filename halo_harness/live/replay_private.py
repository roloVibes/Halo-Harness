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
_LEAD = r"(?<![\w.~-])"  # a path starts here: not inside a word or another path
_TAIL = r"(?:(?P<sep>[\\/]+)(?P<rest>[^\s\"'`<>|;,]+)|(?![\w-]|\.\w))"
OWNER_KEYS = {"title", "plan"}  # the owner's own text (first words) and the names the owner gave the lineup's blocks
ID_KEYS = {"id", "session_id", "run_id", "format", "halo", "kind", "agent_id", "parent", "to", "state", "phase",
           "version", "upgraded_from"}


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


def _rule(path: str, short: str, long: str):
    src = _prefix(path)
    if not src:
        return None
    pat = re.compile(_LEAD + src + _TAIL)
    return lambda s: pat.sub(lambda m: long + re.sub(r"[\\/]+", "/", m.group("rest")) if m.group("sep") else short, s)


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
    if not names:
        return None
    pat = re.compile(r"(?i)(?<![\w.-])(?:" + "|".join(re.escape(n) for n in sorted(names, key=len, reverse=True)) + r")(?![\w-])")
    return lambda s: pat.sub(word, s)


_TOKEN = re.compile(r"(\s+|[\"'`(),;])")


def _relative_path(tok: str) -> bool:
    return ("/" in tok or "\\" in tok) and not re.match(r"^(?:~|[\\/]|[A-Za-z]:|<)", tok)


def scrub(payload, root=None, *, homes=None, users=None, machines=None):
    """The payload with its paths and names rewritten (see the module's doc); `root` is the project folder."""
    homes = list(homes) if homes is not None else _homes()
    path_rules = [r for r in [_rule(str(root), ".", "") if root else None]
                  + [_rule(h, "~", "~/") for h in sorted(homes, key=len, reverse=True)] if r]
    names = [r for r in (_name_rule(list(users) if users is not None else _users(homes), "<user>"),
                         _name_rule(list(machines) if machines is not None else _machines(), "<machine>")) if r]

    def text(s: str, owner: bool) -> str:
        for rule in path_rules:
            s = rule(s)
        if owner or not names:
            return s
        out = []
        for tok in _TOKEN.split(s):
            if tok and not _relative_path(tok):
                for rule in names:
                    tok = rule(tok)
            out.append(tok)
        return "".join(out)

    def walk(obj, owner: bool, key: str = ""):
        if isinstance(obj, str):
            return obj if key in ID_KEYS else text(obj, owner)
        if isinstance(obj, list):
            return [walk(v, owner, key) for v in obj]
        if isinstance(obj, dict):
            return {k: walk(v, owner or k in OWNER_KEYS, k) for k, v in obj.items()}
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
