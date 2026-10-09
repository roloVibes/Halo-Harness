"""halo_harness.agents_schedule -- Halo 2.0.5 round 5 (deliverable 3): a
bio's `schedule:` (`cron:` 5 fields or `every:` a duration) starts the
agent as a BACKGROUND JOB on that cadence while a session that loaded the
team is alive -- never a system service; a bio's `triggers:` (`on:
file_change`/`event`/`message`) start it on the event, one shot per
session. Firing goes through the existing job surfaces (a live session's
own JobRegistry, the status bar's background-jobs count, `halo bg` for the
CLI form), always on the scheduler's own daemon thread -- never the UI
thread. Storage is one JSON file per state dir (`agents-schedules.json`)
so `/agents schedule` and `halo agents schedule list` (possibly a
different process) see what is armed and the next fire time.
"""

from __future__ import annotations

import datetime
import json
import re
import shlex
import sys
import threading
import time
from pathlib import Path
from typing import Optional

MIN_TICK_S = 1.0

# ---- cadence math -----------------------------------------------------------

_CRON_BOUNDS = ((0, 59), (0, 23), (1, 31), (1, 12), (0, 6))


def _cron_field_matches(field: str, value: int) -> bool:
    for part in field.split(","):
        if not part:
            continue
        base, slash, step = part.partition("/")
        step_n = int(step) if slash else 1
        if step_n <= 0:
            return False
        if base == "*":
            lo, hi = 0, value + 1  # "*" with a step: every step_n from 0
            if (value - lo) % step_n == 0:
                return True
            continue
        if "-" in base:
            lo_s, _, hi_s = base.partition("-")
            lo, hi = int(lo_s), int(hi_s)
        elif slash:
            # 2.0.5 release-review nit 14: a single-value base WITH a
            # step ("5/2") is the run 5,7,9,... to the field's end (cron
            # semantics), not "only 5". `value` is always a real datetime
            # component, so the field's own maximum is the ceiling and
            # never gates this match.
            lo, hi = int(base), 10 ** 9
        else:
            lo = hi = int(base)
        if lo <= value <= hi and (value - lo) % step_n == 0:
            return True
    return False


def _cron_day_matches(dom_field: str, dow_field: str, dom: int, dow: int) -> bool:
    """Standard cron day semantics: a `*` day field always matches; when
    BOTH day fields are restricted, EITHER matching is enough (dom OR dow
    -- `0 0 1 * 1` = the 1st of the month plus every Monday); when only
    one is restricted, that one must match."""
    dom_ok = dom_field == "*" or _cron_field_matches(dom_field, dom)
    dow_ok = dow_field == "*" or _cron_field_matches(dow_field, dow)
    if dom_field != "*" and dow_field != "*":
        return dom_ok or dow_ok
    return dom_ok and dow_ok


def cron_next(expr: str, now: "Optional[datetime.datetime]" = None) -> "Optional[datetime.datetime]":
    """The next minute (strictly after `now`) a 5-field cron expression
    fires, or None when it never does within ~a year. Dow field: 0 or 7 is
    Sunday. Minute resolution, same as cron itself.

    vibes/review.md finding 63: (a) a literal 7 in the dow field (a
    documented Sunday spelling) never matched -- the computed value is
    always 0-6, so every `7` in the field is normalized to `0` up front;
    (b) day-of-month and day-of-week are ORed when BOTH are restricted
    (standard cron semantics -- `0 0 1 * 1` fires on the 1st AND on every
    Monday), not ANDed. The old AND made many real schedules impossible,
    and an impossible expression drove the full 366-day minute scan
    (~527k iterations) on every scheduler tick while holding the lock."""
    fields = (expr or "").split()
    if len(fields) != 5:
        return None
    dom_field, dow_field = fields[2], fields[4]
    dow_field = re.sub(r"\d+", lambda m: "0" if m.group(0) == "7" else m.group(0), dow_field)
    base = (now or datetime.datetime.now()).replace(second=0, microsecond=0)
    candidate = base + datetime.timedelta(minutes=1)
    for _ in range(366 * 24 * 60):
        values = (candidate.minute, candidate.hour, candidate.day,
                  candidate.month, (candidate.weekday() + 1) % 7)
        if (all(_cron_field_matches(f, v) for f, v in zip(fields[:2], values[:2]))
                and _cron_field_matches(fields[3], values[3])
                and _cron_day_matches(dom_field, dow_field, values[2], values[4])):
            return candidate
        candidate += datetime.timedelta(minutes=1)
    return None


