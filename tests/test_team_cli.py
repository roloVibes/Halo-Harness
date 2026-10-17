"""tests.test_team_cli -- Halo 3.0.8.0 round R1: `halo team ...`
(halo_harness/team/cli.py, cli_run.py): init, validate, run, status, board,
answer, stop, log and blocks, each with its exit code and `--json`, in a
temp git repo with the runner's seams set to the fakes (team/run.py's
SPAWN / ORCHESTRA / FLOW / DISPATCH). The preflight stops `run` (exit 2)
and `--force` goes past it. No model is called.

Run: python -m tests.test_team_cli
"""
from __future__ import annotations

import contextlib
import io
import json
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from tests.helpers.provider_env_defaults import ensure_default_provider_credentials, ensure_scoped_state_dir_once

ensure_default_provider_credentials()
ensure_scoped_state_dir_once()

from tests.helpers import team_rig as R  # noqa: E402
from tests.helpers.runner import Ctx, new_registry, print_results, run_all  # noqa: E402

test, TESTS = new_registry()


def _call(*argv) -> "tuple[int, str, str]":
    from halo_harness.team.cli import cmd_team
    out, err = io.StringIO(), io.StringIO()
    with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
        code = cmd_team(list(argv))
    return code, out.getvalue(), err.getvalue()


class _In:
    """chdir into a repo and point team/run.py's seams at the fakes (put back after)."""

    def __init__(self, root: Path, fakes=None):
        self.root, self.fakes = root, fakes or R.Fakes()

    def __enter__(self):
        from halo_harness.team import run as TR
        self._cwd = os.getcwd()
        self._seams = (TR.SPAWN, TR.ORCHESTRA, TR.FLOW, TR.DISPATCH)
        TR.SPAWN, TR.ORCHESTRA, TR.FLOW, TR.DISPATCH = self.fakes.spawn, self.fakes.orchestra, self.fakes.flow, self.fakes
        os.chdir(self.root)
        return self

    def __exit__(self, *a):
        from halo_harness.team import run as TR
        os.chdir(self._cwd)
        TR.SPAWN, TR.ORCHESTRA, TR.FLOW, TR.DISPATCH = self._seams


@test
def test_usage_init_and_validate(ctx: Ctx):
    ctx.check("no verb: usage, exit 2", _call()[0] == 2 and "halo team run" in _call()[1])
    ctx.check("--help: exit 0", _call("--help")[0] == 0)
    ctx.check("an unknown verb: exit 2", _call("dance")[0] == 2)
    ctx.check("a bad flag: exit 2", _call("run", "--bogus")[0] == 2)
    root, _state = R.repo()
    (root / ".halo" / "team.yaml").unlink()
    with _In(root):
        code, _o, err = _call("validate")
        ctx.check(f"no team file: exit 1 naming init, got {code} {err!r}", code == 1 and "halo team init" in err)
        code, out, _e = _call("init", "--json")
        data = json.loads(out)
        ctx.check(f"init writes the file, got {data}", code == 0 and data["ok"] and (root / ".halo" / "team.yaml").is_file()
                  and len(data["written"]) == 1)
        ctx.check("init again: exit 1", _call("init")[0] == 1)
        ctx.check("init --force: exit 0", _call("init", "--force")[0] == 0)
        code, out, _e = _call("validate")
        ctx.check(f"the template validates, got {code} {out!r}", code == 0 and out.strip().endswith("valid"))
        code, out, _e = _call("validate", "--json")
        data = json.loads(out)
        ctx.check(f"validate --json, got {sorted(data)}", code == 0 and data["ok"] and data["problems"] == []
                  and set(data) == {"ok", "path", "problems", "warnings"})
        (root / ".halo" / "team.yaml").write_text(R.TEAM.replace("writes: [site]", "writes: [nowhere]"), encoding="utf-8")
        code, out, _e = _call("validate")
        ctx.check(f"a problem: exit 2 with the line, got {code} {out!r}", code == 2 and "writes `nowhere`" in out)
        (root / ".halo" / "team.yaml").write_text("name: [", encoding="utf-8")
        ctx.check("broken YAML: exit 2", _call("validate")[0] == 2)
    root2, _s = R.repo(brief=False)
    (root2 / ".halo" / "team.yaml").unlink()
    with _In(root2):
        code, out, _e = _call("init", "--json")
        ctx.check("init writes a starter brief when there is none",
                  code == 0 and (root2 / "docs" / "BRIEF.md").is_file() and len(json.loads(out)["written"]) == 2)


