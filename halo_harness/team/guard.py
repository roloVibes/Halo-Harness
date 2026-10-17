"""halo_harness.team.guard -- a stage's writes, checked at the permission engine.

An agent stage's session runs with `$HALO_TEAM_SCOPE=<run>/stages/<id>/scope.json`

    {root, run_dir, stage, member, holder, writes: [block ids], blocks: [<block>]}

and `install_from_env(engine, session_dir)` (agent/loop.py, beside the
Orchestra's ClaimGuard) adds a `TeamClaimGuard` to `engine.guards`. For
Write, Edit, MultiEdit and NotebookEdit on a path inside the repo:

* a path in a block ledger (`.halo-block`) or the run ledger (`.halo/team`)
  -> deny: the team runner writes those;
* a path whose innermost block is not one of the stage's `writes` (or that
  sits in no block) -> deny, naming the block and the stage's write blocks;
* a claim key another holder has live -> deny, naming the block, the key,
  the holder and when the claim runs out;
* otherwise the member claims each free key (`<member>@<stage>`), the claim
  moves to `writing`, one `changes.jsonl` line lands in the block's ledger
  and a `change` line in the run's events.jsonl -> allow.

A deny also logs a `claim` line with `refused: true` in the run's log. A
path outside the repo keeps the base decision; an `ask` from the user's own
ask rule stays an ask.
"""

from __future__ import annotations

import os
import time
from pathlib import Path
from typing import Callable, Optional

from halo_harness.orchestra import jsonl
from halo_harness.orchestra.claims import clock_text
from halo_harness.orchestra.index import overlaps
from halo_harness.team import LEDGER_DIR, RUNS_DIR, SCOPE_ENV
from halo_harness.team import blocks as B

GUARDED_TOOLS = ("Write", "Edit", "MultiEdit", "NotebookEdit")


def write_scope(path, *, root, run_dir, stage: str, member: str, writes: list, blocks: list) -> Path:
    jsonl.write_json(path, {"root": str(root), "run_dir": str(run_dir), "stage": stage, "member": member,
                            "holder": B.holder_of(member, stage), "writes": list(writes), "blocks": list(blocks)})
    return Path(path)


