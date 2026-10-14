"""halo_harness.orchestra.guard -- claims checked at the permission engine.

`PermissionEngine.guards` (halo_harness/permissions.py) is a list of objects
with `check(tool_name, tool_input, decision, engine) -> Decision | None`,
consulted after the base decision when it is `allow` or `ask` (a `deny`
always stands). `ClaimGuard` is the Orchestra's: for Write, Edit, MultiEdit
and NotebookEdit on one of the goal's `files` it finds the units the edit
touches (Edit/MultiEdit: the lines where each `old_string` occurs; Write and
NotebookEdit: the whole file) and

* a unit held by ANOTHER holder   -> deny, naming the holder and the expiry;
* a unit no claim of yours covers -> ask ("claim it first or allow once");
* every unit covered by your claim -> allow, and the claim moves to
  `writing` (one `claim` line in events.jsonl).

An `ask` from an explicit ask rule stays an ask. Where no prompt can be shown
(print mode, dontAsk) the guard's ask becomes a deny with the same text.
Every file outside the goal's list keeps the base decision untouched.

`install_from_env(engine, session_dir)` adds a ClaimGuard when the session
runs inside a run ($HALO_ORCHESTRA_RUN=<run_dir>); agent/loop.py calls it for
every Session, so each sub-agent gets its own holder.
"""

from __future__ import annotations

import os
import time
from pathlib import Path
from typing import Callable, Optional

from halo_harness.orchestra import RUN_ENV
from halo_harness.orchestra.claims import ClaimLog, clock_text, holder_for
from halo_harness.orchestra.goal import load_goal, norm_file, repo_root_of
from halo_harness.orchestra.index import index_file, overlaps, units_for_lines

GUARDED_TOOLS = ("Write", "Edit", "MultiEdit", "NotebookEdit")


