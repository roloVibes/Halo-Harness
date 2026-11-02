"""tests.helpers.bundle_rig -- Halo 3.3.7.0 R5: a scratch home for the bundle tests (tests/test_bundle_*.py,
test_bundles_shipped, test_sched_place's claims, test_degrade's reserved rung, the Studio bundle routes).

`BundleHome(lfm=True)` is tests/helpers/sched_rig.SchedHome on the fixture 24 GB card (24,564 MiB, q8_0 KV) with
ComfyUI holding 2 GiB -- 22.0 GB usable -- whose catalog is the sched rig's four models (qwen3.8:27b, qwen3-coder:30b,
qwen3.5:9b, qwen2.5:1.5b) plus, with `lfm=True`, a small `lfm3:1.7b` row (the glasses bundle's chat model). The
configured model is `ol:qwen3-coder:30b@pc`, so the coder is the task-work target. 3.3.9.0 R1: with `voice=True` (the
default) the glasses bundle's CPU speech models (faster-whisper:small.en, kokoro-82m) are on disk in the home's
`huggingface.model_dirs` folder (tests/helpers/voice_files.put: a few bytes each); `voice=False` leaves them absent, and
`voice=("faster-whisper:large-v3-turbo",)` puts those named. The packs live in the scratch home; nothing is installed
anywhere else, nothing downloads (the fake's pulls stay empty), no model is called.

    h.mock, h.host, h.state                     as SchedHome
    h.pack(argv...) -> (code, stdout, stderr)   `halo pack <argv>` in process
    h.claim(bundle, model, gb, host="pc")       a claim row of another bundle in <state>/ollama/claims.json
    h.studio(method, path, body=None, query=None) -> (status, body)   one Studio API call on this home
"""
from __future__ import annotations

import contextlib
import io
from pathlib import Path

from tests.helpers.sched_rig import SchedHome, rows
from tests.helpers.steward_seed import GIB, card

LFM = "lfm3:1.7b"
SPEECH = ("faster-whisper:small.en", "kokoro-82m")
LFM_ROW = {"model": LFM, "size": 1100000000, "capabilities": ["tools"],
           "model_info": {"qwen2.block_count": 28, "qwen2.attention.head_count_kv": 2, "qwen2.attention.key_length": 128,
                          "qwen2.attention.value_length": 128, "qwen2.embedding_length": 1536},
           "details": {"quantization_level": "Q4_K_M", "parameter_size": "1.7B"}}


def fixture_card() -> dict:
    return card(total_mib=24564, kv="q8_0", others=[{"name": "ComfyUI", "bytes": 2 * GIB}])


class BundleHome(SchedHome):
    def __init__(self, *, lfm: bool = True, card_=None, loaded=None, voice=True) -> None:
        super().__init__(card=card_ if card_ is not None else fixture_card(), loaded=loaded)
        self.lfm = lfm
        self.voice = SPEECH if voice is True else tuple(voice or ())

    def __enter__(self) -> "BundleHome":
        super().__enter__()
        from halo_harness.studio import ollama_hosts_view as V
        self.rows = rows()
        if self.lfm:
            self.rows[LFM] = dict(LFM_ROW)
        V.READERS["catalog"] = lambda h: {"models": list(self.rows.values())} if h.name == "pc" else \
            (self.catalogs.get(h.name) or {"models": []})
        self.config(**{"model": "ol:qwen3-coder:30b@pc"})
        self.models = Path(self.root) / "models"
        self.models.mkdir(parents=True, exist_ok=True)
        self.config(**{"huggingface.model_dirs": [str(self.models)]})
        from tests.helpers.voice_files import put
        for name in self.voice:
            put(self.models, name)
        self.repo = Path(self.root) / "repo"  # the cwd: its .halo/packs is the project layer, not the home's
        self.repo.mkdir(parents=True, exist_ok=True)
        self._reset()
        from halo_harness.local_sched.reserve import forget
        forget()
        return self

    def pack(self, *argv) -> "tuple[int, str, str]":
        from halo_harness.packs.cli import cmd_pack
        out, err = io.StringIO(), io.StringIO()
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
            code = cmd_pack(list(argv) + ["--cwd", str(self.repo)])
        return code, out.getvalue(), err.getvalue()

    def claim(self, bundle: str, model: str, gb: float, host: str = "pc") -> None:
        from halo_harness.local_sched import claims_file as CF
        CF.put(CF.local_file(self.state), {"bundle": bundle, "host": host, "model": model, "gb": gb, "holder": "keep",
                                           "scope": "keep", "via": "local", "escalation": "on"})
        from halo_harness.local_sched.reserve import forget
        forget()

    def studio(self, method: str, path: str, body=None, query=None) -> "tuple[int, dict]":
        from halo_harness.studio.api import Request, dispatch
        return dispatch(Request(method=method, path=path, query=query or {}, body=body or {}, cwd=self.repo,
                                state_dir=self.state, server=None))
