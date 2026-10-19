"""tests.test_slash_studio -- `/studio` in the terminal (Halo 3.1.4.0 R2): bare
`/studio` opens Studio on the session you are in (the Session dashboard,
`mode=session` and this session's id) through tui/studio_open.py ->
studio/edit_open.py `open_edit`, and says in one line what happened: the
Studio page already open took it (focused), the browser opened it, or here is
the URL; `/studio <section>` opens that section; `/studio ... url` stays the
builtin that prints the URL; `/roles`, `/org`, `/edit` keep their handlers.
`this_session_id` is the control socket's id, else the session log's. The CLI
twin `halo studio --session` is tests/test_studio_cli_session.py.
Run: python -m tests.test_slash_studio
"""
from __future__ import annotations

import asyncio
import contextlib
import sys
from pathlib import Path
from types import SimpleNamespace

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from tests.helpers.provider_env_defaults import ensure_scoped_state_dir_once  # noqa: E402

ensure_scoped_state_dir_once()

from tests.helpers.runner import Ctx, new_registry, print_results, run_all  # noqa: E402
from tests.test_studio_edit_target import _stub  # noqa: E402

test, TESTS = new_registry()
SID = "tuisession000000000000000000000001"


class _App:
    """What tui/slash.py and tui/studio_open.py touch on the app; workers run at once."""

    def __init__(self, sid: str = SID):
        self.controller = SimpleNamespace(session=SimpleNamespace(log=SimpleNamespace(session_id=sid)), slashes=[],
                                          run_slash=lambda name, args: self.controller.slashes.append((name, args)) or f"{name} {args}")
        self.cwd = Path.cwd()
        self.lines: list = []
        self.notes: list = []
        self.transcript = SimpleNamespace(add_note=lambda text, kind="note": self.notes.append(text))

    def call_later(self, fn, *a, **k):
        self.lines.append(a[0])

    def call_from_thread(self, fn, *a, **k):
        return fn(*a, **k)

    def run_worker(self, work, **kw):
        return work()

    def notify(self, text, **kw):
        self.lines.append(text)


@contextlib.contextmanager
def _opener(how: str = "focused", pages: int = 1):
    """The real open_edit over a Studio that answers: its URL from studio.json, `pages` open to take the focus."""
    from halo_harness.studio import edit_open, launch, server as S
    from halo_harness.tui import studio_open
    targets = []

    def opener(target, **kw):
        targets.append(target)
        return edit_open.open_edit(target, **kw)
    url = lambda state_dir, mode=None, edit=None: "http://127.0.0.1:9/" + launch._query(mode, edit) + "#t=tok"  # noqa: E731
    api = lambda state_dir, method, path, body=None, timeout=5.0: (200, {"pages": pages, **(body or {})})  # noqa: E731
    with _stub(studio_open, "OPENER", opener), _stub(launch, "existing_url", url), _stub(launch, "api_call", api), \
            _stub(launch, "_open", lambda u: how == "opened"):
        saved = S._BACKGROUND.pop("server", None)
        try:
            yield targets
        finally:
            if saved is not None:
                S._BACKGROUND["server"] = saved


def _slash(app, name: str, args: str) -> None:
    from halo_harness.tui.slash import handle_slash
    asyncio.run(handle_slash(app, name, args))


@test
def test_bare_studio_opens_this_session(ctx: Ctx):
    app = _App()
    with _opener("focused") as targets:
        _slash(app, "studio", "")
    t = targets[0] if targets else None
    ctx.check(f"the opener got mode=session and this session's id, got {t}", t is not None and t.mode == "session" and t.session == SID)
    ctx.check(f"one line: focused in the open page, with the URL, got {app.lines}", len(app.lines) == 1
              and app.lines[0].startswith("Opened this session in the Studio page already open")
              and f"?mode=session&session={SID}#t=" in app.lines[0])
    app = _App()
    with _opener("printed", pages=0) as targets:
        _slash(app, "studio", "session")
    ctx.check(f"/studio session is the same; no page, no browser: here is the URL, got {app.lines}", len(app.lines) == 1
              and app.lines[0].startswith("Studio is at http") and "(open it to watch this session)" in app.lines[0]
              and targets and targets[0].session == SID)
    app = _App()
    with _opener("opened", pages=0):
        _slash(app, "studio", "")
    ctx.check(f"no page open: the browser opened it, got {app.lines}", len(app.lines) == 1 and app.lines[0].startswith("Opened this session in Studio in your browser"))


@test
def test_studio_section_opens_that_section(ctx: Ctx):
    app = _App()
    with _opener("focused") as targets:
        _slash(app, "studio", "fleet")
    t = targets[0] if targets else None
    ctx.check(f"/studio fleet: mode=fleet, no session, got {t}", t is not None and t.mode == "fleet" and t.text == "")
    ctx.check(f"its line names Fleet, got {app.lines}", len(app.lines) == 1 and app.lines[0].startswith("Opened Fleet in the Studio page")
              and "?mode=fleet#t=" in app.lines[0])
    for word in ("orchestra", "roles", "org", "design", "flow", "team"):
        app = _App()
        with _opener("focused") as targets:
            _slash(app, "studio", word)
        ctx.check(f"/studio {word} opens {word}", targets and targets[0].mode == word)
    app = _App()
    with _opener() as targets:
        _slash(app, "studio", "kitchen")
    ctx.check(f"an unknown section says what /studio takes and opens nothing, got {app.lines}",
              not targets and len(app.lines) == 1 and "session" in app.lines[0] and "fleet" in app.lines[0])


@test
def test_studio_url_stays_the_builtin(ctx: Ctx):
    app = _App()
    with _opener() as targets:
        _slash(app, "studio", "url")
        _slash(app, "studio", "fleet url")
    ctx.check(f"`url` goes to the builtin (it prints the URL), got {app.controller.slashes}",
              app.controller.slashes == [("studio", "url"), ("studio", "fleet url")] and not targets)


@test
def test_this_session_id_is_the_sockets_then_the_logs(ctx: Ctx):
    from halo_harness.remote import runtime
    from halo_harness.tui.studio_open import this_session_id
    app = _App("fromthelog0000000000000000000001")
    ctx.check("no control socket: the session log's id", this_session_id(app) == "fromthelog0000000000000000000001")
    act = SimpleNamespace(controller=app.controller, session_id="fromthesocket000000000000000001")
    with _stub(runtime, "actives", lambda: [SimpleNamespace(controller=object(), session_id="other"), act]):
        ctx.check("its control socket's id (kept fresh after /clear)", this_session_id(app) == "fromthesocket000000000000000001")
    ctx.check("no controller: ''", this_session_id(SimpleNamespace()) == "")


@test
def test_studio_is_in_the_completion_list_and_the_handlers_stay(ctx: Ctx):
    from halo_harness.commands.builtins import _BUILTIN_SPECS
    from halo_harness.tui import slash
    spec = _BUILTIN_SPECS.get("studio")
    ctx.check(f"/studio is a builtin the completion lists, naming session first, got {spec[:3] if spec else None}",
              spec is not None and str(spec[2]).startswith("[session|") and "this session" in spec[1])
    src = Path(slash.__file__).read_text(encoding="utf-8")
    ctx.check("the TUI handles /studio itself", '"studio": _handle_studio' in src)
    ctx.check("/roles, /org and /edit keep their handlers",
              '"roles": _handle_roles' in src and '"org": _handle_org' in src and '"edit": _handle_edit' in src)


if __name__ == "__main__":
    ctx = Ctx()
    results, passed, failed, skipped = run_all(TESTS, ctx)
    sys.exit(print_results(results, passed, failed, skipped))
