"""halo_harness.flows.steps_media -- the render and confirm steps.

* render: `uses: "comfy:<workflow>"` -- a Halo starter name, a JSON file
  (absolute, or relative to the flow's cwd) or a workflow saved on the
  ComfyUI server (UI format converted through `comfy_graph.to_api`). The
  step's `set` (refs resolved, `--set <step>.<key>=<value>` overrides on
  top, a redo's instructions appended to `prompt`) goes through
  `apply_set`; the graph is queued, waited on with progress lines, and
  every output is fetched over HTTP (`GET /view`) into an artboard of the
  run's design project: `artboards/<id>/render.png|mp4` + `source.json
  {"app": "comfyui", "workflow", "prompt_id", "set"}`, then
  `Project.snapshot()`. A redo writes over the same artboards, so each
  round is a new version. Output `{artboards: [{id, kind, path,
  prompt_id}], prompt_id, prompt, workflow, set}`.
* confirm: the flow-owned human gate over the render (gates.py). accept ->
  `{accepted: [paths], artboards, rounds}`; redo -> the `on_fail` render
  runs again with the instruction, at most MAX_ROUNDS renders in all;
  stop -> the run stops.
"""

from __future__ import annotations

import json
import os
import random
from pathlib import Path

from halo_harness.flows import gates
from halo_harness.flows.refs import resolve_value
from halo_harness.flows.state import StopFlow

MAX_ROUNDS = 5  # renders per run of one render step, like agent/subagent.py's _MAX_APPROVAL_ROUNDS
RENDER_FILES = ("render.png", "render.mp4", "render.webp", "render.jpg", "render.jpeg", "render.gif", "render.webm",
                "render.wav", "render.flac", "render.mp3")


def load_render_workflow(client, workflow: str, cwd) -> "tuple[dict, str]":
    from halo_harness.media import comfy_ops
    starter = comfy_ops.load_starter(workflow)
    if starter is not None:
        return starter, f"starter {workflow!r}"
    return comfy_ops.load_workflow(client, workflow, Path(cwd))


def render_sets(ctx) -> dict:
    sets = resolve_value(dict(ctx.step.get("set") or {}), ctx.outputs)
    sets.update((ctx.overrides or {}).get(ctx.sid) or {})
    for k, v in list(sets.items()):  # a random seed is drawn here, so source.json records the one used
        if k.split(".")[-1] in ("seed", "noise_seed") and (v == -1 or str(v).lower() == "random"):
            sets[k] = random.randint(1, 2**48)
    instructions = [i for i in ctx.record.get("instructions") or [] if i]
    if instructions and "prompt" in sets:
        base = str(sets.get("prompt") or "").rstrip().rstrip(".")
        sets["prompt"] = base + ". " + ". ".join(instructions)
    return sets


def _source(project, aid: str) -> dict:
    try:
        return json.loads((project.artboard_dir(aid) / "source.json").read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}


def _render_name(filename: str, kind: str) -> str:
    ext = os.path.splitext(str(filename))[1].lower() or (".mp4" if kind == "video" else ".png")
    return "render" + ext


