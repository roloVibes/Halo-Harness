"""tests.test_steward_off -- Halo 3.6.0.0 R13: the Ollama steward's background job is OFF unless a person turns it on.

The owner's laptop sat near one full CPU core on the steward's threads (`halo-steward-watch`, `halo-steward-timer`,
`halo-local-resources`). His rule: an option to turn the steward on and off, nothing always on draining resources.

1. The switch's value: a fresh config and one that never set `ollama.steward.job` both mean off; `true` stays on;
   anything else (false, "yes", 1) is off.
2. A Studio and a session in a scratch home, background reads ALLOWED (the tests' usual switch that stops every
   background job is lifted here, so only the steward's own switch keeps it off): no thread of the steward exists,
   and the process sits under 2% of one core over 20 s idle.
3. Settings' switch (the API the Studio page calls) turns it on -- its threads appear -- and off: every thread is
   JOINED within the bound before the answer comes back, the answer names any still alive (none), no restart.
   `halo config set ollama.steward.job true|false` does the same through the Studio's files watcher; the test waits
   on the sync's own result (`steward_synced`), never on a pause.
4. Off, what read its findings says so in one line: the status lines (Local -> Steward, Settings, `halo ollama steward
   status`), the API's `on`/`off_line`, the doctor's server-log rows; the TUI starts no poll of its notes.
The sampler reads a fake machine (resources.SAMPLER_SEAMS), the Ollama address is a refused port: nothing real is read.
Run: python -m tests.test_steward_off
"""
from __future__ import annotations

import contextlib
import io
import json
import os
import threading
import time
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from tests.helpers.runner import Ctx, new_registry, print_results, run_all

test, TESTS = new_registry()
STEWARD_THREADS = ("halo-steward-watch", "halo-steward-timer", "halo-local-resources")
IDLE_S = 20.0


def _names() -> set:
    return {t.name for t in threading.enumerate() if t.is_alive()}


def _steward_threads() -> list:
    return sorted(n for n in _names() if n in STEWARD_THREADS)


@test
def test_the_switch_is_off_unless_it_says_true(ctx: Ctx):
    from tests.helpers.session_rig import SessionRig
    from halo_harness.ollama_steward.job import enabled
    from halo_harness.theme import set_config_value, unset_config_value
    with SessionRig():
        unset_config_value("ollama.steward.job")
        ctx.check("a config that never set the key: off", enabled() is False)
        for value, want in ((True, True), (False, False), ("yes", False), (1, False)):
            set_config_value("ollama.steward.job", value)
            ctx.check(f"ollama.steward.job = {value!r}: {'on' if want else 'off'}", enabled() is want)
        from halo_harness.settings_catalog import row as row_for
        row = row_for("ollama.steward.job")
        ctx.check(f"the fresh-install default is off and applies now, got {row.default} {row.effect}",
                  row.default is False and row.effect == "now" and "CPU" in row.help)


