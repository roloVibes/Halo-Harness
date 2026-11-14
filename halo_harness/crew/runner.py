"""halo_harness.crew.runner -- the step runner: a workflow/1 file run step by step (Halo 3.6.0.0 R2; docs/STUDIO-workflows.md).

    run(wf, request, *, resolve, backend, files=(), emit=None) -> Result

A workflow is steps in order. Each step's agents run at the same time; what each hands back, under its name, is the
step's hand-on text, and the next step gets it together with its own "Gets" words. A step's "When it runs" decides
whether it runs at all (crew/runner_when.py: always / only when the task needs X / only when the task says X / only
when I ask). "Repeat until": after the step, ONE yes/no call by the step's last agent against the until text; no runs
the step again with what it handed on, at most `max` times (default 3, never more than CEILING). Nothing loops past
that: a check that never says yes ends the step at `max` rounds and the receipt says so.

Every model call goes through `backend` (crew/runner_session.py spawns each agent as a child through agent/subagent.py
with the spec crew/spec.py builds; tests pass a fake). Before every call the run checks the money: the workflow's own
`max_usd` (when set) and the session's cap (`backend.session_left()`, None when it has none); either reached stops the
run with one plain line and what was done so far. A step naming an agent that does not exist, or one whose file has a
problem, stops the run BEFORE any model call with the problem line.

`emit(kind, data)` hears the run as it goes: start, step, agent, check, end (the Try it record and Studio's `crew`
frames are made from these).
"""

from __future__ import annotations

import time
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field
from typing import Callable, Optional

from halo_harness.crew import runner_text as T
from halo_harness.crew.formats import agent_problems, workflow_problems
from halo_harness.crew.runner_when import decide

CEILING = 10
DEFAULT_MAX = 3


@dataclass
class Call:
    """One agent's turn as the backend reports it."""
    text: str = ""
    cost_usd: float = 0.0
    ok: bool = True
    error: str = ""
    seconds: float = 0.0
    used: dict = field(default_factory=dict)


@dataclass
class Result:
    state: str = "done"              # done | failed | capped | stopped
    line: str = ""                   # the one plain line on how it ended
    text: str = ""                   # the last step's hand-on text
    cost_usd: float = 0.0
    steps: list = field(default_factory=list)   # [{n, name, state, why, rounds, stop, agents: [...], cost_usd}]


def preflight(wf: dict, resolve: Callable) -> "tuple[list, dict]":
    """(problem lines, {agent name: its file}) -- every agent of every step found and well formed, else the lines."""
    bad = [f"the workflow: {p}" for p in workflow_problems(wf)]
    agents: dict = {}
    for i, s in enumerate(wf.get("steps") or [], 1):
        for name in (s.get("agents") or []) if isinstance(s, dict) else []:
            if name in agents:
                continue
            raw = resolve(name)
            if raw is None:
                bad.append(f"step {i} ({s.get('name')}): no agent named {name} (make it, or take it out of the step)")
                continue
            probs = agent_problems({k: v for k, v in raw.items() if not str(k).startswith("_")}, name=name)
            if probs:
                bad.append(f"step {i} ({s.get('name')}): the agent {name} has a problem: {probs[0]}")
            agents[name] = raw
    return bad, agents


def rounds_of(step: dict) -> int:
    rep = step.get("repeat")
    if not isinstance(rep, dict):
        return 1
    m = rep.get("max")
    m = m if isinstance(m, int) and not isinstance(m, bool) else DEFAULT_MAX
    return max(1, min(CEILING, m))


class _Money:
    def __init__(self, wf: dict, backend) -> None:
        cap = wf.get("max_usd")
        self.cap = float(cap) if isinstance(cap, (int, float)) and not isinstance(cap, bool) and cap > 0 else None
        self.backend, self.spent = backend, 0.0

    def left(self) -> "Optional[float]":
        """Dollars the next call may spend (None: no cap at all)."""
        caps = []
        if self.cap is not None:
            caps.append(self.cap - self.spent)
        s = self.backend.session_left()
        if s is not None:
            caps.append(float(s))
        return min(caps) if caps else None

    def out(self) -> str:
        """'' while there is money; else the plain line naming which cap was reached."""
        if self.cap is not None and self.spent >= self.cap - 1e-9:
            return f"the workflow's cap (${self.cap:.2f} a run) is reached: ${self.spent:.4f} spent"
        s = self.backend.session_left()
        if s is not None and s <= 0:
            return "the session's cap is reached"
        return ""


