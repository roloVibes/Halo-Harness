"""halo_harness.studio.media_render -- a ComfyUI render started from Studio
(Halo 3.0.4.0 round R5): `POST /api/media/render` builds and queues the
graph on the request thread (so it answers with the prompt id), then
`follow()` waits on a daemon thread, publishes `media_render` frames on the
live feed (`session_id: "media:<prompt id>"`, data `{prompt_id, state:
queued|progress|done|error, text, project, artboard, workflow, artboards?,
error?}`) and saves every output as an artboard of the design project:
`render.<ext>` + `source.json {"app": "comfyui", "workflow", "prompt_id",
"set", ...}`, then `Project.snapshot()` (a render over an existing artboard
is its next version). `RENDERS` keeps the last state of each render for
`GET media/renders/<prompt id>`.
"""

from __future__ import annotations

import json
import os
import threading
import time
from typing import Callable, Optional

from halo_harness.flows.steps_media import RENDER_FILES

RENDERS: dict = {}
_lock = threading.Lock()
MAX_KEPT = 50


def _remember(pid: str, data: dict) -> None:
    with _lock:
        RENDERS[pid] = dict(data)
        if len(RENDERS) > MAX_KEPT:
            for old in list(RENDERS)[:len(RENDERS) - MAX_KEPT]:
                RENDERS.pop(old, None)


def render_state(pid: str) -> Optional[dict]:
    with _lock:
        row = RENDERS.get(pid)
        return dict(row) if row else None


def frame(pid: str, data: dict) -> dict:
    return {"session_id": f"media:{pid}", "event": "media_render", "data": dict(data, prompt_id=pid),
            "turn": None, "agent_id": None, "ts": time.time()}


def save_outputs(client, project, outs: list, *, workflow: str, pid: str, sets: dict, artboard: str) -> list:
    """Each output into an artboard (the first one is `artboard`, written over when it exists)."""
    arts = []
    known = {a["id"] for a in project.artboards()}
    for i, out in enumerate(outs):
        kind = "video" if out.get("kind") == "video" else "image"
        title = artboard if i == 0 else f"{artboard} {i + 1}"
        from halo_harness.design.store import slugify
        aid = slugify(title)
        if aid not in known:
            aid = project.add_artboard(title, kind=kind, app="comfyui")["id"]
        d = project.artboard_dir(aid)
        d.mkdir(parents=True, exist_ok=True)
        for old in RENDER_FILES:
            if (d / old).is_file():
                (d / old).unlink()
        data = client.view(out["filename"], out.get("subfolder", ""), out.get("type", "output"))
        ext = os.path.splitext(str(out["filename"]))[1].lower() or (".mp4" if kind == "video" else ".png")
        path = d / ("render" + ext)
        path.write_bytes(data)
        (d / "source.json").write_text(json.dumps(
            {"app": "comfyui", "workflow": workflow, "prompt_id": pid, "set": sets, "title": title, "kind": kind,
             "output": out, "studio": True}, indent=2, default=str) + "\n", encoding="utf-8")
        arts.append({"id": aid, "kind": kind, "path": str(path), "bytes": len(data),
                     "url": f"/design-files/{project.slug}/{aid}/{path.name}"})
    versions = project.snapshot(note=f"comfyui render {pid}")
    project.log_turn({"app": "comfyui", "prompt_id": pid, "artboards": [a["id"] for a in arts],
                      "prompt": sets.get("prompt"), "studio": True})
    by_id = dict(versions)
    for a in arts:
        a["version"] = by_id.get(a["id"]) or next((x.get("latest") for x in project.artboards() if x["id"] == a["id"]), 0)
    return arts


def follow(client, project, *, pid: str, workflow: str, sets: dict, artboard: str, publish: Optional[Callable],
           timeout_s: float = 1800, poll_s: float = 1.0) -> dict:
    """Wait for the render, save it, publish each step; the final state."""
    base = {"project": project.slug, "artboard": artboard, "workflow": workflow}

    def emit(data: dict) -> None:
        row = dict(base, **data)
        _remember(pid, dict(row, prompt_id=pid))
        if publish is not None:
            try:
                publish(frame(pid, row))
            except Exception:
                pass

    from halo_harness.media.comfy_client import ComfyError
    try:
        entry = client.wait(pid, timeout_s=timeout_s, poll_s=poll_s,
                            on_progress=lambda s: emit({"state": "progress", "text": str(s)}))
        outs = client.outputs(entry)
        if not outs:
            raise ComfyError(f"{workflow} finished without an output", 0)
        arts = save_outputs(client, project, outs, workflow=workflow, pid=pid, sets=sets, artboard=artboard)
        emit({"state": "done", "text": f"{len(arts)} artboard(s) into {project.slug}: "
                                        + ", ".join(a["id"] for a in arts), "artboards": arts})
    except Exception as e:  # ComfyError, a timeout, a write error: the frame says which
        emit({"state": "error", "text": str(e), "error": f"{type(e).__name__}: {e}"})
    return render_state(pid) or {}


def start(client, project, *, pid: str, workflow: str, sets: dict, artboard: str, publish: Optional[Callable],
          timeout_s: float = 1800, poll_s: float = 1.0) -> threading.Thread:
    first = dict(project=project.slug, artboard=artboard, workflow=workflow, state="queued",
                 text=f"queued {workflow} on {client.url} as {pid}")
    _remember(pid, dict(first, prompt_id=pid))
    if publish is not None:
        try:
            publish(frame(pid, first))
        except Exception:
            pass
    t = threading.Thread(target=follow, args=(client, project), daemon=True, name=f"halo-media-{pid[:12]}",
                         kwargs=dict(pid=pid, workflow=workflow, sets=sets, artboard=artboard, publish=publish,
                                     timeout_s=timeout_s, poll_s=poll_s))
    t.start()
    return t