@test
def test_off_nothing_of_it_runs_and_the_switch_applies_at_once(ctx: Ctx):
    from tests.helpers.local_seed import Seams
    from tests.helpers.session_rig import SessionRig, text_step
    from halo_harness.config.paths import bridge_home
    from halo_harness.ollama_steward import resources as R
    from halo_harness.studio.api import Request
    from halo_harness.studio.server import start_server
    from halo_harness.studio.settings_api import post_set
    saved_host, saved_poll = os.environ.get("OLLAMA_HOST"), os.environ.get("HALO_STUDIO_FILES_POLL_S")
    saved_seams = dict(R.SAMPLER_SEAMS)
    os.environ["OLLAMA_HOST"] = "http://127.0.0.1:9"  # a refused port: never a real Ollama
    os.environ["HALO_STUDIO_FILES_POLL_S"] = "0.3"
    srv = None
    with SessionRig() as rig:
        os.environ.pop("BRIDGE_TEST_NO_BACKGROUND_NET", None)  # only the steward's own switch keeps it off now
        R.SAMPLER_SEAMS.update({"seams": Seams().as_seams(), "hosts": lambda: [], "ps": lambda host: None})
        try:
            ctrl = rig.controller(rig.session(rig.script("steward-off-idle", [text_step("ok")])))
            state = bridge_home()
            srv = start_server(cwd=rig.cwd, state_dir=state)
            threading.Thread(target=srv.serve_forever, name="test-studio", daemon=True).start()
            ctx.check(f"a session and a Studio run, got {ctrl is not None} {srv.server_address[1]}", ctrl is not None)
            ctx.check(f"no steward thread, got {_steward_threads()}", _steward_threads() == [])
            ctx.check("no job on the Studio", srv.steward_job is None)
            t0, w0 = time.process_time(), time.monotonic()
            time.sleep(IDLE_S)
            used, wall = time.process_time() - t0, time.monotonic() - w0
            ctx.check(f"idle for {wall:.0f} s: {100 * used / wall:.2f}% of one core (under 2%)", used / wall < 0.02)
            ctx.check(f"still no steward thread after the idle, got {_steward_threads()}", _steward_threads() == [])

            def switch(value):
                req = Request(method="POST", path="/api/settings/set", query={}, cwd=rig.cwd, state_dir=state,
                              body={"key": "ollama.steward.job", "value": value}, server=srv)
                return post_set(req)

            def synced(want_on: bool, within: float = 15.0) -> bool:
                """Waits on the switch's own result (srv.steward_synced, set when a sync finished, its threads
                joined), never on a pause: True once a sync left the job as wanted."""
                deadline = time.monotonic() + within
                while time.monotonic() < deadline:
                    if not srv.steward_synced.wait(max(0.0, deadline - time.monotonic())):
                        break
                    srv.steward_synced.clear()
                    if (srv.steward_job is not None) == want_on:
                        return True
                return (srv.steward_job is not None) == want_on

            status, body = switch(True)
            ctx.check(f"Settings' switch: on, got {status} {body.get('steward_lines')}",
                      status == 200 and body.get("steward_lines") == [])
            ctx.check(f"on: the job's threads run without a restart (the start is synchronous), got {_steward_threads()}",
                      srv.steward_job is not None and "halo-steward-timer" in _names()
                      and "halo-steward-watch" in _names() and "halo-local-resources" in _names())
            status, body = switch(False)
            ctx.check(f"Settings' switch: off -- every thread joined within the bound, none reported alive, got "
                      f"{status} {body.get('steward_lines')}", status == 200 and body.get("steward_lines") == [])
            ctx.check(f"off: so its threads are gone when the answer comes, got {_steward_threads()}",
                      _steward_threads() == [] and srv.steward_job is None)

            from halo_harness.config_cli import cmd_config
            srv.steward_synced.clear()
            with contextlib.redirect_stdout(io.StringIO()):
                rc_on = cmd_config(["set", "ollama.steward.job", "true"])
            on = synced(True)
            ctx.check(f"`halo config set ollama.steward.job true`: the watcher's sync started it, got {rc_on} "
                      f"{_steward_threads()}", rc_on == 0 and on and "halo-steward-timer" in _names())
            srv.steward_synced.clear()
            with contextlib.redirect_stdout(io.StringIO()):
                rc_off = cmd_config(["set", "ollama.steward.job", "false"])
            off = synced(False)
            ctx.check(f"`halo config set ollama.steward.job false`: the sync joined every thread, got {rc_off} "
                      f"{srv.steward_lines} {_steward_threads()}",
                      rc_off == 0 and off and srv.steward_lines == [] and _steward_threads() == [])
        finally:
            if srv is not None:
                srv.shutdown()
                srv.server_close()
            R.SAMPLER_SEAMS.clear()
            R.SAMPLER_SEAMS.update(saved_seams)
            for k, v in (("OLLAMA_HOST", saved_host), ("HALO_STUDIO_FILES_POLL_S", saved_poll)):
                if v is None:
                    os.environ.pop(k, None)
                else:
                    os.environ[k] = v


