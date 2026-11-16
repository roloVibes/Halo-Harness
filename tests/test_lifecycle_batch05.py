"""tests.test_lifecycle_batch05 -- one unreadable start time, an editor of the person's own, and the supervisor's
token in another locale (Halo 3.6.0.0, fix package "lifecycle" batch 5).

1. macOS: a model server's home watch that reads the server's start time as unreadable ONCE (a `ps` slower than its
   5 s limit while a large model loads) still stops the server when the home's last Halo goes; it used to give up and
   leave the server running. A Halo whose own start time is unreadable at its first look reads it once more.
2. Linux / macOS: an editor Halo opens for the person (Ctrl+E, `/mcp` e, `halo agents|workflows|maps edit`, `halo
   roles template edit`) is started without Halo's owner marker, so quitting Halo never ends it (a GUI editor with
   unsaved buffers); an environment built without the marker (`--tmux`, the editor) stays without it through
   subprocess_safe.
3. macOS: the supervisor's pulse token (proc_ident) is read in the C locale, so a reader in another locale names the
   same process (fixed in batch 4; this guards it).
Nothing here starts a process it does not end by its own handle; nothing is signalled.
Run: python -m tests.test_lifecycle_batch05
"""
from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path
from types import SimpleNamespace
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from tests.helpers.runner import Ctx, new_registry, print_results, run_all  # noqa: E402

test, TESTS = new_registry()
REPO = Path(__file__).resolve().parent.parent
MARK = "4242-abcdef0123"


# -- 1. one unreadable start time -------------------------------------------------------------------------------------

class _Server:
    """A model server the watch looks at: it runs until a signal reaches it; its start time is unreadable on the
    reads named in `blind` (1-based call numbers)."""

    def __init__(self, start: str, blind=()):
        self.start, self.blind, self.reads, self.running, self.signals = start, set(blind), 0, True, []

    def start_time(self, pid):
        self.reads += 1
        return None if (self.reads in self.blind or not self.running) else self.start

    def pid_running(self, pid):
        return self.running

    def signal(self, pid, hard=False):
        self.signals.append("KILL" if hard else "TERM")
        self.running = False


def _watch_patches(srv: _Server):
    from halo_harness import children as C
    from halo_harness import closing
    from halo_harness import closing_home_watch as W
    return [mock.patch.object(C, "start_time", srv.start_time), mock.patch.object(C, "pid_running", srv.pid_running),
            mock.patch.object(closing, "_signal_tree", srv.signal), mock.patch.object(W, "halos_alive", lambda *a: False),
            mock.patch.object(W.time, "sleep", lambda s: None)]


class _Patched:
    def __init__(self, patches):
        self.patches = patches

    def __enter__(self):
        for p in self.patches:
            p.start()
        return self

    def __exit__(self, *exc):
        for p in reversed(self.patches):
            p.stop()


@test
def test_a_home_watch_that_cannot_read_the_server_once_still_stops_it(ctx: Ctx):
    from halo_harness import closing_home_watch as W
    # reads 1 and 2: the watch's two looks while the home's last halo is gone; read 3: the proof before the signal
    srv = _Server("ps:Sun Nov 15 10:00:00 2026", blind=(3,))
    with _Patched(_watch_patches(srv)):
        rc = W.main(["state", "4343", srv.start, "1", "", ""])
    ctx.check(f"the watch returned {rc} and the server got {srv.signals} (it must be stopped, not left running)",
              rc == 0 and srv.signals[:1] == ["TERM"] and not srv.running)


@test
def test_a_server_whose_start_time_is_never_readable_is_never_signalled(ctx: Ctx):
    from halo_harness import closing_home_watch as W
    srv = _Server("ps:Sun Nov 15 10:00:00 2026", blind=range(1, 99))
    with _Patched(_watch_patches(srv)):
        W._end_server(4343, srv.start)
    ctx.check(f"no proof, no signal: got {srv.signals}", srv.signals == [])
    other = _Server("ps:Mon Nov  9 08:00:00 2026")
    with _Patched(_watch_patches(other)):
        W._end_server(4343, "ps:Sun Nov 15 10:00:00 2026")
    ctx.check(f"a pid that is another process now is not signalled: got {other.signals}", other.signals == [])


