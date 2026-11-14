"""tests.test_step_runner -- Halo 3.6.0.0 R2: the step runner (halo_harness/crew/runner.py) with a fake backend:

1. side by side: a step's agents run at the same time; each one's reply under its name is the next step's input;
2. "When it runs": always, only when the task says a word, only when it needs a PDF, only when I ask;
3. repeat until: one yes/no check by the step's last agent after each round; yes stops it, the receipt says how many
   rounds and why; a check that NEVER says yes ends at `max` (and `max` above 10 is held at 10): no unbounded loop;
4. the caps: the workflow's own max_usd and the session's cap stop the run with one plain line and what was done;
5. a step naming an agent that does not exist, or one whose file has a problem, stops it before any model call.
Run: python -m tests.test_step_runner
"""
from __future__ import annotations

import sys
import threading
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from tests.helpers.runner import Ctx, new_registry, print_results, run_all  # noqa: E402

test, TESTS = new_registry()


def _agent(name: str, model: str = "or:x/y") -> dict:
    return {"format": "agent/1", "name": name, "does": f"{name} does its part.", "model": model, "uses": ["read"], "careful": "ask-changes"}


AGENTS = {n: _agent(n) for n in ("implementer", "tester", "my-reviewer", "reader")}


class Fake:
    """Each call: (agent name, prompt); the reply from `answer(name, prompt)`; each call costs `usd`."""

    def __init__(self, answer=None, usd: float = 0.01, left=None, hold: float = 0.0):
        self.calls: list = []
        self.answer = answer or (lambda name, prompt: f"{name} did it")
        self.usd, self._left, self.hold = usd, left, hold
        self.live = 0
        self.most = 0
        self.lock = threading.Lock()

    def agent(self, raw, prompt, *, step, limit_usd=None):
        from halo_harness.crew.runner import Call
        with self.lock:
            self.live += 1
            self.most = max(self.most, self.live)
            self.calls.append((raw["name"], prompt))
        time.sleep(self.hold)
        with self.lock:
            self.live -= 1
        return Call(text=self.answer(raw["name"], prompt), cost_usd=self.usd)

    def session_left(self):
        return None if self._left is None else self._left(self)

    def stopped(self):
        return False


def _wf(steps: list, **kw) -> dict:
    return {"format": "workflow/1", "name": "ship-a-fix", "for": "Make the change, then check it.", "steps": steps, **kw}


def _run(wf, fake, request="fix the discount", files=()):
    from halo_harness.crew import runner
    seen: list = []
    res = runner.run(wf, request, resolve=AGENTS.get, backend=fake, files=files, emit=lambda k, d: seen.append((k, d)))
    return res, seen


@test
def test_side_by_side_and_the_hand_on(ctx: Ctx):
    wf = _wf([{"name": "Make the change", "agents": ["implementer"], "gets": "the task", "hands": "the diff"},
              {"name": "Check it", "agents": ["tester", "my-reviewer"], "gets": "the diff", "hands": "problems"}])
    fake = Fake(hold=0.3)
    res, seen = _run(wf, fake)
    ctx.check(f"done, got {res.state} {res.line}", res.state == "done")
    ctx.check(f"step 2's two agents ran at the same time, got {fake.most} at once", fake.most == 2)
    second = [p for n, p in fake.calls if n == "tester"][0]
    ctx.check("step 2 gets what step 1 handed on, and its Gets words", "implementer did it" in second and "You get the diff" in second)
    ctx.check(f"the hand-on text is each agent's reply under its name, got {res.text!r}", res.text == "tester:\ntester did it\n\nmy-reviewer:\nmy-reviewer did it")
    ctx.check(f"cost added up, got {res.cost_usd}", abs(res.cost_usd - 0.03) < 1e-9)
    kinds = [k for k, _d in seen]
    ctx.check(f"the run is heard as it goes, got {kinds}", kinds[0] == "start" and kinds[-1] == "end" and kinds.count("agent") == 6)


@test
def test_when_it_runs(ctx: Ctx):
    wf = _wf([{"name": "Make", "agents": ["implementer"]},
              {"name": "Fix it", "agents": ["tester"], "when": {"says": ["fix"]}},
              {"name": "Read the PDF", "agents": ["reader"], "when": {"needs": ["pdf"]}},
              {"name": "Review", "agents": ["my-reviewer"], "when": "ask"}])
    res, _ = _run(wf, Fake(), request="fix the totals")
    states = [(s["name"], s["state"]) for s in res.steps]
    ctx.check(f"says fix: runs; needs a PDF, none: skipped; only when I ask: skipped, got {states}",
              states == [("Make", "done"), ("Fix it", "done"), ("Read the PDF", "skipped"), ("Review", "skipped")])
    res, _ = _run(wf, Fake(), request="read receipt.pdf and have my-reviewer look", files=["receipt.pdf"])
    states = [(s["name"], s["state"]) for s in res.steps]
    ctx.check(f"a PDF named: it runs; the request names my-reviewer: it runs; no fix: skipped, got {states}",
              states == [("Make", "done"), ("Fix it", "skipped"), ("Read the PDF", "done"), ("Review", "done")])
    ctx.check(f"why it was skipped is said, got {res.steps[1]['why']!r}", res.steps[1]["why"].startswith("skipped: the request says none of fix"))


