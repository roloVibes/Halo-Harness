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

**The default map** (no map named, none in config: crew/compile.py `is_default`) is a drawing, never a rule:
`control_for` gives a `PlainMap`, which draws the starter map (the lit Map, its boxes and hand-offs) and answers every
question a session asks with what a plain 3.5 session's default lineup answered -- the shipped `auto` lineup
(templates/teams/auto.yaml, its bios' needs, its delegation and routing, no money cap; your `roles.*` win). One
source: the values are read from that lineup, never copied here. (3.6.0.0 R5 fix; R5b moves that source.)
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
    def cap_usd(self) -> Optional[float]:
        """The map's `caps.session_usd`; never on the default map (crew/compile.py is_default: a plain session had none)."""
        from halo_harness.crew.compile import is_default
        return None if is_default(self.map) else self.map.cap_usd

    @property
    def budget(self) -> dict:
        b = {"band": "mid"}
        if self.cap_usd is not None:
            b["max_budget_usd"] = self.cap_usd
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
        cap = self.cap_usd
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


# -- the default map: the starter drawn, a plain session's answers ----------------------------------------------------
PLAIN_LINEUP = "auto"  # the lineup a plain 3.5 session ran (lineup_default.DEFAULT_LINEUP)
PLAIN_ROLES = {"media-reader": "media"}  # a starter agent whose name is not its card's alias in that lineup

# What the session, agent/subagent.py, models_auto_spawn and the Workflow tool ask a team control; on the default map
# the lineup answers every one of them (properties and bound methods alike).
LINEUP_ANSWERS = ("aliases", "budget", "delegation", "template", "tiers", "tiers_declared", "context", "default",
                  "yields_to", "assignment_for", "bio_for", "route_call", "budget_refusal", "record_spend", "record_turn",
                  "main_alias", "spawn_refusal", "stage_for", "gate_block", "tier_claim", "tier_release", "evaluate_stage",
                  "record_stage", "member_context_addition", "member_hooks", "member_memory", "member_permissions",
                  "handoff_text", "reports_for", "record_report", "escalation_decision")


def plain_lineup(cwd=None, state_dir=None):
    """The shipped `auto` lineup as a plain 3.5 session held it (teams_runtime.TeamControl, `default` true: a knob or a
    role you set yourself wins). Read from the shipped file only: ~/.halo/teams is no longer read. None when it cannot
    be read."""
    try:
        from halo_harness.teams_runtime import TeamControl
        from halo_harness.teams_yaml import _expand_roles_shorthand, _read_yaml_file, bundled_team_templates_dir
        path = bundled_team_templates_dir() / f"{PLAIN_LINEUP}.yaml"
        raw = _read_yaml_file(path)
        if not isinstance(raw, dict):
            return None
        template = {**_expand_roles_shorthand(dict(raw)), "name": PLAIN_LINEUP, "_source": "template", "_path": str(path)}
    except Exception:
        return None
    aliases = {(e.get("as") or e["role"]): e for e in template.get("agents") or [] if isinstance(e, dict) and e.get("role")}
    return TeamControl(name=PLAIN_LINEUP, template=template, aliases=aliases, default=True)


def plain_role(name: str) -> str:
    """The lineup alias a starter agent stands for (its role, so its model is picked as that card's was)."""
    return PLAIN_ROLES.get(name, name)


class PlainMap(MapControl):
    """The default map: draws the starter map, answers as the plain session's lineup (LINEUP_ANSWERS). Its `name` is
    that lineup's, so the Agent and Workflow tools describe themselves as they did; `map_name` is the map drawn."""

    def __init__(self, compiled, lineup, **kw) -> None:
        super().__init__(compiled, **kw)
        self.lineup = lineup
        self.name = lineup.name

    def refresh(self) -> None:
        return None  # the shipped starter does not change under a running session, and it sets no rules to re-read

    def __getattr__(self, key):  # anything else the lineup has (escalation, routing, stages, budget_exhausted ...)
        lineup = self.__dict__.get("lineup")
        if lineup is None:
            raise AttributeError(key)
        return getattr(lineup, key)


for _k in LINEUP_ANSWERS:
    setattr(PlainMap, _k, property(lambda self, _k=_k: getattr(self.lineup, _k)))


def control_for(compiled, *, cwd=None, state_dir=None, session=None) -> MapControl:
    """The team control of a session on `compiled`: a PlainMap on the default map, else a MapControl."""
    from halo_harness.crew.compile import is_default
    lineup = plain_lineup(cwd, state_dir) if is_default(compiled) else None
    if lineup is not None:
        return PlainMap(compiled, lineup, cwd=cwd, state_dir=state_dir, session=session)
    return MapControl(compiled, cwd=cwd, state_dir=state_dir, session=session)
