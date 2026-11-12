"""halo_harness.fleet.mission_wait -- a mission part on a harness whose permission mode asks (Halo 3.4.1.0 R5,
defect 32). Until 3.4.0.1 a part's session was print mode, where an ask is a deny, so on a `default`-mode harness every
part failed, even one that only writes its own outputs into the mission folder Halo made for it. Now:

* `own_write(folder, part, raw, cwd)`: a Write / Edit inside the part's OWN outputs folder (`artifacts/<n>/` of its
  mission folder) is the mission's own bookkeeping and needs no ask (fleet/mission_guard.py allows exactly that). The
  path is checked as written and resolved: no `..`, no `\\\\?\\` / `\\\\.\\` / UNC spelling, no NTFS stream (`x:y`),
  no link out (the folder itself, a folder under it or the file).
* `waits(session)`: any other call that would ask WAITS as an attention card on that machine (the session's own
  waiters, answered through its control socket from Studio's Attention, the TUI or the glance). Halo allows nothing
  else by itself.
* `AskWatch`: while a card is open the part reads "waiting on you (on <machine>)" on the hub (the part's `asking` in
  mission.json, through a `mission_wait` frame for a mirrored part); a card nobody answers within
  `fleet.mission.ask_wait_min` minutes (default 30) ends the part "not done: nobody answered ...".
"""

from __future__ import annotations

import threading
import time
from pathlib import Path
from typing import Optional

from halo_harness.ext import core as _core
from . import mission as M, mission_store as S

DEFAULT_WAIT_MIN = 30.0
_KINDS = (("_permission_waiters", "permission"), ("_question_waiters", "question"), ("_plan_waiters", "plan"))


def wait_min(home=None) -> float:
    try:
        got = float(M._cfg("fleet.mission.ask_wait_min", DEFAULT_WAIT_MIN, home))
    except (TypeError, ValueError):
        got = DEFAULT_WAIT_MIN
    return got if got > 0 else DEFAULT_WAIT_MIN


def own_write(folder, part, raw, cwd=None) -> bool:
    """True when `raw` names a file inside `<folder>/artifacts/<part>/`, by every spelling and once resolved."""
    s = str(raw or "")
    if not s or "\x00" in s or s.replace("\\", "/").startswith("//"):  # \\?\, \\.\ and \\host\share spellings
        return False
    if ".." in s.replace("\\", "/").split("/"):
        return False
    if ":" in (s[2:] if len(s) > 1 and s[1] == ":" else s):  # an NTFS stream (out.txt:x) or a second drive
        return False
    base = Path(folder)
    try:
        real_base = base.resolve()
        own = (base / "artifacts" / str(part)).resolve()
        if own != real_base / "artifacts" / str(part):  # artifacts/ or artifacts/<n> is a link out
            return False
        target = Path(s) if Path(s).is_absolute() else Path(cwd or base) / s
        real = target.resolve()
    except (OSError, ValueError, RuntimeError):
        return False
    return real != own and own in real.parents


def waits(session) -> None:
    """The part's session keeps an ask an ask (print mode would deny it) and parks it until someone answers."""
    engine = getattr(session, "permission_engine", None)
    if engine is not None:
        engine.print_mode = False
    session.interactive = True


def pending(session) -> list:
    """`[(kind, request id, what)]` of the cards the session waits on."""
    out = []
    for attr, kind in _KINDS:
        for rid, slot in list((getattr(session, attr, None) or {}).items()):
            name, ti = (slot or {}).get("tool_name"), (slot or {}).get("tool_input")
            arg = ""
            if isinstance(ti, dict):
                arg = str(ti.get("command") or ti.get("file_path") or ti.get("notebook_path") or ti.get("url") or "")
            what = f"{name} {arg}".strip() if name else kind
            out.append((kind, str(rid), " ".join(what.split())[:160]))
    return out


class AskWatch(threading.Thread):
    """Watches a running part's session for open cards (`run` is a mission_worker_run.WorkerRun)."""

    def __init__(self, run, tick: float = 1.0) -> None:
        super().__init__(daemon=True, name=f"halo-mission-asks-{run.f['mission']}-{run.f['part']}")
        self.run_, self.tick = run, tick
        self.wait_s = wait_min(run.home) * 60.0
        self.done = threading.Event()
        self.since: Optional[float] = None

    def run(self) -> None:
        while not self.done.wait(self.tick):
            try:
                self.step(time.time())
            except Exception:  # the watch never takes the part down
                pass

    def step(self, now: float) -> None:
        session = self.run_.session
        got = pending(session) if session is not None else []
        if got and self.since is None:
            self.since = now
            self._say(got[0][2], now)
        elif not got and self.since is not None:
            self.since = None
            self._say(None, now)
        if got and self.since is not None and now - self.since >= self.wait_s:
            mins = f"{self.wait_s / 60:g}"
            self.run_.unanswered = (f"not done: nobody answered {got[0][2]} on {self._machine()} within {mins} min "
                                    "(fleet.mission.ask_wait_min)")
            self.done.set()
            abort = getattr(session, "abort", None)
            target = getattr(getattr(self.run_, "act", None), "handle", None)
            (target.interrupt if target is not None else abort.set)()

    def stop(self) -> None:
        self.done.set()
        if self.since is not None:
            self._say(None, time.time())

    def _machine(self) -> str:
        return str(_core.get("peers.identity", "harness")(self.run_.home).get("name") or "this machine")

    def _say(self, what: Optional[str], now: float) -> None:
        r = self.run_
        data = {"mission": r.f["mission"], "part": r.f["part"], "what": what, "since": round(now, 3) if what else None,
                "on": self._machine()}
        if r.mode in ("local", "shared"):
            mark(r.folder, data)
        from .mission_worker_session import frame
        frame(r.act, {"action": "mission_wait", **data})


def mark(base, data: dict) -> None:
    """The part's `asking` in mission.json: {what, since, on}, or gone once answered."""
    pid = str(data.get("part") or "")

    def apply(doc: dict) -> None:
        part = (doc.get("parts") or {}).get(pid)
        if isinstance(part, dict):
            if data.get("what"):
                part["asking"] = {k: data.get(k) for k in ("what", "since", "on")}
            else:
                part.pop("asking", None)
    S.update_at(base, apply, str(data.get("mission") or ""), stamp=False)


def note(home, frame_: dict, publish=None) -> bool:
    """The hub's side: a member's `fleet` frame {action: mission_wait, ...} for a part it runs."""
    data = frame_.get("data") if isinstance(frame_.get("data"), dict) else {}
    mid, hid = str(data.get("mission") or ""), str(frame_.get("harness") or "")
    doc = S.load(home, mid) if M.valid_id(mid) else None
    if doc is None or str((doc.get("parts") or {}).get(str(data.get("part")), {}).get("harness")) != hid:
        return False
    mark(S.folder(home, mid), {**data, "what": str(data.get("what") or "")[:160] or None})
    if publish is not None:
        from .mission_run import frame
        frame(publish, (doc.get("hub") or {}).get("id"), {"id": mid, "state": doc.get("state"), "part": str(data.get("part"))})
    return True


def line(part: dict) -> str:
    """`waiting on you (on <machine>): <what>` for a running part with an open card, else ""."""
    a = part.get("asking") if isinstance(part.get("asking"), dict) else None
    if not a or part.get("state") not in ("running", None):
        return ""
    return f"waiting on you (on {a.get('on') or 'its machine'}): {a.get('what') or 'a card'}"
