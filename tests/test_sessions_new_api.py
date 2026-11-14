"""tests.test_sessions_new_api -- Halo 3.3.11.0 R2, Studio starts and ends a session with no terminal
(studio/sessions_new_api.py) over an in-process Studio and the fake upstream (tests/helpers/headless_rig.py);
no model call, every child ended by the teardown and checked gone.

1. GET sessions/new: the default model, Studio's cwd and the picker's rows; a cwd that is no folder is a 422;
2. POST sessions/new -> 202 with the session id it chose; the child registers under that id (`kind: headless`,
   `parent: studio:<this pid>`), GET sessions lists it with its kind, and ~/.halo/studio-sessions.json has it;
3. a submit through POST sessions/<sid>/command runs a turn (the reply is in its tail);
4. a Studio that restarts finds it (GET sessions/started: live);
5. "End session" (`shutdown`) ends the child and its row leaves the registry and the file.
Run: python -m tests.test_sessions_new_api
"""
from __future__ import annotations

import json
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from tests.helpers.runner import Ctx, new_registry, print_results, run_all  # noqa: E402

test, TESTS = new_registry()


@test
def test_new_session_from_studio_then_end_it(ctx: Ctx):
    from tests.helpers.session_rig import wait_for
    from tests.helpers.headless_rig import MODEL, REPLY, HeadlessRig
    with HeadlessRig() as rig:
        rig.spawn_env()
        server = rig.studio()
        code, first = rig.api(server, "GET", "sessions/new")
        ctx.check(f"GET sessions/new: the cwd and the rows, got {code} {str(first)[:200]}",
                  code == 200 and first.get("cwd") == str(rig.proj) and isinstance(first.get("models"), list))
        code, bad = rig.api(server, "POST", "sessions/new", {"model": MODEL, "cwd": str(rig.proj / "no-such-folder")})
        ctx.check(f"a cwd that is no folder: 422, got {code} {bad}", code == 422 and "not a folder" in bad.get("error", ""))
        code, new = rig.api(server, "POST", "sessions/new", {"model": MODEL, "cwd": str(rig.proj)})
        ctx.check(f"202 with the session id, got {code} {new}", code == 202 and len(new.get("session_id") or "") == 32)
        sid, pid = new.get("session_id"), new.get("pid")
        if pid:
            rig.pids.append(pid)
        ctx.check("the resume line names the id", sid in str(new.get("resume")) and "--resume" in str(new.get("resume")))
        entry = rig.entry(sid, 90)
        log = Path(str(new.get("log") or "")).read_text("utf-8", "replace")[-800:] if new.get("log") and Path(new["log"]).exists() else ""
        ctx.check(f"the child registered under that id, got {entry!r}\n{log}", entry is not None)
        if entry is None:
            return
        ctx.check(f"kind headless, parent studio:<this pid>, got {entry.get('kind')} {entry.get('parent')}",
                  entry.get("kind") == "headless" and entry.get("parent") == f"studio:{os.getpid()}" and entry.get("pid") == pid)
        code, rows = rig.api(server, "GET", "sessions")
        mine = [r for r in rows if r.get("session_id") == sid] if isinstance(rows, list) else []
        ctx.check(f"GET sessions lists it with its kind, got {mine}", len(mine) == 1 and mine[0].get("kind") == "headless")
        saved = json.loads((rig.state / "studio-sessions.json").read_text("utf-8"))["sessions"]
        ctx.check(f"studio-sessions.json keeps the pid and the id, got {saved}",
                  any(r["session_id"] == sid and r["pid"] == pid and r["cwd"] == str(rig.proj) for r in saved))

        c = rig.client(entry)
        c.call("subscribe")
        rig.idle(c)
        code, sent = rig.api(server, "POST", f"sessions/{sid}/command", {"cmd": "submit", "text": "hi from the new page", "when_busy": "refuse"})
        ctx.check(f"a submit from Studio, got {code} {sent}", code == 200)
        ctx.check("the turn ran", c.wait_event("turn_done", 40) is not None)
        ctx.check("the reply is in its tail", REPLY in c.call("tail", n=4)["result"]["markdown"])

        rig.stop_studio(server)
        again = rig.studio()
        code, found = rig.api(again, "GET", "sessions/started")
        hit = [r for r in found.get("sessions") or [] if r.get("session_id") == sid]
        ctx.check(f"a restarted Studio finds the child, got {code} {found}", code == 200 and len(hit) == 1 and hit[0].get("live") is True)

        rig.idle(c)
        code, ended = rig.api(again, "POST", f"sessions/{sid}/command", {"cmd": "shutdown", "reason": "End session"})
        ctx.check(f"End session taken, got {code} {ended}", code == 200)
        gone = wait_for(lambda: not any(r.get("session_id") == sid for r in rig.rows()) and "gone", 40)
        ctx.check("its registry row is gone", gone == "gone")
        from halo_harness.bg_run import pid_alive
        ctx.check("the child ended", wait_for(lambda: not pid_alive(pid) and "ended", 30) == "ended")
        code, after = rig.api(again, "GET", "sessions/started")
        ctx.check(f"the file lost it, got {after}", code == 200 and not any(r.get("session_id") == sid for r in after.get("sessions") or []))
    ctx.check(f"no headless child survives, got {rig.survivors()}", rig.survivors() == [])


if __name__ == "__main__":
    ctx = Ctx()
    results, passed, failed, skipped = run_all(TESTS, ctx)
    sys.exit(print_results(results, passed, failed, skipped))