def next_fire_at(entry: dict, now: "Optional[datetime.datetime]" = None) -> "Optional[datetime.datetime]":
    """A schedule entry's next fire time -- `cron` through `cron_next`,
    `every` as `last_run (or armed_at) + every_s`.

    2.0.5 release-review finding 3: a cron entry's next fire is computed
    from the LAST fire point (or arming), never from `now` -- `cron_next`
    returns a time strictly AFTER its argument, so computing from `now`
    meant `nxt <= now` was never true and a cron schedule never fired.
    Both branches therefore share the same base rule."""
    if entry.get("cron"):
        base = entry.get("last_run") or entry.get("armed_at") or 0
        return cron_next(entry["cron"], datetime.datetime.fromtimestamp(float(base)))
    every_s = entry.get("every_s")
    if not every_s or every_s <= 0:
        return None
    base = entry.get("last_run") or entry.get("armed_at") or time.time()
    return datetime.datetime.fromtimestamp(float(base) + float(every_s))


# ---- storage (what is armed, visible across processes) ----------------------

def schedules_path(state_dir) -> Path:
    return Path(state_dir) / "agents-schedules.json"


def load_store(state_dir) -> dict:
    try:
        data = json.loads(schedules_path(state_dir).read_text(encoding="utf-8"))
        if isinstance(data, dict) and isinstance(data.get("entries"), list):
            return data
    except (OSError, ValueError):
        pass
    return {"entries": []}


def save_store(state_dir, store: dict) -> None:
    path = schedules_path(state_dir)
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(store, indent=2, default=str), encoding="utf-8")
    except OSError:
        pass


def list_schedules(state_dir=None) -> "list[dict]":
    """Every ARMED schedule/trigger entry (any owning session; paused ones
    included, marked by the status lines) -- `halo agents schedule list`/
    `/agents schedule` print these."""
    from halo_harness.config.paths import bridge_home
    base = state_dir if state_dir is not None else bridge_home()
    return list(load_store(base).get("entries", []))


def schedule_status_lines(entries: "list[dict]") -> "list[str]":
    """One line per entry: name, cadence/trigger, next fire time (schedules
    only), the owning team, and the last run's note when there is one."""
    if not entries:
        return ["Nothing armed (a session that loads a team with schedules/triggers arms them)."]
    lines = []
    now = datetime.datetime.now()
    for e in entries:
        when = ""
        if e.get("kind") == "trigger":
            when = f"trigger on {e.get('on')}" + (f" {e.get('on_value')}" if e.get("on_value") else "")
            if e.get("fired"):
                when += " (fired)"
        else:
            nxt = next_fire_at(e, now)
            when = f"next {nxt.strftime('%Y-%m-%d %H:%M') if nxt else 'never'}"
        paused = " (paused)" if not e.get("enabled", True) else ""
        note = f" -- {e['last_note']}" if e.get("last_note") else ""
        lines.append(f"  {e.get('name')} ({e.get('agent')}): {when}, team {e.get('team')}{paused}{note}")
    return lines


def build_fire_argv(entry: dict) -> "list[str]":
    """The headless invocation a schedule/trigger fires, as an argv LIST:
    this very harness, print mode, the entry's prompt, then --agent/--team
    (2.0.5 release-review finding 6: the fired job previously ran a bare
    prompt session, not the AGENT -- both flags exist on the main parser)
    and the entry's model when it carries one."""
    argv = [sys.executable, "-m", "halo_harness", "-p", str(entry.get("prompt") or "")]
    if entry.get("agent"):
        argv += ["--agent", str(entry["agent"])]
    if entry.get("team"):
        argv += ["--team", str(entry["team"])]
    if entry.get("model"):
        argv += ["--model", str(entry["model"])]
    return argv


def build_fire_command(entry: dict) -> str:
    """`shlex.join(build_fire_argv(entry))` -- the string form for callers
    that run through a POSIX shell (the job registry's git-bash path);
    never a shell string built by hand."""
    return shlex.join(build_fire_argv(entry))


def _default_fire(session, entry: dict) -> str:
    """A live session's fire path: the EXISTING JobRegistry surface (the
    status bar's background-jobs count, `/tasks`) -- a real background job
    running the headless invocation, never the UI thread."""
    registry = getattr(session, "job_registry", None)
    if registry is None:
        # 2.0.5 release-review nit 10: the detached fallback passes the
        # argv LIST straight to Popen (no shell=True) -- shlex.join's
        # POSIX quoting through cmd.exe mangles on Windows.
        import subprocess
        subprocess.Popen(build_fire_argv(entry), cwd=str(getattr(session, "cwd", ".")),
                         stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, stdin=subprocess.DEVNULL)
        return f"fired {entry.get('name')} (detached; no live job registry)"
    try:
        from halo_harness.tools.bash import git_bash
        shell_path = str(git_bash())
    except Exception:
        shell_path = "bash"
    record, err = registry.start_background(build_fire_command(entry), description=f"schedule {entry.get('name')}",
                                            cwd=str(getattr(session, "cwd", ".")), env={}, shell_path=shell_path)
    if err is not None:
        return f"could not fire {entry.get('name')}: {err}"
    return f"fired {entry.get('name')} as background job {record.job_id}"


