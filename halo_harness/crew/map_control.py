"""halo_harness.crew.map_control -- the map a session runs on, held where a lineup was (Halo 3.6.0.0 R3).

A session with a map in use (`--map`, config `crew.map`) holds a MapControl as its `team_control`: the one object the
agent loop, agent/subagent.py, models_auto_spawn and the Workflow tool already ask about a lineup. It answers the
same questions from the compiled map (crew/compile.py):

- **who main may hand work to**: `targets` (the agents and workflows main has a line to); the Agent tool spawns
  exactly those agents, the Workflow tool runs exactly those workflows (crew/map_run.py);
- **a route** for a hand-off that names no target: the first line from main whose When fires (always, a need, a word,
  "only when I ask" when the task names it); "main decides per task" never routes by itself -- main picks;
- **the model pick**: `bio_for(name)` gives models_auto the agent's needs (`auto` agents), as a lineup card did;
- **the money cap**: `caps.session_usd` -- main's spend and every hand-off's, checked before each hand-off;
- **a changed map**: `refresh()` compiles again before a hand-off when the map file's mtime moved; the line "your
  map changed: lines and boxes apply at the next hand-off" is said once. A map that now has a problem keeps the
  last good one and says the problem once.

Everything else a lineup had (tiers, stages, escalation, memory, hooks) a map does not have: those answers are "none".
"""

from __future__ import annotations

import os
import threading
from typing import Optional

from halo_harness.crew import map_when

CHANGED = "your map changed: lines and boxes apply at the next hand-off"


class MapControl:
    is_map = True
    default = False
    tiers: list = []
    tiers_declared = False
    context: dict = {}
    delegation: dict = {}
    template: dict = {}

    def __init__(self, compiled, *, cwd=None, state_dir=None, session=None) -> None:
        self.map = compiled
        self.name = f"map:{compiled.name}"
        self.map_name = compiled.name
        self.cwd, self.state_dir, self.session = cwd, state_dir, session
        self.lock = threading.Lock()
        self.spend_usd = 0.0
        self.turn_count = 0
        self.notes: list = []  # one-time lines the session says (a changed map, a problem in it)
        self._said: set = set()
        self.fired: list = []  # every hand-off: {line, name, why}

    # -- what main may hand work to -------------------------------------------------------------------------------
    @property
    def aliases(self) -> dict:
        return {n: {"role": n, "agent": n} for n in self.map.agent_targets()}

    def targets(self) -> list:
        return list(self.map.handoffs)

    def yields_to(self, _key: str) -> bool:
        return True

    @property
    def budget(self) -> dict:
        b = {"band": "mid"}
        if self.map.cap_usd is not None:
            b["max_budget_usd"] = self.map.cap_usd
        return b

    def assignment_for(self, target: Optional[str]) -> Optional[dict]:
        return {"role": target, "agent": target} if target and target in self.map.agents else None

    def bio_for(self, target: Optional[str]) -> Optional[dict]:
        if not target or target not in self.map.agents:
            return None
        return {"name": target, "models": {"needs": self.map.needs_of(target)}}

    # -- a changed map ----------------------------------------------------------------------------------------------
    def say(self, line: str) -> None:
        if line not in self._said:
            self._said.add(line)
            self.notes.append(line)

    def take_notes(self) -> list:
        got, self.notes = self.notes, []
        return got

    def refresh(self) -> None:
        """Compile again when the map file changed since (once per change; a bad file keeps the last good map)."""
        path = self.map.path
        try:
            now = os.path.getmtime(path) if path else 0.0
        except OSError:
            return
        if not path or now == self.map.mtime:
            return
        from halo_harness.crew.compile import compile_map
        fresh = compile_map(self.map_name, cwd=self.cwd, state_dir=self.state_dir)
        if fresh.problems:
            self.map.mtime = now
            self.say(f"your map changed but has a problem, so the last good one stays: {fresh.problems[0]}")
            return
        specs = getattr(getattr(self.session, "agent_runtime", None), "agents", None)
        if isinstance(specs, dict):
            specs.update(fresh.specs)
        self.map = fresh
        self.say(CHANGED)

    # -- routing ----------------------------------------------------------------------------------------------------
    def route(self, kind: str, task: str, files=()) -> "tuple[Optional[dict], str]":
        """The first line from main of `kind` (agent / workflow) whose When fires for `task`, and why."""
        for h in self.map.handoffs:
            if h["kind"] != kind:
                continue
            ok, why = map_when.fires(h["when"], task, files, [h["name"], h["box"]])
            if ok:
                return h, why
        return None, ""

    def line_to(self, kind: str, name: str) -> Optional[dict]:
        return next((h for h in self.map.handoffs if h["kind"] == kind and h["name"] == name), None)

    def route_call(self, tool_input: dict, description: str) -> "tuple[Optional[str], Optional[str]]":
        return None, None  # the target is chosen before the spawn (crew/map_run.py); no role rides on top

    # -- the money cap ----------------------------------------------------------------------------------------------
    def spent(self) -> float:
        meter = getattr(self.session, "cost_meter", None)
        own = float(getattr(meter, "total_usd", 0.0) or 0.0) if meter is not None else 0.0
        return own + self.spend_usd

    def budget_refusal(self) -> Optional[str]:
        cap = self.map.cap_usd
        if cap is None:
            return None
        spent = self.spent()
        if spent < cap:
            return None
        return (f"the map {self.map_name}'s session cap (${cap:.2f}, caps.session_usd) is reached: ${spent:.4f} spent; "
                "no more hand-offs this session (raise it in the map, or start a new session)")

    def record_spend(self, usd: float) -> None:
        with self.lock:
            self.spend_usd += float(usd or 0.0)

    def record_turn(self, turns: int = 1) -> None:
        with self.lock:
            self.turn_count += int(turns or 0)

    # -- what a map does not have: the lineup's answers for "none" ----------------------------------------------------
    def main_alias(self) -> Optional[str]:
        return None

    def spawn_refusal(self, *_a, **_k) -> Optional[str]:
        return None

    def stage_for(self, *_a) -> Optional[dict]:
        return None

    def gate_block(self, _stage) -> Optional[str]:
        return None

    def tier_claim(self, *_a) -> None:
        return None

    def tier_release(self, *_a) -> None:
        return None

    def evaluate_stage(self, *_a, **_k) -> "tuple[bool, str]":
        return True, ""

    def record_stage(self, *_a) -> None:
        return None

    def member_context_addition(self, *_a, **_k) -> str:
        return ""

    def member_hooks(self, *_a) -> dict:
        return {}

    def member_memory(self, *_a):
        return None, False

    def member_permissions(self) -> dict:
        return {"mode": None, "deny": [], "ask": [], "allow": [], "offline": False}

    def handoff_text(self, _target, text: str, **_k) -> str:
        return text

    def reports_for(self, _target) -> bool:
        return False

    def record_report(self, _target, one_line: str) -> str:
        return one_line

    def escalation_decision(self, **_k):
        return None
