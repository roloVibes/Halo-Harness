"""tests.helpers.st_home -- Halo 3.3.9.2: the Strata rig. `with StHome() as h:` is tests/helpers/hf_local_env.HfHome (a
fresh home, the fake hub, the box card: a 24 GB card and 64 GB of RAM) plus `huggingface.strata_bin` = [python,
tests/helpers/fake_strata.py], FAKE_STRATA_STATE in the scratch home (the fake's launches: never Strata's real state
folder), HALO_ENV_FILE in the scratch home (Halo's key lands there). On the way out every server the fake started is
stopped (Halo's `halo local stop` first, then any the fake still lists). Nothing reaches anything but the fakes.
"""
from __future__ import annotations

import json
import os
import sys
from pathlib import Path

from tests.helpers.hf_local_env import HfHome

FAKE_ST = Path(__file__).resolve().parent / "fake_strata.py"
_VARS = ("FAKE_STRATA_STATE", "FAKE_STRATA_DOWNLOAD_GB", "FAKE_STRATA_ENGINE_MISSING", "FAKE_STRATA_ENGINE_PCT",
         "FAKE_STRATA_NO_ENGINE", "FAKE_STRATA_LAUNCH_S", "FAKE_STRATA_MODE", "FAKE_STRATA_TOK_S", "FAKE_STRATA_HIT",
         "FAKE_STRATA_PARALLEL", "FAKE_STRATA_KEY", "HALO_ENV_FILE", "HALO_SECRET_STRATA_API_KEY", "HF_LOCAL_PROBE_PORTS")


def reset_caches() -> None:
    from halo_harness.ollama_steward import server_log_hf, servers_hf
    from halo_harness.providers.huggingface_local_probe import reset_auto_detect_cache
    from halo_harness.strata import peer, requirements
    requirements.SEAMS.clear()
    peer.reset()
    servers_hf.reset()
    server_log_hf.reset()
    reset_auto_detect_cache()


class StHome(HfHome):
    def __enter__(self):
        self._st_saved = {k: os.environ.get(k) for k in _VARS}
        for k in _VARS:
            os.environ.pop(k, None)
        super().__enter__()
        os.environ["HALO_ENV_FILE"] = str(self.root / "env")
        os.environ["FAKE_STRATA_STATE"] = str(self.root / "strata-state")
        self.set_hf(strata_bin=[sys.executable, str(FAKE_ST)])
        reset_caches()
        return self

    def set_hf(self, **keys) -> None:
        cfg = self.config()
        cfg.setdefault("huggingface", {}).update(keys)
        (self.state / "config.json").write_text(json.dumps(cfg, indent=2), encoding="utf-8")
        from halo_harness.ollama_steward import servers_hf
        servers_hf.reset()

    def fake_runs(self) -> dict:
        try:
            return json.loads((self.root / "strata-state" / "runs.json").read_text(encoding="utf-8"))
        except (OSError, ValueError):
            return {}

    def __exit__(self, *exc):
        try:
            super().__exit__(*exc)
        finally:
            from tests.helpers import fake_strata
            for run in self.fake_runs().values():
                fake_strata.kill(run.get("pid"))
            reset_caches()
            for k, v in self._st_saved.items():
                if v is None:
                    os.environ.pop(k, None)
                else:
                    os.environ[k] = v


__all__ = ["FAKE_ST", "StHome", "reset_caches"]