class ClaimGuard:
    def __init__(self, run_dir, holder: str, *, clock: Callable[[], float] = time.time):
        self.run_dir = Path(run_dir)
        self.holder = holder
        self.log = ClaimLog(self.run_dir, clock=clock)
        self._goal_cache: tuple = (None, None)

    # ---- the goal's files ------------------------------------------------
    def files(self) -> list:
        """The goal's `files`, normalised; re-read when goal.json changes."""
        path = self.run_dir / "goal.json"
        try:
            mtime = path.stat().st_mtime
        except OSError:
            return []
        if self._goal_cache[0] != mtime:
            try:
                files = [norm_file(f) for f in load_goal(path).files]
            except ValueError:
                files = []
            self._goal_cache = (mtime, files)
        return list(self._goal_cache[1] or [])

    def match(self, file_path, cwd=None) -> Optional[tuple]:
        """`(root, relpath)` when `file_path` is one of the goal's files under
        the run's repo root or under `cwd` (a worker's own worktree); else None."""
        if not file_path:
            return None
        files = set(self.files())
        if not files:
            return None
        target = Path(file_path)
        if not target.is_absolute() and cwd is not None:
            target = Path(cwd) / target
        target = target.resolve()
        roots = [repo_root_of(self.run_dir)]
        if cwd is not None:
            roots.append(Path(cwd))
        for root in roots:
            try:
                rel = target.relative_to(Path(root).resolve()).as_posix()
            except (ValueError, OSError):
                continue
            if rel in files:
                return Path(root).resolve(), rel
        return None

    # ---- which units an edit touches --------------------------------------
    @staticmethod
    def touched_lines(tool_name: str, tool_input: dict, path: Path) -> Optional[list]:
        """Line numbers the edit touches; None means the whole file."""
        if tool_name not in ("Edit", "MultiEdit"):
            return None
        olds = []
        if tool_name == "Edit":
            olds.append(tool_input.get("old_string"))
        else:
            for e in tool_input.get("edits") or []:
                olds.append(e.get("old_string") if isinstance(e, dict) else None)
        try:
            text = path.read_text(encoding="utf-8", errors="replace").replace("\r\n", "\n")
        except OSError:
            return None
        lines: list = []
        for old in olds:
            if not isinstance(old, str) or not old:
                return None
            old = old.replace("\r\n", "\n")
            start, found = 0, False
            while True:
                idx = text.find(old, start)
                if idx < 0:
                    break
                found = True
                first = text.count("\n", 0, idx) + 1
                lines.extend(range(first, first + old.count("\n") + 1))
                start = idx + max(1, len(old))
            if not found:
                return None
        return lines

    def touched_keys(self, tool_name: str, tool_input: dict, root: Path, rel: str) -> list:
        path = root / rel
        units = index_file(path, root=root)
        lines = self.touched_lines(tool_name, tool_input, path)
        if lines is None:
            return [rel]
        return [u.key for u in units_for_lines(units, lines)] or [rel]

    # ---- the check -------------------------------------------------------
    def check(self, tool_name: str, tool_input, decision, engine=None):
        """A replacement Decision, or None to keep `decision`."""
        if tool_name not in GUARDED_TOOLS or not isinstance(tool_input, dict):
            return None
        raw = tool_input.get("notebook_path") if tool_name == "NotebookEdit" else tool_input.get("file_path")
        hit = self.match(raw, getattr(engine, "cwd", None))
        if hit is None:
            return None
        root, rel = hit
        keys = self.touched_keys(tool_name, tool_input, root, rel)
        now = self.log.clock()
        active = self.log.active(now)
        from halo_harness.permissions import Decision
        for key in keys:
            foreign = [c for c in active.values() if c.holder != self.holder and overlaps(c.key, key)]
            if foreign:
                c = foreign[0]
                return Decision("deny", f"`{c.key}` is held by `{c.holder}` until {clock_text(c.expires)}: "
                                        "wait for the release or ask the lead", source="orchestra")
        missing = [k for k in keys if self.log.held_by(self.holder, k, now) is None]
        if missing:
            text = f"no claim on `{missing[0]}`; claim it first (OrchestraClaim) or allow once"
            return self._ask(text, engine)
        self._mark(keys, now)
        if decision.action == "ask" and getattr(decision, "matched_rule", None) is not None:
            return None  # the user's own ask rule still asks
        return Decision("allow", f"held by {self.holder}: " + ", ".join(f"`{k}`" for k in keys),
                        source="orchestra")

    def _mark(self, keys: list, now: float) -> None:
        done = set()
        for key in keys:
            claim = self.log.held_by(self.holder, key, now)
            if claim is not None and claim.key not in done:
                done.add(claim.key)
                self.log.mark_writing(self.holder, claim.key, note="edit allowed by the guard")

    @staticmethod
    def _ask(text: str, engine):
        from halo_harness.permissions import Decision
        if engine is not None and (getattr(engine, "print_mode", False) or getattr(engine, "mode", "") == "dontAsk"):
            return Decision("deny", text + " -- no interactive prompt here", source="orchestra")
        return Decision("ask", text, source="orchestra")


def run_dir_from_env(env=None) -> Optional[Path]:
    """$HALO_ORCHESTRA_RUN when it names a run folder (one with goal.json)."""
    value = (env if env is not None else os.environ).get(RUN_ENV)
    if not value:
        return None
    path = Path(value)
    return path if (path / "goal.json").is_file() else None


def install_from_env(engine, session_dir, env=None) -> Optional[ClaimGuard]:
    """Add a ClaimGuard for this session's holder to `engine.guards` when the
    session runs inside a run. Returns the guard (None outside a run)."""
    run_dir = run_dir_from_env(env)
    if run_dir is None or engine is None or session_dir is None:
        return None
    guards = getattr(engine, "guards", None)
    if guards is None:
        return None
    holder = holder_for(session_dir)
    for g in guards:
        if isinstance(g, ClaimGuard) and g.run_dir == run_dir and g.holder == holder:
            return g
    guard = ClaimGuard(run_dir, holder)
    guards.append(guard)
    return guard
