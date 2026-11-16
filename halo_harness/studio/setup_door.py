"""halo_harness.studio.setup_door -- the doors into Studio's Setup section
(Halo 3.3.0.0 R4, "Setup is Studio": `halo init` opens Studio on Setup).

A setup target names the page and, optionally, the block whose page opens:

    SetupTarget()                 Setup                     ?mode=setup
    SetupTarget(first=True)       Setup, the first run      ?mode=setup&first=1   (`halo init`, `halo start`
                                                                                  with no provider: 3.3.1.0 R1 opens
                                                                                  nothing on its own, the rail's
                                                                                  line says "set up this box")
    SetupTarget(block="team")     Setup, the Team page      ?mode=setup&block=team (`halo setup team`, `/setup`)
    SetupTarget(block="pack:<id>:<block>")   a pack's own block (3.3.11.0 R3, `halo setup <pack>`)

It travels as an edit-target text (`setup`, `setup:first`, `setup:team`), so
`halo studio --edit setup:team`, the detached Studio's argv and
`launch.url_from_info` all carry it (studio/edit_target.py hands the `setup`
kind to `parse` here); a Studio page already open gets it as a `focus` frame
`{edit: "", mode: "setup", block, first}` (ui/src/routes/setup/door.ts).

`open_setup` starts or reuses Studio and opens the browser on it; when no
browser can open here (`HALO_NO_BROWSER`, `SSH_CONNECTION`, Linux with no
`DISPLAY` / `WAYLAND_DISPLAY`, or `webbrowser.open` answering False) the
answer says so and carries the URL. `cli_door` prints the one line a command
prints and returns True when the browser has Setup; on False the caller runs
the terminal wizard (`halo init`, `halo setup`, `halo start`).
"""

from __future__ import annotations

import os
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Optional
from urllib.parse import urlsplit

# The page's blocks by the word a door uses (each is a step's page, routes/setup/pages.ts stepOf); `roles` is the Team block's old name.
BLOCKS = ("providers", "local", "model", "permissions", "theme", "team", "linux", "check")  # 3.5.0.0: no Machines
ALIASES = {"roles": "team", "map": "team"}  # 3.6.0.0 R5 fix: `map` is the page's name now, `team` its block id
BLOCK_TITLES = {"providers": "Providers", "local": "Local models", "model": "Default model", "permissions": "Permissions",
                "theme": "Theme", "team": "Team", "linux": "Linux fixes", "check": "Check"}


@dataclass(frozen=True)
class SetupTarget:
    block: str = ""
    first: bool = False

    @property
    def mode(self) -> str:
        return "setup"

    @property
    def text(self) -> str:
        """The edit-target text: `setup`, `setup:first` or `setup:<block>`."""
        if self.block:
            return f"setup:{self.block}"
        return "setup:first" if self.first else "setup"

    @property
    def display(self) -> str:
        if self.block.startswith("pack:"):  # 3.3.11.0 R3: a pack's own block
            pack_id, _sep, block_id = self.block[len("pack:"):].partition(":")
            return f"Setup ({pack_id}: {block_id})"
        return f"Setup ({BLOCK_TITLES[self.block]})" if self.block in BLOCK_TITLES else "Setup"

    @property
    def verb(self) -> str:
        return "use"

    @property
    def cli(self) -> str:
        return f"halo studio --edit {self.text}"

    def query(self) -> str:
        return "?mode=setup" + ("&first=1" if self.first else "") + (f"&block={self.block}" if self.block else "")

    def focus(self) -> dict:
        """The `focus` frame's data, and POST /api/focus's body."""
        return {"edit": "", "mode": "setup", "session": "", "block": self.block, "first": bool(self.first)}


def block_word(word: str) -> "tuple[Optional[str], str]":
    """`(block, '')` for a block word ('' = the whole page), or `(None, why)`."""
    w = (word or "").strip().lower()
    w = ALIASES.get(w, w)
    if not w or w in BLOCKS:
        return w, ""
    from halo_harness.packs.manifest_setup import split_key  # 3.3.11.0 R3: a pack's own block, pack:<id>:<block>
    if split_key(w)[0]:
        return w, ""
    return None, f"{word!r} is not a Setup block: use one of {', '.join(BLOCKS)} (roles = team) or pack:<id>:<block>"


def parse(text: str) -> "tuple[Optional[SetupTarget], str]":
    """`setup`, `setup:first` or `setup:<block>` -> the target; `(None, why)` for anything else."""
    kind, _sep, rest = (text or "").strip().partition(":")
    if kind.strip().lower() != "setup":
        return None, f"{text!r} is not a Setup target"
    rest = rest.strip().lower()
    if rest == "first":
        return SetupTarget(first=True), ""
    block, why = block_word(rest)
    return (SetupTarget(block=block), "") if block is not None else (None, why)


