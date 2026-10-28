"""tests.helpers.model_switch_rig -- Halo 3.3.5.0 R0: a real Session over a
fake Ollama (`tests/helpers/mock_ollama.MockUpstream` on 127.0.0.1:0) with
several models of different windows and capabilities, for
tests/test_model_switch.py and tests/test_model_switch_paths.py. Never a real
Ollama, never a model call, never the real ~/.halo: a fake home per rig.

Models (host "lan"):
    big:30b     trained 65,536; completion, tools, thinking, vision
    small:9b    trained 65,536, learned cap 32,768; completion, tools
    mid:14b     trained 65,536; completion, tools (no cap: a profile decides)
    notools:7b  trained 32,768; completion only
Every chat answers "ok"; a compaction request gets an eight-section summary.
"""

from __future__ import annotations

import json
import os
import queue
import tempfile
from pathlib import Path

from tests.helpers.fake_home import build_fake_home
from tests.helpers.mock_ollama import MockUpstream, _finish_chat

MODELS = {"big:30b": (65536, ["completion", "tools", "thinking", "vision"]),
          "small:9b": (65536, ["completion", "tools"]),
          "mid:14b": (65536, ["completion", "tools"]),
          "notools:7b": (32768, ["completion"])}
SMALL_CAP = 32768
COMPACTION_MARKER = "Do not mention this summarization process"
_SCRUB = ("OLLAMA_HOST", "OLLAMA_API_KEY", "BRIDGE_STATE_DIR")


def summary_text() -> str:
    from halo_harness.agent.compact import SUMMARY_HEADINGS
    return "\n".join(f"## {h}\nThe user filled the history with notes; nothing else is pending." for h in SUMMARY_HEADINGS)


def _catalog():
    tags, show = {"models": []}, {}
    for i, (name, (trained, caps)) in enumerate(MODELS.items()):
        tags["models"].append({"name": name, "model": name, "modified_at": "2026-01-01T00:00:00Z", "size": 1000 + i,
                               "digest": f"sha256:m0{i}", "details": {"family": "qwen3", "families": ["qwen3"],
                               "parameter_size": "9B", "quantization_level": "Q4_0", "format": "gguf"}})
        show[name] = {"modelfile": "", "parameters": "", "template": "", "capabilities": caps,
                      "details": {"family": "qwen3", "quantization_level": "Q4_0"},
                      "model_info": {"qwen3.context_length": trained}}
    return tags, show


def _answer(handler, body) -> None:
    text = summary_text() if COMPACTION_MARKER in json.dumps((body or {}).get("messages") or []) else "ok"
    _finish_chat(handler, [{"message": {"role": "assistant", "content": text}, "done": True, "done_reason": "stop",
                            "prompt_eval_count": "real", "eval_count": 3}])


class Rig:
    def __enter__(self):
        self._saved = {k: os.environ.get(k) for k in ("BRIDGE_TEST_HOME",) + _SCRUB}
        for k in _SCRUB:
            os.environ.pop(k, None)
        self.fh = build_fake_home()
        os.environ["BRIDGE_TEST_HOME"] = str(self.fh["home"])
        tags, show = _catalog()
        self.mock = MockUpstream(tags_response=tags, show_responses=show, scenarios={m: _answer for m in MODELS}).start()
        from halo_harness.config.paths import bridge_home
        from halo_harness.providers.ollama import reset_catalog_cache
        from halo_harness.theme import set_config_value
        self.state_dir = Path(bridge_home())
        self.state_dir.mkdir(parents=True, exist_ok=True)
        set_config_value("ollama.hosts", [{"name": "lan", "url": self.mock.base_url, "default": True}])
        set_config_value("ollama.auto_calibrate", False)
        reset_catalog_cache()
        from halo_harness.providers.ollama_calibrate import record_calibration
        record_calibration(self.state_dir, host_url=self.mock.base_url, model="small:9b", digest="sha256:m01",
                           max_full_gpu_ctx=SMALL_CAP, ollama_version=self.mock.version_response.get("version"))
        return self

    def __exit__(self, *exc):
        self.mock.stop()
        from halo_harness.providers.ollama import reset_catalog_cache
        reset_catalog_cache()
        for k, v in self._saved.items():
            if v is None:
                os.environ.pop(k, None)
            else:
                os.environ[k] = v

    def resolve(self, raw: str):
        from halo_harness.model import ModelProfile, parse_model_ref
        from halo_harness.providers.stream import ProviderCreds
        ref = parse_model_ref(raw)
        caps = MODELS.get(ref.model, (65536, []))[1]
        return ref, ModelProfile(context_tokens=MODELS.get(ref.model, (65536,))[0], max_output_tokens=4096,
                                 vision="vision" in caps), ProviderCreds(base_url=self.mock.base_url, api_key="")

    def session(self, raw: str = "ol:big:30b@lan", **kw):
        from halo_harness.agent.assemble import SessionContext
        from halo_harness.agent.loop import Session
        from halo_harness.permissions import PermissionEngine
        ref, profile, creds = self.resolve(raw)
        return Session(cwd=self.fh["proj"], model_ref=ref, model_profile=profile, creds=creds, state_dir=self.state_dir,
                       model_label=raw, session_context=SessionContext(cwd=self.fh["proj"], model_label=raw), max_turns=6,
                       permission_engine=PermissionEngine(mode="auto", cwd=self.fh["proj"]), **kw)

    def chats(self, model=None) -> list:
        out = [r["body"] for r in self.mock.requests if r["method"] == "POST" and r["path"].rstrip("/") == "/api/chat"]
        return [b for b in out if model is None or b.get("model") == model]

    def run(self, session, commands: list) -> list:
        """The worker pump (`Session.run`) over `commands`, every event it put out."""
        q: "queue.Queue" = queue.Queue()
        for c in commands + [None]:
            q.put(c)
        seen: list = []
        session.run(q, seen.append)
        return seen


def fill(session, pairs: int, chars: int = 1400) -> None:
    filler = "lorem ipsum dolor sit amet " * (chars // 27 + 1)
    for i in range(pairs):
        session.log.append_user([{"type": "text", "text": f"note {i}: {filler[:chars]}"}])
        session.log.append_assistant(content=[{"type": "text", "text": f"noted {i}. {filler[:chars]}"}], stop_reason="end_turn")


def png_file() -> str:
    """A 1x1 PNG on disk (the log keeps an image as its path)."""
    import base64
    data = base64.b64decode("iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNkYPhfDwAChwGA60e6kgAAAABJRU5ErkJggg==")
    p = Path(tempfile.mkdtemp(prefix="m0-img-")) / "shot.png"
    p.write_bytes(data)
    return str(p)


def markers(evs: list, state: str = "switch") -> list:
    return [e.data.get("text") for e in evs if e.kind == "turn_marker" and e.data.get("state") == state]


def ledger_lines(state_dir) -> list:
    from halo_harness.ollama_steward.ledger import read_calls
    return read_calls(state_dir)
