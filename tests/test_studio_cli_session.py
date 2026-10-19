"""tests.test_studio_cli_session -- `halo studio --session` and what the
Session dashboard needs from the server, without a browser (Halo 3.1.4.0 R2).

1. a section target and its URL: `?mode=session&session=<sid>#t=<token>`,
   `?mode=fleet`; `launch_detached` spawns `halo studio --session <sid>`;
2. the served page carries `data-live-session` (this harness's newest live
   session, '' when none): the page's landing rule reads it;
3. `POST /api/focus {mode, session}` puts the section's `focus` frame out;
   a bad section or session id is a 422;
4. `halo studio --session [<id>]`: with a Studio running it is focused or the
   URL printed (`--no-open`), the newest live session when no id is given, a
   prefix resolved, none live opens Session on its Start view and says so;
   `--edit` with `--session` is exit 2; with no Studio one is started;
5. the session row carries the status's turns and tokens (fleet/local_view.py).
The browser half is tests/test_studio_session.py; the TUI's /studio is
tests/test_slash_studio.py.
Run: python -m tests.test_studio_cli_session
"""
from __future__ import annotations

import contextlib
import json
import sys
import threading
from pathlib import Path
from types import SimpleNamespace

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from tests.helpers.runner import Ctx, new_registry, print_results, run_all  # noqa: E402
from tests.test_studio_edit_target import _out, _stub  # noqa: E402

test, TESTS = new_registry()
SID = "clisession00000000000000000000001"


@contextlib.contextmanager
def _studio(live: bool = True):
    """A fresh home (tests/helpers/fleet_rig.py), a session of it registered live when `live`, and a running Studio over it."""
    from halo_harness.controller import Controller
    from halo_harness.privateio import write_private_atomic
    from halo_harness.providers.config import default_state_dir
    from halo_harness.remote import runtime
    from halo_harness.studio.server import start_server, studio_info_path
    from tests.helpers.fake_remote_session import FakeRegistry, FakeSession
    from tests.helpers.fleet_rig import FleetRig
    with FleetRig() as rig:
        act = None
        if live:
            ctl = Controller(session=FakeSession(SID), cwd=rig.cwd, registry=FakeRegistry()).start()
            rig.controllers.append(ctl)
            act = runtime.start_for_controller(ctl)
        state = Path(default_state_dir())
        state.mkdir(parents=True, exist_ok=True)
        srv = start_server(port=0, cwd=rig.cwd, state_dir=state)
        threading.Thread(target=srv.serve_forever, daemon=True).start()
        write_private_atomic(studio_info_path(state), json.dumps({"pid": 0, "port": srv.server_address[1], "token": srv.token}))
        try:
            yield SimpleNamespace(rig=rig, state=state, srv=srv, act=act)
        finally:
            srv.shutdown()
            srv.server_close()


def _page(srv) -> str:
    import urllib.request
    with urllib.request.urlopen(f"http://127.0.0.1:{srv.server_address[1]}/", timeout=10) as resp:
        return resp.read().decode("utf-8")


@test
def test_the_section_target_and_its_url(ctx: Ctx):
    import io
    from halo_harness.studio import launch
    from halo_harness.studio.server import STUDIO_MODES, url_for
    from halo_harness.studio.session_open import SectionTarget, section_target
    fake = SimpleNamespace(server_address=("127.0.0.1", 4321), token="tok")
    ctx.check("Session is a Studio mode", "session" in STUDIO_MODES)
    ctx.check("url_for: the session in the query, the token in the fragment",
              url_for(fake, "session", SID) == f"http://127.0.0.1:4321/?mode=session&session={SID}#t=tok")
    ctx.check("without a session it is the section", url_for(fake, "session") == "http://127.0.0.1:4321/?mode=session#t=tok")
    t = SectionTarget("session", SID, "this session")
    ctx.check(f"the target names itself, got {t.display!r} {t.cli!r} {t.focus()}", t.display == "this session" and t.cli == f"halo studio --session {SID}"
              and t.focus() == {"edit": "", "mode": "session", "session": SID} and t.verb == "watch")
    f, _ = section_target("fleet", SID)
    ctx.check(f"/studio fleet is Fleet, no session, got {f}", f is not None and f.mode == "fleet" and f.text == "" and f.query() == "?mode=fleet")
    bad, why = section_target("kitchen")
    ctx.check(f"an unknown section says what it takes, got {why!r}", bad is None and "fleet" in why and "session" in why)
    argv = []

    class _P:
        stdout = io.StringIO(f"Halo Studio is at http://127.0.0.1:5/?mode=session&session={SID}#t=t\n")

        def poll(self):
            return None
    import tempfile
    home = Path(tempfile.mkdtemp(prefix="halo-session-launch-"))
    with _stub(launch.subprocess, "Popen", lambda a, **k: argv.append(a) or _P()):
        got = launch.launch_detached("session", cwd=home, state_dir=home / ".halo", open_browser=False, edit=SID, timeout=3)
    ctx.check(f"a background Studio is spawned with --session <sid>, got {argv}", argv and argv[0][argv[0].index("--session") + 1] == SID
              and "--edit" not in argv[0] and "--mode" not in argv[0])
    ctx.check(f"and its URL comes back, got {got!r}", got.endswith(f"session={SID}#t=t"))


