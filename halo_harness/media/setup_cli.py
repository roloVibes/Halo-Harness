"""halo_harness.media.setup_cli -- `halo media init` and `halo media doctor`.

`init` registers the ComfyUI MCP server user-scope through
`mcp_cli._store_entry` (the one writer of `mcpServers` in ~/.claude.json),
stores `comfy.url` in ~/.halo/config.json and, with --install-workflows,
saves the starter workflows into ComfyUI's workflow browser. `doctor`
reports the server, its model folders, saved workflows and the registered
entry; --smoke renders a 64x64 image through the text-to-image starter.
"""

from __future__ import annotations

import sys
import time
from pathlib import Path
from typing import Callable, Optional

from halo_harness.media import comfy_ops
from halo_harness.media.comfy_client import ComfyClient, ComfyError, resolve_url

SERVER_NAME = "comfyui"
NON_MODEL_FOLDERS = ("custom_nodes", "configs")  # listed by /models but not model files
SMOKE_SET = {"width": 64, "height": 64, "steps": 8, "seed": "random", "prompt": "a red apple on a white table, studio light"}


def server_entry(url: str) -> dict:
    return {"type": "stdio", "command": sys.executable, "args": ["-m", "halo_harness.media.comfy_server"],
            "env": {"COMFY_URL": url}}


def registered_entry(cwd: Optional[Path] = None) -> Optional[dict]:
    try:
        from halo_harness.design.crafts_probe import craft_server_entries
        return craft_server_entries(cwd=cwd).get(SERVER_NAME)
    except Exception:
        return None


def _ask(question: str) -> bool:
    try:
        if not sys.stdin.isatty():
            return False
        return input(question + " [y/N] ").strip().lower() in ("y", "yes")
    except (EOFError, OSError):
        return False


def install_workflows(client: ComfyClient, *, yes: bool = False, ask: Callable[[str], bool] = _ask) -> list:
    """Save every starter into ComfyUI's workflows; one question covers
    every starter that is already saved there. Returns the lines printed."""
    existing = {n[:-5] for n in client.workflows()}
    names = comfy_ops.starter_names()
    clash = [n for n in names if n in existing]
    overwrite = yes or (bool(clash) and ask(f"{len(clash)} starter workflow(s) already saved in ComfyUI "
                                            f"({', '.join(clash)}). Overwrite them?"))
    lines = []
    for n in names:
        if n in clash and not overwrite:
            lines.append(f"  kept the saved {n}.json (run with --yes to overwrite it)")
            continue
        client.save_workflow(n, comfy_ops.load_starter(n), overwrite=n in clash)
        lines.append(f"  {'overwrote' if n in clash else 'saved'} workflows/{n}.json")
    return lines


def cmd_init(url: Optional[str], install: bool, yes: bool, out=print) -> int:
    from halo_harness import mcp_cli
    from halo_harness.theme import _config_path, set_config_value
    url = (url or resolve_url()).rstrip("/")
    client = ComfyClient(url, timeout=15)
    reachable = True
    try:
        ver = (client.system_stats().get("system") or {}).get("comfyui_version") or "?"
        out(f"ComfyUI {ver} at {url}: reachable")
    except ComfyError as e:
        reachable = False
        out(f"ComfyUI at {url}: {e} -- registering it anyway; `halo media doctor` checks it again")
    where = mcp_cli._store_entry(scope="user", name=SERVER_NAME, entry=server_entry(url), cwd=Path.cwd())
    set_config_value("comfy.url", url)
    out(f"registered mcpServers.{SERVER_NAME} (user scope) in {where}")
    out(f"comfy.url = {url} in {_config_path()}")
    rc = 0
    if install:
        if not reachable:
            out("--install-workflows skipped: the server is not reachable")
            rc = 1
        else:
            try:
                for line in install_workflows(client, yes=yes):
                    out(line)
            except ComfyError as e:
                out(f"installing the starter workflows failed: {e}")
                rc = 1
    out("Every new Halo session now has the mcp__comfyui__* tools; Halo Design lists ComfyUI as a craft app.")
    return rc


def _gb(n) -> str:
    try:
        return f"{int(n) / 2**30:.1f}"
    except (TypeError, ValueError):
        return "?"


