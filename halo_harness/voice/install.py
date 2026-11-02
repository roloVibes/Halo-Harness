"""halo_harness.voice.install -- a speech model on disk (Halo 3.3.9.0 R1; docs/VOICE.md "Download"):

    present(model, dirs=None) -> Path | None   the folder holding every file the engine loads, under a
        `huggingface.model_dirs` folder: the hub layout `halo local download` writes (<dir>/models--<org>--<name>/
        snapshots/<commit>/), or a plain folder named after the repo (<dir>/<name>/)
    plan(model, *, token=None) -> plan          the hub's listing of the repo, cut to the catalog row's files
    download(model, *, dest_dir, token, on_status, cancel, plan_=None) -> result   providers/hf_download.download
    remove(model, dirs=None) -> (freed bytes, the folder) | (0, None)
    serving(model, state_dir) -> the registry row of a running speech server that serves it, or None

The token is HF_TOKEN read from the environment (models_library.hf_hub.token); it is sent to the hub only and never
written anywhere. Under BRIDGE_TEST_NO_BACKGROUND_NET only a loopback hub is read (providers/hf_download).
"""

from __future__ import annotations

import shutil
from pathlib import Path
from typing import Callable, Optional

from halo_harness.voice.catalog import Row, get


def _dirs(dirs=None) -> list:
    if dirs is not None:
        return [Path(d) for d in dirs]
    from halo_harness.providers.local_model_dirs import resolve_model_dirs
    return resolve_model_dirs()


def _has(folder: Path, row: Row) -> bool:
    try:
        if row.files:
            return all((folder / f).is_file() for f in row.files)
        return folder.is_dir() and any(p.is_file() for p in folder.rglob("*"))
    except OSError:
        return False


def candidates(row: Row, dirs=None) -> list:
    """Every folder a model's files may sit in, newest snapshot first."""
    out = []
    for d in _dirs(dirs):
        hub = d / ("models--" + row.repo.replace("/", "--")) / "snapshots"
        try:
            snaps = sorted((p for p in hub.iterdir() if p.is_dir()), key=lambda p: (-p.stat().st_mtime, p.name)) \
                if hub.is_dir() else []
        except OSError:
            snaps = []
        out += snaps + [d / row.repo.split("/", 1)[-1]]
    return out


def present(model, dirs=None) -> Optional[Path]:
    row = model if isinstance(model, Row) else get(model)
    if row is None:
        return None
    return next((c for c in candidates(row, dirs) if _has(c, row)), None)


def plan(model: str, *, token: Optional[str] = None) -> dict:
    from halo_harness.providers.hf_download import HubError, prepare
    row = get(model)
    if row is None:
        raise HubError("missing", f"{model} is not in the speech catalog (halo voice models lists it)")
    got = prepare(row.repo, None, token=token)
    if row.files:
        files = [f for f in got["files"] if f["name"] in row.files]
        absent = [f for f in row.files if f not in {x["name"] for x in files}]
        if absent:
            raise HubError("no_file", f"{row.repo} does not list {', '.join(absent)} (the files {row.engine} loads): "
                           "the repo id is from memory -- halo voice models marks it unverified")
        got = {**got, "files": files, "total": sum(f["size"] or 0 for f in files)}
    return {**got, "kind": "voice", "model": row.name}


def download(model: str, *, dest_dir, token: Optional[str] = None, on_status: Optional[Callable] = None, cancel=None,
             plan_: Optional[dict] = None) -> dict:
    from halo_harness.providers.hf_download import HubError, download as hub_download
    try:
        p = plan_ or plan(model, token=token)
    except HubError as e:
        return {"ok": False, "error": e.kind, "say": e.message}
    got = hub_download(p["repo"], None, dest_dir=dest_dir, token=token, on_status=on_status, cancel=cancel, plan=p)
    if got.get("ok"):
        where = present(model, [dest_dir])
        got["path"] = str(where) if where else got.get("path")
        got["say"] = f"{model} is on disk in {where or dest_dir}"
    return got


def remove(model: str, dirs=None) -> "tuple[int, Optional[Path]]":
    row = get(model)
    where = present(row, dirs) if row else None
    if where is None:
        return 0, None
    repo = next((p for p in [where, *where.parents] if p.name.startswith("models--")), None)
    target = repo or where
    freed = sum(p.stat().st_size for p in target.rglob("*") if p.is_file())
    shutil.rmtree(target)
    return freed, target


def serving(model: str, state_dir) -> Optional[dict]:
    from halo_harness.providers.local_server import servers
    from halo_harness.voice import is_voice_runtime
    return next((e for e in servers(state_dir) if e.get("alive") and is_voice_runtime(e.get("kind"))
                 and e.get("model") == model), None)


def gb(n) -> str:
    return f"{(n or 0) / 1e9:.2f} GB"
