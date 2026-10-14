"""tests.test_media_comfy_cli -- ComfyUI as a craft app (Halo 3.0.4.0 round
R1), the surfaces: the MCP stdio server spawned through McpManager (the
seven tools, comfy_run + comfy_fetch against tests/helpers/fake_comfy.py,
errors as is_error results on a live server), `halo media init` writing
only `mcpServers.comfyui` in a scoped ~/.claude.json and `comfy.url` in the
scoped config (starters saved, one question for clashes), `doctor` lines
with and without --smoke, `inspect`/`models`/`workflows`, and the Design
craft entry: crafts_probe sees `comfyui` and probes its render tool.
"""

from __future__ import annotations

import contextlib
import io
import json
import os
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from tests.helpers.provider_env_defaults import ensure_scoped_state_dir_once

ensure_scoped_state_dir_once()

from tests.helpers.fake_comfy import FakeComfy  # noqa: E402
from tests.helpers.fake_mcp_server import running_manager  # noqa: E402
from tests.helpers.runner import Ctx, new_registry, print_results, run_all  # noqa: E402

REPO_DIR = Path(__file__).resolve().parent.parent
test, TESTS = new_registry()
TOOLS = {"comfy_models", "comfy_workflows", "comfy_object_info", "comfy_inspect", "comfy_run", "comfy_status", "comfy_fetch"}


@contextlib.contextmanager
def scoped_home():
    """A fresh BRIDGE_TEST_HOME (so ~/.claude.json and ~/.halo are scratch),
    CLAUDE_CONFIG_DIR and COMFY_URL cleared, all restored afterwards."""
    keys = ("BRIDGE_TEST_HOME", "CLAUDE_CONFIG_DIR", "COMFY_URL", "BRIDGE_STATE_DIR")
    saved = {k: os.environ.get(k) for k in keys}
    home = Path(tempfile.mkdtemp(prefix="halo-media-home-"))
    os.environ["BRIDGE_TEST_HOME"] = str(home)
    for k in keys[1:]:
        os.environ.pop(k, None)
    try:
        yield home
    finally:
        for k, v in saved.items():
            if v is None:
                os.environ.pop(k, None)
            else:
                os.environ[k] = v


def _run(argv) -> "tuple[int, str]":
    from halo_harness.media.cli import cmd_media
    buf = io.StringIO()
    with contextlib.redirect_stdout(buf), contextlib.redirect_stderr(buf):
        rc = cmd_media(argv)
    return rc, buf.getvalue()


def _server_cfg(url: str, cwd: Path):
    from halo_harness.mcp.manager import McpServerConfig
    pp = os.pathsep.join(p for p in (str(REPO_DIR), os.environ.get("PYTHONPATH", "")) if p)
    return {"comfyui": McpServerConfig(name="comfyui", type="stdio", command=sys.executable,
                                       args=["-m", "halo_harness.media.comfy_server", str(cwd)],
                                       env={"COMFY_URL": url, "PYTHONPATH": pp}, cwd=str(cwd))}


def _text(result) -> str:
    return "".join(getattr(c, "text", "") or "" for c in (result.content or []))


