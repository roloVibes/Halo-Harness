"""halo_harness.team.parallel -- the members of one agent stage run at the same
time (Halo 3.1.2.0 R2; team/run_stage.py calls it, docs/TEAM.md).

Every member that is not the lead starts at once, in a thread pool bounded
by `limit`: the tightest `max_parallel` of the members' lineup tiers
(`TeamControl.tier_of`, teams_tiers.py); members whose tiers set none run
all at once, capped at CAP. A member on another harness of the fleet goes
out through DISPATCH and holds its slot until its result lands. The lead
runs after them with their hand-backs, as before.

Each member's work is a unit of its own on the one machine (work/states.py):

    ready -> running -> done | failed       (a delegated member: ready -> running | waiting -> ...)

and the stage row carries it as `members_state: {name: state}` (machine
words), each move logged as a `state` line naming the member, so Studio's
`team` frames carry the row with it. A member that fails does not stop the
others: they finish, and then the stage fails (the lead is not run).
"""

from __future__ import annotations

from concurrent.futures import FIRST_COMPLETED, ThreadPoolExecutor, wait
from typing import Callable, Optional

from halo_harness.team import board as BD
from halo_harness.team import spec as S
from halo_harness.work.states import check_move

CAP = 8


def limit(team: dict, names: list, *, cwd=None, state_dir=None) -> int:
    """How many of `names` run at once: the tightest `max_parallel` of their tiers, else all (at most CAP)."""
    from halo_harness.team.resolve import _lineup
    from halo_harness.teams_runtime import TeamControl
    cache: dict = {}
    caps = []
    for name in names:
        m = S.member_by_name(team, name)
        lineup = _lineup(m["lineup"], cwd, state_dir, cache) if m and m.get("lineup") else None
        if not lineup:
            continue
        control = TeamControl(name=m["lineup"], template=lineup)
        index = control.tier_of(m["role"])
        cap = control.tiers[index].get("max_parallel") if index is not None else None
        if cap:
            caps.append(int(cap))
    return max(1, min(caps)) if caps else max(1, min(len(names) or 1, CAP))


def initial(workers: list, lead: str) -> dict:
    """`members_state` as a round starts: every member ready; a lead that merges others' hand-backs pending."""
    out = {m: "ready" for m in workers}
    if lead:
        out[lead] = "pending" if workers else "ready"
    return out


def mark(runner, sid: str, name: str, state: str, text: str = "") -> None:
    """Move member `name` of stage `sid` to machine state `state` (through the machine's edges) on its row."""
    moved: dict = {}

    def apply(board: dict) -> None:
        row = BD.row(board, sid)
        if row is None:
            return
        states = dict(row.get("members_state") or {})
        was = states.get(name) or "pending"
        check_move(f"member {name} of stage {sid}", was, state)
        if was != state:
            states[name] = state
            row["members_state"] = states
            moved["was"] = was
    BD.update_board(runner.run_dir, apply)
    if moved:
        BD.log(runner.run_dir, "state", f"{sid}: {name} {state}" + (f" ({text})" if text else ""), stage=sid,
               member=name, member_state=state, was=moved["was"])


def run_members(runner, sid: str, names: list, launch: Callable[[str], Optional[Callable]],
                result_of: Callable[[object], dict]) -> None:
    """Start every member of `names` without a result yet, at most the stage's cap at once, and wait for the
    ones that run here. `launch(name)` returns the call to run in the pool, or None for a member that went
    out through DISPATCH (it holds a slot through `live["handles"]` until poll_live lands its result)."""
    live = runner.live[sid]
    todo = [n for n in names if n not in live["results"] and n not in live["handles"]]
    if not todo:
        return
    cap = int(live.get("cap") or CAP)
    with ThreadPoolExecutor(max_workers=max(1, min(cap, len(todo))), thread_name_prefix=f"team-{sid}") as pool:
        running: dict = {}
        while todo or running:
            while todo and len(running) + len(live["handles"]) < cap:
                name = todo.pop(0)
                job = launch(name)
                if job is not None:
                    mark(runner, sid, name, "running")
                    running[pool.submit(job)] = name
            if not running:
                return  # the rest wait for a delegated member's slot: the next tick starts them
            done, _ = wait(list(running), return_when=FIRST_COMPLETED)
            for future in done:
                name = running.pop(future)
                try:
                    raw = future.result()
                except Exception as e:  # a member's own failure never takes the runner down
                    raw = {"ok": False, "error": f"{type(e).__name__}: {e}"}
                res = result_of(raw)
                live["results"][name] = res
                mark(runner, sid, name, "done" if res.get("ok") else "failed", "" if res.get("ok") else res.get("error", ""))
