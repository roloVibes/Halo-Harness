"""halo_harness.supervise.services -- the enabled packs' services, kept running by the supervisor (Halo 3.3.13.0 R3;
docs/SUPERVISE.md "Pack services", docs/EXTENSION_API.md "Services"). The files and the rows other processes read
are supervise/services_rows.py.

    Services(state_dir, popen=None, clock=time.time)
      .tick() -> [row]   every pack that is enabled AND granted `services`: an autostart service that is not running
                         starts (unless the owner stopped it), one that ended starts again by its `restart` rule after a
                         wait (5 s, doubling to 300 s; back to 5 s after ten minutes up), one whose pack went off or lost
                         the grant is stopped, a Start / Stop the owner asked for (services-want.json) is applied, and
                         the state file is written
      .stop_all()        the supervisor's way out: each service it runs is asked to stop (its stop file), then ended

A service runs in the pack's folder with the environment a pack hook gets (Halo's provider keys left out,
CLAUDE_PLUGIN_ROOT, HALO_PACK_ID) plus HALO_SERVICE (<pack>/<name>), HALO_SERVICE_HEALTH (its health file),
HALO_SERVICE_STOP (the file whose existence asks it to end) and HALO_SUPERVISOR=1; its stdout and stderr go to its log
in the pack's data folder. A service that needs a session asks the supervisor for one (remote/session_start.py), so the
provider keys never reach the pack's program.
"""

from __future__ import annotations

import os
import subprocess
import time
from pathlib import Path

from halo_harness.packs import manifest_services as MS
from halo_harness.supervise import procgroup as PG
from halo_harness.supervise import services_rows as R

WAIT_S, WAIT_MAX_S, CALM_S, STOP_WAIT_S = 5.0, 300.0, 600.0, 5.0


def _env(pack, entry: dict, key: str, state_dir=None) -> dict:
    from halo_harness.packs.interpreter import pack_env
    from halo_harness.providers.config import tool_child_env
    env = tool_child_env(dict(os.environ))  # the provider keys Halo holds stay out, as for every pack hook
    hf = R.health_file(pack.id, entry, state_dir)
    env.update({"CLAUDE_PLUGIN_ROOT": str(pack.root), "HALO_PACK_ID": pack.id, "HALO_SERVICE": key,
                "HALO_SERVICE_HEALTH": str(hf or ""), "HALO_SERVICE_STOP": str(R.stop_file(key, state_dir)),
                "HALO_SUPERVISOR": "1"})
    return pack_env(pack.root, env)