@test
def test_off_the_readers_say_so_in_one_line(ctx: Ctx):
    from tests.helpers.session_rig import SessionRig
    from halo_harness.config.paths import bridge_home
    from halo_harness.ollama_steward import job_state, notes
    from halo_harness.studio.api import Request
    from halo_harness.studio.ollama_steward_api import get_steward
    from halo_harness.theme import set_config_value
    with SessionRig():
        state = bridge_home()
        notes.append(state, "note", "an old note from when it was on", lines=["an old note from when it was on"])
        lines = job_state.format_status(job_state.status(state))
        ctx.check(f"the status: ONE line that says the steward is off and how to turn it on, got {lines}",
                  len(lines) == 1 and lines[0].startswith("steward job: not running -- the steward is off")
                  and "halo config set ollama.steward.job true" in lines[0])
        status, body = get_steward(Request(method="GET", path="/api/ollama/steward", query={}, body={}, cwd=state,
                                           state_dir=state))
        ctx.check(f"the API says off with the line the page shows, got {status} {body.get('on')} {body.get('off_line')!r}",
                  status == 200 and body["on"] is False and "the steward is off" in (body.get("off_line") or ""))
        from halo_harness.doctor_local_servers import server_steps

        class _S:
            name, runtime = "hand", "llama-server"
        import halo_harness.ollama_steward.log_status_hf as LS
        saved = LS.status
        LS.status = lambda sd, s: {"state": "unreadable", "line": "no log path is known: set `log`"}
        try:
            rows = server_steps(state, servers=[_S()])
        finally:
            LS.status = saved
        ctx.check(f"the doctor's server-log row says the steward is off, got {rows}",
                  rows and "the steward is off: nothing reads this log now" in rows[0]["reason"])

        class _App:
            class controller:
                state_dir = state
        from halo_harness.tui.steward_notice import start_steward_poll
        ctx.check("the TUI starts no poll of the steward's notes", start_steward_poll(_App()) is None)
        set_config_value("ollama.steward.job", True)
        status, body = get_steward(Request(method="GET", path="/api/ollama/steward", query={}, body={}, cwd=state,
                                           state_dir=state))
        ctx.check(f"on: the full status again, got {body.get('on')} {body.get('status_lines')}",
                  body["on"] is True and body["status_lines"][0].startswith("steward job: not running (it starts with"))
        cfg = json.loads((state / "config.json").read_text(encoding="utf-8"))
        ctx.check("a config that says true stays true", cfg["ollama"]["steward"]["job"] is True)


# ---- the judge's pass (3.6.0.0 R13) ----
@test
def test_two_reactions_to_one_write_never_orphan_a_job(ctx: Ctx):
    """Judge: the Settings request and the files watcher both call sync_steward for one config write; serialised,
    with the registry as the truth, they leave exactly one job (on) or none (off), never an orphan."""
    from types import SimpleNamespace
    from tests.helpers.local_seed import Seams
    from tests.helpers.session_rig import SessionRig
    from halo_harness.config.paths import bridge_home
    from halo_harness.ollama_steward import job as J
    from halo_harness.ollama_steward import resources as R
    from halo_harness.studio.server import sync_steward
    from halo_harness.theme import set_config_value
    saved_host, saved_seams = os.environ.get("OLLAMA_HOST"), dict(R.SAMPLER_SEAMS)
    os.environ["OLLAMA_HOST"] = "http://127.0.0.1:9"
    with SessionRig():
        os.environ.pop("BRIDGE_TEST_NO_BACKGROUND_NET", None)
        R.SAMPLER_SEAMS.update({"seams": Seams().as_seams(), "hosts": lambda: [], "ps": lambda host: None})
        server = SimpleNamespace(state_dir=bridge_home(), steward_job=None, steward_synced=threading.Event(),
                                 steward_lines=[])
        try:
            for value in (True, False, True):
                set_config_value("ollama.steward.job", value)
                ts = [threading.Thread(target=sync_steward, args=(server,)) for _ in range(4)]
                for t in ts:
                    t.start()
                for t in ts:
                    t.join(30)
                registered = J._JOBS.get(str(server.state_dir))
                timers = [n for n in _names() if n == "halo-steward-timer"]
                ctx.check(f"{'on' if value else 'off'}: the Studio's job is the registry's, {int(value)} timer thread, "
                          f"got {server.steward_job is registered} {timers}",
                          server.steward_job is registered and (registered is not None) == value
                          and len([t for t in threading.enumerate() if t.name == "halo-steward-timer"]) == int(value))
        finally:
            set_config_value("ollama.steward.job", False)
            sync_steward(server)
            R.SAMPLER_SEAMS.clear()
            R.SAMPLER_SEAMS.update(saved_seams)
            if saved_host is None:
                os.environ.pop("OLLAMA_HOST", None)
            else:
                os.environ["OLLAMA_HOST"] = saved_host


