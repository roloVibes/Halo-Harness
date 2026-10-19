"""halo_harness.tui.studio_open -- the terminal opens Studio on the thing to edit
(Halo 3.1.1.0 R3: Studio is the one editor of bios and lineups; the TUI shows
them read-only), and on the session you are in (3.1.4.0 R2: `/studio`).

`open_target(host, "bio:coder")` resolves the target (studio/edit_target.py,
a bare name too), then on a worker opens Studio on it, or focuses the Studio
already running for this home (studio/edit_open.py), and tells the user what
happened in one line: it opened the browser, or here is the URL. The read-only
views' `e`, `/edit`, `/agents edit`, `/teams edit`, the lists' "Edit in
Studio" buttons and the wizard's Team step all call it.

`open_section(host, "")` is the TUI's `/studio`: bare (or `session`) opens the
Session dashboard on this session (`?mode=session&session=<id>`, the id from
`this_session_id`); `/studio <section>` opens that section. Same opener, one
line: focused (a Studio page already open took it), opened, started, or the URL.

`new_bio` / `new_lineup` write a starter file (what "New" in a terminal list
does now) so that Studio has something to open.

`OPENER` is the one call that reaches Studio; tests replace it.
"""

from __future__ import annotations

import uuid
from pathlib import Path
from typing import Callable, Optional

from halo_harness.studio.edit_open import describe, open_edit

OPENER: Callable = open_edit


def _app(host):
    return getattr(host, "app", None) or host


def _default_line(host, line: str) -> None:
    try:
        _app(host).notify(line, title="Studio", timeout=12)
    except Exception:
        pass


def _open_on_worker(host, target, *, cwd, state_dir, say: Callable[[str], None], cli: str) -> None:
    """OPENER on a worker; its one line (or why Studio did not open) goes to `say`."""
    if state_dir is None:
        from halo_harness.providers.config import default_state_dir
        state_dir = default_state_dir()
    folder = Path(cwd) if cwd is not None else Path.cwd()

    def _work() -> None:
        try:
            line = describe(OPENER(target, cwd=folder, state_dir=Path(state_dir)))
        except Exception as e:  # Studio could not be reached or started: say so, keep the session
            line = f"Studio did not open: {type(e).__name__}: {e}. Run `{cli}` in a shell."
        try:
            _app(host).call_from_thread(say, line)
        except Exception:
            say(line)
    from halo_harness.tui.worker_guard import guarded_worker
    guarded_worker(host, _work, thread=True, name="studio-edit", group="studio-edit")


def open_target(host, text: str, *, cwd=None, state_dir=None, on_line: Optional[Callable[[str], None]] = None) -> bool:
    """Start opening `text` in Studio; False (and the reason shown) when it is not an edit target."""
    from halo_harness.studio.edit_target import resolve
    say = on_line or (lambda line: _default_line(host, line))
    target, why = resolve(text, cwd=cwd, state_dir=state_dir)
    if target is None:
        say(why)
        return False
    say(f"Opening {target.text} in Studio...")
    _open_on_worker(host, target, cwd=cwd, state_dir=state_dir, say=say, cli=f"halo studio --edit {target.text}")
    return True


def this_session_id(host) -> str:
    """The session this terminal runs: its control socket's id (kept fresh after /clear), else its log's."""
    controller = getattr(_app(host), "controller", None)
    if controller is None:
        return ""
    try:
        from halo_harness.remote import runtime
        for act in runtime.actives():
            if act.controller is controller:
                return str(act.session_id or "")
    except Exception:
        pass
    try:
        return str(controller.session.log.session_id or "")
    except Exception:
        return ""


def open_section(host, word: str = "", *, cwd=None, state_dir=None, on_line: Optional[Callable[[str], None]] = None) -> bool:
    """`/studio [<section>]`: Studio on this session (bare) or on that section; one line says what happened."""
    from halo_harness.studio.session_open import section_target
    say = on_line or (lambda line: _default_line(host, line))
    target, why = section_target(word, this_session_id(host))
    if target is None:
        say(why)
        return False
    _open_on_worker(host, target, cwd=cwd, state_dir=state_dir, say=say, cli=target.cli)
    return True


def new_bio(*, cwd=None, state_dir=None, extends: Optional[str] = None, name: Optional[str] = None,
            preference: str = "") -> "tuple[str, list[str]]":
    """A starter bio (`agent-<hex>`, or `<extends>-child` extending that bio; `preference`: its model
    to start from): `(name, problems)`."""
    from halo_harness.agents_yaml import find_agent_bio_path, save_agent_bio
    name = name or (f"{extends}-child" if extends else f"agent-{uuid.uuid4().hex[:6]}")
    if extends and find_agent_bio_path(name, cwd=cwd, state_dir=state_dir):
        name = f"{extends}-child-{uuid.uuid4().hex[:4]}"
    data = {"description": "", **({"extends": extends} if extends else {}),
            **({"models": {"preference": preference}} if preference else {})}
    ok, problems = save_agent_bio(name, data, cwd=cwd, state_dir=state_dir)
    return (name, []) if ok else ("", problems)


def new_lineup(*, cwd=None, state_dir=None, name: Optional[str] = None) -> "tuple[str, list[str]]":
    """A starter lineup (`lineup-<hex>`): `(name, problems)`."""
    from halo_harness.teams_yaml import new_team_template_from_template
    name = name or f"lineup-{uuid.uuid4().hex[:6]}"
    ok, problems = new_team_template_from_template(name, None, cwd=cwd, state_dir=state_dir)
    return (name, []) if ok else ("", problems)