def no_browser_reason(env: "Optional[dict]" = None, platform: Optional[str] = None) -> str:
    """Why no browser can open on this box ('' when one may): the same rule for every door."""
    env = os.environ if env is None else env
    platform = sys.platform if platform is None else platform
    if (env.get("HALO_NO_BROWSER") or "").strip() not in ("", "0"):
        return "HALO_NO_BROWSER is set"
    if env.get("SSH_CONNECTION") or env.get("SSH_TTY"):
        return "this is an SSH session"
    if platform.startswith("linux") and not (env.get("DISPLAY") or env.get("WAYLAND_DISPLAY")):
        return "no DISPLAY or WAYLAND_DISPLAY"
    return ""


def _in_the_terminal(browser, wb) -> bool:
    """lynx, w3m, links, www-browser (GenericBrowser) and elinks run in the foreground on this very terminal."""
    elinks = getattr(wb, "Elinks", None)
    return type(browser) is wb.GenericBrowser or (isinstance(elinks, type) and isinstance(browser, elinks))


def open_in_a_window(url: str, *, env: "Optional[dict]" = None, platform: Optional[str] = None, wb=None) -> bool:
    """Every door's browser (closing.open_url): nothing when `no_browser_reason` says so; else Python's browsers in
    their order, never one that would take this terminal (Python registers text browsers whenever TERM is set and
    runs them in the foreground, over a full-screen session) unless the person named it in BROWSER. True when one
    took the URL; False and the caller prints the address."""
    if no_browser_reason(env, platform):
        return False
    import webbrowser
    wb = webbrowser if wb is None else wb
    env = os.environ if env is None else env
    if (sys.platform if platform is None else platform) not in ("win32", "darwin"):
        from halo_harness.studio.open_link import once_link  # fx studio batch 2: no key on a readable command line
        url = once_link(url)
    try:
        wb.get()  # registers the standard browsers once
    except wb.Error:
        return False
    entries = [c.strip() for c in (env.get("BROWSER") or "").split(os.pathsep) if c.strip()]
    named = {c.lower() for c in entries}
    order = getattr(wb, "_tryorder", None)  # Python's own try order (webbrowser.open walks it the same way)
    names = list(order) if isinstance(order, list) else [None]
    if named:  # fx jb3: BROWSER named programs: only those, never another browser in their place (closing.open_url)
        names = [n for n in names if str(n).lower() in named] or entries
    posix = (sys.platform if platform is None else platform) != "win32"
    from halo_harness import closing
    for name in names:
        if closing.stop_asked():  # fx jb3: Studio closed before its browser opened: no browser after a stop
            return False
        try:
            try:
                browser = wb.get(name)
            except wb.Error:
                if not named:
                    raise
                browser = wb.GenericBrowser(name)  # a named program webbrowser never registered (BROWSER set late)
            if not (named or not _in_the_terminal(browser, wb)):
                continue
            if posix and type(browser) is wb.GenericBrowser and not _a_text_browser(browser):
                if _own_session(browser, url):
                    return True
            elif browser.open(url):
                return True
        except Exception:
            continue
    return False


_TEXT_BROWSERS = ("lynx", "w3m", "links", "elinks", "www-browser")


def _a_text_browser(browser) -> bool:
    return os.path.basename(str(getattr(browser, "name", ""))).lower() in _TEXT_BROWSERS


def _own_session(browser, url: str) -> bool:
    """fx jb3: a program BROWSER names, run as Python's GenericBrowser runs it (its args, %s the URL, True when it
    exits 0) but in its own session: the terminal's Ctrl+C never reaches it, and it carries no Halo marker."""
    from halo_harness import closing
    from halo_harness import subprocess_safe as sp
    cmd = [browser.name] + [str(a).replace("%s", url) for a in (getattr(browser, "args", None) or ["%s"])]
    with closing.without_marker():
        proc = sp.Popen(cmd, close_fds=True, start_new_session=True, env=closing.scrubbed_env())
    return proc.wait() == 0


def _state_dir() -> Path:
    from halo_harness.providers.config import default_state_dir
    return Path(default_state_dir())