class Services:
    def __init__(self, state_dir, *, popen=None, clock=time.time, cwd=None) -> None:
        self.state_dir, self.clock, self.cwd = Path(state_dir), clock, cwd
        self.popen = popen or subprocess.Popen
        self.procs: dict = {}  # key -> Popen: the ones this supervisor started
        self.groups: dict = {}  # key -> procgroup.Group: each one's children with it (REVIEW #17)
        self.rec: dict = dict(R.read_json(R.state_path(self.state_dir)).get("services") or {})
        for r in self.rec.values():  # a new supervisor starts each service afresh; a Stop the owner asked for stays
            if isinstance(r, dict) and r.get("state") != "running":
                r.update(exit=None, next_at=0.0, restarts=0, asked_stop=False)

    def tick(self) -> list:
        now = self.clock()
        wants = R.read_json(R.want_path(self.state_dir))
        if wants:  # 3.3.14.0 R2 (REVIEW #25): only the asks read here leave the file; a later one waits for the next tick
            R.take_wants(wants, self.state_dir)
        seen = set()
        for pack, e, granted in R.declared(self.state_dir, self.cwd):
            key = MS.key_of(pack.id, e["name"])
            seen.add(key)
            r = self.rec.setdefault(key, {"state": "off", "restarts": 0, "next_at": 0.0})
            r.update(pack=pack.id, name=e["name"], description=str(e.get("description") or ""),
                     autostart=e.get("autostart") is True, restart=MS.restart_of(e))
            ask = wants.get(key)
            if ask in ("start", "stop"):
                r["held"] = ask == "stop"
                if ask == "start":
                    r.update(next_at=0.0, restarts=0, exit=None, asked_stop=False)
            self._poll(key, r, e, now)
            if not granted:
                self._stop(key, r, f"not granted services (halo pack grant {pack.id} services)")
            elif r["state"] == "running" and r.get("held"):
                self._stop(key, r, "stopped by you")
            elif r["state"] != "running" and not r.get("held") and (r["autostart"] or ask == "start"
                                                                     or r.get("started_once")) and self._may(r, now):
                self._start(pack, e, key, r, now)
            if r["state"] == "running":
                r["health"], hline = R.health(pack.id, e, self.state_dir)  # a file's age is wall-clock time
                r["line"] = hline or r.get("line")
            else:
                r["health"] = "unknown"
        for key in [k for k in self.rec if k not in seen]:
            self._stop(key, self.rec[key], "the pack is off")
            self.rec.pop(key, None)
        self._save()
        return R.rows_of(self.rec)

    def _may(self, r: dict, now: float) -> bool:
        if r.get("exit") is not None and not r.get("asked_stop"):
            rule = r.get("restart") or "on-failure"
            if rule == "never" or (rule == "on-failure" and r.get("exit") == 0):
                return False
        return now >= float(r.get("next_at") or 0)

    def _poll(self, key: str, r: dict, e: dict, now: float) -> None:
        proc = self.procs.get(key)
        if proc is None:
            if r.get("state") == "running" and not _alive(r):
                r.update(state="failed", exit=None, pid=None, line="it ended while no supervisor watched it")
            return
        code = proc.poll()
        if code is None:
            if now - float(r.get("since") or now) > CALM_S:
                r["restarts"] = 0
            return
        self.procs.pop(key, None)
        PG.finish(self.groups.pop(key, None))  # what it left running goes with it
        _, hline = R.health(r["pack"], e, self.state_dir)
        r.update(state="stopped" if code == 0 else "failed", exit=code, pid=None,
                 line=(f"exit {code}: {hline}" if code and hline else hline or f"exit {code}"))
        # 3.3.13.1 (REVIEW #15, CORE-1): the exponent is capped first; 5.0 * 2 ** 1024 raised OverflowError at
        # the 1025th failure in a row and every tick after it
        r["next_at"] = now + min(WAIT_MAX_S, WAIT_S * 2 ** min(int(r.get("restarts") or 0), 7))
        r["restarts"] = int(r.get("restarts") or 0) + 1

    def _start(self, pack, e: dict, key: str, r: dict, now: float) -> None:
        from halo_harness.packs.manifest_policy import run_argv
        from halo_harness.remote import proc_ident
        log = R.data_dir(pack.id, self.state_dir) / MS.log_of(e)
        try:
            R.stop_file(key, self.state_dir).unlink()
        except OSError:
            pass
        try:
            log.parent.mkdir(parents=True, exist_ok=True)
            with open(log, "ab") as out:
                kw: dict = {"cwd": str(pack.root), "env": _env(pack, e, key, self.state_dir), "stdout": out,
                            "stderr": subprocess.STDOUT, "stdin": subprocess.DEVNULL}
                kw.update(PG.popen_kwargs())  # its own process group (REVIEW #17)
                if os.name == "nt":
                    kw["creationflags"] |= getattr(subprocess, "CREATE_NO_WINDOW", 0)
                proc = self.popen(run_argv(e, pack.root), **kw)
        except OSError as ex:
            r.update(state="failed", exit=None, line=f"it did not start: {type(ex).__name__}: {ex}",
                     next_at=now + WAIT_MAX_S)
            return
        self.procs[key] = proc
        self.groups[key] = PG.attach(proc)
        r.update(state="running", pid=proc.pid, pstart=proc_ident.start_token(proc.pid), since=now, exit=None,
                 line="started", log=str(log), started_once=True, asked_stop=False)

    def _stop(self, key: str, r: dict, why: str) -> None:
        if r.get("state") != "running":
            if r.get("state") not in ("failed", "stopped"):
                r["line"] = why
            return
        path = R.stop_file(key, self.state_dir)
        try:
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text("stop\n", encoding="utf-8")
        except OSError:
            pass
        proc, group = self.procs.pop(key, None), self.groups.pop(key, None)
        if proc is not None:  # 3.3.14.0 R2 (REVIEW #17): the group is signalled, so its children end with it
            try:
                proc.wait(STOP_WAIT_S)
            except subprocess.TimeoutExpired:
                PG.term(group) if group is not None else proc.terminate()
                try:
                    proc.wait(STOP_WAIT_S)
                except subprocess.TimeoutExpired:
                    PG.kill(group) if group is not None else proc.kill()
            PG.finish(group)
        elif _alive(r):
            _end_pid(int(r["pid"]))
        r.update(state="stopped", pid=None, exit=0, line=why, asked_stop=True)

    def stop_all(self) -> None:
        for key, r in list(self.rec.items()):
            if r.get("state") == "running":
                self._stop(key, r, "the supervisor stopped")
                r["asked_stop"] = False  # the next supervisor starts it again
        self._save()

    def _save(self) -> None:
        R.write_json(R.state_path(self.state_dir), {"version": 1, "services": self.rec})


def _alive(r: dict) -> bool:
    from halo_harness.remote.proc_ident import pulse_alive
    return pulse_alive({"pid": r.get("pid"), "pstart": r.get("pstart"), "started": r.get("since")})


def _end_pid(pid: int) -> None:
    try:
        if os.name == "nt":
            subprocess.run(["taskkill", "/PID", str(pid), "/T", "/F"], capture_output=True, timeout=10)
        else:
            import signal
            os.kill(pid, signal.SIGTERM)
    except (OSError, subprocess.SubprocessError):
        pass
