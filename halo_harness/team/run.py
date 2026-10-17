"""halo_harness.team.run -- the team runner.

`TeamRunner(team, run_dir, ...)` drives one run's board. `request(stage)`
queues a stage (manual, or a trigger); `tick()` is one pass: it honours
`stop.json`, applies gate answers (`accept` -> done and every
`stage_done:<it>` stage queued; `redo` -> the stage runs again with the
text; `stop` -> the run ends), polls delegated members and the block
watchers, then runs the queued stages one at a time (team/run_stage.py). It
answers whether anything is still live (a running or gated stage, a queued
one, or, with `watch`, an armed block watcher). `loop()` ticks until idle.

All model work goes through seams, so tests use fakes:

    SPAWN(member, prompt, *, cwd, env, stage, run_dir) -> {ok, text, cost_usd, error, session_id}
    ORCHESTRA(goal, *, root, stage, run_dir)           -> {ok, text, cost_usd, error, run_id}
    FLOW(name, *, intake, cwd, stage, run_dir)         -> {ok, text, cost_usd, error, run_id}
    DISPATCH.send(member, task) -> (status, body)       200 running | 202 asked | 403 refused | other failed
    DISPATCH.poll(handle) -> None | {state: asked|running} | {ok, state, text, cost_usd, error}
    ACCEPT(role, prompt) -> reply text                  (an acceptance with a prompt)

None means the real ones (team/adapters.py, team/delegate.py).
"""

from __future__ import annotations

import time
from pathlib import Path
from typing import Callable, Optional

from halo_harness.team import board as BD
from halo_harness.team import spec as S
from halo_harness.team import stages as ST
from halo_harness.team.triggers import BlockWatch

SPAWN: Optional[Callable] = None
ORCHESTRA: Optional[Callable] = None
FLOW: Optional[Callable] = None
DISPATCH = None
ACCEPT: Optional[Callable] = None
POLL_S = 0.5
FINAL = ("done", "failed", "skipped")


def rows_for(team: dict, *, cwd=None, state_dir=None) -> list:
    rows = []
    for s in team["workflow"]["stages"]:
        members = S.stage_members(team, s, cwd=cwd, state_dir=state_dir)
        lead = S.stage_lead(team, s, members)
        m = S.member_by_name(team, lead)
        rows.append(BD.stage_row(s, members, lead, m.get("harness") if m and s["kind"] == "agent" else None))
    return rows


def open_run(team: dict, *, run: Optional[str] = None, new: bool = False, cwd=None, state_dir=None) -> Path:
    """The named run, else the latest open run, else a new one."""
    root = Path(team["root"])
    if run:
        found = BD.find_run(root, run)
        if found is None:
            raise ValueError(f"no team run {run!r} in {root}")
        return found
    found = None if new else BD.latest_run(root, open_only=True)
    return found or BD.new_run(root, team, rows_for(team, cwd=cwd, state_dir=state_dir))


