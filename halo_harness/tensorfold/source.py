"""halo_harness.tensorfold.source -- what `tensorfold serve` is given for a model (Halo 3.3.9.3; docs/MODELS-tensorfold.md
"Serve"). TensorFold serves "a complete local checkpoint directory or an existing Hugging Face cache" and `tensorfold
serve REPO` serves a cached checkpoint by its repository name (README "Send a request", "Models on disk": from the source,
unverified against a live run). Halo never downloads a checkpoint for it on its own: `tensorfold pull` is the user's.

    resolve(model, env=None) -> {arg, name, where, repo, path} | None
        a folder with a config.json -> that folder (arg = its path); a repo id in the Hub cache TensorFold reads
        (`HF_HUB_CACHE`, else `HF_HOME/hub`, else ~/.cache/huggingface/hub) -> the repo id itself; a repo id Halo's
        download job put in a `huggingface.model_dirs` folder (the hub cache's layout) -> its snapshot folder
    missing_line(model) -> one line: the download (the GB TensorFold's table states) and the two routes to it
"""

from __future__ import annotations

from pathlib import Path
from typing import Optional


def _snapshot(root: Path, repo: str) -> Optional[Path]:
    d = Path(root) / ("models--" + repo.replace("/", "--"))
    try:
        ref = (d / "refs" / "main").read_text(encoding="utf-8").strip()
    except OSError:
        ref = ""
    snaps = d / "snapshots"
    cand = [snaps / ref] if ref else []
    try:
        cand += sorted((p for p in snaps.iterdir() if p.is_dir()), key=lambda p: p.stat().st_mtime, reverse=True)
    except OSError:
        pass
    return next((p for p in cand if (p / "config.json").is_file()), None)


def _model_dirs(env=None) -> list:
    try:
        from halo_harness.providers.local_model_dirs import resolve_model_dirs
        return [Path(p) for p in resolve_model_dirs(env=env)]
    except Exception:
        return []


def resolve(model: str, env=None) -> Optional[dict]:
    raw = str(model or "").strip()
    if not raw:
        return None
    p = Path(raw).expanduser()
    if p.is_dir() and (p / "config.json").is_file():
        name = p.parent.parent.name.split("--")[-1] if p.parent.name == "snapshots" else p.name
        return {"arg": str(p.resolve()), "name": name, "where": "the folder", "repo": None, "path": p.resolve()}
    if raw.count("/") != 1 or p.is_absolute():
        return None
    repo = raw.split("@", 1)[0]
    from halo_harness.providers.huggingface_hub_cache import resolve_hub_cache_root
    hub = resolve_hub_cache_root(env)
    snap = _snapshot(hub, repo)
    if snap is not None:
        return {"arg": repo, "name": repo.rsplit("/", 1)[-1], "where": f"the Hugging Face cache ({hub})", "repo": repo,
                "path": snap}
    for d in _model_dirs(env):
        snap = _snapshot(d, repo)
        if snap is not None:
            return {"arg": str(snap), "name": repo.rsplit("/", 1)[-1], "where": f"{d} (Halo's download)", "repo": repo,
                    "path": snap}
    return None


def missing_line(model: str) -> str:
    from halo_harness.tensorfold.catalog import match
    row = match(model)
    size = f" ({row['size_words']}, TensorFold's figure)" if row and row.get("size_words") else (
        " (its size is not in TensorFold's table: tensorfold info names the floor after the pull)")
    if row and row.get("convert"):
        return f"{model} is not on disk{size}: {row['pull']}; then halo local serve --runtime tensorfold --model <the folder>"
    pull = row["pull"] if row else f"tensorfold pull {model}"
    return (f"{model} is not on disk{size}: {pull} downloads it into the Hugging Face cache (yours to run), or halo "
            f"local download {model.split('@', 1)[0]} puts it in a huggingface.model_dirs folder; then serve it again")
