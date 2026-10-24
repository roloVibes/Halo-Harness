"""tests.helpers.isolation_rig -- a scratch home, a repo with an Orchestra run, lineups and bios that declare
the 3.1.8.0 R5 opt-ins, a temp bin folder (`which` looks only there) and a fake `op` (tests only).

No docker, podman, sudo or op ever runs: the worker's runner is a recorder, `which` finds only what a test
puts in the bin folder (a docker there is an empty file nobody runs), and `op` is a small python script
on that folder that prints the value a test gave it for each ref. Values here are made up for the tests.
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path

import yaml


class IsoEnv:
    """`with IsoEnv() as e:` -- BRIDGE_TEST_HOME/BRIDGE_STATE_DIR in a fresh folder, BRIDGE_TEST_NO_BACKGROUND_NET,
    `e.bin` (prepended to PATH), `e.which` (looks only in e.bin), the lane module's WHICH pointed at it."""

    KEYS = ("BRIDGE_TEST_HOME", "BRIDGE_STATE_DIR", "BRIDGE_TEST_NO_BACKGROUND_NET", "PATH", "HALO_SECRET_KEYS",
            "HALO_SECRET_PASS", "HALO_ORCHESTRA_LANE", "HALO_TOOLS_CAPS", "HALO_TOOLS_CAPS_BY", "HALO_OPT_INS")

    def __enter__(self):
        self._saved = {k: os.environ.get(k) for k in self.KEYS}
        self.root = Path(tempfile.mkdtemp(prefix="iso-rig-"))
        os.environ["BRIDGE_TEST_HOME"] = str(self.root)
        os.environ["BRIDGE_STATE_DIR"] = str(self.root / ".halo")
        os.environ["BRIDGE_TEST_NO_BACKGROUND_NET"] = "1"
        for k in self.KEYS[4:]:
            os.environ.pop(k, None)
        self.state = self.root / ".halo"
        self.state.mkdir(parents=True, exist_ok=True)
        self.bin = self.root / "bin"
        self.bin.mkdir()
        os.environ["PATH"] = str(self.bin) + os.pathsep + (self._saved["PATH"] or "")
        from halo_harness.isolation import lane
        self._which = lane.WHICH
        lane.WHICH = self.which
        return self

    def __exit__(self, *exc):
        from halo_harness.isolation import lane
        lane.WHICH = self._which
        for k, v in self._saved.items():
            os.environ.pop(k, None) if v is None else os.environ.__setitem__(k, v)

    def which(self, name: str):
        import shutil
        return shutil.which(name, path=str(self.bin))

    def tool(self, name: str) -> Path:
        """An empty stand-in for `name` that `which` finds (never run: the worker's runner is a recorder)."""
        path = self.bin / (name + (".cmd" if os.name == "nt" else ""))
        path.write_text("@echo off\r\nexit 9\r\n" if os.name == "nt" else "#!/bin/sh\nexit 9\n", encoding="utf-8")
        path.chmod(0o755)
        return path

    def fake_op(self, values: dict) -> Path:
        """A fake `op`: `op read <ref> [--account A]` prints values[ref], else exits 1. It logs its argv."""
        (self.bin / "op_values.json").write_text(json.dumps(values), encoding="utf-8")
        script = self.bin / "fake_op.py"
        script.write_text(
            "import json, sys, pathlib\n"
            "here = pathlib.Path(__file__).resolve().parent\n"
            "with open(here / 'op_calls.jsonl', 'a', encoding='utf-8') as f:\n"
            "    f.write(json.dumps(sys.argv[1:]) + chr(10))\n"
            "values = json.loads((here / 'op_values.json').read_text(encoding='utf-8'))\n"
            "ref = sys.argv[2] if len(sys.argv) > 2 and sys.argv[1] == 'read' else ''\n"
            "if ref not in values:\n"
            "    sys.stderr.write('[ERROR] could not read secret' + chr(10)); sys.exit(1)\n"
            "sys.stdout.write(values[ref] + chr(10))\n", encoding="utf-8")
        if os.name == "nt":
            path = self.bin / "op.cmd"
            path.write_text(f'@"{sys.executable}" "{script}" %*\r\n', encoding="utf-8")
        else:
            path = self.bin / "op"
            path.write_text(f'#!/bin/sh\nexec "{sys.executable}" "{script}" "$@"\n', encoding="utf-8")
            path.chmod(0o755)
        return path

    def op_calls(self) -> list:
        log = self.bin / "op_calls.jsonl"
        return [json.loads(ln) for ln in log.read_text(encoding="utf-8").splitlines()] if log.is_file() else []

    def lineup(self, name: str, data: dict) -> None:
        d = self.state / "teams"
        d.mkdir(parents=True, exist_ok=True)
        (d / f"{name}.yaml").write_text(yaml.safe_dump({"name": name, **data}, sort_keys=False), encoding="utf-8")

    def bio(self, name: str, data: dict) -> None:
        d = self.state / "agents"
        d.mkdir(parents=True, exist_ok=True)
        (d / f"{name}.yaml").write_text(yaml.safe_dump({"name": name, "description": name, **data}, sort_keys=False),
                                        encoding="utf-8")


def run_with_lane(lineup: str = "", bio: str = "", worker: str = "subagent"):
    """A repo, a run whose goal names `lineup`, and lane 2's handle (its job naming `bio`): `(repo, run_dir, lane)`."""
    from halo_harness.orchestra.goal import Goal, new_run
    from halo_harness.orchestra.lanes import Lane
    from halo_harness.orchestra.split import Job
    from tests.helpers.orchestra_fixtures import make_repo
    repo = make_repo("iso-run-")
    goal = Goal(what="Write the five functions of basket.py", done_when="the tests pass", stop_when="two returns",
                workers=2, files=["basket.py"], lineup=lineup, worker=worker)
    run_dir = new_run(repo, goal)
    job = Job("job-2", "write subtotal", ["basket.py#subtotal"], 2, 2)
    job.bio = bio
    lane = Lane.create(run_dir, job, branch="b", worktree=run_dir / "wt" / "worker-2", started=0.0)
    (run_dir / "wt" / "worker-2").mkdir(parents=True, exist_ok=True)
    lane.prompt = "write subtotal"
    return repo, run_dir, lane


class Recorder:
    """The worker's runner: records argv, cwd and env; answers one result line."""

    def __init__(self, text: str = "done"):
        self.calls: list = []
        self.text = text

    def __call__(self, argv, **kw):
        self.calls.append({"argv": list(argv), **kw})
        out = json.dumps({"type": "result", "is_error": False, "result": self.text, "session_id": "s-2",
                          "total_cost_usd": 0.001})
        return subprocess.CompletedProcess(argv, 0, out + "\n", "")