@test
def test_mcp_server_tools_and_run(ctx: Ctx):
    cwd = Path(tempfile.mkdtemp(prefix="halo-comfy-mcp-"))
    with FakeComfy() as fake, running_manager(_server_cfg(fake.url, cwd), tool_env=dict(os.environ), cwd=cwd) as mgr:
        names = {t[1] for t in mgr.all_tools()}
        ctx.check(f"the seven tools are listed, got {sorted(names)}", {f"mcp__comfyui__{t}" for t in TOOLS} <= names)
        res = mgr.call("comfyui", "comfy_run", {"workflow": "text-to-image-qwen", "set": {"prompt": "a kite", "width": 64, "height": 64}})
        ctx.check(f"comfy_run is not an error: {_text(res)[:300]}", not getattr(res, "is_error", False))
        body = json.loads(_text(res))
        ctx.check("comfy_run returns the prompt id and an image output", body["prompt_id"].startswith("fake-") and body["outputs"][0]["kind"] == "image")
        ctx.check("the fake got the overrides", fake.prompts[-1]["graph"]["4"]["inputs"]["prompt"] == "a kite")
        res = mgr.call("comfyui", "comfy_fetch", {"output": body["outputs"][0], "to_path": "artboards/hero/render.png"})
        target = cwd / "artboards" / "hero" / "render.png"
        ctx.check(f"comfy_fetch wrote under the server's cwd: {_text(res)[:200]}", target.is_file() and not getattr(res, "is_error", False))
        ctx.check("it reports path and bytes", json.loads(_text(res))["bytes"] == target.stat().st_size)
        res = mgr.call("comfyui", "comfy_fetch", {"output": body["outputs"][0], "to_path": "../escape.png"})
        ctx.check(f"a path outside the cwd is an is_error result, got {_text(res)[:200]}", getattr(res, "is_error", False) and "outside" in _text(res))
        res = mgr.call("comfyui", "comfy_run", {"workflow": "nothing-by-this-name"})
        ctx.check("an unknown workflow is an is_error result naming the choices", getattr(res, "is_error", False) and "text-to-image-qwen" in _text(res))
        res = mgr.call("comfyui", "comfy_inspect", {"workflow": "Fixture UI workflow"})
        rows = json.loads(_text(res))["nodes"]
        ctx.check("comfy_inspect converts a saved UI workflow", any(r["node"] == "17:1" for r in rows))
        res = mgr.call("comfyui", "comfy_status", {"prompt_id": body["prompt_id"]})
        ctx.check("comfy_status says done", json.loads(_text(res))["state"] == "done")
        res = json.loads(_text(mgr.call("comfyui", "comfy_models", {})))
        ctx.check(f"comfy_models rows are {{folder, count}}, got {res[:2]}", {"folder": "loras", "count": 6} in res)
        res = json.loads(_text(mgr.call("comfyui", "comfy_models", {"folder": "vae"})))
        ctx.check("comfy_models(folder) is {folder, count, files}", res["folder"] == "vae" and res["count"] == len(res["files"]) == 4)
        res = json.loads(_text(mgr.call("comfyui", "comfy_object_info", {"node": "sampler"})))
        ctx.check(f"comfy_object_info searches by substring, got {res}", "KSampler" in res.get("matches", {}))
        ctx.check("the server is still connected after errors", next(s for s in mgr.status() if s["name"] == "comfyui")["state"] == "connected")


@test
def test_media_init_writes_only_the_comfyui_entry(ctx: Ctx):
    from halo_harness.media.setup_cli import install_workflows
    from halo_harness.media.comfy_client import ComfyClient
    with scoped_home() as home, FakeComfy() as fake:
        cj = home / ".claude.json"
        before = {"numStartups": 3, "mcpServers": {"other": {"type": "stdio", "command": "x", "args": []}},
                  "projects": {"/p": {"mcpServers": {"proj": {"command": "y"}}}}}
        cj.write_text(json.dumps(before, indent=2) + "\n", encoding="utf-8")
        rc, out = _run(["init", "--url", fake.url + "/", "--install-workflows", "--yes"])
        ctx.check(f"init exits 0, got {rc}: {out}", rc == 0 and "registered mcpServers.comfyui" in out)
        after = json.loads(cj.read_text(encoding="utf-8"))
        entry = after["mcpServers"].get("comfyui")
        ctx.check(f"the entry is the stdio server with COMFY_URL, got {entry}",
                  entry == {"type": "stdio", "command": sys.executable, "args": ["-m", "halo_harness.media.comfy_server"], "env": {"COMFY_URL": fake.url}})
        del after["mcpServers"]["comfyui"]
        ctx.check("nothing else in ~/.claude.json changed", after == before)
        conf = json.loads((home / ".halo" / "config.json").read_text(encoding="utf-8"))
        ctx.check(f"comfy.url is in the scoped config, got {conf}", conf.get("comfy", {}).get("url") == fake.url)
        ctx.check("the starters were saved into ComfyUI", {"text-to-image-qwen.json", "image-to-video-wan22.json"} <= set(fake.workflows))
        asked = []
        lines = install_workflows(ComfyClient(fake.url), ask=lambda q: asked.append(q) or False)
        ctx.check(f"a clash asks once for every starter and keeps them on no, got {asked} {lines}",
                  len(asked) == 1 and "2 starter" in asked[0] and all("kept" in l for l in lines))


