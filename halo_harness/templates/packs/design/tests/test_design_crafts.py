"""The design pack's tests/test_design_crafts.py (was tests/test_design_crafts.py in Halo's core) -- the craft apps
as design engines (Halo 3.0.1.0 round D4): discovery from a claude.json-shaped dict (user and project scope,
case-insensitive, only the craft apps) through `ext.host.mcp_servers`, a live probe through `ext.host.mcp_probe` over
tests/fake_craft.py registered under a craft name (connected, tools counted, the render tool reported missing because
the fake does not have it), a dead command reported as failed, the probe lines, and the pack's `GET crafts` route with
and without `probe` (`halo design doctor [--probe]` before the pack). Scoped home.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

from tests.run import PACK, Ctx, main, mod, new_registry, scratch  # noqa: E402

scratch()

test, TESTS = new_registry()
FAKE = {"type": "stdio", "command": sys.executable, "args": [str(PACK / "tests" / "fake_craft.py")], "env": {}}


@test
def test_discovery_from_the_session_config(ctx: Ctx):
    _m = mod("server/crafts_probe.py")
    cj = {"mcpServers": {"VectorCraft": dict(FAKE), "filesystem": dict(FAKE)},
          "projects": {str(PACK): {"mcpServers": {"pdfcraft": dict(FAKE)}}}}
    ents = _m.craft_server_entries(cj, PACK)
    ctx.check(f"user and project craft servers are found, lower-cased, nothing else, got {sorted(ents)}",
              set(ents) == {"vectorcraft", "pdfcraft"})
    ctx.check("registered_craft_servers is the same set", _m.registered_craft_servers(cj, PACK) == {"vectorcraft", "pdfcraft"})
    ctx.check("an empty config is an empty set, never an error", _m.registered_craft_servers({}, PACK) == set())
    cfgs = _m.craft_server_configs(cj, PACK)
    ctx.check("configs are the entries a probe starts", set(cfgs) == {"vectorcraft", "pdfcraft"} and cfgs["vectorcraft"]["command"] == sys.executable)
    via_crafts = mod("server/crafts.py").registered_craft_servers
    ctx.check("crafts.registered_craft_servers delegates", via_crafts(cj, PACK) == {"vectorcraft", "pdfcraft"})


@test
def test_probe_live_and_dead(ctx: Ctx):
    _m = mod("server/crafts_probe.py")
    cj = {"mcpServers": {"vectorcraft": dict(FAKE),
                         "pdfcraft": {"type": "stdio", "command": "halo-no-such-binary-xyz", "args": [], "env": {}}}}
    env = dict(os.environ, FAKE_CRAFT_TOOLS="9")
    rows = _m.probe_crafts(_m.craft_server_configs(cj, PACK), tool_env=env, cwd=PACK)
    by = {r["app"]: r for r in rows}
    ctx.check(f"the fake server under a craft name connects and its tools are counted, got {by.get('vectorcraft')}",
              by["vectorcraft"]["state"] == "connected" and by["vectorcraft"]["tool_count"] == 9)
    ctx.check("the render tool is reported missing on the fake", by["vectorcraft"]["render_tool"] == "export" and by["vectorcraft"]["render_present"] is False)
    ctx.check("a dead command is failed with a reason", by["pdfcraft"]["state"] != "connected" and by["pdfcraft"]["error"])
    lines = _m.probe_lines(rows)
    ctx.check("the probe lines say up/MISSING and the failure", any("up, " in l and "MISSING" in l for l in lines)
              and any("pdfcraft" in l and "up," not in l for l in lines))


@test
def test_the_crafts_route(ctx: Ctx):
    routes, crafts_probe = mod("server/routes.py"), mod("server/crafts_probe.py")
    cj = {"mcpServers": {"vectorcraft": dict(FAKE)}}
    orig = crafts_probe.craft_server_configs
    crafts_probe.craft_server_configs = lambda claude_json=None, cwd=None: orig(cj, PACK)
    try:
        status, body = routes.crafts({})
        reg = [a["app"] for a in body["apps"] if a["registered"]]
        ctx.check(f"GET crafts lists the eight with registration, got {body.get('line')!r}",
                  status == 200 and len(body["apps"]) == 8 and reg == ["vectorcraft"] and "1 of 8 craft apps registered" in body["line"])
        status, body = routes.crafts({"probe": "1"})
        ctx.check(f"GET crafts?probe=1 starts each one and says MISSING for the fake's render tool, got {body.get('probe_lines')}",
                  status == 200 and body["probe"][0]["state"] == "connected" and any("MISSING" in l for l in body["probe_lines"]))
    finally:
        crafts_probe.craft_server_configs = orig


@test
def test_comfyui_is_the_eighth_craft_app(ctx: Ctx):
    """(Halo 3.0.4.0 R1, tests/test_media_comfy_cli.py's crafts check before the pack.)"""
    crafts = mod("server/crafts.py")
    ctx.check("comfyui is the eighth craft app", list(crafts.APPS)[-1] == "comfyui" and len(crafts.APPS) == 8)
    spec = crafts.APPS["comfyui"]
    ctx.check("its spec: kinds, render tool, ext", spec["kinds"] == ("image", "video") and spec["render"] == "mcp__comfyui__comfy_run" and spec["ext"] == "png")
    ctx.check("the recipe ends in comfy_fetch into the artboard and source.json",
              "comfy_fetch" in spec["recipe"] and "artboards/<id>/render.mp4" in spec["recipe"] and "source.json" in spec["recipe"])
    guide = "\n".join(crafts.guide_lines({"comfyui"}))
    ctx.check("the Design skill names it", "- comfyui:" in guide and "render.mp4" in guide)


if __name__ == "__main__":
    sys.exit(main(TESTS))
