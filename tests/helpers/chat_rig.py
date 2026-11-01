"""tests.helpers.chat_rig -- Halo 3.3.7.0 R5: a scratch home for the steward's chat (tests/test_steward_chat.py,
tests/test_studio_steward_chat.py).

`ChatHome(steps, main_steps=None)` scopes this process to a fresh `BRIDGE_TEST_HOME` (the test flag on, `OLLAMA_HOST` at
a refused port) whose one Ollama host, `loop`, is a MockUpstream on 127.0.0.1:0: the steward's model
`steward-mock:1b` answers the fixed replies `steps` in order (each a JSON object or a string, ScriptedByCallCount), the
session's main model `main-mock:8b` answers `main_steps`; `ollama.steward.model` and `model` name them. The rules read
fixture ledger lines (the 27B's prompts at 31k of a 32k window: a `window-small` finding) and a measured cap of 65,536;
the card and the catalog reach the rules through studio/ollama_hosts_view.READERS. No real model, nothing beyond
127.0.0.1, every variable it touches restored.

    h.state, h.mock, h.url, h.finding (the window finding's id), h.calls(model) -> how often that model was asked
"""
from __future__ import annotations

import json
import os
import shutil
import tempfile

from tests.helpers.mock_ollama import MockUpstream, ScriptedByCallCount

STEWARD, MAIN = "steward-mock:1b", "main-mock:8b"
_VARS = ("BRIDGE_TEST_HOME", "BRIDGE_STATE_DIR", "BRIDGE_TEST_NO_BACKGROUND_NET", "OLLAMA_HOST", "HALO_OFFLINE")


def step(obj, *, tin: int = 900, tout: int = 30) -> list:
    text = obj if isinstance(obj, str) else json.dumps(obj)
    return [{"message": {"role": "assistant", "content": text}, "done": True, "done_reason": "stop",
             "prompt_eval_count": tin, "eval_count": tout, "eval_duration": 1000, "prompt_eval_duration": 1000}]


class ChatHome:
    def __init__(self, steps: list, main_steps=None) -> None:
        self.steps, self.main_steps = [step(s) for s in steps], [step(s) for s in (main_steps or ["(no main step)"])]

    def __enter__(self) -> "ChatHome":
        from tests.helpers.steward_seed import card, rows
        self._saved = {k: os.environ.get(k) for k in _VARS}
        for k in ("BRIDGE_STATE_DIR", "HALO_OFFLINE"):
            os.environ.pop(k, None)
        self.root = tempfile.mkdtemp(prefix="hs_chat-")
        os.environ.update(BRIDGE_TEST_HOME=self.root, BRIDGE_TEST_NO_BACKGROUND_NET="1", OLLAMA_HOST="http://127.0.0.1:9")
        self.steward_s, self.main_s = ScriptedByCallCount(self.steps), ScriptedByCallCount(self.main_steps)
        tags = {"models": [{"name": m, "model": m, "size": 1000, "digest": f"sha256:{i}a", "details": {
            "family": "qwen3", "parameter_size": "1B", "quantization_level": "Q4_0"}} for i, m in enumerate((STEWARD, MAIN))]}
        show = {m: {"capabilities": ["completion"], "details": {"family": "qwen3"},
                    "model_info": {"qwen3.context_length": 32768}} for m in (STEWARD, MAIN)}
        self.mock = MockUpstream(scenarios={STEWARD: self.steward_s, MAIN: self.main_s}, tags_response=tags,
                                 show_responses=show).start()
        self.url = f"http://127.0.0.1:{self.mock.port}"
        from halo_harness.config.paths import bridge_home
        from halo_harness.theme import set_config_value
        self.state = bridge_home()
        self.state.mkdir(parents=True, exist_ok=True)
        for k, v in {"ollama.hosts": [{"name": "loop", "url": self.url}], "ollama.auto_calibrate": False,
                     "ollama.steward.model": f"ol:{STEWARD}@loop", "model": f"ol:{MAIN}@loop",
                     "ollama.steward.probe_new": False}.items():
            set_config_value(k, v)
        from halo_harness.studio import ollama_hosts_view as V
        self._readers = dict(V.READERS)
        r = rows()
        V.READERS["card"] = lambda h: {**card(total_mib=24564, kv="q8_0"), "read_at": "fixture"}
        V.READERS["catalog"] = lambda h: {"models": list(r.values())}
        V.reset_cache()
        self._seed()
        return self

    def _seed(self) -> None:
        from halo_harness.ollama_steward.ledger import append_lines
        from halo_harness.ollama_steward.rules import gather, run_rules
        from halo_harness.providers.ollama_calibrate import record_calibration
        from halo_harness.studio import ollama_hosts_view as V
        from tests.helpers.steward_seed import line
        host = {"name": "loop", "url": self.url}
        record_calibration(self.state, host_url=self.url, model="qwen3.8:27b", digest=None, max_full_gpu_ctx=65536,
                           ollama_version=None)
        append_lines(self.state, [line(host=host, prompt_eval_count=31000, ago=300 - i, session=None) for i in range(5)])
        found = run_rules(gather(self.state, **V.readers()))
        self.finding = next((f["id"] for f in found if f.get("model") == "qwen3.8:27b"), "")

    def calls(self, model: str) -> int:
        return (self.steward_s if model == STEWARD else self.main_s).calls

    def __exit__(self, *exc) -> None:
        from halo_harness.studio import ollama_hosts_view as V
        self.mock.stop()
        V.READERS.clear()
        V.READERS.update(self._readers)
        V.reset_cache()
        for k, v in self._saved.items():
            if v is None:
                os.environ.pop(k, None)
            else:
                os.environ[k] = v
        shutil.rmtree(self.root, ignore_errors=True)
