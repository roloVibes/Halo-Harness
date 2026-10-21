"""tools/capture_identity.py -- one placeholder identity for every Studio
capture (Halo 3.1.7.0 R2: captures carry no real names). The repo is public
and its pictures are made on a real machine, so every capture tool draws the
same made-up harness, `you@studio`, and no absolute path from that machine.

* `begin()` first thing in a tool's main, before its scratch home is made:
  the temp root moves out of the user profile when it sits in one (Windows:
  `%ProgramData%\\halo-capture`; `HALO_CAPTURE_TMP` names another), and the
  harness's user and host read `you` and `studio`, so every home's default
  harness name is `you@studio` (the user@host fallback of fleet/identity.py).
* `placeholder(state)` before a tool serves Studio over `state` (or enters a
  rig): `fleet.name: you@studio` in the scoped home's config and in
  `<state>/config.json`, then every name Studio would draw (the harness name
  of the process and of `state`, its user and host) is checked against this
  machine's own user and host. One that carries either stops the tool with
  STOP_LINE and exit code 2.
* `guard(dom, page)` / `guard_page(c, page)` on every page a tool dumps or
  shoots: a home path (`Users\\`, `Users/`, `home/`), `AppData`, or this
  machine's user or host name in the DOM stops the tool with DOM_LINE and
  exit code 1. The DOM is read, never the pixels.
* `restore()` undoes `begin()` (the unit tests run in one process).
"""
from __future__ import annotations

import os
import re
import shutil
import socket
import tempfile
from pathlib import Path
from typing import Iterable, Optional

USER, HOST = "you", "studio"
NAME = f"{USER}@{HOST}"
STOP_LINE = ("capture stopped: Studio would draw this machine's own user or host name; "
             "every capture draws you@studio (tools/capture_identity.py)")
DOM_LINE = "capture stopped: the {page} page carries {what}: {near} (tools/capture_identity.py)"
PATHS = (("a home path", re.compile(r"Users[\\/]")), ("a home path", re.compile(r"(?<![A-Za-z0-9_])home/")),
         ("an AppData path", re.compile(r"AppData")))
# names a machine may carry that this repo's fixtures use on purpose, or that are ordinary words in Studio's text
# (a CI runner's account is `runner`; the Team bar says "no runner"): checked only in a user@ / path shape
SHAPE_ONLY = frozenset({"runner", "runneradmin", "root", "ubuntu", "vagrant", "docker", "desktop", "laptop", "server",
                        "computer", "workstation", "localhost", "local", USER, HOST})
_saved: dict = {}


def _placeholders() -> frozenset:
    try:
        from halo_harness.privacy_rules import PLACEHOLDER_HOME_NAMES
    except Exception:
        return frozenset({"user", "kali", "test"})
    return frozenset(PLACEHOLDER_HOME_NAMES)


def real_names() -> "tuple[tuple, str]":
    """(user names, host name) of this machine, read past begin()'s placeholder (the environment, not fleet_identity)."""
    users = {os.environ.get(k, "") for k in ("USER", "USERNAME", "LOGNAME")}
    try:
        import getpass
        users.add(getpass.getuser())
    except Exception:
        pass
    try:
        users.add(Path.home().name)
    except Exception:
        pass
    try:
        host = socket.gethostname().split(".")[0]
    except OSError:
        host = ""
    return tuple(sorted(u for u in users if u)), host


def _word(name: str) -> "re.Pattern":
    return re.compile(r"(?<![A-Za-z0-9])" + re.escape(name) + r"(?![A-Za-z0-9])", re.I)


def _checked(names: Iterable[str]) -> list:
    skip = _placeholders()
    return [n for n in names if n and len(n) >= 2 and n.lower() not in skip]


def check_names(names: Iterable[str], users: "Optional[Iterable[str]]" = None, host: "Optional[str]" = None) -> Optional[str]:
    """The first of `names` (what Studio would draw) that is this machine's `user@host` or carries its user or host
    name as a word; None when every one is a placeholder."""
    if users is None or host is None:
        users, host = real_names()
    users = list(users)
    real = {f"{u}@{host}".lower() for u in users}
    words = [_word(n) for n in _checked([*users, host or ""]) if n.lower() not in (USER, HOST)]  # the placeholder's own words
    for name in (str(n or "") for n in names):
        if name.lower() in real or any(w.search(name) for w in words):
            return name
    return None


def leaks(text: str, users: "Optional[Iterable[str]]" = None, host: "Optional[str]" = None) -> list:
    """[(what, position)] for every home path, AppData path or this machine's user or host name in `text`."""
    if users is None or host is None:
        users, host = real_names()
    found = [(what, m.start()) for what, rx in PATHS for m in [rx.search(text or "")] if m]
    for u in _checked(users):
        shapes = [r"(?<![A-Za-z0-9._-])" + re.escape(u) + "@", r"[\\/]" + re.escape(u) + r"(?=[\\/]|$|[\"'<\s])"]
        if u.lower() not in SHAPE_ONLY and len(u) >= 3:
            shapes.append(_word(u).pattern)
        for rx in shapes:
            m = re.search(rx, text or "", re.I)
            if m:
                found.append(("this machine's user name", m.start()))
                break
    for h in _checked([host or ""]):
        rx = "@" + re.escape(h) + r"(?![A-Za-z0-9-])" if h.lower() in SHAPE_ONLY or len(h) < 5 else _word(h).pattern
        m = re.search(rx, text or "", re.I)
        if m:
            found.append(("this machine's host name", m.start()))
    return found


