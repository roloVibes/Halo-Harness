"""tests.test_media_comfy -- ComfyUI as a craft app (Halo 3.0.4.0 round R1),
the library half: the HTTP client against tests/helpers/fake_comfy.py, the
UI-to-API conversion on a fixture (links, widget order from object_info, a
seed's control slot, a converted widget, a muted node, a note, a subgraph),
`set` by id, title and starter key, `only` pruning, the starters checked
against the object_info fixture, and run + wait + fetch writing under the
working directory (and nowhere else). The CLI, the MCP server and the
craft entry are in test_media_comfy_cli.py. ComfyUI is always the fake.
"""

from __future__ import annotations

import os
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from tests.helpers.provider_env_defaults import ensure_scoped_state_dir_once

ensure_scoped_state_dir_once()

from tests.helpers.fake_comfy import UI_NAME, FakeComfy, fixture  # noqa: E402
from tests.helpers.runner import Ctx, new_registry, print_results, run_all  # noqa: E402

test, TESTS = new_registry()


def _raises(fn, exc_type):
    try:
        fn()
    except exc_type as e:
        return e
    return None


@test
def test_client_round_trips(ctx: Ctx):
    from halo_harness.media.comfy_client import ComfyClient, ComfyError
    with FakeComfy() as fake:
        c = ComfyClient(fake.url, timeout=10)
        ctx.check("system_stats carries the version", c.system_stats()["system"]["comfyui_version"] == "0.37.0")
        ctx.check("model folders listed", "diffusion_models" in c.model_folders() and "TTS" in c.model_folders())
        ctx.check("a folder's files come back as the server lists them", c.models("loras") == fixture("models.json")["loras"])
        ctx.check("object_info() is every class", "KSampler" in c.object_info())
        ctx.check("object_info(node) is that class", list(c.object_info("SaveImage")) == ["SaveImage"])
        ctx.check("saved workflows are listed with .json", UI_NAME in c.workflows())
        ctx.check("a saved workflow is read by name, .json optional", "nodes" in c.workflow(UI_NAME[:-5]))
        e = _raises(lambda: c.models("no_such_folder"), ComfyError)
        ctx.check(f"an HTTP error is a ComfyError with its status, got {e!r}", e is not None and e.status == 404)
        e = _raises(lambda: c.workflow("missing"), ComfyError)
        ctx.check("a missing workflow is a 404", e is not None and e.status == 404)
        enc = [p for m, p in fake.requests if m == "GET" and p.startswith("/userdata/workflows")]
        ctx.check(f"the userdata path encodes its slash (one route segment), got {enc}", all(p.startswith("/userdata/workflows%2F") for p in enc))
    e = _raises(lambda: ComfyClient("http://127.0.0.1:9", timeout=2).system_stats(), ComfyError)
    ctx.check(f"an unreachable server is status 0 and says so, got {e!r}", e is not None and e.status == 0 and "not reachable" in str(e))


@test
def test_resolve_url_precedence(ctx: Ctx):
    from halo_harness.media.comfy_client import DEFAULT_URL, resolve_url
    from halo_harness.theme import set_config_value
    old_home, old_url = os.environ.get("BRIDGE_TEST_HOME"), os.environ.pop("COMFY_URL", None)
    os.environ["BRIDGE_TEST_HOME"] = tempfile.mkdtemp(prefix="halo-comfy-url-")
    try:
        ctx.check("nothing set is the local default", resolve_url() == DEFAULT_URL)
        set_config_value("comfy.url", "http://comfy-host.example:8188/")
        ctx.check("config comfy.url is used (trailing slash dropped)", resolve_url() == "http://comfy-host.example:8188")
        ctx.check("COMFY_URL wins over the config", resolve_url({"COMFY_URL": "http://other.example:9000"}) == "http://other.example:9000")
    finally:
        os.environ["BRIDGE_TEST_HOME"] = old_home or os.environ["BRIDGE_TEST_HOME"]
        if old_url is not None:
            os.environ["COMFY_URL"] = old_url