class TeamRunner:
    def __init__(self, team: dict, run_dir, *, spawn=None, orchestra=None, flow=None, dispatch=None, accept=None,
                 clock: Callable = time.time, watch: bool = False, cwd=None, state_dir=None):
        from halo_harness.team import adapters
        self.team, self.run_dir, self.root = team, Path(run_dir), Path(team["root"])
        self.spawn = spawn or SPAWN or adapters.spawn_member
        self.orchestra = orchestra or ORCHESTRA or adapters.run_orchestra
        self.flow = flow or FLOW or adapters.run_flow
        self.dispatch = dispatch or DISPATCH
        self.accept = accept or ACCEPT
        self.clock, self.watching, self.cwd, self.state_dir = clock, watch, cwd, state_dir
        self.queue: "list[tuple[str, str]]" = []
        self.live: dict = {}
        self.watch = BlockWatch(team, fire_fn=self._on_block, clock=clock)
        for s in team["workflow"]["stages"]:
            self.watch.arm_block(s)

    # ---- board helpers -------------------------------------------------------
    def board(self) -> dict:
        return BD.read_board(self.run_dir)

    def row(self, sid: str) -> dict:
        return BD.row(self.board(), sid) or {}

    def stage(self, sid: str) -> dict:
        s = S.stage_by_id(self.team, sid)
        if s is None:
            raise ValueError(f"team {self.team['name']} has no stage {sid!r} "
                             f"(stages: {', '.join(x['id'] for x in self.team['workflow']['stages'])})")
        return s

    def delegate(self):
        if self.dispatch is None:
            from halo_harness.team.delegate import FleetDelegate
            self.dispatch = FleetDelegate()
        return self.dispatch

    # ---- starting stages -----------------------------------------------------
    def request(self, sid: str, why: str = "manual", redo: str = "") -> bool:
        """Queue a stage; False when it is already running or queued."""
        self.stage(sid)
        if self.board().get("state") != "open":
            return False
        if sid in self.live or any(q[0] == sid for q in self.queue) or self.row(sid).get("state") == "running":
            return False
        self.queue.append((sid, redo))
        BD.log(self.run_dir, "trigger", f"{sid} starts: {why}", stage=sid, why=why)
        BD.set_stage(self.run_dir, sid, "ready", why)
        return True

    def _on_block(self, _session, entry: dict) -> str:
        return "queued" if self.request(entry["stage"], f"block {entry['block']} changed") else "already running"

    def fire_done(self, sid: str) -> None:
        for s in self.team["workflow"]["stages"]:
            kind, target = S.parse_trigger(s["trigger"])
            if kind == "stage_done" and target == sid:
                self.request(s["id"], f"stage {sid} done")

    # ---- answers and stop ------------------------------------------------------
    def apply_answer(self, sid: str, ans: dict) -> None:
        row = self.row(sid)
        BD.set_stage(self.run_dir, sid, gate_answer=ans)
        if ans["action"] == "stop":
            return self.stop_run(ans.get("text") or f"stopped at the gate of {sid}")
        if ans["action"] == "redo":
            BD.set_stage(self.run_dir, sid, "ready", "redo")
            self.queue.append((sid, ans.get("text") or "do it again"))
            return None
        was_gated = row.get("state") == "gated"
        BD.set_stage(self.run_dir, sid, "done", "accepted")
        if was_gated:
            self.fire_done(sid)
        return None

    def stop_run(self, reason: str) -> None:
        for sid, live in list(self.live.items()):
            for handle in (live.get("handles") or {}).values():
                try:
                    getattr(self.delegate(), "stop", lambda *a: False)(handle, reason)
                except Exception:
                    pass
        self.live.clear()
        self.queue.clear()

        def apply(board: dict) -> None:
            board["state"], board["stop_reason"] = "stopped", reason
            for r in board.get("stages") or []:
                if r.get("state") in ("pending", "ready", "running", "gated"):
                    r["state"], r["waiting"] = "skipped", ""
        BD.update_board(self.run_dir, apply)
        for s in self.team["workflow"]["stages"]:
            ST.close_gate(self.run_dir, s["id"])
        BD.log(self.run_dir, "report", f"run stopped: {reason}", status="stopped", reason=reason)

    # ---- the tick ----------------------------------------------------------------
    def tick(self) -> bool:
        from halo_harness.team.run_stage import poll_live, run_queued
        if self.board().get("state") != "open":
            return False
        reason = BD.stop_requested(self.run_dir)
        if reason:
            BD.stop_path(self.run_dir).unlink(missing_ok=True)
            self.stop_run(reason)
            return False
        BD.beat(self.run_dir)
        for r in self.board().get("stages") or []:
            if ST.read_gate(self.run_dir, r["id"]):
                ans = ST.take_answer(self.run_dir, r["id"])
                if ans is not None:
                    self.apply_answer(r["id"], ans)
                    if self.board().get("state") != "open":
                        return False
        poll_live(self)
        self.watch.poll()
        run_queued(self)
        self._settle_run()
        return self.active()

    def _settle_run(self) -> None:
        board = self.board()
        rows = board.get("stages") or []
        if board.get("state") == "open" and rows and all(r.get("state") in ("done", "skipped") for r in rows) \
                and not self.queue and not self.live:
            gated = [r["id"] for r in rows if ST.read_gate(self.run_dir, r["id"])]
            if not gated:
                BD.update_board(self.run_dir, lambda b: b.update(state="done"))
                BD.log(self.run_dir, "report", f"run done: ${BD.cost(board):.4f}", status="done",
                       cost_usd=BD.cost(board))

    def status(self) -> str:
        """busy (a stage runs or is queued), gated (only answers are awaited),
        watching (only block watchers are armed, with `watch`), idle or over."""
        board = self.board()
        if board.get("state") != "open":
            return "over"
        rows = board.get("stages") or []
        if self.queue or self.live or any(r.get("state") in ("running", "ready") for r in rows):
            return "busy"
        if any(ST.read_gate(self.run_dir, r["id"]) for r in rows):
            return "gated"
        if self.watching and any(t["stage"] for t in self.watch.armed()):
            return "watching"
        return "idle"

    def active(self) -> bool:
        return self.status() in ("busy", "gated", "watching")

    def adopt(self) -> None:
        """A new runner over an existing run: queued rows queue again; a row a
        runner that ended left `running` fails with that reason."""
        for r in self.board().get("stages") or []:
            if r.get("state") == "ready" and not any(q[0] == r["id"] for q in self.queue):
                self.queue.append((r["id"], ""))
            elif r.get("state") == "running" and r["id"] not in self.live:
                BD.set_stage(self.run_dir, r["id"], "failed", "the runner that ran it ended",
                             error="the runner that ran it ended: run it again with halo team run " + r["id"],
                             ended=round(time.time(), 3), waiting="")

    def loop(self, *, until: str = "idle", poll_s: float = POLL_S, sleep: Callable = time.sleep,
             max_ticks: Optional[int] = None) -> dict:
        """Tick until the run is idle (`until="gate"`: also stop when only a gate waits)."""
        n = 0
        try:
            while self.tick():
                if until == "gate" and self.status() == "gated":
                    break
                n += 1
                if max_ticks is not None and n >= max_ticks:
                    break
                sleep(poll_s)
        finally:
            BD.beat(self.run_dir, clear=True)
        return self.board()