class TeamScheduler:
    """One live session's armed schedules + triggers. `fire_fn(session,
    entry) -> note` is the seam (tests substitute a recorder); the default
    is `_default_fire`. Triggers are ONE SHOT per session ("start it on
    the event"); schedules repeat on their cadence until `stop()`."""

    def __init__(self, session, team, *, fire_fn=None, tick_s: float = MIN_TICK_S, clock=None):
        self.session = session
        self.team = team
        self.fire_fn = fire_fn or _default_fire
        self.tick_s = max(0.05, float(tick_s))
        self.clock = clock or time.time
        self.entries: "list[dict]" = []
        self.triggers: "list[dict]" = []
        self._file_mtimes: dict = {}
        self._stop = threading.Event()
        self._lock = threading.Lock()
        self._thread: "Optional[threading.Thread]" = None

    # ---- arming -----------------------------------------------------------
    def arm_bio(self, bio: dict, alias: str) -> "list[str]":
        """Register one bio's own `schedule:`/`triggers:` (validated shape;
        anything malformed is skipped, never raised). Returns the entry
        names armed."""
        notes: "list[str]" = []
        schedule = bio.get("schedule") or {}
        prompt = schedule.get("prompt")
        if prompt:
            entry = {"id": f"{self.team.name}:{alias}:schedule", "name": alias, "agent": bio.get("name") or alias,
                     "kind": "schedule", "cron": schedule.get("cron"),
                     "every_s": None if schedule.get("every") is None
                     else _every_seconds(schedule.get("every")),
                     "prompt": prompt, "model": schedule.get("model") or (bio.get("models") or {}).get("preference"),
                     "team": self.team.name, "enabled": True, "armed_at": self.clock(),
                     "last_run": None, "last_note": ""}
            if entry["cron"] or entry["every_s"]:
                with self._lock:
                    self.entries.append(entry)
                notes.append(entry["id"])
        for i, t in enumerate(bio.get("triggers") or []):
            if not isinstance(t, dict) or t.get("on") not in ("file_change", "event", "message"):
                continue
            entry = {"id": f"{self.team.name}:{alias}:trigger{i}", "name": alias,
                     "agent": bio.get("name") or alias, "kind": "trigger", "on": t.get("on"),
                     "on_value": t.get("paths") if t.get("on") == "file_change"
                     else (t.get("name") or t.get("from")),
                     "prompt": t.get("prompt") or (bio.get("schedule") or {}).get("prompt") or "",
                     "model": (bio.get("models") or {}).get("preference"),
                     "team": self.team.name, "enabled": True, "armed_at": self.clock(), "fired": False,
                     "last_note": ""}
            with self._lock:
                self.triggers.append(entry)
                if t.get("on") == "file_change":
                    for p in t.get("paths") or []:
                        try:
                            self._file_mtimes[str(p)] = Path(p).stat().st_mtime
                        except OSError:
                            self._file_mtimes[str(p)] = None
            notes.append(entry["id"])
        return notes

    # ---- lifecycle ----------------------------------------------------------
    def start(self) -> None:
        if self._thread is not None:
            return
        self._thread = threading.Thread(target=self._run, name=f"halo-team-schedule-{self.team.name}", daemon=True)
        self._thread.start()

    def stop(self) -> None:
        self._stop.set()

    def _run(self) -> None:
        while not self._stop.wait(self.tick_s):
            try:
                self._poll_files()
                self._fire_due()
            except Exception:
                continue

    # ---- trigger observation (called from the session's own threads) -------
    def observe_event(self, kind: str) -> None:
        with self._lock:
            pending = [t for t in self.triggers if t["on"] == "event" and not t["fired"]
                       and t.get("on_value") == kind]
            for t in pending:
                t["fired"] = True
        for t in pending:
            self._fire(t, f"event {kind}")

    def notify_message(self, from_role: str) -> None:
        with self._lock:
            pending = [t for t in self.triggers if t["on"] == "message" and not t["fired"]
                       and t.get("on_value") == from_role]
            for t in pending:
                t["fired"] = True
        for t in pending:
            self._fire(t, f"message from {from_role}")

    def _poll_files(self) -> None:
        with self._lock:
            pending = []
            for t in self.triggers:
                if t["on"] != "file_change" or t["fired"]:
                    continue
                for p in t.get("on_value") or []:
                    try:
                        mtime = Path(p).stat().st_mtime
                    except OSError:
                        mtime = None
                    if self._file_mtimes.get(str(p)) is not None and mtime != self._file_mtimes.get(str(p)):
                        t["fired"] = True
                        pending.append((t, p))
                        break
                    self._file_mtimes[str(p)] = mtime
        for t, p in pending:
            self._fire(t, f"file change {p}")

    # ---- firing ---------------------------------------------------------------
    def _fire_due(self) -> None:
        now = self.clock()
        with self._lock:
            due = []
            for e in self.entries:
                if not e.get("enabled", True):
                    continue
                nxt = next_fire_at(e, datetime.datetime.fromtimestamp(now))
                if nxt is not None and nxt.timestamp() <= now:
                    e["last_run"] = now
                    due.append(e)
        for e in due:
            self._fire(e, "cadence")

    def _fire(self, entry: dict, why: str) -> None:
        try:
            note = self.fire_fn(self.session, entry)
        except Exception as e:
            note = f"fire failed: {type(e).__name__}"
        # 2.0.5 release-review nit 13: the last_note write is under the
        # lock (it raced the tick loop's entry scans and _persist's
        # snapshot); fire_fn itself stays OUTSIDE it -- it may block.
        with self._lock:
            entry["last_note"] = f"{why}: {note}"
        self._persist()

    def _persist(self) -> None:
        state_dir = getattr(self.session, "state_dir", None)
        if state_dir is None:
            return
        with self._lock:
            mine = [dict(e) for e in self.entries] + [dict(t) for t in self.triggers]
        store = load_store(state_dir)
        kept = [e for e in store.get("entries", []) if e.get("team") != self.team.name]
        store["entries"] = kept + mine
        save_store(state_dir, store)

    def disarm(self) -> None:
        """Session close: drop THIS team's entries from the shared store."""
        state_dir = getattr(self.session, "state_dir", None)
        if state_dir is None:
            return
        store = load_store(state_dir)
        store["entries"] = [e for e in store.get("entries", []) if e.get("team") != self.team.name]
        save_store(state_dir, store)


