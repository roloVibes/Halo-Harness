"""tests.helpers.review_mock -- shared scaffolding for the /review tests
(Halo 2.0.10 round 1): a scratch git repo, a real agent.loop.Session wired to
the mock upstream with the reviewer / judge / coder roles pointed at three mock
models, and a `Router` scenario that answers each upstream request from a
function of the last user message (so each dimension, judge call and fix call
can get its own scripted reply).
"""
from __future__ import annotations

import os
import subprocess
import sys
import tempfile
import threading
import time
from pathlib import Path

from tests.helpers.mock_openai import SCENARIOS, _finish

REVIEWER_MODEL, JUDGE_MODEL, CODER_MODEL = "rv-reviewer", "rv-judge", "rv-coder"
ROLE_TABLE = {"reviewer": f"or:mock/{REVIEWER_MODEL}", "judge": f"or:mock/{JUDGE_MODEL}",
              "coder": f"or:mock/{CODER_MODEL}"}


def text_step(text: str) -> list:
    return [
        {"choices": [{"index": 0, "delta": {"role": "assistant"}}]},
        {"choices": [{"index": 0, "delta": {"content": text}}]},
        {"choices": [{"index": 0, "delta": {}, "finish_reason": "stop"}]},
    ]


def last_user_text(body: dict) -> str:
    for m in reversed((body or {}).get("messages") or []):
        if isinstance(m, dict) and m.get("role") == "user":
            c = m.get("content")
            if isinstance(c, str):
                return c
            if isinstance(c, list):
                return "".join(p.get("text", "") for p in c if isinstance(p, dict))
    return ""


class Router:
    """A scenario callable: `fn(prompt) -> reply text`. Records every call and
    the peak number of requests in flight; `delay` holds each reply."""

    def __init__(self, fn, delay: float = 0.0, on_call=None):
        self.fn, self.delay, self.on_call = fn, delay, on_call
        self.prompts: "list[str]" = []
        self.active = 0
        self.peak = 0
        self._lock = threading.Lock()

    def __call__(self, handler, body) -> None:
        prompt = last_user_text(body)
        with self._lock:
            self.prompts.append(prompt)
            self.active += 1
            self.peak = max(self.peak, self.active)
        try:
            if self.on_call:
                self.on_call(prompt)
            if self.delay:
                time.sleep(self.delay)
            reply = self.fn(prompt)
        finally:
            with self._lock:
                self.active -= 1
        _finish(handler, text_step(reply))


def register(reviewer=None, judge=None, coder=None) -> None:
    for name, router in ((REVIEWER_MODEL, reviewer), (JUDGE_MODEL, judge), (CODER_MODEL, coder)):
        if router is not None:
            SCENARIOS[name] = router


def git(cwd: Path, *args: str) -> str:
    return subprocess.run(["git", *args], cwd=str(cwd), capture_output=True, text=True, check=True).stdout


def make_repo() -> Path:
    """main with a.py; branch `feature` adds util.py and changes a.py (committed)."""
    d = Path(tempfile.mkdtemp(prefix="rv-run-"))
    git(d, "init", "-q", "-b", "main")
    git(d, "config", "user.email", "test@example.invalid")
    git(d, "config", "user.name", "Test")
    git(d, "config", "commit.gpgsign", "false")
    (d / "a.py").write_text("def add(a, b):\n    return a + b\n", encoding="utf-8")
    git(d, "add", "-A")
    git(d, "commit", "-q", "-m", "base")
    git(d, "checkout", "-q", "-b", "feature")
    (d / "a.py").write_text("def add(a, b):\n    return a - b\n", encoding="utf-8")
    (d / "util.py").write_text("def first(xs):\n    return xs[0]\n", encoding="utf-8")
    git(d, "add", "-A")
    git(d, "commit", "-q", "-m", "feature work")
    return d


def new_session(mock, cwd: Path, *, max_concurrent=None):
    """A real print-style Session in `cwd` whose role table points at the three mock models."""
    from halo_harness.agent.assemble import SessionContext
    from halo_harness.agent.loop import Session
    from halo_harness.model import ModelProfile, parse_model_ref
    from halo_harness.permissions import PermissionEngine
    from halo_harness.providers.stream import ProviderCreds

    os.environ["BRIDGE_TEST_HOME"] = str(Path(tempfile.mkdtemp(prefix="rv-home-")))
    model = "or:mock/rv-main"
    session = Session(
        cwd=cwd, model_ref=parse_model_ref(model), model_profile=ModelProfile(),
        creds=ProviderCreds(base_url=mock.base_url, api_key="k"),
        state_dir=Path(tempfile.mkdtemp(prefix="rv-state-")), model_label=model,
        session_context=SessionContext(cwd=cwd, model_label=model, bare=True), openrouter_base_url=mock.base_url,
        max_turns=10, permission_engine=PermissionEngine(mode="acceptEdits", cwd=cwd), agents={}, routes={},
    )
    session.interactive = False
    session.agent_runtime.role_table = dict(ROLE_TABLE)
    if max_concurrent is not None:
        session.agent_runtime.max_concurrent = max_concurrent
    return session


def finding_json(file="a.py", line=2, severity="high", category="logic-error", short="subtracts instead of adds",
                 summary="add() now subtracts.", scenario="add(1, 2) returns -1"):
    import json
    return json.dumps({"file": file, "line": line, "severity": severity, "category": category,
                       "short_summary": short, "summary": summary, "failure_scenario": scenario})


def fenced(items: "list[str]") -> str:
    return "```json\n[" + ",".join(items) + "]\n```"


def fake_gh(diff_text: str, meta_json: str) -> Path:
    """A `gh` on PATH that answers `pr diff N` and `pr view N --json ...`."""
    d = Path(tempfile.mkdtemp(prefix="rv-fakegh-"))
    (d / "diff.txt").write_text(diff_text, encoding="utf-8")
    (d / "meta.json").write_text(meta_json, encoding="utf-8")
    (d / "fake_gh.py").write_text(
        "import sys, pathlib\n"
        "here = pathlib.Path(__file__).parent\n"
        "(here / 'calls.txt').open('a').write(' '.join(sys.argv[1:]) + '\\n')\n"
        "a = sys.argv[1:]\n"
        "if a[:2] == ['pr', 'diff']:\n"
        "    sys.stdout.write((here / 'diff.txt').read_text(encoding='utf-8'))\n"
        "elif a[:2] == ['pr', 'view']:\n"
        "    sys.stdout.write((here / 'meta.json').read_text(encoding='utf-8'))\n"
        "else:\n"
        "    sys.stderr.write('unexpected: ' + ' '.join(a)); sys.exit(2)\n", encoding="utf-8")
    if os.name == "nt":
        (d / "gh.cmd").write_text(f'@echo off\r\n"{sys.executable}" "%~dp0fake_gh.py" %*\r\n', encoding="utf-8")
    else:
        sh = d / "gh"
        sh.write_text(f'#!/bin/sh\nexec "{sys.executable}" "$(dirname "$0")/fake_gh.py" "$@"\n', encoding="utf-8")
        sh.chmod(0o755)
    return d
