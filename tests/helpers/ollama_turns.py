"""tests.helpers.ollama_turns -- Halo 3.2.3.0 R1: a real `halo -p`
Session in a subprocess against `tests/helpers/mock_ollama.MockUpstream`
(never a real Ollama, never a real model), shared by tests/test_ollama_
trim_recovery.py and tests/test_ollama_trim_500.py.
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

from tests.helpers.fake_home import build_fake_home
from tests.helpers.mock_ollama import DEFAULT_SHOW, DEFAULT_TAGS, MockUpstream, _finish_chat

REPO_DIR = Path(__file__).resolve().parent.parent.parent

_COMPACTION_MARKER = "Do not mention this summarization process"

def _env(fh, mock) -> dict:
    env = dict(os.environ)
    env.pop("BRIDGE_STATE_DIR", None)
    for k in [k for k in env if k.startswith("HALO_")]:
        env.pop(k, None)
    env.pop("OLLAMA_API_KEY", None)
    env.update({"BRIDGE_TEST_HOME": str(fh["home"]), "BRIDGE_TEST_NO_BACKGROUND_NET": "1",
                "OLLAMA_HOST": mock.base_url, "PYTHONPATH": str(REPO_DIR)})
    return env


def _run(fh, mock, prompt: str, model: str, timeout: float = 90):
    args = [sys.executable, "-m", "halo_harness", "-p", prompt, "--model", f"ol:{model}",
            "--cwd", str(fh["proj"]), "--permission-mode", "auto", "--verbose"]
    return subprocess.run(args, env=_env(fh, mock), cwd=str(REPO_DIR), capture_output=True, text=True,
                          timeout=timeout)


def _mock_with(model: str, trained: "int | None") -> MockUpstream:
    """A mock whose catalog has `model` at `trained` context (None: not in
    the catalog, the ceiling is the hard cap)."""
    tags = json.loads(json.dumps(DEFAULT_TAGS))
    show = json.loads(json.dumps(DEFAULT_SHOW))
    if trained is not None:
        tags["models"].append({"name": model, "model": model, "modified_at": "2026-01-01T00:00:00Z",
                               "size": 1234, "digest": "sha256:feedface",
                               "details": {"family": "qwen3", "families": ["qwen3"], "parameter_size": "1B",
                                           "quantization_level": "Q4_0", "format": "gguf"}})
        show[model] = {"modelfile": "", "parameters": "", "template": "", "capabilities": ["tools"],
                       "details": {"family": "qwen3", "quantization_level": "Q4_0"},
                       "model_info": {"qwen3.context_length": trained}}
    return MockUpstream(tags_response=tags, show_responses=show)


def _done(text: str, prompt_eval_count="real") -> list:
    return [{"message": {"role": "assistant", "content": text}, "done": True, "done_reason": "stop",
             "prompt_eval_count": prompt_eval_count, "eval_count": 3}]


def _is_compaction(body) -> bool:
    return _COMPACTION_MARKER in json.dumps((body or {}).get("messages") or [])


class _Script:
    """Answers a compaction request with a summary, and every other
    request with the next step of `steps` (a list of NDJSON lines, or a
    callable `(handler, body)`), the last step repeating."""

    def __init__(self, steps: list):
        self.steps = steps
        self.calls = 0

    def __call__(self, handler, body) -> None:
        if _is_compaction(body):
            _finish_chat(handler, _done("## Summary\nThe user asked for a note; nothing else.", 1))
            return
        step = self.steps[min(self.calls, len(self.steps) - 1)]
        self.calls += 1
        step(handler, body) if callable(step) else _finish_chat(handler, step)


def _shape(chats) -> str:
    """"A" an answering request, "C" a compaction request, runs of C collapsed."""
    out = ""
    for c in chats:
        ch = "C" if _is_compaction(c["body"]) else "A"
        if not (ch == "C" and out.endswith("C")):
            out += ch
    return out


def _chats(mock) -> list:
    return [r for r in mock.requests if r["method"] == "POST" and r["path"].rstrip("/") == "/api/chat"]


def _num_ctx(req) -> int:
    return ((req["body"] or {}).get("options") or {}).get("num_ctx")


def _floor_of(req) -> int:
    """Halo's own estimate of a sent request (its `num_predict` is the reply's room)."""
    from halo_harness.providers.ollama_prompt import estimate_request_tokens
    body = req["body"] or {}
    return estimate_request_tokens(body.get("messages"), body.get("tools"), "",
                                   reply_tokens=(body.get("options") or {}).get("num_predict"))


def _base_floor() -> int:
    """Halo's own prompt in this fake home, measured once (one plain turn)."""
    if "v" not in _BASE:
        fh = build_fake_home()
        mock = _mock_with("probe-model", None)
        mock.start()
        try:
            mock.scenarios["probe-model"] = _Script([_done("ok")])
            _run(fh, mock, "hi", "probe-model")
            req = _chats(mock)[0]
            _BASE["v"] = _floor_of(req)
            _BASE["prompt"] = _BASE["v"] - max(1024, (req["body"].get("options") or {}).get("num_predict") or 0)
        finally:
            mock.stop()
    return _BASE["v"]


def _no_room_trained() -> int:
    """A trained context the window always lands ON (the prompt fits with
    a smaller reply), so a trim there cannot be answered by a raise."""
    _base_floor()
    return _BASE["prompt"] + 4096


_BASE: dict = {}


def _pow2_above(n: int) -> int:
    p = 1
    while p < n:
        p *= 2
    return p
