"""halo_harness.media.comfy_ops -- what the `mcp__comfyui__*` tools and the
`halo media` commands both do: find a workflow (inline graph, JSON file,
saved name on the server, or a Halo starter), build its API graph with the
`set`/`only` edits, queue it, wait, list its outputs, and fetch an output
over HTTP into a file under the working directory.
"""

from __future__ import annotations

import json
import os
import time
from pathlib import Path
from typing import Callable, Optional

from halo_harness.media.comfy_client import ComfyClient, ComfyError, queue_state
from halo_harness.media.comfy_graph import ComfyGraphError, apply_set, for_queue, only, to_api

STARTERS_DIR = Path(__file__).resolve().parent.parent / "templates" / "comfy"


def starter_names() -> list:
    return sorted(p.stem for p in STARTERS_DIR.glob("*.json"))


def load_starter(name: str) -> Optional[dict]:
    stem = name[:-5] if name.lower().endswith(".json") else name
    p = STARTERS_DIR / f"{stem}.json"
    return json.loads(p.read_text(encoding="utf-8")) if p.is_file() else None


def load_workflow(client: ComfyClient, workflow, cwd: Optional[Path] = None) -> "tuple[dict, str]":
    """(graph, label). Order: an inline graph, a JSON file path, a workflow
    saved on the server (with or without .json), a Halo starter."""
    if isinstance(workflow, dict):
        return workflow, "inline graph"
    text = str(workflow or "").strip()
    if not text:
        raise ComfyError("workflow is empty: give a saved name, a starter name, a .json path or a graph", 0)
    if text.startswith("{"):
        try:
            return json.loads(text), "inline graph"
        except ValueError as e:
            raise ComfyError(f"the inline workflow is not valid JSON: {e}", 0) from None
    base = Path(cwd or os.getcwd())
    path = Path(text).expanduser()
    path = path if path.is_absolute() else base / path
    if path.is_file():
        try:
            return json.loads(path.read_text(encoding="utf-8")), str(path)
        except ValueError as e:
            raise ComfyError(f"{path} is not valid JSON: {e}", 0) from None
    try:
        return client.workflow(text), f"saved workflow {text!r}"
    except ComfyError as e:
        if e.status not in (404, 400):
            raise
    starter = load_starter(text)
    if starter is not None:
        return starter, f"starter {text!r}"
    try:
        saved = ", ".join(n[:-5] for n in client.workflows()) or "(none)"
    except ComfyError:
        saved = "(could not list)"
    raise ComfyError(f"no workflow {text!r}: saved on the server: {saved}; starters: {', '.join(starter_names())}", 404)


def _upload_local_images(client: ComfyClient, graph: dict, cwd: Path) -> None:
    """A LoadImage `image` that names a file on THIS machine is uploaded to
    the server first (the server may be another host)."""
    for nid, n in graph.items():
        if n.get("class_type") not in ("LoadImage", "LoadImageMask"):
            continue
        val = (n.get("inputs") or {}).get("image")
        if not isinstance(val, str) or not val:
            continue
        p = Path(val).expanduser()
        p = p if p.is_absolute() else cwd / p
        if p.is_file():
            n["inputs"]["image"] = client.upload_image(str(p))


def build_graph(client: ComfyClient, workflow, sets: Optional[dict] = None, only_ids=None,
                cwd: Optional[Path] = None) -> dict:
    graph, label = load_workflow(client, workflow, cwd)
    try:
        api = to_api(graph, client.object_info)
        api = apply_set(api, sets or {})
        if only_ids:
            api = only(api, only_ids)
    except ComfyGraphError as e:
        raise ComfyError(f"{label}: {e}", 0) from None
    _upload_local_images(client, api, Path(cwd or os.getcwd()))
    return for_queue(api)


