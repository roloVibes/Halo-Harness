"""halo_harness.media.comfy_server -- ComfyUI as an MCP stdio server (the
eighth craft app): `python -m halo_harness.media.comfy_server [cwd]` or
`halo media serve`. Same `mcp.server.lowlevel.Server` + `stdio_server()`
pattern as `halo_harness.mcp.serve`. The server URL comes from `COMFY_URL`
(what `halo media init` writes into the registered entry), else
`comfy.url` in ~/.halo/config.json, else http://127.0.0.1:8188.

Every failure is an `is_error` result naming the node or the HTTP status;
a tool never takes the process down.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Optional

from halo_harness.media import comfy_ops
from halo_harness.media.comfy_client import ComfyClient, ComfyError

_WF = {"type": "string", "description": "A workflow saved in ComfyUI (by name, '.json' optional), a Halo starter "
       "('text-to-image-qwen', 'image-to-video-wan22'), a path to a JSON file, or the graph itself as a JSON string. "
       "UI-format graphs are converted to API format."}

TOOLS = [
    {"name": "comfy_models", "description": "Model files on the ComfyUI server. Without `folder`: every model folder "
     "with its file count. With `folder` (checkpoints, diffusion_models, loras, vae, text_encoders, upscale_models, "
     "TTS, ...): the files in it.",
     "input_schema": {"type": "object", "properties": {"folder": {"type": "string"}}}},
    {"name": "comfy_workflows", "description": "The workflows saved in ComfyUI's editor and Halo's starter workflows.",
     "input_schema": {"type": "object", "properties": {}}},
    {"name": "comfy_object_info", "description": "Node classes on the server. With `node`: that class's inputs, "
     "outputs and defaults (or the classes whose name contains it). Without: every class name by category.",
     "input_schema": {"type": "object", "properties": {"node": {"type": "string"}}}},
    {"name": "comfy_inspect", "description": "A workflow's nodes as API format: node id, class, title and literal "
     "inputs (and the `set` keys a starter declares). Use it to pick `set` keys for comfy_run.",
     "input_schema": {"type": "object", "properties": {"workflow": _WF}, "required": ["workflow"]}},
    {"name": "comfy_run", "description": "Queue a workflow and (by default) wait for it. `set` overrides inputs: "
     "{'<node id>.<input>': v} or {'<node title>.<input>': v} or a starter key such as {'prompt': ..., 'width': 1024, "
     "'seed': 'random'}; a LoadImage `image` naming a local file is uploaded first. `only` keeps just the listed output "
     "nodes and what feeds them. Returns {prompt_id, outputs: [{node, filename, subfolder, type, kind}]}; pass an "
     "output to comfy_fetch to save it.",
     "input_schema": {"type": "object", "properties": {
         "workflow": _WF, "set": {"type": "object", "description": "input overrides"},
         "only": {"type": "array", "items": {"type": "string"}, "description": "output node ids or titles to keep"},
         "wait": {"type": "boolean", "default": True}, "timeout_s": {"type": "number", "default": 1800}},
         "required": ["workflow"]}},
    {"name": "comfy_status", "description": "A queued prompt's state (pending, running, done, error) and, when done, "
     "its outputs.",
     "input_schema": {"type": "object", "properties": {"prompt_id": {"type": "string"}}, "required": ["prompt_id"]}},
    {"name": "comfy_fetch", "description": "Download one output (an item of comfy_run's `outputs`, or "
     "'subfolder/filename') over HTTP and write it to `to_path` under the working directory, e.g. "
     "artboards/<id>/render.png. Returns the path and byte size.",
     "input_schema": {"type": "object", "properties": {
         "output": {"type": "object", "properties": {"filename": {"type": "string"}, "subfolder": {"type": "string"},
                                                     "type": {"type": "string"}}},
         "to_path": {"type": "string"}}, "required": ["output", "to_path"]}},
]


def _workflow_arg(args: dict):
    wf = args.get("workflow")
    if wf is None or (isinstance(wf, str) and not wf.strip()):
        raise ComfyError("workflow is required", 0)
    return wf


def call_tool(name: str, args: dict, *, client: Optional[ComfyClient] = None, cwd: Optional[Path] = None):
    """Dispatch one tool call; returns a JSON-able result or raises."""
    from halo_harness.media.comfy_graph import describe_inputs, to_api
    client = client or ComfyClient()
    cwd = Path(cwd or Path.cwd())
    args = args or {}
    if name == "comfy_models":
        return comfy_ops.model_rows(client, args.get("folder") or None)
    if name == "comfy_workflows":
        return comfy_ops.workflows_listing(client)
    if name == "comfy_object_info":
        return comfy_ops.object_info_view(client, args.get("node") or None)
    if name == "comfy_inspect":
        graph, label = comfy_ops.load_workflow(client, _workflow_arg(args), cwd)
        return {"workflow": label, "nodes": describe_inputs(to_api(graph, client.object_info))}
    if name == "comfy_run":
        sets = args.get("set") or {}
        if not isinstance(sets, dict):
            raise ComfyError("set must be an object of {key: value}", 0)
        only_ids = args.get("only") or []
        if isinstance(only_ids, str):
            only_ids = [only_ids]
        return comfy_ops.run(client, _workflow_arg(args), sets, only_ids, wait=args.get("wait", True) is not False,
                             timeout_s=float(args.get("timeout_s") or 1800), cwd=cwd)
    if name == "comfy_status":
        pid = str(args.get("prompt_id") or "").strip()
        if not pid:
            raise ComfyError("prompt_id is required", 0)
        return comfy_ops.status(client, pid)
    if name == "comfy_fetch":
        return comfy_ops.fetch(client, args.get("output"), str(args.get("to_path") or ""), cwd)
    raise ComfyError(f"unknown tool {name!r}; tools: {', '.join(t['name'] for t in TOOLS)}", 0)


def tool_result(name: str, args: dict, *, client=None, cwd=None) -> "tuple[str, bool]":
    """(text, is_error) -- never raises."""
    try:
        return json.dumps(call_tool(name, args, client=client, cwd=cwd), indent=1, ensure_ascii=False), False
    except ComfyError as e:
        return f"{name}: {e}", True
    except Exception as e:  # a bug or an odd reply must never take the server down
        return f"{name}: {type(e).__name__}: {e}", True


async def run_server(cwd: Path) -> None:
    import asyncio

    import mcp.server.stdio
    import mcp.types as types
    from mcp.server.lowlevel import Server

    client = ComfyClient()

    async def on_list_tools(_ctx, _params):
        return types.ListToolsResult(tools=[types.Tool(name=t["name"], description=t["description"],
                                                       input_schema=t["input_schema"]) for t in TOOLS])

    async def on_call_tool(_ctx, params):
        text, is_error = await asyncio.to_thread(tool_result, params.name, dict(params.arguments or {}),
                                                 client=client, cwd=cwd)
        return types.CallToolResult(content=[types.TextContent(type="text", text=text)], is_error=is_error)

    server = Server("comfyui", version="1.0", on_list_tools=on_list_tools, on_call_tool=on_call_tool)
    async with mcp.server.stdio.stdio_server() as (read_stream, write_stream):
        await server.run(read_stream, write_stream, server.create_initialization_options())


def main(argv=None) -> int:
    import asyncio
    argv = sys.argv[1:] if argv is None else argv
    cwd = Path(argv[0]).resolve() if argv else Path.cwd()
    asyncio.run(run_server(cwd))
    return 0


if __name__ == "__main__":
    sys.exit(main())