@test
def test_a_halo_reads_its_own_start_time_again_when_the_first_look_fails(ctx: Ctx):
    from halo_harness import closing
    answers = iter([None, "ps:Sun Nov 15 10:00:00 2026"])
    saved = {k: closing._STATE.get(k) for k in ("me_pid", "me_start")}
    try:
        closing._STATE["me_pid"] = None
        with mock.patch.object(closing, "_start", lambda pid: next(answers, None)), \
                mock.patch.object(closing.time, "sleep", lambda s: None):
            pid, start = closing.me()
    finally:
        closing._STATE.update(saved)
    ctx.check(f"the start time this halo keeps for its life: {start!r}", start == "ps:Sun Nov 15 10:00:00 2026")


@test
def test_a_home_watch_is_given_the_server_start_time_read_again_after_one_failed_look(ctx: Ctx):
    from halo_harness import closing
    from halo_harness import subprocess_safe as sp
    answers = iter([None, "ps:Sun Nov 15 10:00:00 2026"])
    started = []

    def popen(argv, **kw):  # nothing is started: the watch's command line is what is checked
        started.append(argv)
        return SimpleNamespace(pid=999999)
    with mock.patch.object(closing, "_start", lambda pid: next(answers, None)), \
            mock.patch.object(closing, "me", lambda: (1, "ps:me")), \
            mock.patch.object(closing.time, "sleep", lambda s: None), mock.patch.object(sp, "Popen", popen):
        try:
            closing.start_home_watch(SimpleNamespace(pid=4646), Path("state"))
        except Exception:
            pass  # what follows the spawn (the watch's own start time, the registry) is not this test's
    argv = started[0] if started else []
    ctx.check(f"the watch is told the server's start time, got {argv[5:6]}", argv[5:6] == ["ps:Sun Nov 15 10:00:00 2026"])


# -- 2. an editor of the person's own -----------------------------------------------------------------------------

def _child_marker(env) -> str:
    from halo_harness import subprocess_safe as sp
    out = sp.run([sys.executable, "-c", "import os; print(os.environ.get('HALO_OWNER', '-'))"], env=env,
                 capture_output=True, text=True, timeout=60)
    return out.stdout.strip()


@test
def test_an_environment_built_without_the_marker_stays_without_it(ctx: Ctx):
    from halo_harness import closing
    with mock.patch.dict(os.environ, {closing.MARKER: MARK}):
        scrubbed = _child_marker(closing.scrubbed_env())
        built = _child_marker({k: v for k, v in os.environ.items() if k != closing.MARKER})
    ctx.check(f"a scrubbed environment (--tmux, an editor) reaches the child without the marker, got {scrubbed!r}",
              scrubbed == "-")
    ctx.check(f"a caller's own environment still carries this tree's marker, got {built!r}", built == MARK)


class _Call:
    def __init__(self):
        self.envs = []

    def __call__(self, *a, **kw):
        self.envs.append(kw.get("env"))
        return SimpleNamespace(returncode=0) if "shell" in kw else 0


def _unmarked(env) -> bool:
    from halo_harness import closing
    return isinstance(env, dict) and closing.MARKER not in env and closing.WATCH not in env