@test
def test_ui_to_api_conversion(ctx: Ctx):
    from halo_harness.media.comfy_graph import ComfyGraphError, is_api_format, to_api
    info = fixture("object_info.json")
    ui = fixture("ui_workflow.json")
    ctx.check("a UI graph is not API format", not is_api_format(ui))
    api = to_api(ui, info)
    ctx.check("the result is API format", is_api_format(api))
    ctx.check(f"notes and the muted LoadImage are left out, got {sorted(api)}", "19" not in api and "20" not in api)
    ks = api["16"]["inputs"]
    ctx.check(f"widgets map in object_info order, the seed's control slot skipped, got {ks}",
              ks["seed"] == 42 and ks["cfg"] == 7.5 and ks["sampler_name"] == "euler" and ks["scheduler"] == "simple" and ks["denoise"] == 1.0)
    ctx.check("a widget converted to an input takes the link", ks["steps"] == ["21", 0])
    ctx.check("links are [source id, slot]", ks["model"] == ["10", 0] and ks["negative"] == ["14", 0] and ks["latent_image"] == ["15", 0])
    ctx.check("EmptyLatentImage widgets", api["15"]["inputs"] == {"width": 512, "height": 768, "batch_size": 1})
    ctx.check("a primitive's control slot is skipped", api["21"]["inputs"] == {"value": 30})
    ctx.check("the subgraph is flattened to <outer>:<inner> with outer links resolved",
              api["17:1"]["class_type"] == "VAEDecode" and api["17:1"]["inputs"] == {"samples": ["16", 0], "vae": ["12", 0]})
    ctx.check("a link to the subgraph's output resolves inside it", api["18"]["inputs"]["images"] == ["17:1", 0])
    ctx.check("titles are carried in _meta (set title, else the display name)",
              api["13"]["_meta"]["title"] == "Positive" and api["17:1"]["_meta"]["title"] == "Inner decode" and api["15"]["_meta"]["title"])
    bad = dict(ui, nodes=ui["nodes"] + [{"id": 30, "type": "NoSuchNode", "mode": 0, "widgets_values": [1]}])
    e = _raises(lambda: to_api(bad, info), ComfyGraphError)
    ctx.check(f"an unknown class names the node and the class, got {e}", e is not None and "node 30" in str(e) and "NoSuchNode" in str(e))


@test
def test_apply_set_by_id_title_and_key(ctx: Ctx):
    from halo_harness.media import comfy_ops
    from halo_harness.media.comfy_graph import ComfyGraphError, apply_set, to_api
    api = to_api(fixture("ui_workflow.json"), fixture("object_info.json"))
    out = apply_set(api, {"13.text": "a dog", "Negative.text": "noisy", "15.width": "640", "17:1.samples": ["16", 0]})
    ctx.check("by node id", out["13"]["inputs"]["text"] == "a dog")
    ctx.check("by node title", out["14"]["inputs"]["text"] == "noisy")
    ctx.check("a string number for an int input becomes an int", out["15"]["inputs"]["width"] == 640)
    ctx.check("subgraph ids with a colon work", out["17:1"]["inputs"]["samples"] == ["16", 0])
    ctx.check("the input graph is not modified", api["13"]["inputs"]["text"] == "a cat in a hat")
    e = _raises(lambda: apply_set(api, {"text": "x"}), ComfyGraphError)
    ctx.check(f"an ambiguous bare input names the candidates, got {e}", e is not None and "13" in str(e) and "14" in str(e))
    e = _raises(lambda: apply_set(api, {"Nope.text": 1}), ComfyGraphError)
    ctx.check(f"no match lists node ids and titles, got {e}", e is not None and "Positive" in str(e) and "Node ids" in str(e))
    starter = comfy_ops.load_starter("text-to-image-qwen")
    s = apply_set(starter, {"prompt": "p", "negative": "n", "width": 64, "height": 96, "steps": 4, "seed": "random"})
    ctx.check("starter keys reach their inputs", s["4"]["inputs"]["prompt"] == "p" and s["4"]["inputs"]["negative_prompt"] == "n"
              and s["5"]["inputs"]["width"] == 64 and s["5"]["inputs"]["height"] == 96 and s["6"]["inputs"]["steps"] == 4)
    ctx.check("seed 'random' becomes a fresh int", isinstance(s["6"]["inputs"]["seed"], int) and s["6"]["inputs"]["seed"] != starter["6"]["inputs"]["seed"])
    v = apply_set(comfy_ops.load_starter("image-to-video-wan22"), {"steps": 6, "seed": 7, "length": 33})
    ctx.check("a key several nodes declare sets all of them", v["13"]["inputs"]["steps"] == 6 and v["14"]["inputs"]["steps"] == 6
              and v["13"]["inputs"]["noise_seed"] == 7 and v["6"]["inputs"]["length"] == 33)


@test
def test_only_pruning(ctx: Ctx):
    from halo_harness.media.comfy_graph import ComfyGraphError, dangling_links, only
    g = {"1": {"class_type": "A", "inputs": {}}, "2": {"class_type": "B", "inputs": {"x": ["1", 0]}, "_meta": {"title": "Keep me"}},
         "3": {"class_type": "C", "inputs": {}}, "4": {"class_type": "D", "inputs": {"y": ["3", 0], "z": ["1", 0]}}}
    ctx.check("only an id keeps it and what feeds it", sorted(only(g, ["2"])) == ["1", "2"])
    ctx.check("only a title works too", sorted(only(g, ["Keep me"])) == ["1", "2"])
    ctx.check("several outputs keep the union", sorted(only(g, ["2", "4"])) == ["1", "2", "3", "4"])
    ctx.check("nothing dangles after pruning", dangling_links(only(g, ["4"])) == [])
    ctx.check("an unknown id is an error", _raises(lambda: only(g, ["9"]), ComfyGraphError) is not None)