@test
def test_doctor_lines_and_smoke(ctx: Ctx):
    with scoped_home(), FakeComfy() as fake:
        rc, out = _run(["doctor", "--url", fake.url])
        ctx.check(f"doctor reports the server, got {out}", rc == 0 and "reachable" in out and "ComfyUI 0.37.0" in out and "Fake GPU" in out)
        ctx.check("model folder counts", "diffusion_models 8" in out and "loras 6" in out and "(2 empty)" in out)
        ctx.check("saved workflows", "saved workflows (2): Fixture UI workflow, Second saved" in out)
        ctx.check("each starter is checked against the server", "starter text-to-image-qwen: ready" in out and "starter image-to-video-wan22: ready" in out)
        ctx.check("an unregistered server says how to register", "not registered: run `halo media init`" in out and "--smoke" in out)
        _run(["init", "--url", fake.url])
        rc, out = _run(["doctor", "--url", fake.url, "--smoke"])
        ctx.check(f"after init the entry is shown, got {out}", "registered: mcpServers.comfyui" in out and f"COMFY_URL={fake.url}" in out)
        ctx.check("the smoke render reports its output and time", rc == 0 and "smoke ok: halo/text-to-image_00001_.png" in out and "PNG" in out)
        sent = fake.prompts[-1]["graph"]
        ctx.check("the smoke render is 64x64", sent["5"]["inputs"]["width"] == 64 and sent["5"]["inputs"]["height"] == 64)
    with scoped_home():
        rc, out = _run(["doctor", "--url", "http://127.0.0.1:9"])
        ctx.check(f"a dead server fails with a reason, got {out}", rc == 1 and "not reachable" in out)


@test
def test_inspect_models_workflows(ctx: Ctx):
    with scoped_home(), FakeComfy() as fake:
        rc, out = _run(["inspect", "text-to-image-qwen", "--url", fake.url])
        ctx.check(f"inspect prints nodes, inputs and set keys, got {out[:400]}", rc == 0 and "TextEncodeQwenImage21" in out and "set keys: prompt -> prompt" in out)
        rc, out = _run(["inspect", "Fixture UI workflow", "--json", "--url", fake.url])
        ctx.check("inspect --json converts a saved UI workflow", rc == 0 and json.loads(out)["nodes"])
        rc, out = _run(["models", "video", "--url", fake.url])
        ctx.check(f"models video lists the video folders, got {out[:200]}", rc == 0 and "diffusion_models (8)" in out and "TTS" not in out)
        rc, out = _run(["models", "audio", "--url", fake.url])
        ctx.check("models audio lists TTS and audio encoders", "TTS (" in out and "audio_encoders (2)" in out and "loras" not in out)
        rc, out = _run(["workflows", "--url", fake.url])
        ctx.check("workflows lists saved and starters", "Fixture UI workflow" in out and "text-to-image-qwen" in out)
        rc, out = _run(["inspect", "nothing-here", "--url", fake.url])
        ctx.check(f"an unknown workflow exits 1 with the names, got {out}", rc == 1 and "starters:" in out)


@test
def test_crafts_probe_sees_comfyui(ctx: Ctx):
    from halo_harness.design import crafts
    from halo_harness.design.crafts_probe import craft_server_configs, craft_server_entries, probe_crafts
    from halo_harness.media.setup_cli import server_entry
    ctx.check("comfyui is the eighth craft app", list(crafts.APPS)[-1] == "comfyui" and len(crafts.APPS) == 8)
    spec = crafts.APPS["comfyui"]
    ctx.check("its spec: kinds, render tool, ext", spec["kinds"] == ("image", "video") and spec["render"] == "mcp__comfyui__comfy_run" and spec["ext"] == "png")
    ctx.check("the recipe ends in comfy_fetch into the artboard and source.json",
              "comfy_fetch" in spec["recipe"] and "artboards/<id>/render.mp4" in spec["recipe"] and "source.json" in spec["recipe"])
    guide = "\n".join(crafts.guide_lines({"comfyui"}))
    ctx.check("the Design skill names it", "- comfyui:" in guide and "render.mp4" in guide)
    with FakeComfy() as fake:
        entry = server_entry(fake.url)
        entry["env"]["PYTHONPATH"] = os.pathsep.join(p for p in (str(REPO_DIR), os.environ.get("PYTHONPATH", "")) if p)
        cj = {"mcpServers": {"ComfyUI": entry}}
        ctx.check("the entry is found case-insensitively", set(craft_server_entries(cj, REPO_DIR)) == {"comfyui"})
        rows = probe_crafts(craft_server_configs(cj, REPO_DIR), tool_env=dict(os.environ), cwd=REPO_DIR)
        ctx.check(f"the probe connects and finds the render tool, got {rows}",
                  rows and rows[0]["state"] == "connected" and rows[0]["tool_count"] == 7 and rows[0]["render_present"] is True)


if __name__ == "__main__":
    ctx = Ctx()
    results, passed, failed, skipped = run_all(TESTS, ctx)
    sys.exit(print_results(results, passed, failed, skipped, label="media comfy cli tests"))
