"""halo_harness.teams_runtime -- Halo 2.0.5 round 5 "team control": the
lineup sections ENFORCED by the live agent loop. `teams_yaml.py` stays the
schema/storage layer; this module is the runtime state machine a session
holds while it runs under a team (`team:` in config.json or `--team`):

- `routing`: a task kind -> role/alias (with `default`), applied to every
  Agent call at spawn time when the call named no `role` of its own.
- `delegation`: `max_depth` (the session's own depth cap), `max_parallel`
  (the session's own in-flight spawn cap), `handoff` shape and
  `forward_text` (what the parent hands the child / gets back).
- `budget`: `max_budget_usd`/`max_total_turns`/`max_wall_time` -- when
  exhausted the team STOPS DELEGATING and says so in one line (a stop with
  the reason, never a judgement of the request); `agents_may_exceed: true`
  makes the budget advisory for members while still counting it.
- `escalation`: `triggers` (tool_failures/context_overflow/budget_exhausted)
  -> `to` model, `ask: true` shows the existing approval card first,
  `false` switches and announces (the switch itself lives in
  `agent/loop.py`, which owns models -- this module only DECIDES).
- `context`/`permissions`: files/skills/memory.namespace+writers and
  mode/rules/offline applied to every member on top of the bio's own.
- `org`: `reports_to` addresses each member's one-line hand-back report.
- `pipeline`: stages in order; a `required` gate must pass its stage's
  acceptance before the next stage starts, an `optional` one records and
  continues (`agents_doctor.check_expectation` is the checker).
"""

from __future__ import annotations

import re
import threading
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional


def active_team_name(cli_flag: Optional[str] = None) -> Optional[str]:
    """`--team` (this one run) -> config's own `team:` key."""
    if cli_flag:
        return cli_flag
    try:
        from halo_harness.theme import get_config_value
        name = get_config_value("team", default=None)
        return name if isinstance(name, str) and name.strip() else None
    except Exception:
        return None


def _duration_seconds(raw) -> "Optional[float]":
    """A budget `max_wall_time` value -- a bare number is seconds, a
    string like `3h`/`30m` parses through the same duration reader
    `agents_yaml` validates the field with."""
    if isinstance(raw, (int, float)) and not isinstance(raw, bool) and raw > 0:
        return float(raw)
    from halo_harness.agents_yaml import parse_every_duration
    return parse_every_duration(raw)


