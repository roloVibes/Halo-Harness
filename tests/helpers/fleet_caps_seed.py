"""tests.helpers.fleet_caps_seed -- capability catalogs for the Halo 3.0.6.0
R6 tests, the Fleet Chrome scenarios and tools/capture_fleet.py:

    hub_catalog(identity)      the hub's own: a workstation with an RTX 4090, ComfyUI, design and film apps
    member_catalog(identity)   a member: a Linux box with gridcraft and the data CLIs
    seed(home, catalog)        written as `<home>/fleet/capabilities.json` (fresh, with its hash)
    mcp_setup(user_home, state_home, servers, tools)   a scoped ~/.claude.json + tool-cache files, so a real
                               gather lists those servers and tools without starting one
"""
from __future__ import annotations

import json
import time
from pathlib import Path


def _tools(*pairs) -> list:
    return [{"name": n, "desc": d} for n, d in pairs]


def _who(identity: dict) -> dict:
    return {k: identity.get(k) for k in ("id", "name", "host", "os", "version")}


def hub_catalog(identity: dict) -> dict:
    return {"harness": _who(identity), "at": time.time(), "tags": ["studio", "gpu"],
            "mcp": [{"name": "designcraft", "transport": "stdio", "tools": _tools(
                        ("new_document", "Create a page layout document"), ("render_page", "Render one page to PNG"))},
                    {"name": "filmcraft", "transport": "stdio", "tools": _tools(
                        ("command_run", "Run one editing command on the timeline"), ("render_frame", "Render a frame"))},
                    {"name": "comfyui", "transport": "stdio", "tools": _tools(
                        ("comfy_run", "Run a ComfyUI workflow: images and video from local diffusion models"))}],
            "skills": ["design", "pptx"], "roles": [{"role": "main", "bio": "general", "lineup": "balanced"}],
            "providers": [{"name": "OpenRouter", "id": "openrouter", "ok": True}],
            "models": [{"id": "or:anthropic/claude-fable-5", "provider": "openrouter", "best_for": ["visual", "design"]}],
            "craft_apps": ["comfyui", "designcraft", "filmcraft"],
            "media": {"comfyui": True, "models": [{"name": "qwen_image_2.1.safetensors", "kind": "image-gen"}]},
            "hardware": {"os": "windows", "distro": "windows", "release": "11", "cpu": "AMD Ryzen 9 7900X", "cores": 24,
                         "ram_gb": 64, "gpu": [{"name": "NVIDIA GeForce RTX 4090", "vram_gb": 24}], "disk_free_gb": 410.6},
            "clis": {"git": "2.45.1", "node": "24.15.0", "python": "3.11.7", "docker": "29.2.0", "ffmpeg": "installed"},
            "projects": [{"name": "Halo-Harness", "repo": "Halo-Harness", "branch": "master"}],
            "integrations": {"paperclip": False, "postiz": True, "signal": True}}


def member_catalog(identity: dict) -> dict:
    return {"harness": _who(identity), "at": time.time(), "tags": ["linux", "data"],
            "mcp": [{"name": "gridcraft", "transport": "stdio", "tools": _tools(
                        ("write_range", "Write values and formulas into a spreadsheet range"),
                        ("insert_chart", "Insert a chart built from a range"))}],
            "skills": ["xlsx"], "roles": [], "providers": [{"name": "Databricks", "id": "databricks", "ok": True}],
            "models": [{"id": "ol:qwen3-coder:30b", "provider": "ollama", "best_for": [], "local": True}],
            "craft_apps": ["gridcraft"], "media": {"comfyui": False, "models": []},
            "hardware": {"os": "linux", "distro": "debian", "release": "6.12", "cpu": "Intel Core i7", "cores": 8,
                         "ram_gb": 16, "gpu": [], "disk_free_gb": 120.0},
            "clis": {"git": "2.47.0", "python": "3.12.8", "docker": None, "ffmpeg": None},
            "projects": [{"name": "ledger", "repo": "ledger", "branch": "main"}],
            "integrations": {"paperclip": False, "postiz": False, "signal": False}}


def seed(home, catalog: dict) -> dict:
    from halo_harness.fleet import capabilities
    cat = {**catalog, "at": time.time()}
    cat["hash"] = capabilities.digest(cat)
    capabilities.save(cat, Path(home))
    return cat


def mcp_setup(user_home, state_home, servers: dict, tools: dict) -> None:
    """`servers` {name: raw entry} into `<user_home>/.claude.json`; `tools` {name: [(tool, desc)]} as cache files."""
    from halo_harness.mcp.manager import parse_server, sanitize_name
    from halo_harness.mcp.tools_cache import config_cache_key
    path = Path(user_home) / ".claude.json"
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        data = {}
    data.setdefault("mcpServers", {}).update(servers)
    path.write_text(json.dumps(data), encoding="utf-8")
    for name, pairs in tools.items():
        cfg = parse_server(name, servers[name], scope="user")
        out = Path(state_home) / "mcp" / "tools-cache" / f"{sanitize_name(name)}.json"
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(json.dumps({"hash": config_cache_key(cfg), "cached_at": time.time(), "instructions": None,
                                   "tools": [{"name": n, "description": d, "input_schema": {"type": "object"}}
                                             for n, d in pairs]}), encoding="utf-8")