@test
def test_repeat_until_yes_and_never(ctx: Ctx):
    rounds = {"n": 0}

    def answer(name, prompt):
        if prompt.startswith("A check after the step"):
            rounds["n"] += 1
            return "yes, 41 passed" if rounds["n"] >= 2 else "no: 1 test failed"
        return f"{name} ran"
    wf = _wf([{"name": "Check it", "agents": ["implementer", "tester"], "repeat": {"until": "the tests pass", "max": 3}}])
    fake = Fake(answer)
    res, _ = _run(wf, fake)
    s = res.steps[0]
    ctx.check(f"two rounds, stopped on yes, got {s['rounds']} {s['stop']!r}", s["rounds"] == 2 and s["stop"].startswith("the check said yes after round 2"))
    checks = [n for n, p in fake.calls if p.startswith("A check")]
    ctx.check(f"the check is the step's last agent, once a round, got {checks}", checks == ["tester", "tester"])
    again = [p for n, p in fake.calls if n == "implementer"][1]
    ctx.check("round 2 is told the check said no, with what it handed on", "Round 2" in again and "said no" in again)
    from halo_harness.crew import runner
    ctx.check("the receipt says the rounds and why", "2 round(s), the check said yes" in runner.receipt(res)[0])
    never = Fake(lambda name, prompt: "no, not yet" if prompt.startswith("A check") else "tried")
    res, _ = _run(_wf([{"name": "Loop", "agents": ["tester"], "repeat": {"until": "it is perfect", "max": 3}}]), never)
    ctx.check(f"a check that never says yes: exactly 3 rounds, then it stops, got {res.steps[0]}",
              res.steps[0]["rounds"] == 3 and len(never.calls) == 6 and res.steps[0]["stop"].startswith("at most 3 times"))
    wild = Fake(lambda name, prompt: "no" if prompt.startswith("A check") else "tried")
    res, _ = _run(_wf([{"name": "Loop", "agents": ["tester"], "repeat": {"until": "never", "max": 50}}]), wild)
    ctx.check(f"max 50 is a problem line before any call, got {res.line!r}", res.state == "failed" and not wild.calls)
    from halo_harness.crew.runner import CEILING, rounds_of
    ctx.check(f"the ceiling holds whatever the file says, got {rounds_of({'repeat': {'until': 'x', 'max': 99}})}",
              rounds_of({"repeat": {"until": "x", "max": 99}}) == CEILING == 10)


@test
def test_the_caps(ctx: Ctx):
    never = Fake(lambda name, prompt: "no" if prompt.startswith("A check") else "tried", usd=0.05)
    wf = _wf([{"name": "Loop", "agents": ["tester"], "repeat": {"until": "never", "max": 10}}], max_usd=0.12)
    res, _ = _run(wf, never)
    ctx.check(f"the workflow's max_usd stops it with one line, got {res.state} {res.line!r}",
              res.state == "capped" and res.line.startswith("the workflow's cap ($0.12 a run) is reached"))
    ctx.check(f"what was done so far is kept, got {len(never.calls)} calls ${res.cost_usd}", len(never.calls) == 3 and res.cost_usd >= 0.12)
    sess = Fake(usd=0.05, left=lambda f: 0.08 - 0.05 * len(f.calls))
    wf2 = _wf([{"name": "A", "agents": ["implementer"]}, {"name": "B", "agents": ["tester"]}, {"name": "C", "agents": ["reader"]}])
    res, _ = _run(wf2, sess)
    ctx.check(f"the session's cap stops it, got {res.state} {res.line!r} after {len(sess.calls)} calls",
              res.state == "capped" and res.line.startswith("the session's cap is reached; stopped before step 3") and len(sess.calls) == 2)


@test
def test_a_bad_step_stops_before_any_call(ctx: Ctx):
    fake = Fake()
    res, seen = _run(_wf([{"name": "A", "agents": ["implementer"]}, {"name": "B", "agents": ["nobody-here"]}]), fake)
    ctx.check(f"an agent that does not exist: no call, the problem line, got {res.line!r}",
              res.state == "failed" and not fake.calls and "no agent named nobody-here" in res.line)
    ctx.check("the end says the problems", seen[-1][0] == "end" and seen[-1][1]["problems"])
    AGENTS["broken"] = {**_agent("broken"), "careful": "reckless"}
    try:
        res, _ = _run(_wf([{"name": "A", "agents": ["broken"]}]), fake)
    finally:
        AGENTS.pop("broken")
    ctx.check(f"an agent file with a problem: no call, its line, got {res.line!r}",
              res.state == "failed" and not fake.calls and "the agent broken has a problem: careful" in res.line)


if __name__ == "__main__":
    ctx = Ctx()
    results, passed, failed, skipped = run_all(TESTS, ctx)
    sys.exit(print_results(results, passed, failed, skipped))
