"""halo_harness.fleet.mission_guard -- a mission part's claims at the
permission engine (Halo 3.0.6.0 "Fleet Missions" round R7).

`MissionClaimGuard` joins `PermissionEngine.guards` (the same hook
Orchestra's ClaimGuard uses) of a `mission-worker` session and of every
sub-agent it starts (`inherited`). For Write, Edit, MultiEdit and
NotebookEdit it finds the file's path relative to the part's folder (its
worktree for a repo part, the mission folder for a files part):

* inside one of the part's claims (mission_claims.covers) -> the base
  decision stands untouched: the owner's own rules decide, a claim never
  allows anything by itself;
* anywhere else -> deny, with a one-line reason, and `on_refused(rel, tool,
  reason)` raises it (the worker logs `claim_refused` in the mission folder
  and publishes a `fleet` frame `{action: "mission_claim", mission, part,
  file, tool, reason}` that the hub turns into a `mission_claim` attention row).

A deny from the owner's rules always stands (the engine never asks a guard
then), so a mission only ever narrows what a session may do.
"""

from __future__ import annotations

import time
from pathlib import Path
from typing import Callable, Optional

from halo_harness.fleet.mission_claims import covers

GUARDED_TOOLS = ("Write", "Edit", "MultiEdit", "NotebookEdit")
REPEAT_S = 30.0


class MissionClaimGuard:
    inherited = True  # a sub-agent's engine gets the same guard (agent/subagent.py)

    def __init__(self, cwd, claims: list, *, mission: str, part: str, allow=(),
                 on_refused: Optional[Callable] = None) -> None:
        self.cwd = Path(cwd)
        self.claims = [str(c) for c in claims or []]
        self.mission, self.part = mission, str(part)
        self.allow = {str(a).replace("\\", "/") for a in allow}
        self.on_refused = on_refused
        self.refused: list = []
        self._last: dict = {}

    def rel(self, raw, cwd=None) -> Optional[str]:
        """`raw` relative to the part's folder (forward slashes), or None when it is outside it."""
        target = Path(str(raw))
        if not target.is_absolute():
            target = Path(cwd or self.cwd) / target
        try:
            return target.resolve().relative_to(self.cwd.resolve()).as_posix()
        except (ValueError, OSError):
            return None

    def reason(self, rel: Optional[str], raw) -> str:
        claims = ", ".join(self.claims) or "nothing"
        where = rel if rel is not None else f"{Path(str(raw)).name} (outside the part's folder)"
        return (f"mission {self.mission} part {self.part} may edit only its claims ({claims}); {where} is not one of "
                "them: another part owns it, or it is outside the mission")

    def check(self, tool_name: str, tool_input, decision, engine=None):
        """None keeps the base decision; a deny Decision for an edit outside the claims."""
        if tool_name not in GUARDED_TOOLS or not isinstance(tool_input, dict):
            return None
        raw = tool_input.get("notebook_path") if tool_name == "NotebookEdit" else tool_input.get("file_path")
        if not isinstance(raw, str) or not raw:
            return None
        rel = self.rel(raw, getattr(engine, "cwd", None))
        if rel is not None and (rel in self.allow or covers(self.claims, rel)):
            return None
        why = self.reason(rel, raw)
        self._raise(rel or Path(raw).name, tool_name, why)
        from halo_harness.permissions import Decision
        return Decision("deny", why, source="mission")

    def _raise(self, rel: str, tool: str, why: str) -> None:
        now = time.time()
        if now - self._last.get((rel, tool), 0.0) < REPEAT_S:
            return
        self._last[(rel, tool)] = now
        self.refused.append({"ts": round(now, 3), "file": rel, "tool": tool, "reason": why})
        if self.on_refused is not None:
            try:
                self.on_refused(rel, tool, why)
            except Exception:
                pass


def install(engine, guard: MissionClaimGuard) -> MissionClaimGuard:
    guards = getattr(engine, "guards", None)
    if guards is not None and guard not in guards:
        guards.append(guard)
    return guard


def inherit(parent_engine, child_engine) -> None:
    """The guards a sub-agent's engine takes over from its parent's (agent/subagent.py)."""
    mine = [g for g in getattr(parent_engine, "guards", None) or [] if getattr(g, "inherited", False)]
    if mine and getattr(child_engine, "guards", None) is not None:
        child_engine.guards.extend(g for g in mine if g not in child_engine.guards)