def _every_seconds(raw) -> "Optional[float]":
    from halo_harness.agents_yaml import parse_every_duration
    return parse_every_duration(raw)


def run_once(name: str, *, state_dir=None, popen=None) -> str:
    """`halo agents schedule run <name>` -- fire one armed entry right now,
    through `bg_run`'s own detached background-run surface (`halo bg`).
    `popen` is the same seam `start_background_run` itself takes."""
    from halo_harness.bg_run import start_background_run
    entries = list_schedules(state_dir)
    # Match the entry's alias, its id, or the underlying bio's own name --
    # a bio armed under its team's MAIN alias should still be runnable as
    # itself (`halo agents schedule run <bio>`).
    entry = next((e for e in entries if name in (e.get("name"), e.get("id"), e.get("agent"))), None)
    if entry is None:
        return f"no armed schedule or trigger named {name!r}"
    import subprocess
    # 2.0.5 release-review finding 6: same shape as build_fire_argv -- the
    # agent and team ride along (start_background_run prepends the harness
    # itself), so the fired job runs AS the agent, not as a bare session.
    argv = ["-p", str(entry.get("prompt") or "")]
    if entry.get("agent"):
        argv += ["--agent", str(entry["agent"])]
    if entry.get("team"):
        argv += ["--team", str(entry["team"])]
    if entry.get("model"):
        argv += ["--model", str(entry["model"])]
    run = start_background_run(argv, popen=popen or subprocess.Popen)
    return f"fired {name!r} as background run {run['id']} (log: {run['log_path']})"


def arm_session(session, team_control, *, fire_fn=None) -> "Optional[TeamScheduler]":
    """Arm every member bio's schedule/triggers for THIS session (called
    once, on the session's first turn under a team). Also registers them
    in the shared store so `list`/`/agents schedule` see them. `fire_fn`
    is the same seam TeamScheduler's own constructor takes (tests)."""
    scheduler = TeamScheduler(session, team_control, fire_fn=fire_fn)
    seen_bios: set = set()
    for alias in sorted(team_control.aliases):
        bio = team_control.bio_for(alias)
        # One bio armed ONCE even when several aliases assign it (the
        # schedule starts the AGENT, not the alias -- double-assigning a
        # bio must not double-fire it).
        if bio and bio.get("name") not in seen_bios:
            seen_bios.add(bio.get("name"))
            scheduler.arm_bio(bio, alias)
    if scheduler.entries or scheduler.triggers:
        scheduler._persist()
        scheduler.start()
        return scheduler
    return None


def stop_session_scheduler(session) -> None:
    scheduler = getattr(session, "_team_scheduler", None)
    if scheduler is not None:
        scheduler.stop()
        scheduler.disarm()
        session._team_scheduler = None
