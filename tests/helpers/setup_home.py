"""tests.helpers.setup_home -- a scratch home for the Setup route tests (Halo
3.3.0.0 R2, tests/test_setup_providers_api.py): `BRIDGE_TEST_HOME`, its own env
file (`HALO_ENV_FILE` in that home, never ~/.config/halo/env), no background
network, every provider variable taken out of the environment and put back,
the Models rows stubbed (they probe configured Ollama hosts), Setup's last
probe results and detection lines forgotten."""

from __future__ import annotations

import json
import os
import tempfile
from pathlib import Path

PREFIXES = ("OPENROUTER_", "DATABRICKS_", "ANTHROPIC_", "OPENAI_", "TYPESAFE_", "EXPLABS_", "HF_", "HALO_SECRET_", "BRIDGE_STATE_DIR",
            "HALO_ENV_FILE", "BRIDGE_ENV_FILE", "OLLAMA_HOST", "BRIDGE_TEST_NO_BACKGROUND_NET")


class SetupHome:
    """A scratch home with its own env file; every provider variable taken out of the environment and put back."""

    def __enter__(self):
        self._saved = {k: v for k, v in os.environ.items() if k.startswith(PREFIXES) or k == "BRIDGE_TEST_HOME"}
        for k in self._saved:
            os.environ.pop(k, None)
        d = Path(tempfile.mkdtemp(prefix="setup-prov-"))
        os.environ["BRIDGE_TEST_HOME"] = str(d)
        os.environ["HALO_ENV_FILE"] = str(d / "halo-env")
        os.environ["BRIDGE_TEST_NO_BACKGROUND_NET"] = "1"
        from halo_harness.providers.config import default_state_dir
        from halo_harness.studio import setup_providers_state as S
        S.LAST_REACH.clear()
        S.forget_detection()
        self.home, self.env_file = d, d / "halo-env"
        self.state_dir, self.cwd = Path(default_state_dir()), d / "project"
        self.state_dir.mkdir(parents=True, exist_ok=True)
        self.cwd.mkdir(parents=True)
        from halo_harness.studio import model as M  # the Models panel's rows probe Ollama hosts: never here
        self._rows_fn, M.model_rows = M.model_rows, (lambda *_a, **_k: [])
        return self

    def __exit__(self, *exc):
        from halo_harness.studio import model as M
        M.model_rows = self._rows_fn
        for k in [k for k in os.environ if k.startswith(PREFIXES) or k == "BRIDGE_TEST_HOME"]:
            os.environ.pop(k, None)
        os.environ.update(self._saved)

    def call(self, method: str, path: str, body=None):
        from halo_harness.studio.api import Request, dispatch
        return dispatch(Request(method=method, path=path, query={}, body=body or {}, cwd=self.cwd, state_dir=self.state_dir))

    def config(self) -> dict:
        p = self.state_dir / "config.json"
        return json.loads(p.read_text(encoding="utf-8")) if p.is_file() else {}

    def env_text(self) -> str:
        return self.env_file.read_text(encoding="utf-8") if self.env_file.is_file() else ""
