"""halo_harness.init_wait -- `halo init` waits for Setup's Done, then starts halo
(Halo 3.3.3.0 R1, "Setup hands off to halo"; docs/WIZARD.md, docs/COMMANDS-init.md).

`halo init` on a terminal opens Studio on Setup (studio/setup_door.py) and,
unless `--no-launch` or `HALO_INIT_NO_LAUNCH=1`, stays: the door's one line
says "Press Done there and halo starts here", then `wait_for_done` watches
for the Summary's Done (studio/setup_done.py) -- the marker file first, then
`GET setup/state` on the running Studio with the token in `~/.halo/
studio.json`, once per `POLL_S` (1.0 s; `HALO_INIT_POLL_S`), the marker file
again whenever the GET fails. A marker from an earlier init does not count:
only a `done_at` not earlier than the wait's start. The answer is one word:

    done          Done was pressed: the Summary's four lines are printed and
                  `launch_halo(cwd)` starts the TUI exactly as bare `halo` does
    gone          Studio stopped answering for GONE_S (10 s) and no marker
    interrupted   Ctrl+C

`launch_halo`, `sleep` and `http_get` are this module's names so a test
swaps them: no test waits a real second or opens a TUI.
"""

from __future__ import annotations

import os
import time
from pathlib import Path
from typing import Callable, Optional

POLL_S = 1.0
GONE_S = 10.0
NO_LAUNCH_ENV = "HALO_INIT_NO_LAUNCH"
POLL_ENV = "HALO_INIT_POLL_S"
INTERRUPTED_LINE = "Setup stays open in the browser; run `halo` when you are done there."
GONE_LINE = "Studio closed; run `halo` when you are ready."

sleep = time.sleep


def launch_halo(cwd) -> int:
    """Bare `halo` in `cwd`: the default args, the full-screen session, `/update`'s restart (cli.launch_bare)."""
    from halo_harness.cli import launch_bare
    return launch_bare(cwd)


def http_get(state_dir, path: str, timeout: float = 5.0) -> Optional[dict]:
    """One GET on the running Studio's loopback API with the port and token `~/.halo/studio.json` holds now
    (studio/launch.py `api_call`, read again on every poll): the JSON body on a 200, else None."""
    from halo_harness.studio.launch import api_call
    try:
        got = api_call(Path(state_dir), "GET", path, timeout=timeout)
    except Exception:
        return None
    if not got or got[0] != 200 or not isinstance(got[1], dict):
        return None
    return got[1]


def wanted(args, env: Optional[dict] = None) -> bool:
    """Whether `halo init` waits and launches: not with `--no-launch`, not with HALO_INIT_NO_LAUNCH=1."""
    env = os.environ if env is None else env
    if getattr(args, "no_launch", False):
        return False
    return (env.get(NO_LAUNCH_ENV) or "").strip() in ("", "0")


def poll_seconds(env: Optional[dict] = None) -> float:
    env = os.environ if env is None else env
    try:
        value = float((env.get(POLL_ENV) or "").strip() or POLL_S)
    except ValueError:
        return POLL_S
    return value if value >= 0 else POLL_S


def _wait(state_dir, poll_s: float, sleep_fn: Callable[[float], None],
          deadline: Optional[float], since: str) -> "tuple[str, Optional[dict]]":
    from halo_harness.studio.setup_done import later, setup_done_at
    failed = waited = 0.0
    state: Optional[dict] = None
    try:
        while True:
            if later(setup_done_at(state_dir), since):
                return "done", state
            got = http_get(state_dir, "setup/state")
            if got is not None:
                state, failed = got, 0.0
                if later(got.get("done_at"), since):
                    return "done", state
            else:
                failed += max(poll_s, 0.001)
                if failed >= GONE_S:
                    return ("done", state) if later(setup_done_at(state_dir), since) else ("gone", state)
            if deadline is not None and waited >= deadline:
                return "gone", state
            sleep_fn(poll_s)
            waited += poll_s
    except KeyboardInterrupt:
        return "interrupted", state


def wait_for_done(state_dir, poll_s: float = POLL_S, sleep: Optional[Callable] = None,
                  deadline: Optional[float] = None, since: Optional[str] = None) -> str:
    """"done" | "gone" | "interrupted" (above). The Studio is the one `<state_dir>/studio.json` names, read again
    on every poll. `sleep` None: this module's `sleep`; `deadline`: seconds of polling (counted in poll_s steps,
    never the clock) after which the answer is "gone"; `since`: the wait's start (default now), a `done_at` must
    not be earlier."""
    from halo_harness.studio.setup_done import now_iso
    word, _state = _wait(state_dir, poll_s, sleep or globals()["sleep"], deadline, since or now_iso())
    return word


def _last_check_word(last) -> str:
    """routes/setup/checkStore.ts lastCheckWord: "not run", "ok HH:MM", "stopped HH:MM" or "N failed HH:MM"."""
    if not isinstance(last, dict) or not last.get("when"):
        return "not run"
    try:
        hhmm = time.strftime("%H:%M", time.localtime(float(last["when"])))
    except (TypeError, ValueError, OverflowError, OSError):
        hhmm = "?"
    failed = sum(1 for r in last.get("results") or [] if isinstance(r, dict) and not r.get("ok"))
    if failed:
        return f"{failed} failed {hhmm}"
    return f"{'stopped' if last.get('stopped') else 'ok'} {hhmm}"


def summary_lines(state: Optional[dict]) -> "list[str]":
    """The Summary's four lines: the providers set, the default model, the lineup, the last check."""
    s = state if isinstance(state, dict) else {}
    providers = s.get("providers") if isinstance(s.get("providers"), dict) else {}
    named = [k for k, v in providers.items() if isinstance(v, dict) and v.get("set")]
    team = s.get("team") if isinstance(s.get("team"), dict) else {}
    active = str(team.get("active") or "")
    if active == "one-model":
        lineup = "one model for everything"
    elif active:
        lineup = active + (" (default)" if team.get("source") == "default" else "")
    else:
        lineup = "not set"
    return [f"Provider: {', '.join(named) if named else 'not set'}", f"Default model: {s.get('model') or 'not set'}",
            f"Lineup: {lineup}", f"Last check: {_last_check_word(s.get('last_check'))}"]


def _local_state(cwd, state_dir) -> Optional[dict]:
    """The state read here when the Studio's last answer is missing (Done seen in the marker only)."""
    try:
        from halo_harness.studio.setup_state import setup_state
        return setup_state(cwd, state_dir)
    except Exception:
        return None


def run(say: Callable[[str], None], *, cwd, state_dir, poll_s: Optional[float] = None,
        deadline: Optional[float] = None) -> int:
    """`halo init`'s wait after the door: Done -> the four lines and bare halo (its exit code); Ctrl+C or Studio
    gone -> one line and 0."""
    from halo_harness.studio.setup_done import now_iso
    since = now_iso()
    word, state = _wait(state_dir, poll_seconds() if poll_s is None else poll_s, globals()["sleep"], deadline, since)
    if word == "interrupted":
        say(INTERRUPTED_LINE)
        return 0
    if word == "gone":
        say(GONE_LINE)
        return 0
    fresh = http_get(state_dir, "setup/state")
    for line in summary_lines(fresh or state or _local_state(cwd, state_dir)):
        say(line)
    return launch_halo(cwd)
