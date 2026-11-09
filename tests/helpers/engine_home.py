"""tests.helpers.engine_home -- the rig for the engines of the descriptor table. `with EngineHome() as h:` is
tests/helpers/hf_local_env.HfHome (a fresh home, the fake hub, the box card) plus `huggingface.engine_bins` = each
engine's [python, tests/helpers/fake_engine.py, <id>], the adapter's seams saying Linux x86_64 (no WSL), HALO_ENV_FILE in
the scratch home (a key lands there), FAKE_ENGINE_STATE a scratch folder (the fake's argv log, Strata's supervisor
state) and HF_HUB_CACHE a scratch folder (`h.cached(repo)` writes a snapshot there). The exit stops every server Halo
started and every process the fake's supervisor started. Nothing reaches anything but the fakes on 127.0.0.1.
"""
from __future__ import annotations

import json
import os
import sys
from pathlib import Path

from tests.helpers.hf_local_env import HfHome

FAKE = Path(__file__).resolve().parent / "fake_engine.py"
LINUX = {"os": "linux", "arch": "x86_64", "wsl": False}
_VARS = ("FAKE_ENGINE_STATE", "FAKE_ENGINE_LOAD_S", "FAKE_ENGINE_EXIT", "FAKE_ENGINE_DOWNLOAD_GB", "FAKE_ENGINE_WAITING",
         "HALO_ENV_FILE", "HF_HUB_CACHE", "FREETOKEN_API_KEY", "HALO_SECRET_FREETOKEN_API_KEY",
         "HALO_SECRET_STRATA_API_KEY", "HALO_SECRET_TENSORFOLD_API_KEY")


def reset_caches() -> None:
    from halo_harness.engines import adapter, bench, peer
    from halo_harness.ollama_steward import server_log_hf, servers_hf
    from halo_harness.providers.huggingface_local_probe import reset_auto_detect_cache
    adapter.SEAMS.clear()
    bench.SEAMS.clear()
    peer.reset()
    servers_hf.reset()
    server_log_hf.reset()
    reset_auto_detect_cache()


class EngineHome(HfHome):
    def __enter__(self):
        self._en_saved = {k: os.environ.get(k) for k in _VARS}
        for k in _VARS:
            os.environ.pop(k, None)
        super().__enter__()
        self.fake_state, self.hub_cache = self.root / "fake-engine", self.root / "hub"
        os.environ.update(HALO_ENV_FILE=str(self.root / "env"), FAKE_ENGINE_STATE=str(self.fake_state),
                          HF_HUB_CACHE=str(self.hub_cache))
        self.set_hf(engine_bins={e: [sys.executable, str(FAKE), e] for e in ("freetoken", "strata", "tensorfold")})
        reset_caches()
        from halo_harness.engines import adapter
        adapter.SEAMS.update(os=lambda: "linux", machine=lambda: "x86_64", wsl=lambda: False)
        return self

    def set_hf(self, **keys) -> None:
        cfg = self.config()
        cfg.setdefault("huggingface", {}).update(keys)
        (self.state / "config.json").write_text(json.dumps(cfg, indent=2), encoding="utf-8")
        from halo_harness.ollama_steward import servers_hf
        servers_hf.reset()

    def checkpoint(self, name: str = "Qwen3.6-35B-A3B-NVFP4") -> Path:
        d = self.models / name
        d.mkdir(parents=True, exist_ok=True)
        (d / "config.json").write_text(json.dumps({"architectures": ["Qwen3_5MoeForCausalLM"]}), encoding="utf-8")
        return d

    def cached(self, repo: str) -> Path:
        d = self.hub_cache / ("models--" + repo.replace("/", "--")) / "snapshots" / "abc123"
        d.mkdir(parents=True, exist_ok=True)
        (d / "config.json").write_text("{}", encoding="utf-8")
        return d

    def argv(self) -> list:
        try:
            return [json.loads(x) for x in (self.fake_state / "argv").read_text(encoding="utf-8").splitlines()]
        except OSError:
            return []

    def __exit__(self, *exc):
        try:
            super().__exit__(*exc)
        finally:
            from tests.helpers.fake_engine import kill
            try:
                rows = json.loads((self.fake_state / "servers.json").read_text(encoding="utf-8"))
            except (OSError, ValueError):
                rows = []
            for r in rows:
                kill(r.get("pid"))
            reset_caches()
            for k, v in self._en_saved.items():
                if v is None:
                    os.environ.pop(k, None)
                else:
                    os.environ[k] = v


__all__ = ["EngineHome", "FAKE", "LINUX", "reset_caches"]