def render(ctx) -> dict:
    from halo_harness.media import comfy_ops
    from halo_harness.media.comfy_client import ComfyError
    workflow = str(ctx.step.get("uses") or "")[len("comfy:"):]
    want = ctx.step.get("outputs") or {}
    sets = render_sets(ctx)
    client = ctx.adapters.comfy_client()
    try:
        graph, label = load_render_workflow(client, workflow, ctx.cwd)
        api = comfy_ops.build_graph(client, graph, sets, cwd=Path(ctx.cwd))
        pid = client.queue_prompt(api)
        ctx.flow.log("step", f"{ctx.sid}: queued {label} on {client.url} as {pid}", step=ctx.sid, prompt_id=pid)
        entry = client.wait(pid, timeout_s=ctx.adapters.render_timeout_s, poll_s=ctx.adapters.poll_s,
                            on_progress=lambda s: ctx.flow.log("note", f"{ctx.sid}: {s}", step=ctx.sid, prompt_id=pid))
        outs = client.outputs(entry)
    except ComfyError as e:
        raise StopFlow(f"{ctx.sid}: {e}") from None
    if not outs:
        raise StopFlow(f"{ctx.sid}: {label} finished without an output")
    project = ctx.project()
    prev = [a.get("id") for a in ((ctx.record.get("output") or {}).get("artboards") or [])]
    if not prev:  # a render killed after it made its artboards: write over them, never beside them
        prev = [a["id"] for a in project.artboards() if _source(project, a["id"]).get("flow_run") == ctx.run
                and _source(project, a["id"]).get("step") == ctx.sid]
    title = str(want.get("artboard") or ctx.sid)
    arts = []
    for i, out in enumerate(outs):
        kind = str(want.get("kind") or out.get("kind") or "image")
        kind = kind if kind in ("image", "video") else ("video" if out.get("kind") == "video" else "image")
        aid = prev[i] if i < len(prev) and project.artboard_dir(prev[i]).is_dir() else None
        if aid is None:
            aid = project.add_artboard(title if i == 0 else f"{title} {i + 1}", kind=kind, app="comfyui")["id"]
        d = project.artboard_dir(aid)
        for old in RENDER_FILES:
            if (d / old).is_file():
                (d / old).unlink()
        try:
            data = client.view(out["filename"], out.get("subfolder", ""), out.get("type", "output"))
        except ComfyError as e:
            raise StopFlow(f"{ctx.sid}: fetching {out['filename']}: {e}") from None
        path = d / _render_name(out["filename"], kind)
        path.write_bytes(data)
        (d / "source.json").write_text(json.dumps(
            {"app": "comfyui", "workflow": workflow, "prompt_id": pid, "set": sets, "title": title, "kind": kind,
             "output": out, "flow_run": ctx.run, "step": ctx.sid}, indent=2, default=str) + "\n", encoding="utf-8")
        arts.append({"id": aid, "kind": kind, "path": str(path), "prompt_id": pid, "bytes": len(data)})
    versions = project.snapshot(note=f"flow {ctx.run} {ctx.sid} round {int(ctx.record.get('rounds') or 0) + 1}")
    project.log_turn({"flow": ctx.run, "step": ctx.sid, "app": "comfyui", "prompt_id": pid,
                      "artboards": [a["id"] for a in arts], "prompt": sets.get("prompt")})
    ctx.record["rounds"] = int(ctx.record.get("rounds") or 0) + 1
    ctx.flow.log("step", f"{ctx.sid}: {len(arts)} artboard(s) into {project.slug}: "
                         + ", ".join(a["id"] for a in arts), step=ctx.sid, artboards=arts, versions=versions)
    return {"artboards": arts, "prompt_id": pid, "prompt": sets.get("prompt"), "workflow": workflow, "set": sets}


def _target(ctx) -> str:
    on_fail = str(ctx.step.get("on_fail") or "")
    if on_fail.startswith("redo:"):
        return on_fail[len("redo:"):]
    earlier = [s.get("id") for s in ctx.spec.get("steps") or [] if s.get("kind") == "render"
               and s.get("id") in ctx.outputs]
    if not earlier:
        raise StopFlow(f"{ctx.sid}: no render before this confirm step")
    return earlier[-1]


def confirm(ctx) -> dict:
    target = _target(ctx)
    while True:
        shown = (ctx.outputs.get(target) or {})
        arts = shown.get("artboards") or []
        ctx.record["rounds"] = int(ctx.record.get("rounds") or 0) + 1
        ctx.save()
        text = "\n".join(a["path"] for a in arts) + "\n" + str(shown.get("prompt") or "")
        if ctx.adapters.auto_accept:
            ctx.flow.log("gate", f"{ctx.sid}: accepted automatically (--yes): " + ", ".join(a["path"] for a in arts),
                         step=ctx.sid, id=f"{ctx.run}:{ctx.sid}", action="accept", auto=True, artboards=arts)
            return {"accepted": [a["path"] for a in arts], "artboards": arts, "rounds": ctx.record["rounds"]}
        gate = gates.post_gate(ctx.flow, ctx.n, {"id": f"{ctx.run}:{ctx.sid}", "step": ctx.sid, "position": "You",
                                                 "text": text, "artboards": arts, "round": ctx.record["rounds"],
                                                 "target": target})
        ctx.flow.set(ctx.sid, "waiting", "the render needs your answer")
        ans = gates.wait_answer(ctx.flow, ctx.n, gate, poll_s=ctx.adapters.poll_s,
                                auto_accept=ctx.adapters.auto_accept, answer_gate=ctx.adapters.answer_gate)
        ctx.flow.set(ctx.sid, "running")
        if ans["action"] == "accept":
            return {"accepted": [a["path"] for a in arts], "artboards": arts, "rounds": ctx.record["rounds"]}
        if ans["action"] == "stop":
            raise StopFlow(f"stopped at {ctx.sid}" + (f": {ans['instruction']}" if ans["instruction"] else ""))
        renders = int(ctx.runner.record_of(target).get("rounds") or 0)
        if renders >= MAX_ROUNDS:
            raise StopFlow(f"{ctx.sid}: {target} has rendered {MAX_ROUNDS} times; the gate stops the run here")
        ctx.runner.rerun(target, ans["instruction"])
