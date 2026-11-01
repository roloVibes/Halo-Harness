"""halo_harness.local_pool.gguf -- where the pool model's GGUF is on this machine (Halo 3.3.8.0 R3; docs/POOL.md "The
preflight"). Only the controller holds the file: llama-server ships the tensors to every rpc-server.

    find(model) -> {path, files, where, line} | {path: None, line, download}
        the catalog row's `repo` in a huggingface.model_dirs folder (the layout `halo local download` writes:
        <dir>/models--<org>--<name>/snapshots/<commit>/<file>) or the Hugging Face hub cache, the files whose name
        holds the row's `file` (a quant word such as Q4_K_M; a split GGUF's first shard `-00001-of-` is the one
        llama-server opens, it finds the rest itself). Not found: the one Download line (the existing download + verify
        job; nothing downloads until it is pressed).
Reads the disk only.
"""

from __future__ import annotations

from pathlib import Path
from typing import Optional


def _roots() -> list:
    """The model folders, then the hub cache -- under the test flag only when HF_HUB_CACHE / HF_HOME names one (a test
    never reads this machine's own cache)."""
    import os
    from halo_harness.config.paths import background_net_disabled
    from halo_harness.providers.huggingface_hub_cache import resolve_hub_cache_root
    from halo_harness.providers.local_model_dirs import resolve_model_dirs
    hub = [] if background_net_disabled() and not (os.environ.get("HF_HUB_CACHE") or os.environ.get("HF_HOME")) \
        else [resolve_hub_cache_root()]
    return [d for d in resolve_model_dirs() + hub if d.is_dir()]


def _pick(files: list, word: str) -> list:
    w = (word or "").lower()
    hit = [f for f in files if not w or w in f.name.lower()]
    return sorted(hit, key=lambda f: ("-00001-of-" not in f.name.lower() and "-of-" in f.name.lower(), f.name))


def find(model: dict, roots: Optional[list] = None) -> dict:
    org_name = str(model.get("repo") or "").replace("/", "--")
    for root in roots if roots is not None else _roots():
        snaps = Path(root) / f"models--{org_name}" / "snapshots"
        if not snaps.is_dir():
            continue
        files = [f for f in snaps.rglob("*.gguf") if f.is_file() or f.is_symlink()]
        got = _pick(files, model.get("file") or "")
        if got:
            size = sum(f.stat().st_size for f in got if f.exists())
            return {"path": str(got[0]), "files": [str(f) for f in got], "where": str(root),
                    "line": f"the GGUF is here: {got[0].name} ({size / 2 ** 30:.1f} GB in {len(got)} file"
                            f"{'' if len(got) == 1 else 's'}, under {root})"}
    from halo_harness.local_pool.recommend import _download, rate
    d = _download(model, rate())
    return {"path": None, "download": d,
            "line": f"the GGUF is not on this machine: Download {d['gb']:g} GB (~{d['eta']} at {d['eta_from']}) -- "
                    f"{d['cli']}; nothing downloads until you press it"}