@test
def test_starters_are_valid_api_graphs(ctx: Ctx):
    from halo_harness.media import comfy_ops
    from halo_harness.media.comfy_graph import check_against, describe_inputs, is_api_format
    info = fixture("object_info.json")
    names = comfy_ops.starter_names()
    ctx.check(f"both starters ship, got {names}", names == ["image-to-video-wan22", "text-to-image-qwen"])
    keys = set()
    for n in names:
        g = comfy_ops.load_starter(n)
        ctx.check(f"{n} is API format", is_api_format(g))
        ctx.check(f"{n} matches the server's nodes and model files: {check_against(g, info)}", check_against(g, info) == [])
        for row in describe_inputs(g):
            keys |= set(row.get("keys") or {})
    ctx.check(f"the documented keys are declared, got {sorted(keys)}",
              {"prompt", "negative", "width", "height", "seed", "steps", "image", "length"} <= keys)
    g = comfy_ops.load_starter("text-to-image-qwen")
    g["1"]["inputs"]["unet_name"] = "missing.safetensors"
    ctx.check("a model the server lacks is reported", any("missing.safetensors" in p for p in check_against(g, info)))


@test
def test_run_wait_fetch_under_cwd(ctx: Ctx):
    from halo_harness.media import comfy_ops
    from halo_harness.media.comfy_client import ComfyClient, ComfyError
    cwd = Path(tempfile.mkdtemp(prefix="halo-comfy-cwd-"))
    (cwd / "start.png").write_bytes(b"\x89PNG fake")
    with FakeComfy() as fake:
        c = ComfyClient(fake.url, timeout=10)
        seen = []
        res = comfy_ops.run(c, "text-to-image-qwen", {"prompt": "x", "width": 64, "height": 64}, cwd=cwd, poll_s=0.01,
                            on_progress=seen.append)
        sent = fake.prompts[-1]["graph"]
        ctx.check("the queued graph carries the overrides", sent["5"]["inputs"]["width"] == 64 and sent["4"]["inputs"]["prompt"] == "x")
        ctx.check("the queued graph keeps only titles in _meta", all(set(n.get("_meta", {})) <= {"title"} for n in sent.values()))
        ctx.check(f"progress was reported while waiting, got {seen}", seen and seen[0] in ("running", "pending"))
        out = res["outputs"]
        ctx.check(f"one image output, got {out}", len(out) == 1 and out[0]["kind"] == "image" and out[0]["subfolder"] == "halo")
        got = comfy_ops.fetch(c, out[0], "artboards/a1/render.png", cwd)
        target = cwd / "artboards" / "a1" / "render.png"
        ctx.check("fetch writes the PNG under the cwd", target.is_file() and target.read_bytes()[:4] == b"\x89PNG" and got["bytes"] == target.stat().st_size)
        for bad in ("../outside.png", str(Path(tempfile.gettempdir()) / "halo-outside.png")):
            e = _raises(lambda: comfy_ops.fetch(c, out[0], bad, cwd), ComfyError)
            ctx.check(f"fetch to {bad!r} outside the cwd is an error", e is not None and "outside the working directory" in str(e))
        ctx.check("nothing was written outside", not (cwd.parent / "outside.png").exists())
        vid = comfy_ops.run(c, "image-to-video-wan22", {"image": "start.png", "length": 17}, cwd=cwd, poll_s=0.01)
        ctx.check("a local start image is uploaded first", fake.uploads and fake.uploads[-1]["name"] == "start.png"
                  and fake.prompts[-1]["graph"]["1"]["inputs"]["image"] == "start.png")
        ctx.check(f"a SaveVideo output is kind video, got {vid['outputs']}", [o["kind"] for o in vid["outputs"]] == ["video"])
        ui = comfy_ops.run(c, UI_NAME[:-5], {"Positive.text": "saved"}, only_ids=["18"], cwd=cwd, poll_s=0.01)
        ctx.check("a saved UI workflow runs by name (converted, set by title)", fake.prompts[-1]["graph"]["13"]["inputs"]["text"] == "saved"
                  and ui["outputs"][0]["filename"].startswith("out_"))
        e = _raises(lambda: comfy_ops.run(c, "text-to-image-qwen", {"prompt": "__fail__"}, cwd=cwd, poll_s=0.01), ComfyError)
        ctx.check(f"an execution error names the node, got {e}", e is not None and "node 4" in str(e) and "TextEncodeQwenImage21" in str(e))
        e = _raises(lambda: comfy_ops.run(c, "no such workflow", cwd=cwd), ComfyError)
        ctx.check(f"an unknown workflow lists saved and starter names, got {e}", e is not None and "Fixture UI workflow" in str(e) and "text-to-image-qwen" in str(e))
        bad = {"1": {"class_type": "NoSuchNode", "inputs": {}}}
        e = _raises(lambda: comfy_ops.run(c, bad, cwd=cwd), ComfyError)
        ctx.check(f"a /prompt validation error names the node and class, got {e}", e is not None and e.status == 400 and "node 1 (NoSuchNode)" in str(e))
        st = comfy_ops.status(c, res["prompt_id"])
        ctx.check("status of a finished prompt is done with outputs", st["state"] == "done" and st["outputs"])


if __name__ == "__main__":
    ctx = Ctx()
    results, passed, failed, skipped = run_all(TESTS, ctx)
    sys.exit(print_results(results, passed, failed, skipped, label="media comfy tests"))