def starter_lines(client: ComfyClient) -> list:
    """Each starter checked against this server's nodes and model files."""
    from halo_harness.media.comfy_graph import check_against, to_api
    try:
        info = client.object_info()
    except ComfyError as e:
        return [f"  starters: could not read /object_info: {e}"]
    out = []
    for name in comfy_ops.starter_names():
        problems = check_against(to_api(comfy_ops.load_starter(name), info), info)
        out.append(f"  starter {name}: " + ("ready" if not problems else "; ".join(problems[:3])
                                            + (f" (+{len(problems) - 3} more)" if len(problems) > 3 else "")))
    return out


def doctor_lines(client: ComfyClient, *, cwd: Optional[Path] = None) -> "tuple[list, bool]":
    lines, ok = [f"ComfyUI at {client.url}"], True
    try:
        t0 = time.monotonic()
        stats = client.system_stats()
        ms = int((time.monotonic() - t0) * 1000)
        sysd = stats.get("system") or {}
        lines.append(f"  reachable ({ms} ms): ComfyUI {sysd.get('comfyui_version', '?')}, python "
                     f"{str(sysd.get('python_version', '?')).split()[0]}, pytorch {sysd.get('pytorch_version', '?')}")
        for d in stats.get("devices") or []:
            lines.append(f"  device: {d.get('name')} -- {_gb(d.get('vram_free'))} of {_gb(d.get('vram_total'))} GB VRAM free")
    except ComfyError as e:
        lines.append(f"  not reachable: {e}")
        ok = False
    if ok:
        try:
            rows = comfy_ops.model_rows(client)
            rows = [r for r in rows if r["folder"] not in NON_MODEL_FOLDERS]
            full = [f"{r['folder']} {r['count']}" for r in rows if r.get("count")]
            empty = sum(1 for r in rows if not r.get("count"))
            lines.append(f"  model folders: {', '.join(full) or '(no model files)'} ({empty} empty)")
            saved = comfy_ops.workflows_listing(client)["saved"]
            lines.append(f"  saved workflows ({len(saved)}): {', '.join(saved) or '(none)'}")
        except ComfyError as e:
            lines.append(f"  listing failed: {e}")
            ok = False
    lines.extend(starter_lines(client) if ok else [f"  starters: {', '.join(comfy_ops.starter_names())}"])
    entry = registered_entry(cwd)
    if entry is None:
        lines.append("  not registered: run `halo media init` to add mcpServers.comfyui")
    else:
        reg_url = str((entry.get("env") or {}).get("COMFY_URL") or "(COMFY_URL unset: config or default)")
        same = "" if reg_url.rstrip("/") == client.url else f" (differs from {client.url})"
        lines.append(f"  registered: mcpServers.{SERVER_NAME} -> {entry.get('command')} "
                     f"{' '.join(map(str, entry.get('args') or []))}, COMFY_URL={reg_url}{same}")
    return lines, ok


def smoke(client: ComfyClient, timeout_s: float = 900, out=print) -> bool:
    out(f"  smoke: queueing text-to-image-qwen at 64x64 ({SMOKE_SET['steps']} steps)")
    t0 = time.monotonic()
    try:
        res = comfy_ops.run(client, "text-to-image-qwen", dict(SMOKE_SET), timeout_s=timeout_s,
                            on_progress=lambda s: out(f"    {s}"))
        images = [o for o in res["outputs"] if o["kind"] == "image"]
        if not images:
            out(f"  smoke FAILED: prompt {res['prompt_id']} finished with no image output ({res['outputs']})")
            return False
        first = images[0]
        data = client.view(first["filename"], first["subfolder"], first["type"])
        name = f"{first['subfolder']}/{first['filename']}" if first["subfolder"] else first["filename"]
        is_png = data[:8] == b"\x89PNG\r\n\x1a\n"
        out(f"  smoke ok: {name} ({len(data)} bytes{', PNG' if is_png else ''}) in {time.monotonic() - t0:.1f}s, "
            f"prompt {res['prompt_id']}")
        return True
    except ComfyError as e:
        out(f"  smoke FAILED after {time.monotonic() - t0:.1f}s: {e}")
        return False


def cmd_doctor(url: Optional[str], do_smoke: bool, timeout_s: float = 900, out=print) -> int:
    client = ComfyClient((url or resolve_url()).rstrip("/"), timeout=15)
    lines, ok = doctor_lines(client)
    for line in lines:
        out(line)
    if do_smoke and ok:
        ok = smoke(client, timeout_s, out) and ok
    elif not do_smoke and ok:
        out("  (add --smoke to render a 64x64 test image)")
    return 0 if ok else 1
