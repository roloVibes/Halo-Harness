"""halo_harness.studio.local_download_job -- Halo 3.3.5.0 R5: Local's Hugging Face downloads, the pull jobs'
machinery (studio/local_pull_job.py: the same store, `_measure`, the frames' pace, `cancel`, `current`) with
`kind: "download"`. One job per folder + repo/file: a second ask while it runs joins it. A daemon thread calls
providers/hf_download.download, so a download outlives the page that started it. Every change publishes

    {session_id: "local", event: "download", ts, data: {job, kind: "download", host: <the folder>, name: <repo[ file]>,
     repo, file, dir, path, status, digest: <the file moving>, total, completed, percent, speed, eta, done, error, ok,
     cancelled, say, via, started}}

(at most four a second while bytes move; every status change and the end at once). A cancel stops between chunks
and the part file stays (downloading again resumes). When one ends well the model folders' listing is read again
(studio/local_hf_view.reset) and the caches every model list reads are dropped, so the Hugging Face page and the
Library row say "on disk in <folder>".
"""

from __future__ import annotations

import threading
import time
from pathlib import Path
from typing import Callable, Optional

from halo_harness.studio import local_pull_job as J


def key(dest_dir, repo: str, file: str = "") -> str:
    try:
        d = str(Path(dest_dir).expanduser().resolve())
    except OSError:
        d = str(dest_dir)
    return f"dl|{d.lower()}|{repo.lower()}|{(file or '').lower()}"


def _find(k: str) -> Optional[dict]:
    return next((j for j in J._jobs.values() if not j["done"] and j["key"] == k), None)


def start(dest_dir, repo: str, file: str = "", publish: Optional[Callable] = None, *, token: Optional[str] = None,
          plan: Optional[dict] = None, download=None) -> dict:
    """Download `repo` (or its `file`) into `dest_dir`; the job's view, `joined` when it was running already.
    `download=` takes any fn(repo, file, *, dest_dir, token, on_status, cancel, plan) -> {ok, cancelled, say, ...}."""
    k = key(dest_dir, repo, file)
    name = f"{repo} {file}".strip()
    with J._lock:
        hit = _find(k)
        if hit is not None:
            return {**J.view(hit), "joined": True}
        job = J._new(str(dest_dir), name, "this machine", publish, None, False)
        job.update(key=k, kind="download", repo=repo, file=file or "", dir=str(dest_dir), path=None,
                   say=f"downloading {name} into {dest_dir}")
    from halo_harness.providers.hf_download import download as do_download
    fn = download or do_download

    def on(obj: dict) -> None:
        with J._lock:
            before = job["status"]
            J._measure(job, obj, time.monotonic())
        J._send(job, force=obj.get("status") != before and not obj.get("completed"))

    def body() -> None:
        try:
            got = fn(repo, file or None, dest_dir=dest_dir, token=token, on_status=on, cancel=job["cancel"], plan=plan)
        except Exception as e:
            got = {"ok": False, "error": type(e).__name__, "say": f"the download of {name} stopped: {e}"}
        with J._lock:
            job["path"] = got.get("path")
        if got.get("ok"):
            from halo_harness.studio import local_hf_view
            local_hf_view.reset()
        J._finish(job, got)

    threading.Thread(target=body, name=f"halo-local-{job['job']}", daemon=True).start()
    J._send(job, force=True)
    return {**J.view(job), "joined": False}


def current() -> dict:
    return J.current("download")


def cancel(job_id: str) -> Optional[dict]:
    got = J.get(job_id)
    if got is None or got.get("kind") != "download":
        return None
    return J.cancel(job_id)


__all__ = ["cancel", "current", "key", "start"]