@test
def test_every_editor_halo_opens_starts_without_the_owner_marker(ctx: Ctx):
    from halo_harness import closing, crew_cli_parts, roles_cli
    from halo_harness import subprocess_safe as sp
    from halo_harness.tui import app as tui_app
    from halo_harness.tui.dialogs import mcp_status
    got = {}
    with mock.patch.dict(os.environ, {closing.MARKER: MARK, closing.WATCH: "1:x", "EDITOR": "gedit"}):
        os.environ.pop("VISUAL", None)
        call = _Call()
        with mock.patch.object(roles_cli.subprocess, "call", call):
            roles_cli._run_editor("gedit", Path("t.json"), label="t")
        got["halo roles template edit"] = call.envs[-1]
        call = _Call()
        from halo_harness.crew import store
        with mock.patch.object(store, "find", lambda *a, **k: (Path("w.yaml"), "user")), \
                mock.patch.object(crew_cli_parts.subprocess, "call", call), \
                mock.patch.object(crew_cli_parts.sys.stdin, "isatty", lambda: True):
            crew_cli_parts.edit("workflow", "w", Path("."))
        got["halo workflows edit"] = call.envs[-1]
        # Ctrl+E and /mcp e: the methods run against a stand-in for the app (no terminal is taken over)
        call = _Call()

        class _Susp:
            def __enter__(self):
                return self

            def __exit__(self, *e):
                return False
        fake_app = SimpleNamespace(prompt_input=SimpleNamespace(text="draft", document=SimpleNamespace(end=0),
                                                                move_cursor=lambda *a: None),
                                   suspend=_Susp, notify=lambda *a, **k: None, _enter_suspend_for_editor=lambda: None,
                                   _exit_suspend_for_editor=lambda: None, cwd=".")
        with mock.patch.object(sp, "run", call):
            tui_app.BridgeApp.action_open_editor(fake_app)
            got["Ctrl+E"] = call.envs[-1] if call.envs else None
            from halo_harness import mcp_cli
            screen = SimpleNamespace(app=fake_app, _set_hint=lambda *a: None, _run_action_async=lambda *a, **k: None,
                                     _reconnect=None)
            with mock.patch.object(mcp_cli, "locate_server_source", lambda *a, **k: (Path("m.json"), 3)):
                mcp_status.McpStatus._edit_with_external_editor(screen, "srv", SimpleNamespace(scope="project"), "gedit")
            got["/mcp e"] = call.envs[-1] if len(call.envs) > 1 else None
    for where, env in got.items():
        ctx.check(f"{where}: the editor's environment carries no owner marker", _unmarked(env))


# -- 3. the supervisor's token in another locale --------------------------------------------------------------------

@test
def test_macos_a_pulse_token_reads_the_same_in_every_locale(ctx: Ctx):
    from halo_harness import bg_run
    from halo_harness.remote import proc_ident
    pid = 4545

    def ps(argv, **kw):  # Apple's ps prints lstart with strftime %c in the caller's LC_ALL / LC_TIME / LANG
        env = kw.get("env") or os.environ
        loc = env.get("LC_ALL") or env.get("LC_TIME") or env.get("LANG") or "C"
        when = "Sun Nov 15 10:00:00 2026" if loc in ("C", "POSIX", "en_US.UTF-8") else "So 15 Nov 10:00:00 2026"
        cols = [a for a in argv if a.endswith("=")]
        out = " ".join(("S" if c == "stat=" else when) for c in cols if c in ("stat=", "lstart="))
        return subprocess.CompletedProcess(argv, 0, out + "\n", "")
    tokens = []
    for lang in ("", "de_DE.UTF-8"):
        getattr(bg_run, "_PS_SEEN", {}).clear()
        env = {k: v for k, v in os.environ.items() if k not in ("LC_ALL", "LC_TIME", "LANG")}
        if lang:
            env["LANG"] = lang
        with mock.patch.dict(os.environ, env, clear=True), mock.patch.object(bg_run.subprocess, "run", ps):
            tokens.append(proc_ident._ps_token(pid))
    getattr(bg_run, "_PS_SEEN", {}).clear()
    ctx.check(f"a launchd supervisor's token and a German terminal's read are one: {tokens}",
              tokens[0] and tokens[0] == tokens[1])


if __name__ == "__main__":
    ctx = Ctx()
    results, passed, failed, skipped = run_all(TESTS, ctx)
    sys.exit(print_results(results, passed, failed, skipped))
