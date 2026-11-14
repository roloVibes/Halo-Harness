# Studio: Local -> the Media panels

Read this when you check ComfyUI from Studio: whether it answers, its models and its workflows, in the Media panels the palette opens on Local.

Part of [Halo Studio](STUDIO.md), which lists every part.

## Media: the ComfyUI panels

Halo 3.0.4.0 made them Design's optional panels; since 3.3.13.0 R2 (Design left the core for the design pack) they are
**Local**'s, because ComfyUI is local model work: **Media status**, **Media models** and **Workflows** open from the
palette as drawers over Local's page's right edge (3.6.0.0 R0a; the header's **+** before) until you close them. The palette's Media lines
(**Media: status**, **scan**, **models**, **workflows**) open them too, going to Local first from another section.
Rendering a workflow into a design project is the design pack's Render panel
([its README](../halo_harness/templates/packs/design/README.md)).

| Panel | What it shows |
|---|---|
| **Media status** | a dot that ticks green on every check (every 15 s while a Media panel is open), the ComfyUI version, the GPU's VRAM bar, the model count and the cache's age, **Scan** (reads the server's model folders and saved workflows into the cache) |
| **Media models** | tabs image / video / audio / upscale; each row is a file with its family, precision and size (and a note: a 4-step LoRA, the high- or low-noise expert); encoders, LoRAs and VAEs of the same families sit under **supporting files** |
| **Workflows** | Halo's starters and the workflows saved on the server; click one for the inputs a render can set (`*` marks a named input) |

While ComfyUI does not answer, the group is one card instead of three panels: where Studio looked, the error, and the
fix (start ComfyUI, then `halo media init --url <its address>` or `COMFY_URL`, then **Check again**). The models tab is
remembered in your browser (`halo.studio.media.tab`).

## Media routes (3.0.4.0)

The JSON routes behind the Media panels. Every one sits behind the same loopback, Host, Origin and bearer-token guard as
the rest of `/api/`. They ask ComfyUI at `COMFY_URL`, the config's `comfy.url`, or `http://127.0.0.1:8188`
([COMFYUI.md](COMFYUI.md)).

| Route | Answer |
|---|---|
| `GET media/status` | `{url, reachable, version, python, pytorch, gpus, registered, cache: {scanned, age_s, rows, workflows}, checked, age_s, checking}` |
| `GET media/models?kind=image-gen\|video-gen\|audio-gen\|upscale\|all` | `{kind, rows, scanned, url}` from the cached inventory |
| `POST media/scan` | `{rows, workflows, scanned, url}`: reads the server into the cache |
| `GET media/workflows` | `{workflows: [{name, source: starter\|saved}], reachable, url}` (the cache's names when the server is down) |
| `GET media/workflows/<name>/inputs?source=starter\|saved` | `{workflow, source, label, nodes}`: each node's settable inputs |

`media/status` refreshes in the background every 15 s and never holds a request for more than 2 s. A render into a
design project (`POST media/render` before 3.3.13.0) is the design pack's `POST render`, its steps the pack's live
frames of kind `render`.