def run(client: ComfyClient, workflow, sets: Optional[dict] = None, only_ids=None, wait: bool = True,
        timeout_s: float = 1800, cwd: Optional[Path] = None, on_progress: Optional[Callable[[str], None]] = None,
        poll_s: float = 1.0) -> dict:
    t0 = time.monotonic()
    api = build_graph(client, workflow, sets, only_ids, cwd)
    pid = client.queue_prompt(api)
    out = {"prompt_id": pid, "nodes": len(api)}
    if not wait:
        out.update(state="queued", outputs=[])
        return out
    entry = client.wait(pid, timeout_s=timeout_s, poll_s=poll_s, on_progress=on_progress)
    out.update(state="done", outputs=client.outputs(entry), elapsed=round(time.monotonic() - t0, 1))
    return out


def status(client: ComfyClient, prompt_id: str) -> dict:
    entry = client.history(prompt_id)
    if entry:
        st = entry.get("status") or {}
        if st.get("status_str") == "error":
            from halo_harness.media.comfy_errors import execution_error_text
            return {"prompt_id": prompt_id, "state": "error", "error": execution_error_text(prompt_id, st)}
        return {"prompt_id": prompt_id, "state": "done", "outputs": client.outputs(entry)}
    return {"prompt_id": prompt_id, "state": queue_state(client.queue(), prompt_id)}


def _output_ref(output) -> dict:
    if isinstance(output, dict) and output.get("filename"):
        return {"filename": str(output["filename"]), "subfolder": str(output.get("subfolder") or ""),
                "type": str(output.get("type") or "output")}
    text = str(output or "").strip().replace("\\", "/")
    if not text:
        raise ComfyError("output is empty: pass one of comfy_run's outputs (or 'subfolder/filename')", 0)
    sub, _, name = text.rpartition("/")
    return {"filename": name, "subfolder": sub, "type": "output"}


def inside(path: Path, root: Path) -> bool:
    try:
        real, base = os.path.realpath(path), os.path.realpath(root)
        return os.path.commonpath([os.path.normcase(real), os.path.normcase(base)]) == os.path.normcase(base)
    except ValueError:
        return False


def fetch(client: ComfyClient, output, to_path: str, cwd: Optional[Path] = None) -> dict:
    ref = _output_ref(output)
    root = Path(cwd or os.getcwd())
    target = Path(str(to_path or "").strip() or ref["filename"]).expanduser()
    target = target if target.is_absolute() else root / target
    if str(to_path or "").endswith(("/", "\\")) or target.is_dir():
        target = target / ref["filename"]
    if not inside(target, root):
        raise ComfyError(f"to_path {str(to_path)!r} resolves to {target}, outside the working directory {root}; "
                         "comfy_fetch writes under the working directory", 0)
    data = client.view(ref["filename"], ref["subfolder"], ref["type"])
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_bytes(data)
    return {"path": str(target), "bytes": len(data), "source": ref}


def model_rows(client: ComfyClient, folder: Optional[str] = None):
    if folder:
        files = client.models(folder)
        return {"folder": folder, "count": len(files), "files": files}
    rows = []
    for f in client.model_folders():
        try:
            rows.append({"folder": f, "count": len(client.models(f))})
        except ComfyError as e:
            rows.append({"folder": f, "count": None, "error": str(e)})
    return rows


def workflows_listing(client: ComfyClient) -> dict:
    return {"saved": [n[:-5] for n in client.workflows()], "starters": starter_names()}


def object_info_view(client: ComfyClient, node: Optional[str] = None) -> dict:
    if node:
        try:
            spec = client.object_info(node)
        except ComfyError:
            spec = {}
        if spec:
            return spec
    info = client.object_info()
    if node:
        needle = node.lower()
        hits = {k: v.get("category", "") for k, v in info.items()
                if needle in k.lower() or needle in str(v.get("display_name", "")).lower()}
        return {"query": node, "matches": dict(sorted(hits.items())[:200]), "count": len(hits)}
    by_cat: dict = {}
    for k, v in info.items():
        by_cat.setdefault(str(v.get("category") or "uncategorized"), []).append(k)
    return {"count": len(info), "by_category": {c: sorted(v) for c, v in sorted(by_cat.items())}}
