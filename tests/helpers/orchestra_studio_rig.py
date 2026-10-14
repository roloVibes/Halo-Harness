"""tests.helpers.orchestra_studio_rig -- a Studio server over a temp git repo
holding a finished Orchestra run (the R2 fixture: basket.py, five lanes,
lane 5's import conflicting with lane 4's, a fresh judge, a report), plus an
authenticated JSON client and an SSE reader. No model is ever called."""
from __future__ import annotations

import json
import queue
import shutil
import tempfile
import threading
import time
import urllib.error
import urllib.request
from pathlib import Path


def finished_run(repo=None):
    """`(repo, run_dir)`: the five-lane run with one conflict, finished."""
    from halo_harness.orchestra.run import run
    from tests.helpers import orchestra_fixtures as F
    repo = repo or F.make_repo("orch-studio-")
    run_dir = F.make_run(repo)
    report = run(run_dir, model_calls=F.FakeLead(F.split_answer([[f] for f in F.FUNCS])),
                 spawn=F.FakeWorker(F.CONFLICT_SOLUTIONS, F.CONFLICT_IMPORTS), judge=F.FakeJudge(F.COMBINED_IMPORT))
    assert report["status"] == "finished", report.get("stop_reason")
    return repo, run_dir


def fake_runner(gate: "threading.Event | None" = None):
    """orchestra_api.RUNNER: the R2 fakes; the workers wait for `gate` first."""
    from tests.helpers import orchestra_fixtures as F

    def runner(run_dir, goal, model):
        worker = F.FakeWorker()

        def spawn(lane):
            if gate is not None:
                gate.wait(20)
            return worker(lane)
        return {"model_calls": F.FakeLead(F.split_answer([[f] for f in F.FUNCS])), "spawn": spawn,
                "judge": F.FakeJudge()}
    return runner


class Studio:
    def __init__(self, repo: Path):
        self.repo = Path(repo)

    def __enter__(self):
        from halo_harness.studio.server import start_server
        self.state = Path(tempfile.mkdtemp(prefix="studio-orch-")) / ".halo"
        self.state.mkdir()
        self.srv = start_server(port=0, cwd=self.repo, state_dir=self.state)
        threading.Thread(target=self.srv.serve_forever, daemon=True).start()
        self.base = f"http://127.0.0.1:{self.srv.server_address[1]}"
        return self

    def __exit__(self, *a):
        self.srv.shutdown()
        self.srv.server_close()
        shutil.rmtree(self.state.parent, ignore_errors=True)

    def call(self, method: str, path: str, body=None, token: "str | None" = None):
        data = json.dumps(body).encode("utf-8") if body is not None else None
        req = urllib.request.Request(self.base + "/api/" + path, data=data, method=method)
        req.add_header("Authorization", "Bearer " + (self.srv.token if token is None else token))
        if data is not None:
            req.add_header("Content-Type", "application/json")
        try:
            with urllib.request.urlopen(req, timeout=20) as r:
                return r.status, json.loads(r.read() or b"{}")
        except urllib.error.HTTPError as e:
            return e.code, json.loads(e.read() or b"{}")

    def get(self, path: str, token: "str | None" = None):
        return self.call("GET", path, token=token)

    def post(self, path: str, body=None):
        return self.call("POST", path, body or {})


class Reader:
    """SSE frames off one /api/events response, into a queue."""

    def __init__(self, url: str):
        self.frames: "queue.Queue" = queue.Queue()
        self.resp = urllib.request.urlopen(url, timeout=10)
        threading.Thread(target=self._run, daemon=True).start()

    def _run(self):
        kind = ""
        try:
            for raw in self.resp:
                line = raw.decode("utf-8").rstrip("\r\n")
                if line.startswith("event: "):
                    kind = line[7:]
                elif line.startswith("data: "):
                    self.frames.put((kind, json.loads(line[6:])))
        except Exception:
            pass

    def wait(self, pred, timeout: float):
        end = time.monotonic() + timeout
        while time.monotonic() < end:
            try:
                kind, frame = self.frames.get(timeout=max(0.01, end - time.monotonic()))
            except queue.Empty:
                break
            if pred(kind, frame):
                return frame
        return None

    def close(self):
        try:
            import socket
            self.resp.fp.raw._sock.shutdown(socket.SHUT_RDWR)
        except Exception:
            pass


def _writable(func, path, _exc):
    import os
    import stat
    try:
        os.chmod(path, stat.S_IWRITE)
        func(path)
    except OSError:
        pass


def cleanup(*repos) -> None:
    """Remove temp repos (git keeps its objects read-only on Windows)."""
    for repo in repos:
        if repo is not None:
            shutil.rmtree(repo, onerror=_writable)