def run(wf: dict, request: str, *, resolve: Callable, backend, files=(), emit: Optional[Callable] = None) -> Result:
    say = emit or (lambda kind, data: None)
    name = str(wf.get("name") or "workflow")
    steps = [s for s in wf.get("steps") or [] if isinstance(s, dict)]
    res = Result()
    bad, agents = preflight(wf, resolve)
    if bad:
        res.state, res.line = "failed", f"{name} did not start: " + "; ".join(bad[:3])
        say("end", {"state": res.state, "line": res.line, "cost_usd": 0.0, "problems": bad})
        return res
    money = _Money(wf, backend)
    say("start", {"workflow": name, "steps": [s.get("name") for s in steps], "max_usd": money.cap})
    carry, started = "", time.time()
    for i, step in enumerate(steps, 1):
        rec = {"n": i, "name": step.get("name"), "state": "running", "why": "", "rounds": 0, "stop": "",
               "agents": [], "cost_usd": 0.0}
        res.steps.append(rec)
        go, why = decide(step.get("when"), request, files, step)
        rec["why"] = why
        if not go:
            rec["state"] = "skipped"
            say("step", dict(rec))
            continue
        say("step", dict(rec))
        hand, prev, most = "", "", rounds_of(step)
        for rnd in range(1, most + 1):
            if backend.stopped():
                return _end(res, "stopped", f"stopped by you during step {i}", started, say, carry)
            why_out = money.out()
            if why_out:
                rec["state"] = "capped"
                return _end(res, "capped", f"{why_out}; stopped before step {i}" + (f", round {rnd}" if rnd > 1 else ""), started, say, carry)
            rec["rounds"] = rnd
            calls = _step_calls(wf, step, i, request, carry, prev, rnd, agents, backend, money, rec, say)
            hand = T.hand_on(calls)
            failed = [(n, c) for n, c in calls if not c.ok]
            if failed:
                rec["state"] = "failed"
                n, c = failed[0]
                return _end(res, "failed", f"step {i} ({step.get('name')}): {n} failed: {c.error or 'no reply'}", started, say, hand or carry)
            if most == 1 and not isinstance(step.get("repeat"), dict):
                break
            why_out = money.out()
            if why_out:
                rec["state"] = "capped"
                return _end(res, "capped", f"{why_out}; stopped before step {i}'s check", started, say, hand)
            until = str(step["repeat"].get("until") or "")
            last = agents[step["agents"][-1]]
            got = backend.agent(last, T.check_prompt(until, hand, step), step=i, limit_usd=money.left())
            money.spent += float(got.cost_usd or 0.0)
            rec["cost_usd"] = round(rec["cost_usd"] + float(got.cost_usd or 0.0), 6)
            yes = T.said_yes(got.text) if got.ok else False
            say("check", {"n": i, "round": rnd, "yes": yes, "line": T.first_line(got.text) or got.error, "cost_usd": got.cost_usd})
            if yes:
                rec["stop"] = f'the check said yes after round {rnd} ("{until}")'
                break
            if rnd == most:
                rec["stop"] = f"at most {most} times: the check never said yes (\"{until}\")"
            prev = hand
        rec["state"] = "done"
        say("step", dict(rec))
        carry = hand
    return _end(res, "done", f"{name}: {len(steps)} step(s) done", started, say, carry)


def _step_calls(wf, step, i, request, carry, prev, rnd, agents, backend, money, rec, say) -> list:
    names = list(step.get("agents") or [])
    prompt = {n: T.step_prompt(wf, step, i, request, carry, prev, rnd, n) for n in names}
    for n in names:
        say("agent", {"n": i, "round": rnd, "name": n, "state": "working"})
    left = money.left()
    share = None if left is None else max(0.0, left) / max(1, len(names))

    def one(n):
        t0 = time.time()
        try:
            c = backend.agent(agents[n], prompt[n], step=i, limit_usd=share)
        except Exception as e:  # a backend fault is the step's failure line, never a dead run
            c = Call(ok=False, error=f"{type(e).__name__}: {str(e)[:200]}")
        c.seconds = c.seconds or round(time.time() - t0, 1)
        return n, c

    if len(names) == 1:
        calls = [one(names[0])]
    else:
        with ThreadPoolExecutor(max_workers=len(names), thread_name_prefix="crew-step") as pool:
            calls = list(pool.map(one, names))
    for n, c in calls:
        money.spent += float(c.cost_usd or 0.0)
        rec["cost_usd"] = round(rec["cost_usd"] + float(c.cost_usd or 0.0), 6)
        row = {"n": i, "round": rnd, "name": n, "state": "done" if c.ok else "failed", "cost_usd": c.cost_usd,
               "seconds": c.seconds, "used": c.used, "text": T.short(c.text, 600), "error": c.error}
        rec["agents"] = [a for a in rec["agents"] if a["name"] != n] + [row]
        say("agent", row)
    return calls


def _end(res: Result, state: str, line: str, started: float, say, text: str) -> Result:
    res.state, res.line, res.text = state, line, text
    res.cost_usd = round(sum(float(s.get("cost_usd") or 0.0) for s in res.steps), 6)
    for s in res.steps:
        if s["state"] == "running":
            s["state"] = "stopped" if state != "done" else "done"
    say("end", {"state": state, "line": line, "cost_usd": res.cost_usd, "seconds": round(time.time() - started, 1),
                "text": T.short(text, 2000)})
    return res


def receipt(res: Result) -> "list[str]":
    """One line per step for the receipt: what ran, how many rounds and why it stopped, the cost."""
    out = []
    for s in res.steps:
        who = " + ".join(a["name"] for a in s.get("agents") or []) or "-"
        bits = [f"step {s['n']} {s['name']}: {s['state']}"]
        if s["state"] == "skipped":
            bits.append(s.get("why") or "")
        else:
            bits.append(who)
            if s.get("rounds", 0) > 1 or s.get("stop"):
                bits.append(f"{s['rounds']} round(s), {s.get('stop') or 'stopped'}")
            bits.append(f"${float(s.get('cost_usd') or 0):.4f}")
        out.append(" · ".join(b for b in bits if b))
    return out
