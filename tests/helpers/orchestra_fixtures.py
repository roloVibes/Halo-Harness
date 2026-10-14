"""tests.helpers.orchestra_fixtures -- a real temp git repo with the reel's
basket.py, and fake lead / worker / judge for the Orchestra run tests.
No model is ever called: the fakes write the functions themselves."""
from __future__ import annotations

import json
import subprocess
import sys
import tempfile
from pathlib import Path

TEMPLATES = Path(__file__).resolve().parent.parent.parent / "halo_harness" / "templates" / "orchestra"
FUNCS = ("add_item", "remove_item", "subtotal", "apply_discount", "total")
SOLUTIONS = {
    "add_item": ["    entry = basket.setdefault(name, [Decimal(price), 0])", "    entry[1] += qty", "    return basket"],
    "remove_item": ["    entry = basket[name]", "    entry[1] -= qty", "    if entry[1] <= 0:",
                    "        del basket[name]", "    return basket"],
    "subtotal": ['    return sum((price * qty for price, qty in basket.values()), Decimal("0"))'],
    "apply_discount": ['    cut = amount * (100 - Decimal(percent)) / 100',
                       '    return cut.quantize(Decimal("0.01"), rounding="ROUND_HALF_UP")'],
    "total": ["    return apply_discount(subtotal(basket), percent)"],
}
# The conflict variant: two lanes each add a name to line 2's import.
CONFLICT_SOLUTIONS = dict(SOLUTIONS, apply_discount=[
    '    cut = amount * (100 - Decimal(percent)) / 100',
    '    return cut.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)'], total=[
    "    try:", "        return apply_discount(subtotal(basket), percent)", "    except InvalidOperation:",
    '        raise ValueError("a price in the basket is not a number")'])
CONFLICT_IMPORTS = {"apply_discount": "from decimal import Decimal, ROUND_HALF_UP",
                    "total": "from decimal import Decimal, InvalidOperation"}
COMBINED_IMPORT = "from decimal import Decimal, InvalidOperation, ROUND_HALF_UP"
PY = f'"{sys.executable}"'


def git(repo, *args) -> str:
    out = subprocess.run(["git", *args], cwd=str(repo), capture_output=True, text=True, encoding="utf-8")
    if out.returncode != 0:
        raise RuntimeError(f"git {args}: {out.stderr}")
    return out.stdout


def make_repo(prefix: str = "orch-run-") -> Path:
    repo = Path(tempfile.mkdtemp(prefix=prefix))
    for name in ("basket.py", "test_basket.py"):
        # LF regardless of how this checkout holds the template (a CRLF
        # checkout would make the first lane's LF edit touch every line and
        # the second merge conflict for no reason)
        text = (TEMPLATES / name).read_text(encoding="utf-8")
        (repo / name).write_text(text, encoding="utf-8", newline="\n")
    (repo / ".gitignore").write_text("__pycache__/\n", encoding="utf-8")
    git(repo, "init", "-q")
    for key, value in (("user.name", "t"), ("user.email", "t@t"), ("core.autocrlf", "false"),
                       ("commit.gpgsign", "false")):
        git(repo, "config", key, value)
    git(repo, "add", "-A")
    git(repo, "commit", "-q", "-m", "basket: five functions to write")
    return repo


def make_run(repo: Path, *, workers: int = 5, return_cap: int = 2, test: str = "", stop_when: str = "two returns"):
    from halo_harness.orchestra.goal import Goal, new_run
    goal = Goal(what="Write the five functions of basket.py", done_when="the tests pass", stop_when=stop_when,
                workers=workers, return_cap=return_cap, test=test or f"{PY} -m unittest -q test_basket",
                files=["basket.py"], test_timeout_s=60)
    return new_run(repo, goal)


def split_answer(groups) -> str:
    """The lead's JSON for `groups` (a list of lists of function names)."""
    return json.dumps({"jobs": [{"title": "write " + " and ".join(g), "claims": [f"basket.py#{f}" for f in g]}
                                for g in groups]})


class FakeLead:
    def __init__(self, *answers):
        self.answers = list(answers)
        self.prompts = []

    def __call__(self, prompt: str):
        self.prompts.append(prompt)
        return {"text": self.answers.pop(0) if len(self.answers) > 1 else self.answers[0],
                "cost_usd": 0.001, "session_id": f"lead-{len(self.prompts)}"}


def write_function(path: Path, name: str, body: list) -> None:
    """Replace the body of `name` (everything after its one-line docstring
    up to the blank lines before the next def) with `body`."""
    lines = path.read_text(encoding="utf-8").split("\n")
    start = next(i for i, line in enumerate(lines) if line.startswith(f"def {name}("))
    end = next((i for i in range(start + 1, len(lines)) if lines[i].startswith("def ")), len(lines))
    while end > start and not lines[end - 1].strip():
        end -= 1
    lines[start + 2:end] = body
    path.write_text("\n".join(lines), encoding="utf-8", newline="")


def set_import(path: Path, line: str) -> None:
    lines = path.read_text(encoding="utf-8").split("\n")
    lines[1] = line   # line 2, right under the docstring
    path.write_text("\n".join(lines), encoding="utf-8", newline="")


class FakeWorker:
    """Per lane: join, claim each key, mark writing, write the function,
    mark written (with the snapshot), release -- the rule, done by hand."""

    def __init__(self, solutions=None, imports=None, fail_lanes=(), wrong=None, stop_lanes=None):
        self.solutions = solutions or SOLUTIONS
        self.imports = imports or {}
        self.calls = []
        self.fail_lanes = set(fail_lanes)
        self.wrong = dict(wrong or {})          # name -> body written on that lane's FIRST pass only
        self.stop_lanes = dict(stop_lanes or {})

    def __call__(self, lane):
        from halo_harness.orchestra.claims import ClaimLog
        from halo_harness.orchestra.workers import join_lane, record_written
        first = all(n != lane.n for n, _ in self.calls)
        self.calls.append((lane.n, lane.retry_text))
        if lane.n in self.fail_lanes:
            raise RuntimeError("the fake worker fell over")
        if lane.n in self.stop_lanes:
            return {"text": f"I looked at it.\nSTOP: {self.stop_lanes[lane.n]}", "cost_usd": 0.001}
        holder = f"worker{lane.n}-{len(self.calls)}/main"
        join_lane(lane.run_dir, lane.n, holder)
        log = ClaimLog(lane.run_dir)
        path = lane.worktree / "basket.py"
        for key in lane.job.claims:
            name = key.split("#", 1)[1]
            assert log.claim(holder, key).ok, f"claim {key}"
            log.mark_writing(holder, key)
            write_function(path, name, self.wrong[name] if first and name in self.wrong else self.solutions[name])
            log.mark_written(holder, key)
            record_written(lane.run_dir, holder, key, lane.worktree)
            log.release(holder, key)
            if name in self.imports:
                set_import(path, self.imports[name])
        return {"text": f"wrote {lane.job.claims}", "cost_usd": 0.002, "session_id": holder.split("/")[0]}


class FakeJudge:
    def __init__(self, *answers):
        self.answers = list(answers) or [COMBINED_IMPORT]
        self.calls = []

    def __call__(self, hunks, goal, file):
        self.calls.append({"hunks": hunks, "file": file, "goal": goal.what})
        text = self.answers[min(len(self.calls), len(self.answers)) - 1]
        return {"text": text, "session_id": f"judge-session-{len(self.calls)}", "messages_before": 0,
                "cost_usd": 0.0005}