@test
def test_run_status_board_log_blocks_answer_stop(ctx: Ctx):
    root, _state = R.repo()
    with _In(root) as env:
        ctx.check("status before any run: exit 1", _call("status")[0] == 1)
        ctx.check("an unknown stage: exit 2", _call("run", "nope")[0] == 2)
        code, out, _e = _call("run", "draft")
        ctx.check(f"run draft: exit 0, waits at the gate, got {code} {out!r}",
                  code == 0 and "waiting at draft: halo team answer draft accept|redo|stop" in out and "+" in out)
        code, out, _e = _call("status", "--json")
        st = json.loads(out)
        ctx.check(f"status --json, got {st}", code == 0 and st["state"] == "open" and st["waiting"] == ["draft"]
                  and st["stages"] == {"gated": ["draft"], "pending": ["review", "build", "post"]}
                  and st["runner_live"] is False and abs(st["cost_usd"] - 0.01) < 1e-9)
        code, out, _e = _call("status")
        ctx.check("status text names what to answer", code == 0 and "halo team answer draft" in out)
        code, out, _e = _call("board", "--json")
        board = json.loads(out)
        ctx.check(f"board --json, got {sorted(board)}", code == 0 and [r["id"] for r in board["stages"]]
                  == ["draft", "review", "build", "post"] and board["stages"][0]["state"] == "gated")
        code, out, _e = _call("board")
        ctx.check("board text has one row per stage", code == 0 and out.count("\n") >= 6 and "orchestra" in out)
        code, out, _e = _call("log", "--json")
        log = json.loads(out)
        ctx.check(f"log --json, got {log['next']}", code == 0 and log["next"] == len(log["events"]) > 3)
        code, out, _e = _call("log", "--since", "2")
        ctx.check("log text skips the first lines", code == 0 and out.count("\n") == log["next"] - 2)
        code, out, _e = _call("blocks", "--json")
        rows = json.loads(out)
        ctx.check("blocks --json lists every block", code == 0 and [b["id"] for b in rows] == ["copy", "site", "notes"])
        ctx.check("blocks <id> --json is one block", json.loads(_call("blocks", "copy", "--json")[1])["id"] == "copy")
        ctx.check("an unknown block: exit 1", _call("blocks", "nope")[0] == 1)
        ctx.check("answer a stage that is not waiting: exit 1", _call("answer", "review", "accept")[0] == 1)
        ctx.check("a bad answer word: exit 1", _call("answer", "draft", "maybe")[0] == 1)
        code, out, _e = _call("answer", "draft", "accept", "--json")
        data = json.loads(out)
        ctx.check(f"answer drives the run on, got {data['message']}", code == 0 and data["driven"] is True
                  and [r["state"] for r in data["board"]["stages"]] == ["done", "done", "pending", "done"])
        ctx.check("the fakes saw review and post", any(c[0] == "flow" for c in env.fakes.calls))
        ctx.check("run with no pending manual stage: exit 1", _call("run")[0] == 1)
        code, out, _e = _call("stop", "--reason", "enough", "--json")
        ctx.check(f"stop: exit 0, got {out}", code == 0 and json.loads(out)["reason"] == "enough")
        ctx.check("the run is stopped", json.loads(_call("status", "--json")[1])["state"] == "stopped")
        ctx.check("stop again: exit 1", _call("stop")[0] == 1)
        stopped = json.loads(_call("status", "--json")[1])["run"]
        code, _o, err = _call("run", "draft", "--run", stopped)
        ctx.check(f"run on the stopped run: exit 1 naming --new, got {err!r}", code == 1 and "--new" in err)
        code, out, _e = _call("run", "draft", "--json")
        ctx.check("after a stop, run starts a new run", code == 0 and json.loads(out)["state"] == "open"
                  and json.loads(out)["run"] != stopped)
        code, out, _e = _call("run", "draft", "--json")
        ctx.check("the open run's stage waits at its gate: run draft again starts round 2", code == 0)
        code, out, _e = _call("run", "draft", "--new", "--json")
        ctx.check("--new starts another run beside the open one", code == 0 and json.loads(out)["state"] == "open")
        env.fakes.fail.add("writer")
        code, _o, _e = _call("run", "draft", "--new")
        ctx.check("a stage that fails: exit 1", code == 1)