@test
def test_the_page_carries_the_newest_live_session(ctx: Ctx):
    with _studio(live=True) as h:
        page = _page(h.srv)
        ctx.check(f"a session is live here: the page names it, got {page[:160]!r}", f'data-live-session="{h.act.session_id}"' in page and 'id="root"' in page)
    with _studio(live=False) as h:
        ctx.check("nothing live: the mark is empty", 'data-live-session=""' in _page(h.srv))


@test
def test_focus_takes_a_section_and_its_session(ctx: Ctx):
    from halo_harness.studio import launch
    from halo_harness.studio.events import bridge_for
    with _studio(live=False) as h:
        page = bridge_for(h.srv).subscribe("all")
        status, body = launch.api_call(h.state, "POST", "focus", {"mode": "session", "session": SID})
        frame = None
        for _ in range(50):
            frame = page.get(0.1)
            if frame and frame.get("event") == "focus":
                break
        ctx.check(f"200 with the pages open, got {status} {body}", status == 200 and body.get("pages") == 1 and body.get("mode") == "session")
        ctx.check(f"the frame names the section and the session, got {frame}", (frame or {}).get("data") == {"edit": "", "mode": "session", "session": SID})
        ctx.check("a section that is not one is a 422", launch.api_call(h.state, "POST", "focus", {"mode": "kitchen"})[0] == 422)
        ctx.check("a session for another section is a 422", launch.api_call(h.state, "POST", "focus", {"mode": "fleet", "session": SID})[0] == 422)
        ctx.check("an edit target still works", launch.api_call(h.state, "POST", "focus", {"edit": "team"})[0] == 200)
        bridge_for(h.srv).unsubscribe(page)


@test
def test_halo_studio_session(ctx: Ctx):
    from halo_harness.studio import launch
    from halo_harness.studio.server import cmd_studio
    rc, text = _out(cmd_studio, ["--edit", "team", "--session"])
    ctx.check(f"--edit with --session: exit 2, got {rc} {text!r}", rc == 2 and "pick one" in text)
    with _studio(live=True) as h, _stub(launch, "_open", lambda url: False):
        sid = h.act.session_id
        rc, text = _out(cmd_studio, ["--session", "--no-open"])
        ctx.check(f"no id: the newest live session, printed, got {rc} {text!r}", rc == 0 and f"?mode=session&session={sid}#t=" in text
                  and text.startswith("Studio is at") and "watch" in text)
        rc, text = _out(cmd_studio, ["--session", sid[:8], "--no-open"])
        ctx.check(f"a prefix resolves to the live session, got {text!r}", rc == 0 and f"session={sid}#t=" in text)
        rc, text = _out(cmd_studio, ["--session", sid])
        ctx.check(f"no page open, no browser: the URL is the answer, got {text!r}", rc == 0 and f"session={sid}#t=" in text)
        rc, text = _out(cmd_studio, ["--session", "nosuchsession", "--no-open"])
        ctx.check(f"a session not live here: chosen anyway, and said, got {text!r}", rc == 0 and "is not live on this harness" in text
                  and "session=nosuchsession#t=" in text)
    with _studio(live=False) as h, _stub(launch, "_open", lambda url: False):
        rc, text = _out(cmd_studio, ["--session", "--no-open"])
        ctx.check(f"none live: Session on its Start view, said, got {rc} {text!r}", rc == 0 and "no session is live on this harness" in text
                  and "?mode=session#t=" in text)
        (h.state / "studio.json").unlink()
        calls = []
        with _stub(launch, "launch_detached", lambda mode, **k: calls.append((mode, k)) or "http://127.0.0.1:1/?mode=session#t=t"), \
                _stub(launch, "existing_url", lambda *a, **k: ""):
            from halo_harness.studio.edit_open import open_edit
            from halo_harness.studio.session_open import SectionTarget
            r = open_edit(SectionTarget("session", SID), cwd=h.rig.cwd, state_dir=h.state)
        ctx.check(f"no Studio: one is started on Session, got {r} {calls}", r["how"] == "started" and calls and calls[0][0] == "session"
                  and calls[0][1].get("edit") == SID)


@test
def test_the_session_row_carries_turns_and_tokens(ctx: Ctx):
    from halo_harness.fleet.local_view import session_row
    row = session_row({"session_id": SID, "cwd": "/x", "started": 1.0},
                      {"turn": 4, "total_input_tokens": 1200, "total_output_tokens": 340, "context_tokens": 900, "context_limit": 200000,
                       "model": "or:mock/m", "cost_usd": 0.02}, [])
    ctx.check(f"turns, tokens and the context, got {row}", (row["turns"], row["tokens_in"], row["tokens_out"], row["context_tokens"], row["context_limit"])
              == (4, 1200, 340, 900, 200000))
    row = session_row({"session_id": SID}, None, None)
    ctx.check("a session that said nothing has None", row["turns"] is None and row["tokens_in"] is None)


if __name__ == "__main__":
    ctx = Ctx()
    results, passed, failed, skipped = run_all(TESTS, ctx)
    sys.exit(print_results(results, passed, failed, skipped))
