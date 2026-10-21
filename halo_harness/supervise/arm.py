"""halo_harness.supervise.arm -- the lineups' schedules and triggers, armed by
the supervisor (Halo 3.1.8.0 R1), so they no longer die with a session.

Every lineup in the state dir and in each queued goal's repo that declares a
schedule or a trigger (a member bio's `schedule:` / `triggers:`, a tier's
`trigger`) is armed through agents_schedule.arm_session with a small
session-like object (`Supervised`: state_dir, cwd, the tool env a session
there would have, a bg_run-backed job surface) and `owner="supervisor"`, so its store entries
carry the mark. A team a live session armed already is left to it until that
session closes (the next scan arms it). The double-fire guard the other way:
a session's `_arm_team_scheduler_once` skips a team the supervisor owns while
its pulse is live (agents_schedule.supervisor_owns).

A fire is a `halo bg` run (`halo bg list` shows it). Fires are idempotent:
the store keeps the running fire's bg id (`running_bg`); a fire that comes
due while it still runs is skipped with a `last_note`.

`on: event` / `on: message` triggers are fed from the live sessions' control
socket feeds (the frames supervise/loop.py taps from studio/events.py's
EventBridge): every event kind for `on: event`, a `subagent_end`'s name for
`on: message`; a repo lineup sees only sessions in its repo.
"""

from __future__ import annotations

from pathlib import Path
from typing import Callable, Optional

RESCAN_S = 60.0


class BgJobs:
    """The job surface a supervised fire uses: each fire is a background run (bg_run.py)."""

    def __init__(self, popen=None):
        self.popen = popen

    def running(self, bg_id: Optional[str]) -> bool:
        if not bg_id:
            return False
        from halo_harness.bg_run import is_our_process, load_run
        meta = load_run(str(bg_id))
        return bool(meta) and is_our_process(meta)

    def start(self, session, entry: dict) -> dict:
        import subprocess
        from halo_harness.agents_schedule import _fire_env, build_fire_argv
        from halo_harness.bg_run import start_background_run
        argv = build_fire_argv(entry)[3:]  # past `<python> -m halo_harness`: start_background_run adds the harness
        return start_background_run(argv, popen=self.popen or subprocess.Popen, env=_fire_env(session, entry),
                                    cwd=str(session.cwd))


class Supervised:
    """What a TeamScheduler reads of a session (tests/test_agents_schedule.py's `_Session`)."""

    agent_depth = 0

    def __init__(self, state_dir, cwd, tool_env: Optional[dict] = None, jobs: Optional[BgJobs] = None):
        self.state_dir, self.cwd = Path(state_dir), Path(cwd)
        self.tool_env = dict(tool_env or {})
        self.jobs = jobs or BgJobs()
        self.job_registry = None  # fires go through `fire` below, never a TUI's registry


def fire(session: Supervised, entry: dict) -> str:
    """The supervisor's fire: skip while the previous fire's job still runs, else a new bg run."""
    if session.jobs.running(entry.get("running_bg")):
        return f"skipped: the previous fire (bg {entry['running_bg']}) still runs"
    run = session.jobs.start(session, entry)
    entry["running_bg"] = run["id"]
    return f"fired {entry.get('name')} as background run {run['id']}"


def tool_env(cwd) -> dict:
    """The environment a session in `cwd` gives its tools (settings.json's `env` chain, the harness's own
    secrets stripped: providers/config.tool_child_env), the fired job's overlay (agents_schedule._fire_env)."""
    try:
        from halo_harness.config.settings import resolve_settings
        from halo_harness.providers.config import tool_child_env
        return tool_child_env(resolve_settings(cwd).effective_env)
    except Exception:
        return {}


def declares(control) -> bool:
    """The lineup has something to arm: a member's schedule or triggers, a tier's trigger."""
    for alias in control.aliases:
        bio = control.bio_for(alias) or {}
        if (bio.get("schedule") or {}).get("prompt") or bio.get("triggers"):
            return True
    return bool(control.tiers_declared and any(t.get("trigger") for t in control.tiers))


def lineups(state_dir, repos: list) -> list:
    """`[(name, cwd, scope)]`: the state dir's lineups (scope None: every session) and each repo's own."""
    from halo_harness.teams_yaml import list_team_templates, project_teams_dir
    out, seen = [], set()
    for repo in repos:
        d = project_teams_dir(repo)
        for p in sorted(d.glob("*.yaml")) if d.is_dir() else []:
            if not p.name.endswith(".team.yaml") and p.stem not in seen:
                seen.add(p.stem)
                out.append((p.stem, Path(repo), Path(repo)))
    for name in list_team_templates(cwd=Path(state_dir), state_dir=state_dir, include_templates=False):
        if name not in seen:
            seen.add(name)
            out.append((name, Path.cwd(), None))
    return out


class Armer:
    """The supervisor's armed teams: `scan()` arms what is new, `feed(frame)` observes, `stop()` disarms."""

    def __init__(self, state_dir, *, popen=None, fire_fn: Optional[Callable] = None, tick_s: float = 1.0,
                 clock: Callable = None):
        import time
        self.state_dir = Path(state_dir)
        self.jobs = BgJobs(popen)
        self.fire_fn = fire_fn or fire
        self.tick_s = tick_s
        self.clock = clock or time.monotonic
        self.armed: dict = {}  # team name -> (scheduler, scope)
        self._last = -1e9

    def scan(self, repos: list, force: bool = False) -> list:
        """Arm every declaring lineup not armed yet; returns the team names armed now."""
        if not force and self.clock() - self._last < RESCAN_S:
            return []
        self._last = self.clock()
        from halo_harness.agents_schedule import arm_session, armed_by_live_session
        from halo_harness.teams_runtime import load_team_control
        new = []
        for name, cwd, scope in lineups(self.state_dir, repos):
            if name in self.armed or armed_by_live_session(name, self.state_dir):
                continue
            control = load_team_control(name, cwd=cwd, state_dir=self.state_dir)
            if control is None or not declares(control):
                continue
            session = Supervised(self.state_dir, cwd, tool_env(cwd), self.jobs)
            scheduler = arm_session(session, control, fire_fn=self.fire_fn, owner="supervisor", tick_s=self.tick_s)
            if scheduler is not None:
                self.armed[name] = (scheduler, scope)
                new.append(name)
        return new

    def feed(self, frame: dict, cwd_of: Callable[[str], Optional[str]]) -> None:
        """One frame of a live session's feed: `on: event` for its kind, `on: message` for a sub-agent's end."""
        kind = str(frame.get("event") or "")
        if not kind or kind == "sessions":
            return
        cwd = cwd_of(str(frame.get("session_id") or "")) or ""
        data = frame.get("data") if isinstance(frame.get("data"), dict) else {}
        for scheduler, scope in list(self.armed.values()):
            if scope is not None and not _inside(cwd, scope):
                continue
            try:
                scheduler.observe_event(kind)
                if kind == "subagent_end" and data.get("name"):
                    scheduler.notify_message(str(data["name"]))
            except Exception:
                continue

    def stop(self) -> None:
        for scheduler, _scope in list(self.armed.values()):
            scheduler.stop()
            scheduler.disarm()
        self.armed.clear()


def _inside(cwd: str, scope: Path) -> bool:
    if not cwd:
        return False
    try:
        Path(cwd).resolve().relative_to(Path(scope).resolve())
        return True
    except (ValueError, OSError):
        return False
