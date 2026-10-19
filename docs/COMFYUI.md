# ComfyUI in Halo

Read this when you want Halo to render images or video with ComfyUI on your own GPU.

[ComfyUI](https://github.com/comfyanonymous/ComfyUI) runs diffusion models on
your own GPU: still images (Qwen Image), image-to-video clips (Wan 2.2),
upscales (SeedVR2), speech (TTS Audio Suite) and anything else a workflow
wires up. Halo treats it as the eighth craft app: one MCP server,
`mcp__comfyui__*`, that every session and every Design turn
can call, and `halo media` to set it up and check it.

The server can be another machine on your network. Halo talks to it only over
HTTP: workflows go up with `POST /prompt`, results come back through
`GET /view`, never from a disk path.

## Set it up

```sh
halo media init --url http://gpu-box:8188 --install-workflows
halo media doctor --smoke
```

`init` registers `mcpServers.comfyui` in `~/.claude.json` (user scope, the
same writer `halo mcp add` uses):

```json
"comfyui": {"type": "stdio", "command": "<the python Halo runs on>",
            "args": ["-m", "halo_harness.media.comfy_server"],
            "env": {"COMFY_URL": "http://gpu-box:8188"}}
```

and stores `comfy.url` in `~/.halo/config.json`. `--install-workflows` saves
the starter workflows (below) into ComfyUI's workflow browser; when one of the
same name is already there it asks once (`--yes` overwrites). The URL is
`--url`, else `COMFY_URL`, else `comfy.url`, else `http://127.0.0.1:8188`.

`doctor` prints the server's version and GPU, the model folders with their
file counts, the saved workflows, whether each starter's nodes and model files
exist on this server, and the registered entry. `--smoke` renders a 64x64
image through the text-to-image starter and prints the output name and how
long it took (the first run includes loading the models).

## The tools

| tool | what it does |
|---|---|
| `comfy_models(folder?)` | without `folder`: `[{folder, count}]` for every model folder; with it: `{folder, count, files}` |
| `comfy_workflows()` | `{saved: [...], starters: [...]}` |
| `comfy_object_info(node?)` | one node class's inputs and outputs, the classes whose name contains `node`, or every class by category |
| `comfy_inspect(workflow)` | the workflow's nodes in API format: id, class, title, literal inputs, and the `set` keys a starter declares |
| `comfy_run(workflow, set={}, only=[], wait=true, timeout_s=1800)` | queue it; with `wait`, block until it finishes and return `{prompt_id, outputs: [{node, filename, subfolder, type, kind}]}` (`kind` is image, video, audio or other) |
| `comfy_status(prompt_id)` | pending, running, done (with outputs) or error (naming the node) |
| `comfy_fetch(output, to_path)` | download one output and write it under the working directory, e.g. `artboards/hero/render.png`; returns the path and byte size |

`workflow` is a workflow saved in ComfyUI (by its name, `.json` optional), a
starter name, a path to a JSON file, or the graph itself. Graphs saved by the
editor are UI format; Halo converts them to API format the way the editor
does on Run (links resolved, widget values mapped in each node class's input
order from `/object_info`, notes dropped, muted nodes left out, bypassed nodes
passed through, subgraphs flattened to `<outer id>:<inner id>`).

Every failure comes back as an error result naming the node or the HTTP
status: a validation error from `/prompt` lists each failing node and its
class, an execution error names the node that raised.

## `set` and `only`

`set` overrides inputs before the run:

- `{"6.text": "..."}` by node id (`"129:93.text"` for a node inside a subgraph);
- `{"Positive.text": "..."}` by node title (every node with that title);
- `{"prompt": "...", "width": 1024}` by a key: one a node declares in
  `_meta.keys` (the starters do), else the one node with a literal input of
  that name.

A seed of `"random"` or `-1` becomes a fresh seed. A `LoadImage` `image` that
names a file on your machine is uploaded to the server first.

`only` keeps the listed output nodes (ids or titles) and everything that feeds
them, so one stage of a big workflow can run alone.

## The starter workflows

Hand-written API-format graphs in `halo_harness/templates/comfy/`, built from
the server's own `/object_info`:

| starter | nodes | keys |
|---|---|---|
| `text-to-image-qwen` | UNETLoader `qwen_image_2.1_int8_convrot`, CLIPLoader `qwen3vl_8b_int8_convrot` (type qwen_image), VAELoader `qwen_image_2.1_vae_bf16`, TextEncodeQwenImage21, EmptyLatentImage, KSampler (cfg 1, 25 steps), VAEDecode, SaveImage `halo/text-to-image` | `prompt`, `negative`, `width`, `height`, `seed`, `steps` |
| `image-to-video-wan22` | LoadImage, umt5 text encoder, Wan 2.1 VAE, WanImageToVideo, Wan 2.2 i2v high and low noise 14B fp8 each with its lightx2v 4-step LoRA (the models keep their own sampling shift of 8, as in ComfyUI's Wan 2.2 template), two KSamplerAdvanced (steps 0-2 and 2-end), VAEDecode, CreateVideo 16 fps, SaveVideo `halo/image-to-video` | `image`, `prompt`, `negative`, `width`, `height`, `length`, `seed`, `steps` |

```text
comfy_run {"workflow": "text-to-image-qwen", "set": {"prompt": "a lighthouse at dusk", "width": 1328, "height": 800, "seed": "random"}}
comfy_run {"workflow": "image-to-video-wan22", "set": {"image": "artboards/hero/render.png", "prompt": "slow push-in, fog drifting", "length": 81}}
```

Qwen Image 2.1 encodes its prompt with `TextEncodeQwenImage21` (the positive
and negative conditioning are its first two outputs), not `CLIPTextEncode`.
`length` is frames at 16 fps (81 is about five seconds). With `steps` above 4
on the video starter, also raise the samplers' `end_at_step`/`start_at_step`
split (`13.end_at_step`, `14.start_at_step`).

## Your own saved workflows

Anything saved in the ComfyUI editor runs by name:

```sh
halo media workflows
halo media inspect "Image to video (smart fit)"
```

`inspect` prints every node's id, class, title and literal inputs, which are
the `set` keys: `comfy_run {"workflow": "Image to video (smart fit)", "set":
{"3001.image": "start.png", "3050:93.text": "the subject turns and smiles"}}`.

## Inventory

Models on the server are listed by what they produce, not by folder:

```sh
halo models --media --refresh
halo models --best-for video-gen
```

`--refresh` reads `GET /models/<folder>` (every folder except `custom_nodes`
and `configs`), the file sizes from `GET /experiment/models/<folder>` and the
node classes from `GET /object_info`, and writes `~/.halo/media-models.json`
(`{"scanned", "url", "rows", "workflows"}`); the other commands read that
cache. A row is `{ref: "comfy:<file>", provider: "comfyui", folder, file,
kind, modalities_in, modalities_out, local, price_in_per_m: 0,
price_out_per_m: 0, size_bytes, quant, family, notes}`.

| kind | what lands there |
|---|---|
| `image-gen` | `diffusion_models` and `checkpoints` files, unless the name says video |
| `video-gen` | the name says `i2v` (image in), `s2v` (audio in), `t2v`, `wan`, `SCAIL`, `ltx` and similar |
| `upscale` | `upscale_models` and SeedVR |
| `tts` | one row per `TTS/<engine>` folder, when the server has a TTS engine node (otherwise `other`) |
| `lora`, `vae`, `encoder`, `other` | supporting rows: listed, never ranked |

`quant` is read from the file name (bf16, fp16, fp8, int8, else `unknown`);
`family` groups the parts of one model (`qwen-image`, `wan`, `seedvr`, `sam`).
The Design model chooser shows the generators as "Media models (ComfyUI)"
(`GET /api/design/models?media=1`), and `halo media models` prints the same
table after a fresh scan. See [MODELS.md](MODELS.md) "Media models".

## In Halo Design

Once registered, ComfyUI is listed by `halo design doctor` and taught to every
design turn. Its recipe: `comfy_workflows` -> `comfy_inspect` -> `comfy_run`
with `set` -> `comfy_fetch` into `artboards/<id>/render.png` (a still) or
`artboards/<id>/render.mp4` (a clip) -> `artboards/<id>/source.json`
`{"app": "comfyui", "workflow": ..., "prompt_id": ..., "set": {...}}`.
`halo design doctor --probe` spawns the server and checks `comfy_run` is there.

## Troubleshooting

- **The server is on another machine.** Start ComfyUI with `--listen 0.0.0.0`
  and open its port (8188) in that machine's firewall. Halo reaches LAN and
  loopback addresses directly, without any `HTTP_PROXY` you have set.
- **GPU contention.** A diffusion model and a large local LLM (Ollama,
  llama-server) share one GPU's memory. Unload the LLM (`ollama stop <model>`)
  before a long video render, or expect the render to fail with out-of-memory
  or crawl. `doctor` shows the free VRAM.
- **The first run is slow.** Loading Qwen Image or the two Wan 2.2 14B models
  takes a minute or more; later runs reuse them unless ComfyUI runs with
  `--disable-smart-memory`.
- **UI vs API format.** The editor's "Save" writes UI format (nodes, links,
  widgets_values); "Export (API)" writes API format (node id -> class_type and
  inputs). Halo takes either. A node class the server does not have is
  reported by node id and class.
- **A saved workflow will not convert.** Nested subgraphs are not supported;
  run `halo media inspect <name>` to see where it stops.
