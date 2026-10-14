"""halo_harness.media.cli -- `halo media`: ComfyUI as a craft app.

    halo media init [--url U] [--install-workflows] [--yes]   register mcpServers.comfyui, store comfy.url
    halo media doctor [--url U] [--smoke] [--timeout S]       server, model folders, workflows, the entry
    halo media serve                                         the MCP stdio server (what the entry runs)
    halo media inspect <workflow> [--json]                   a workflow's nodes and literal inputs
    halo media models [image|video|audio]                    model files by folder
    halo media workflows                                     saved workflows and the starters
"""

from __future__ import annotations

import argparse
import json
import sys
from typing import Optional

from halo_harness.media.comfy_client import ComfyClient, ComfyError, resolve_url

MODALITY_FOLDERS = {
    "image": ("checkpoints", "diffusion_models", "text_encoders", "vae", "loras", "controlnet", "clip_vision",
              "upscale_models", "latent_upscale_models", "embeddings", "model_patches"),
    "video": ("diffusion_models", "text_encoders", "vae", "loras", "clip_vision", "frame_interpolation",
              "optical_flow", "upscale_models", "latent_upscale_models"),
    "audio": ("TTS", "voices", "audio_encoders"),
}


def _client(url: Optional[str] = None) -> ComfyClient:
    return ComfyClient((url or resolve_url()).rstrip("/"), timeout=30)


def cmd_models(modality: Optional[str], url: Optional[str] = None) -> int:
    client = _client(url)
    folders = client.model_folders()
    from halo_harness.media.setup_cli import NON_MODEL_FOLDERS
    wanted = [f for f in MODALITY_FOLDERS[modality] if f in folders] if modality else         [f for f in folders if f not in NON_MODEL_FOLDERS]
    shown = 0
    for f in wanted:
        files = client.models(f)
        if not files:
            continue
        shown += 1
        print(f"{f} ({len(files)})")
        for name in files:
            print(f"  {name}")
    if not shown:
        print(f"no model files{' for ' + modality if modality else ''} on {client.url}")
    return 0


def cmd_workflows(url: Optional[str] = None) -> int:
    from halo_harness.media import comfy_ops
    listing = comfy_ops.workflows_listing(_client(url))
    print(f"saved in ComfyUI ({len(listing['saved'])}):")
    for n in listing["saved"]:
        print(f"  {n}")
    print(f"Halo starters ({len(listing['starters'])}):")
    for n in listing["starters"]:
        print(f"  {n}")
    return 0


def _short(v, width: int = 100) -> str:
    text = json.dumps(v, ensure_ascii=False) if not isinstance(v, str) else repr(v)
    text = text.replace("\n", " ")
    return text if len(text) <= width else text[:width - 3] + "..."


def cmd_inspect(workflow: str, as_json: bool = False, url: Optional[str] = None) -> int:
    from pathlib import Path

    from halo_harness.media import comfy_ops
    from halo_harness.media.comfy_graph import ComfyGraphError, describe_inputs, to_api
    client = _client(url)
    graph, label = comfy_ops.load_workflow(client, workflow, Path.cwd())
    try:
        rows = describe_inputs(to_api(graph, client.object_info))
    except ComfyGraphError as e:
        raise ComfyError(f"{label}: {e}", 0) from None
    if as_json:
        print(json.dumps({"workflow": label, "nodes": rows}, indent=1, ensure_ascii=False))
        return 0
    print(f"{label}: {len(rows)} node(s); set a value with '<node id>.<input>' or '<title>.<input>'")
    for r in rows:
        title = f"  \"{r['title']}\"" if r.get("title") else ""
        print(f"{r['node']:>8}  {r['class_type']}{title}")
        for k, v in r["inputs"].items():
            print(f"{'':>10}{k} = {_short(v)}")
        if r.get("keys"):
            print(f"{'':>10}set keys: " + ", ".join(f"{k} -> {v}" for k, v in r["keys"].items()))
    return 0


def _parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="halo media", description="ComfyUI as a craft app: local image, video and "
                                "audio generation through the mcp__comfyui__* tools.")
    sub = p.add_subparsers(dest="cmd")
    s = sub.add_parser("init", help="register mcpServers.comfyui (user scope) and store comfy.url")
    s.add_argument("--url", help="the ComfyUI server (default: COMFY_URL, comfy.url, http://127.0.0.1:8188)")
    s.add_argument("--install-workflows", action="store_true", help="save the starter workflows into ComfyUI")
    s.add_argument("--yes", action="store_true", help="overwrite same-named saved workflows without asking")
    s = sub.add_parser("doctor", help="the server, its model folders and workflows, the registered entry")
    s.add_argument("--url", help="check this server instead of the configured one")
    s.add_argument("--smoke", action="store_true", help="render a 64x64 image through the text-to-image starter")
    s.add_argument("--timeout", type=float, default=900, help="seconds the smoke render may take (default 900)")
    sub.add_parser("serve", help="run the ComfyUI MCP server on stdio")
    s = sub.add_parser("inspect", help="a workflow's nodes, titles and literal inputs")
    s.add_argument("workflow", help="saved name, starter name or .json path")
    s.add_argument("--json", action="store_true", help="print JSON")
    s.add_argument("--url", help="the ComfyUI server to read from")
    s = sub.add_parser("models", help="model files by folder")
    s.add_argument("modality", nargs="?", choices=sorted(MODALITY_FOLDERS), help="only the folders for this modality")
    s.add_argument("--url", help="the ComfyUI server to read from")
    s = sub.add_parser("workflows", help="saved workflows and the starters")
    s.add_argument("--url", help="the ComfyUI server to read from")
    return p


def cmd_media(argv: list) -> int:
    parser = _parser()
    args = parser.parse_args(argv)
    if not args.cmd:
        parser.print_help()
        return 0
    try:
        if args.cmd == "init":
            from halo_harness.media.setup_cli import cmd_init
            return cmd_init(args.url, args.install_workflows, args.yes)
        if args.cmd == "doctor":
            from halo_harness.media.setup_cli import cmd_doctor
            return cmd_doctor(args.url, args.smoke, args.timeout)
        if args.cmd == "serve":
            from halo_harness.media.comfy_server import main
            return main([])
        if args.cmd == "inspect":
            return cmd_inspect(args.workflow, args.json, args.url)
        if args.cmd == "models":
            return cmd_models(args.modality, args.url)
        if args.cmd == "workflows":
            return cmd_workflows(args.url)
    except ComfyError as e:
        print(f"halo media {args.cmd}: {e}", file=sys.stderr)
        return 1
    parser.print_help()
    return 2