def open_setup(target: SetupTarget, *, cwd=None, state_dir=None, why: Optional[str] = None,
               timeout: float = 45.0, own: bool = False) -> dict:  # launch.START_S
    """`{"url", "how": focused|opened|started|printed|failed, "pages", "target", "why"}`: Studio on Setup.

    A Studio already running for this home is reused (its open pages take the `focus` frame, else the browser
    opens the URL); none: one starts in the background (`launch_detached`, no browser of its own) and this
    process opens the browser, so a browser that cannot open is known here. `why` (default `no_browser_reason()`)
    set: Studio is found or started and only the URL is the answer. `own` (3.6.0.0 R10, `halo init`): only a Studio
    this process started counts as running -- a launch never attaches to a server it did not start (closing.py)."""
    from halo_harness.studio import edit_open, launch
    state_dir = Path(state_dir) if state_dir is not None else _state_dir()
    cwd = Path(cwd) if cwd is not None else Path.cwd()
    why = no_browser_reason() if why is None else why
    found = launch.own_url if own else launch.existing_url
    running = edit_open._focus_in_process(target, publish=False) or found(state_dir, target.mode, target.text)
    other = None
    if not running and own:  # 3.6.0.0 R10 (judge item 3): a Studio whose owner is alive is used as it is, never adopted
        other = launch.live_owned(state_dir)
        running = launch.url_from_info(other, target.mode, target.text) if other else ""
    if running:
        out = edit_open.open_edit(target, cwd=cwd, state_dir=state_dir, open_browser=not why, timeout=timeout)
        if other:
            out["whose"] = launch.whose(other)
    else:
        url = launch.launch_detached(target.mode, cwd=cwd, state_dir=state_dir, open_browser=False, timeout=timeout,
                                     edit=target.text)
        how = "failed" if not url else ("printed" if why else ("started" if launch._open(url) else "printed"))
        from halo_harness import closing
        out = {"url": url, "how": how, "pages": 0, "target": target.display,
               "unsure": how == "started" and closing.open_unsure()}  # join: handed on, not seen to open
        if how == "failed":  # 3.6.0.0 R10: the child's exit code and its last line, every time
            out["why"] = launch.failure_line() or "it gave no address and no reason"
            out["target"] = target.display
            return out
    if out.get("how") == "printed" and not why:
        why = "no browser took the URL"
    out["why"] = why if out.get("how") == "printed" else ""
    out["target"] = target.display
    return out


def forward_hint(url: str) -> str:
    """The port-forward line `halo studio` prints, for this URL's port ('' when it has none)."""
    try:
        port = urlsplit(url).port
    except ValueError:
        port = None
    if not port:
        return ""
    return f"Over SSH: ssh -L {port}:127.0.0.1:{port} <host>, then open the same URL on your machine."


def cli_door(target: SetupTarget, *, terminal_cli: str, fallback: str, say: Callable[[str], None] = print,
             cwd=None, state_dir=None, wait: bool = False) -> bool:
    """A command's door: open Setup and print one line; True when the browser has it. False: the URL (with the
    port-forward hint) or why Studio did not start is printed, then `fallback` ("the terminal wizard runs here
    instead.") and the caller runs it. `wait` (3.3.3.0 R1, `halo init`): the one line also says the terminal
    waits for Setup's Done (halo_harness/init_wait.py); 3.3.15.0 R6: "This terminal starts halo when you press Done
    there (Ctrl+C: stop here; `halo` later starts it)." (init_wait.WAIT_LINE)."""
    try:
        out = open_setup(target, cwd=cwd, state_dir=state_dir, own=wait)
    except Exception as e:  # Studio could not be reached or started: the terminal path runs
        out = {"url": "", "how": "failed", "why": f"{type(e).__name__}: {e}"}
    url, how = out.get("url") or "", out.get("how")
    if out.get("whose") and url:  # 3.6.0.0 R10: whose Studio this is; leaving does not stop it
        say(f"Using the Studio already running for this home, {out['whose']}: it stays with that launch.")
    if how in ("focused", "opened", "started") and url:
        where = "in the Studio page already open" if how == "focused" else "in your browser"
        head = f"{target.display} is open {where}"
        if how != "focused" and out.get("unsure"):  # join: the browser start was handed on; Halo cannot know yet
            head = f"{target.display} is opening {where}; if nothing opens, open it yourself"
        if wait:  # 3.3.15.0 R6: the terminal stays and becomes the session (halo_harness/init_wait.py)
            from halo_harness.init_wait import WAIT_LINE
            say(WAIT_LINE.format(where=head, url=url))
        else:
            say(f"{head}: {url}. `{terminal_cli}` runs the terminal {fallback} instead.")
        if how == "started" and not wait:  # 3.6.0.0 R10: no detached Studio -- it runs while this command does
            from halo_harness.studio.launch import hold
            hold(state_dir if state_dir is not None else _state_dir(), say)
        return True
    if url:
        say(f"{target.display} is at {url} (no browser opens here: {out.get('why') or 'none answered'}).")
        hint = forward_hint(url)
        if hint:
            say(hint)
    else:
        say(f"Studio did not start{(': ' + out['why']) if out.get('why') else ''}.")
    say(f"The terminal {fallback} runs here instead.")
    return False