@test
def test_run_stops_on_a_problem_and_on_the_preflight(ctx: Ctx):
    from tests.helpers.preflight_seed import Home
    root, _state = R.repo(R.TEAM.replace("writes: [site]", "writes: [nowhere]"))
    with _In(root):
        code, _o, err = _call("run", "draft")
        ctx.check(f"a problem in the file: exit 2, nothing ran, got {err!r}", code == 2 and "nothing ran" in err)
    with Home():
        root, _state = R.repo(R.TEAM.replace("{name: writer, lineup: standard, role: main}",
                                             "{name: writer, lineup: pf-bad, role: main}"))
        with _In(root) as env:
            code, _o, err = _call("run", "draft")
            ctx.check(f"the preflight blocks: exit 2 with the findings and --force, got {err[:160]!r}",
                      code == 2 and "preflight:" in err and "member `writer` (lineup `pf-bad`)" in err and "--force" in err
                      and not env.fakes.calls)
            code, _o, _e = _call("run", "draft", "--force")
            ctx.check("--force runs anyway", code == 0 and any(c[0] == "spawn" for c in env.fakes.calls))


@test
def test_halo_dispatches_team(ctx: Ctx):
    from halo_harness import cli
    out = io.StringIO()
    with contextlib.redirect_stdout(out):
        code = cli._main(["team", "--help"])
    ctx.check(f"`halo team` reaches cmd_team, got {code}", code == 0 and "halo team init" in out.getvalue())


@test
def test_the_real_seams_argv_and_the_fleet_delegate_without_a_hub(ctx: Ctx):
    import subprocess
    from halo_harness.team import SCOPE_ENV
    from halo_harness.team.adapters import spawn_member
    from halo_harness.team.delegate import FleetDelegate
    seen = {}

    def fake_run(argv, **kw):
        seen.update(argv=argv, **kw)
        lines = ["noise", '{"type": "result", "result": "did it", "total_cost_usd": 0.2, "session_id": "s1", "is_error": false}', ""]
        return subprocess.CompletedProcess(argv, 0, stdout=chr(10).join(lines), stderr="")
    root, _state = R.repo()
    member = {"name": "editor", "lineup": "standard", "role": "reviewer", "harness": None}
    out = spawn_member(member, "the prompt", cwd=root, env={SCOPE_ENV: "x.json"}, stage="s", run_dir=root, runner=fake_run)
    argv = seen["argv"]
    ctx.check(f"halo -p under the lineup as the alias's bio, got {argv[1:]}",
              argv[1:4] == ["-m", "halo_harness", "-p"] and argv[4] == "the prompt"
              and argv[argv.index("--team") + 1] == "standard" and argv[argv.index("--agent") + 1] == "default-model"
              and argv[argv.index("--permission-mode") + 1] == "auto")
    ctx.check("the scope env, utf-8 and the repo as cwd", seen["env"][SCOPE_ENV] == "x.json" and seen["encoding"] == "utf-8"
              and seen["cwd"] == str(root))
    ctx.check(f"the JSON result comes back, got {out}", out == {"ok": True, "text": "did it", "cost_usd": 0.2,
                                                               "session_id": "s1", "error": ""})
    bad = spawn_member(member, "p", cwd=root, env={}, stage="s", run_dir=root,
                       runner=lambda a, **k: subprocess.CompletedProcess(a, 3, stdout="", stderr="boom"))
    ctx.check(f"no JSON: a failure naming the exit code, got {bad}", bad["ok"] is False and "exited 3" in bad["error"])
    status, body = FleetDelegate(home=_state).send({"name": "remote", "harness": "kali"}, {"team": "t", "stage": "s"})
    ctx.check(f"no hub on this machine: 503 naming how to start one, got {status} {body}",
              status == 503 and "halo fleet serve" in body["error"])


if __name__ == "__main__":
    ctx = Ctx()
    results, passed, failed, skipped = run_all(TESTS, ctx)
    sys.exit(print_results(results, passed, failed, skipped, label="team cli tests"))