@test
def test_halo_host_obeys_the_switch_without_a_restart(ctx: Ctx):
    """Judge: `halo host serve` started the resources sampler whatever the switch said, and a change reached it only
    at a restart. Now: off, no sampler and no job; the setting changed while it runs, its loop follows (sync_steward,
    called every tick). No listener is opened here: the service object is driven directly."""
    from tests.helpers.session_rig import SessionRig
    from halo_harness.config.paths import bridge_home
    from halo_harness.host.service import HostService
    from halo_harness.ollama_steward import resources as R
    from halo_harness.theme import set_config_value
    wants, made = [], []

    class _Job:
        def stop(self):
            made.append("stopped")
            return []
    saved_want = R.want
    R.want = lambda state_dir, owner, on, **kw: wants.append((owner, on)) or {}
    try:
        with SessionRig():
            svc = HostService(bridge_home(), port=0, bind="127.0.0.1", name="gpu-box", record=False,
                              job=lambda home: made.append("started") or _Job())
            from halo_harness.ollama_steward.job import enabled
            svc._steward_on = enabled()
            ctx.check("off by default", svc._steward_on is False)
            ctx.check("off: nothing changes on a tick", svc.sync_steward() == [] and wants == [] and made == [])
            set_config_value("ollama.steward.job", True)
            svc.sync_steward()
            ctx.check(f"turned on: the job and the sampler start, got {made} {wants}",
                      made == ["started"] and wants == [("host", True)])
            set_config_value("ollama.steward.job", False)
            svc.sync_steward()
            ctx.check(f"turned off: the job stops and the sampler is released, got {made} {wants}",
                      made == ["started", "stopped"] and wants[-1] == ("host", False) and svc.job is None)
    finally:
        R.want = saved_want


@test
def test_a_home_whose_job_was_on_before_hears_once_that_it_is_off(ctx: Ctx):
    from tests.helpers.session_rig import SessionRig
    from halo_harness.config.paths import bridge_home
    from halo_harness.ollama_steward import job as J
    from halo_harness.theme import set_config_value, unset_config_value
    with SessionRig():
        state = bridge_home()
        ctx.check("a fresh home (the job never ran): no notice", J.off_notice(state) is None)
        (state / "ollama").mkdir(parents=True, exist_ok=True)
        (state / "ollama" / "steward-job.json").write_text('{"where": "studio", "stopped": 1}', encoding="utf-8")
        first, second = J.off_notice(state), J.off_notice(state)
        ctx.check(f"a home whose job ran before 3.6.0.0: once, got {first!r} then {second!r}",
                  first and "now off by default; turn it on in Settings > Ollama" in first and second is None)
        (state / "ollama" / J._NOTICE_MARK).unlink()
        set_config_value("ollama.steward.job", False)
        ctx.check("a home that set the key itself: no notice", J.off_notice(state) is None)
        unset_config_value("ollama.steward.job")


if __name__ == "__main__":
    ctx = Ctx()
    results, passed, failed, skipped = run_all(TESTS, ctx)
    sys.exit(print_results(results, passed, failed, skipped))