def _masked(text: str, at: int, users, host) -> str:
    near = (text or "")[max(0, at - 30): at + 40].replace("\n", " ")
    for n in sorted(_checked([*users, host or ""]), key=len, reverse=True):
        near = re.sub(re.escape(n), "<user>" if n in users else "<host>", near, flags=re.I)
    return near


def guard(dom: str, page: str, users: "Optional[Iterable[str]]" = None, host: "Optional[str]" = None) -> None:
    """Stop the tool (exit 1, one line) when the DOM of `page` carries a real path or name (this machine's, unless
    `users` and `host` name others)."""
    if users is None or host is None:
        users, host = real_names()
    users = list(users)
    hits = leaks(dom, users, host)
    if hits:
        what, at = hits[0]
        print(DOM_LINE.format(page=page, what=what, near=_masked(dom, at, users, host)), flush=True)
        raise SystemExit(1)


def guard_page(c, page: str) -> None:
    """`guard` over the live page of a DevTools-protocol Chrome (tests/helpers/cdp.py)."""
    guard(str(c.js("document.documentElement.outerHTML") or ""), page)


def checked_dump(chrome, url: str, page: str, *extra: str):
    """One `--dump-dom` run of `url` (capture_studio.chrome), guarded; None without Chrome."""
    r = chrome(["--dump-dom", *extra, url])
    if r is not None:
        guard(r.stdout, page)
    return r


def _neutral_temp() -> Optional[Path]:
    """Where the capture's temp files go when the system temp sits in a user profile; None when it is neutral."""
    if os.environ.get("HALO_CAPTURE_TMP"):
        return Path(os.environ["HALO_CAPTURE_TMP"])
    if not leaks(tempfile.gettempdir()):
        return None
    if os.name == "nt":
        return Path(os.environ.get("ProgramData") or (os.environ.get("SystemDrive", "C:") + "\\ProgramData")) / "halo-capture"
    return Path("/tmp/halo-capture")


def begin() -> None:
    """The neutral temp root and the placeholder user and host, once per process (restore() undoes both)."""
    if "begun" in _saved:
        return
    from halo_harness.remote import fleet_identity as FI
    _saved.update(begun=True, user=FI._user, host=FI._host, tempdir=tempfile.tempdir)
    FI._user, FI._host = (lambda: USER), (lambda: HOST)
    base = _neutral_temp()
    if base is not None:
        base.mkdir(parents=True, exist_ok=True)
        own = tempfile.mkdtemp(prefix="studio-", dir=str(base))
        _saved.update(base=base, own=own)
        tempfile.tempdir = own
        import atexit
        atexit.register(restore)


def _write_name(state: Path) -> None:
    import json
    path = Path(state) / "config.json"
    try:
        data = json.loads(path.read_text(encoding="utf-8")) if path.is_file() else {}
    except (OSError, ValueError):
        data = {}
    data = data if isinstance(data, dict) else {}
    fleet = data.get("fleet") if isinstance(data.get("fleet"), dict) else {}
    data["fleet"] = {**fleet, "name": NAME}
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")


def drawn(states: Iterable = ()) -> list:
    """Every name Studio would draw for this harness: its name (the process's and each state's), user and host."""
    from halo_harness.fleet import identity
    me = identity.harness()
    names = [identity.fleet_name(), me.get("name"), me.get("user"), me.get("host")]
    for s in states:
        h = identity.harness(Path(s))
        names += [identity.fleet_name(Path(s)), h.get("name"), h.get("user"), h.get("host")]
    return [str(n) for n in names if n]


def placeholder(state=None) -> None:
    """`you@studio` in the scoped home's config and in `state`'s; stop (STOP_LINE, exit 2) when a drawn name is real."""
    if not (os.environ.get("BRIDGE_TEST_HOME") or os.environ.get("BRIDGE_STATE_DIR")):
        raise RuntimeError("capture_identity.placeholder runs after the scratch home is scoped (chrome_driver.scope_home)")
    begin()
    from halo_harness.fleet import identity
    from halo_harness.theme import set_config_value
    set_config_value("fleet.name", NAME)
    if state is not None:
        _write_name(Path(state))
    identity.forget_cache()
    if check_names(drawn([state] if state is not None else [])) is not None:
        print(STOP_LINE, flush=True)
        raise SystemExit(2)


def _writable(func, path, _exc) -> None:
    import stat
    try:
        os.chmod(path, stat.S_IWRITE)
        func(path)
    except OSError:
        pass


def restore() -> None:
    """Undo begin(): the real fleet_identity functions, the system temp root (the capture's own folder removed)."""
    if "begun" not in _saved:
        return
    from halo_harness.remote import fleet_identity as FI
    FI._user, FI._host = _saved["user"], _saved["host"]
    tempfile.tempdir = _saved["tempdir"]
    if _saved.get("own"):
        shutil.rmtree(_saved["own"], onerror=_writable)  # what a rig left: git keeps its objects read-only on Windows
        try:
            os.rmdir(_saved["base"])
        except OSError:
            pass  # another capture is using it
    _saved.clear()