@dataclass
class TeamControl:
    """One live session's enforced lineup. Thread-safe: every mutating call
    runs under `lock` (parallel children call back into the same object)."""
    name: str
    template: dict
    aliases: dict = field(default_factory=dict)     # role/alias -> assignment entry
    started_at: float = field(default_factory=time.time)
    lock: threading.Lock = field(default_factory=threading.Lock)
    spend_usd: float = 0.0
    turn_count: int = 0
    reports: list = field(default_factory=list)
    stage_results: dict = field(default_factory=dict)  # stage name -> {"passed": bool, "note": str}
    budget_stopped: Optional[str] = None
    escalated: bool = False

    # ---- sections (read-only views of the resolved template) --------------
    @property
    def delegation(self) -> dict:
        return self.template.get("delegation") or {}

    @property
    def routing(self) -> dict:
        return self.template.get("routing") or {}

    @property
    def budget(self) -> dict:
        return self.template.get("budget") or {}

    @property
    def escalation(self) -> dict:
        return self.template.get("escalation") or {}

    @property
    def context(self) -> dict:
        return self.template.get("context") or {}

    @property
    def permissions(self) -> dict:
        return self.template.get("permissions") or {}

    @property
    def stages(self) -> list:
        return (self.template.get("pipeline") or {}).get("stages") or []

    # ---- routing -----------------------------------------------------------
    def route_call(self, tool_input: dict, description: str) -> "tuple[Optional[str], Optional[str]]":
        """`(kind, target)` for one Agent call: an explicit `role=` always
        wins (the model chose), else the first `routing` key (or a member's
        own `use_for` word) appearing in the description/prompt, else the
        template's `default`. `(None, None)` when the template routes
        nothing and has no default."""
        if tool_input.get("role"):
            return None, None
        routing = dict(self.routing)
        routing.pop("default", None)
        text = f"{description or ''}\n{tool_input.get('prompt') or ''}".lower()
        for kind, target in routing.items():
            if re.search(rf"\b{re.escape(kind.lower())}\b", text):
                return kind, target
        for target, entry in self.aliases.items():
            for word in (entry.get("use_for") or []):
                if isinstance(word, str) and re.search(rf"\b{re.escape(word.lower())}\b", text):
                    return word, target
        default = self.routing.get("default")
        return ("default", default) if default else (None, None)

    def assignment_for(self, target: Optional[str]) -> Optional[dict]:
        if not target:
            return None
        return self.aliases.get(target)

    def bio_for(self, target: Optional[str]) -> Optional[dict]:
        entry = self.assignment_for(target)
        if not entry:
            return None
        from halo_harness.agents_yaml import resolve_agent_bio
        return resolve_agent_bio(entry.get("agent"))

    # ---- budget ------------------------------------------------------------
    @property
    def budget_exhausted(self) -> bool:
        return self.budget_stopped is not None

    def budget_refusal(self) -> Optional[str]:
        """The one-line stop when the budget is out, else None (and records
        the stop reason so `budget_exhausted` can drive escalation)."""
        b = self.budget
        with self.lock:
            if self.budget_stopped is not None:
                return self._stopped_line()
            cap_usd = b.get("max_budget_usd")
            if cap_usd is not None and self.spend_usd >= float(cap_usd):
                self.budget_stopped = f"team budget max_budget_usd={cap_usd} exhausted (spent ${self.spend_usd:.4f})"
            else:
                cap_turns = b.get("max_total_turns")
                if cap_turns is not None and self.turn_count >= int(cap_turns):
                    self.budget_stopped = f"team budget max_total_turns={cap_turns} exhausted ({self.turn_count} turns)"
                else:
                    cap_wall = b.get("max_wall_time")
                    wall_s = _duration_seconds(cap_wall)
                    if cap_wall is not None and wall_s is not None \
                            and (time.time() - self.started_at) >= wall_s:
                        self.budget_stopped = f"team budget max_wall_time={cap_wall} exhausted"
            if self.budget_stopped is None:
                return None
        return self._stopped_line()

    def _stopped_line(self) -> str:
        advisory = (" -- members may still run (agents_may_exceed: true)"
                    if self.budget.get("agents_may_exceed") else " -- delegation stopped")
        return f"{self.budget_stopped}{advisory}; finish the work in the main session instead."

    def record_spend(self, usd: float) -> None:
        with self.lock:
            self.spend_usd += float(usd or 0.0)

    def record_turn(self, turns: int = 1) -> None:
        with self.lock:
            self.turn_count += int(turns)

    # ---- pipeline ----------------------------------------------------------
    def stage_for(self, kind: Optional[str], target: Optional[str]) -> Optional[dict]:
        for stage in self.stages:
            if kind and stage.get("name") == kind:
                return stage
            if target and stage.get("role") == target:
                return stage
        return None

    def gate_block(self, stage: Optional[dict]) -> Optional[str]:
        """A `required` gate that has not passed blocks every LATER stage --
        the one-line stop naming which stage waits on which."""
        if not stage:
            return None
        for earlier in self.stages:
            if earlier.get("name") == stage.get("name"):
                return None
            if earlier.get("gate") != "required":
                continue
            result = self.stage_results.get(earlier.get("name"))
            if result is None or not result.get("passed"):
                return (f"stage {stage.get('name')!r} waits on stage {earlier.get('name')!r} -- its required "
                        f"gate has not passed yet; finish that stage first.")
        return None

    def evaluate_stage(self, stage: dict, child_text: str, call_fn=None) -> "tuple[bool, str]":
        """`(ok, one_line)` -- the stage's own `acceptance` (or its
        assignment bio's) checked against the member's result text, or
        through `call_fn(role, prompt)` when the acceptance names a prompt
        (`agents_doctor`'s real subprocess path / a test's fake)."""
        from halo_harness.agents_doctor import check_expectation
        acceptance = stage.get("acceptance")
        if not acceptance:
            bio = self.bio_for(stage.get("role"))
            acceptance = (bio or {}).get("acceptance") or {}
        expect = acceptance.get("expect") or "non-empty"
        prompt = acceptance.get("prompt")
        if prompt and call_fn is not None:
            try:
                response = call_fn(stage.get("role"), prompt)
                return check_expectation(response or "", expect), f"acceptance {expect!r}: {(response or '')[:80]!r}"
            except Exception as e:
                return False, f"acceptance run failed: {type(e).__name__}"
        ok = check_expectation(child_text or "", expect)
        return ok, f"acceptance {expect!r} on the stage result"

    def record_stage(self, stage: dict, ok: bool, note: str) -> None:
        with self.lock:
            self.stage_results[stage.get("name")] = {"passed": bool(ok), "note": note}

    # ---- member shaping ------------------------------------------------------
    def member_context_addition(self, target: Optional[str], *, cwd=None, state_dir=None) -> str:
        """Team-level context (files/skills/memory) plus the bio's own --
        everything a member gets on top of its spec body."""
        from halo_harness.teams_yaml import member_system_context_addition
        parts: "list[str]" = []
        context = self.context
        base = Path(cwd) if cwd is not None else Path.cwd()
        for rel in context.get("files") or []:
            try:
                path = Path(rel)
                path = path if path.is_absolute() else base / path
                parts.append(path.read_text(encoding="utf-8"))
            except OSError:
                continue
        skills = context.get("skills") or []
        if skills:
            parts.append("Team skills (invoke by name): " + ", ".join(str(s) for s in skills))
        entry = self.assignment_for(target)
        bio_name = (entry or {}).get("agent")
        if bio_name:
            addition = member_system_context_addition(bio_name, team_name=self.name, cwd=cwd, state_dir=state_dir)
            if addition:
                parts.append(addition)
        return "\n\n".join(p for p in parts if p and p.strip())

    def member_hooks(self, target: Optional[str]) -> dict:
        """The bio's own `hooks` merged with the assignment's `hooks`
        override (the override wins per key) -- the same
        pre_tool/post_tool/on_start/on_finish shape `agents_yaml` validates."""
        bio = self.bio_for(target) or {}
        hooks = dict(bio.get("hooks") or {})
        override = (self.assignment_for(target) or {}).get("hooks") or {}
        hooks.update(override)
        return hooks

    def member_memory(self, target: Optional[str], state_dir) -> "tuple[Optional[Path], bool]":
        """`(dir, may_write)` for `context.memory` -- a namespaced shared
        memory directory under `<state>/teams/<name>/memory/`, writable
        only by `writers` (role/alias list; everyone else reads)."""
        memory = self.context.get("memory") or {}
        namespace = memory.get("namespace")
        if not namespace:
            return None, False
        directory = Path(state_dir) / "teams" / self.name / "memory" / str(namespace)
        writers = memory.get("writers") or []
        return directory, (target in writers)

    def member_permissions(self) -> dict:
        """`{mode, deny, ask, allow, offline}` -- the team's own permissions
        section (rules in the same settings.json grammar the parent engine
        already takes), applied on top of each member bio's own."""
        p = self.permissions
        rules = p.get("rules") or {}
        return {"mode": p.get("mode"),
                "deny": list(rules.get("deny") or []),
                "ask": list(rules.get("ask") or []),
                "allow": list(rules.get("allow") or []),
                "offline": bool(p.get("offline"))}

    def handoff_text(self, target: Optional[str], text: str, *, cost_usd: float = 0.0,
                     child_log_path: Optional[str] = None) -> str:
        """The `delegation.handoff` shape applied to a member's hand-back."""
        shape = self.delegation.get("handoff") or "summary"
        if shape == "summary" or not text:
            return text
        if shape == "full":
            log = f"\n\n[full transcript: {child_log_path}]" if child_log_path else ""
            return f"{text}{log}"
        # structured
        entry = self.assignment_for(target) or {}
        lines = [f"[handoff] role: {target or entry.get('role') or '?'}",
                 f"[handoff] status: {'empty result' if not text.strip() else 'done'}",
                 f"[handoff] cost_usd: {cost_usd:.4f}",
                 "[handoff] result:", text]
        return "\n".join(lines)

    def record_report(self, target: Optional[str], one_line: str) -> str:
        """`org`: every member's completion is a one-line report addressed to
        the position it reports to (a plain hand-back to the spawner when
        the org names none)."""
        reports_to = None
        entry = self.assignment_for(target) or {}
        for p in (self.template.get("org") or {}).get("positions") or []:
            if isinstance(p, dict) and (p.get("agent") == entry.get("agent") or p.get("title") == target):
                reports_to = p.get("reports_to")
                break
        line = f"[team {self.name}] {target or 'member'} -> {reports_to or 'main'}: {one_line}"
        with self.lock:
            self.reports.append(line)
        return line

    # ---- escalation ---------------------------------------------------------
    def escalation_decision(self, *, tool_failures: bool = False, context_overflow: bool = False) -> "Optional[tuple]":
        """`(trigger, to_ref, ask)` when the team's escalation section says
        to switch NOW, else None. `budget_exhausted` reads this control's
        own budget state; the other two arrive already thresholded from
        the caller's turn (the same `TOOL_FAILURE_THRESHOLD` /
        `_turn_context_overflow_count` the local escalation path uses)."""
        section = self.escalation
        to = section.get("to")
        if not to:
            return None
        triggers = section.get("triggers") or []
        trigger = None
        if "budget_exhausted" in triggers and self.budget_exhausted:
            trigger = "budget_exhausted"
        elif "tool_failures" in triggers and tool_failures:
            trigger = "tool_failures"
        elif "context_overflow" in triggers and context_overflow:
            trigger = "context_overflow"
        if trigger is None or self.escalated:
            return None
        return trigger, to, bool(section.get("ask"))


def load_team_control(name: Optional[str] = None, *, cwd=None, state_dir=None) -> Optional[TeamControl]:
    """Resolve the named (or active) team template into a TeamControl, or
    None when nothing is active / the template fails to resolve. Never
    raises."""
    from halo_harness.teams_yaml import resolve_team_template
    team_name = name or active_team_name()
    if not team_name:
        return None
    try:
        template = resolve_team_template(team_name, cwd=cwd, state_dir=state_dir)
    except Exception:
        return None
    if not template:
        return None
    aliases: dict = {}
    for entry in template.get("agents") or []:
        if isinstance(entry, dict) and entry.get("role"):
            aliases[entry.get("as") or entry["role"]] = entry
    return TeamControl(name=team_name, template=template, aliases=aliases)