class TeamClaimGuard:
    def __init__(self, scope: dict, *, clock: Callable[[], float] = time.time):
        self.scope = scope
        self.root = Path(scope["root"]).resolve()
        self.run_dir = Path(scope["run_dir"]) if scope.get("run_dir") else None
        self.stage, self.member = str(scope.get("stage") or ""), str(scope.get("member") or "")
        self.holder = str(scope.get("holder") or B.holder_of(self.member, self.stage))
        self.writes = list(scope.get("writes") or [])
        self.team = {"blocks": list(scope.get("blocks") or []), "root": str(self.root)}
        self.clock = clock

    @classmethod
    def from_file(cls, path, **kw) -> Optional["TeamClaimGuard"]:
        data = jsonl.read_json(path, None)
        return cls(data, **kw) if isinstance(data, dict) and data.get("root") else None

    # ---- the run log --------------------------------------------------------
    def _event(self, kind: str, text: str, **data) -> None:
        if self.run_dir is None:
            return
        try:
            from halo_harness.team.board import log
            log(self.run_dir, kind, text, stage=self.stage, member=self.member, holder=self.holder, **data)
        except (OSError, ValueError):
            pass

    def _deny(self, text: str, **data):
        from halo_harness.permissions import Decision
        self._event("claim", text, refused=True, **data)
        return Decision("deny", text, source="team")

    # ---- the check ----------------------------------------------------------
    def target(self, tool_name: str, tool_input: dict, cwd=None) -> Optional[Path]:
        raw = tool_input.get("notebook_path") if tool_name == "NotebookEdit" else tool_input.get("file_path")
        if not raw:
            return None
        p = Path(str(raw))
        if not p.is_absolute():
            p = Path(cwd or self.root) / p
        return p.resolve()

    def check(self, tool_name: str, tool_input, decision, engine=None):
        if tool_name not in GUARDED_TOOLS or not isinstance(tool_input, dict):
            return None
        path = self.target(tool_name, tool_input, getattr(engine, "cwd", None))
        if path is None:
            return None
        try:
            rel = path.relative_to(self.root).as_posix()
        except ValueError:
            return None
        parts = Path(rel).parts
        if any(p.endswith(LEDGER_DIR) for p in parts) or tuple(parts[:2]) == RUNS_DIR:
            return self._deny(f"`{rel}` is a team ledger file: the team runner writes it, the stage writes its blocks "
                              f"({', '.join(self.writes) or 'none'})", path=rel)
        block = B.block_for(self.team, self.root, path)
        if block is None or block["id"] not in self.writes:
            where = f"block `{block['id']}`" if block else "no block"
            return self._deny(f"`{rel}` is in {where}; stage `{self.stage}` writes "
                              f"{', '.join(f'`{w}`' for w in self.writes) or 'no block'}", path=rel,
                              block=block["id"] if block else None)
        keys = B.keys_for(self.root, block, path, tool_name, tool_input)
        if block["claims"] != "none":
            denied = self._claim(block, keys, rel)
            if denied is not None:
                return denied
        op = "write" if tool_name in ("Write", "NotebookEdit") else "edit"
        for key in keys:
            line = B.record_change(self.root, block, by=self.holder, member=self.member, stage=self.stage, op=op,
                                   key=key, summary=f"{tool_name} {rel}", clock=self.clock)
            self._event("change", f"{self.holder} {op} {key} in block {block['id']}", block=block["id"], change=line)
        if decision.action == "ask" and getattr(decision, "matched_rule", None) is not None:
            return None
        from halo_harness.permissions import Decision
        return Decision("allow", f"block `{block['id']}`, held by {self.holder}: " + ", ".join(f"`{k}`" for k in keys),
                        source="team")

    def _claim(self, block: dict, keys: list, rel: str):
        log = B.claim_log(self.root, block, clock=self.clock)
        B.ensure_ledger(self.root, block)
        now = log.clock()
        active = log.active(now)
        for key in keys:
            foreign = [c for c in active.values() if c.holder != self.holder and overlaps(c.key, key)]
            if foreign:
                c = foreign[0]
                return self._deny(f"block `{block['id']}`: `{c.key}` is held by {c.holder} until "
                                  f"{clock_text(c.expires)} ({c.state}); wait for its release or write another part",
                                  block=block["id"], key=c.key, by=c.holder, path=rel)
        for key in keys:
            if log.held_by(self.holder, key, now) is None:
                result = log.claim(self.holder, key, note=f"stage {self.stage}")
                if not result.ok:
                    return self._deny(f"block `{block['id']}`: {result.text}", block=block["id"], key=key,
                                      by=result.holder, path=rel)
                self._event("claim", f"{self.holder} claimed {key} in block {block['id']}", block=block["id"],
                            key=key, op="claim")
            held = log.held_by(self.holder, key, now)
            if held is not None:
                log.mark_writing(self.holder, held.key, note="a write by the stage")
        B.write_state(self.root, block, log)
        return None


def install_from_env(engine, session_dir=None, env=None) -> Optional[TeamClaimGuard]:
    """Add a TeamClaimGuard for `$HALO_TEAM_SCOPE` to `engine.guards`; None outside a team stage."""
    value = (env if env is not None else os.environ).get(SCOPE_ENV)
    guards = getattr(engine, "guards", None) if engine is not None else None
    if not value or guards is None:
        return None
    for g in guards:
        if isinstance(g, TeamClaimGuard) and g.scope.get("_path") == value:
            return g
    guard = TeamClaimGuard.from_file(value)
    if guard is None:
        return None
    guard.scope["_path"] = value
    guards.append(guard)
    return guard
