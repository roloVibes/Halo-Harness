# Studio: the Local section

Read this when you watch the machines that serve your local models and what they serve: the live resources and traffic, every host with its controls, every model with its fit.

Part of [Halo Studio](STUDIO.md), which lists every part.

## Local: the machines and the models (3.3.5.0)

**Local** is Studio's tenth section, on `Alt+0` (the tenth slot; a pack's own section has no key and is reached by
its rail row or the palette). It holds everything Halo knows about local models in one tab, paged like Settings: a
page rail on the left, one page on the right, a head on each page that says what it holds, which of Local's five ideas
it carries, and its help behind **How this page works**. Nothing opens on its own; the page last open in this browser
comes back (`halo.studio.local.page`). The seven pages, in the rail's order:

| Page | What it holds | Filled in |
|---|---|---|
| Resources | a live strip per host (GPU, VRAM and what holds it, RAM, CPU, temperature) and the traffic view | 3.3.5.0 R1 |
| Hosts | every server Halo knows as a card, with Load, Unload, keep-alive, Make it fit and Add to hosts | 3.3.5.0 R1 |
| Models | every installed model per host with its card, its fit meter, its roles and the intent filter | 3.3.5.0 R1 |
| Library | Ollama's library and the Hugging Face Hub to browse, each row with a fit badge | 3.3.5.0 R2 |
| Hugging Face | Hugging Face local models downloaded, served, stopped and deleted | 3.3.5.0 R4 |
| Benchmarks | a measured battery per model (the speed card), tuning scans, changes that revert | 3.3.5.0 R5 |
| Steward | the steward's chat, and several local models scheduled on one card | 3.3.5.0 R6 |

The doors: `halo local` opens Studio on Local (a Studio already running for this home takes it in its open page),
`halo local hosts` on the Hosts page (`?mode=local&page=hosts`), `halo studio --edit local:models` the same from the
studio command, `halo studio --mode local`, `/studio local` in the TUI, and the palette's **Local: <page>** rows. Fleet's
Ollama panel stays the short form of the same data; each of its model rows has **open in Local**, which opens Models
on that host ([MODELS-ollama-steward.md](MODELS-ollama-steward.md)).

![Local -> Resources: a live strip per host, the traffic view under it](media/studio-local.png)

## Resources

**The strips.** One per host this machine serves (the `ollama.hosts` entries whose address is this machine; "this
machine" when none is), sampled **once a second** while the page is open, and while the Ollama steward's job runs (it
starts with Studio and the fleet hub). The page holds the sampler on with a 45-second lease it renews every 15 seconds
(`POST local/resources/watch {on}`), so a closed tab lets it stop. Each strip shows:

- **VRAM** used of total as a bar, and **what holds most of it**: the model `/api/ps` has loaded (read every five
  seconds), or the process `nvidia-smi --query-compute-apps` names when the driver gives per-process bytes. Under
  Windows' WDDM driver every process reads `[N/A]`, so the holder there is always a model from `/api/ps`.
- **GPU use** as a number and a line of the last minute.
- **RAM** used of total, **CPU** (the whole machine, between two reads) and the **temperature** when the tool reports one.
- **not Ollama**: the bytes on the card that Ollama's own models do not account for (another program, the desktop).

Every number's title says where it came from, or why there is none. The readers, per OS:

| Figure | Linux | Windows | macOS |
|---|---|---|---|
| GPU use, VRAM, temperature | `nvidia-smi --query-gpu=utilization.gpu,memory.used,memory.total,temperature.gpu`, else `rocm-smi --json` | the same | `ioreg -r -d 1 -w 0 -c IOAccelerator` (the GPU's memory in use; its utilization when the registry gives it) over `sysctl -n hw.memsize` (unified memory) |
| GPU use when not reported | -- | -- | `powermetrics` when it runs without sudo, else **n/a** |
| Who holds the card | `nvidia-smi --query-compute-apps`, else `/api/ps` | `/api/ps` (WDDM gives no bytes per process) | `/api/ps` |
| RAM | `/proc/meminfo` (MemTotal minus MemAvailable) | `GlobalMemoryStatusEx` | `memory_pressure`'s free share of `hw.memsize` |
| CPU | `/proc/stat` | `GetSystemTimes` | `ps -A -o %cpu` over the core count |
| Temperature | nvidia-smi, rocm-smi | nvidia-smi | not read (it needs sudo) |

Nothing here needs sudo, and the readers are the standard library and those tools only. A host another machine serves
has a strip here when that machine is a fleet member and its own sampler runs: the member's newest samples ride its
ledger push to the hub (`fleet.ollama.share`), and the hub keeps the last five minutes per host, under its own name for
the host when one of its `ollama.hosts` entries points at the member's address. The strip then says **via <member>**.

The fit planner reads the newest sample too: when a sample is newer than a host's hardware card, its **not Ollama**
bytes are what the planner counts as held by other programs, so a ComfyUI that starts now shrinks the budget at once.

**The traffic view.** Under the strips, the Live display's cousin: every call to a local server as it happens, newest at
the foot. One row per call (the ledger's line, [MODELS-ollama-steward.md](MODELS-ollama-steward.md)): the time, the host,
the model, the machine that called (the ledger's `from`), the kind (turn, compaction, small, repair, calibrate), the
prompt tokens in and the reply tokens out, the window sent (its source as the title), trimmed / cut / the status, the
reply's tok/s, the request and reply bytes, and the `fitted` and `from <model>` marks of a switch. The steward's server
events (loaded, unloaded, reloaded, spilled, trimmed) sit between them as muted rows. Above the list a sparkline per
host counts the calls per minute of the last 15 minutes, a trim or a cut marked on its minute, with the bytes in and out
of the newest minute. Filters narrow it by host, model, machine and kind; **Follow** keeps the newest row in view, and
scrolling up pauses it (a pill counts what came since).

A row arrives the moment its call ends: the ledger writer publishes each line (`ollama_steward/ledger_tap.py`). In
Studio's own process (and on a hub, the lines its members forward) that is a `traffic` frame at once; a session in
another process posts the line to the Studio running for its home (`POST /api/local/traffic`). A page that opens later
reads the last 15 minutes (`GET local/traffic?since=15m`); a row is never shown twice (its id is the line's own text
hashed).

## Hosts

Every host Halo knows, as a card, grouped: the configured `ollama.hosts` entries, the Hugging Face local servers
(`huggingface.local_servers`), the hosts fleet members serve (their samples reached this hub), and the servers Setup's
Find or Scan found that are not added yet. A card shows the URL, the kind (Ollama, an OpenAI-dialect gateway, a local
server), the server's version, who serves it, what is loaded now (each model's VRAM share and when it unloads), the
hardware card's lines, the steward profiles for it, **who calls it** (the ledger's `from` over the last 24 hours), and the
steward's newest open finding.

The controls its kind allows:

- **Load** warms an installed model the way Ollama documents it, a `POST /api/generate` with no prompt, at the steward
  profile's window (else the host's `max_ctx`, else the server's default) and kept for the **keep-alive** you pick (the
  profile's by default). Nothing is generated.
- **Unload** sends `keep_alive: 0`.
- **Make it fit** (idea 4): when the models the halos ask for do not fit the card together, the fit planner's chosen
  option (a window per model, one model at a time, another host) is applied as steward profiles through the steward's
  own guards (`ollama/steward/apply`), and **Undo** beside it takes them back. A server-side option is never applied:
  Fleet's Ollama panel shows its exact line to copy.
- **Add to hosts** on a found server writes the `ollama.hosts` entry through Setup's own Ollama writer.

A host this machine serves is controlled from here. A host another machine serves is controlled **through the fleet
member that serves it** when this Studio runs the hub: the command (`ollama_load`, `ollama_unload`) goes to that member's
live session and runs under its `fleet.allow_control`, like a steer (`ask` puts a card in its owner's TUI, `all` applies
it, `none` refuses). When that cannot happen the buttons are off and the card says why: the member's control is `none`,
it has no live session, this Studio is not its hub, or no member serves the host. Nothing here writes a server's
settings.

## Models

Every model each host has installed (Ollama's `/api/tags` with `/api/show`; a local server's `/v1/models`), one row each:
the card's chips (think, tools, vision, the purpose, the window: [MODELS-cards.md](MODELS-cards.md)), the **fit meter** on
that host's card (idea 1), its size, whether it is loaded, the steward profile's window and reserve, the roles it can
hold (a role it cannot hold says why as its title) and, unfolded on click, **how Halo calls it**. **Use as default** saves
it as the model a session starts on (Setup's save, `setup/config`); **Make it the coder lane** appears on a model that
cannot orchestrate here but can code, and writes the `local-coder` lineup with the best local orchestrator as main
(`models/lane`, the same offer `/model` makes).

**Intents, not model names** (idea 3): the filter on top ranks the rows for what you want a model for -- **code** (coding
models first, then instruct models that call tools), **chat** (instruct, then reasoning, then coders), **read long
documents** (the largest window this card runs), **look at images** (models that see) and **embed** (embedding models
only) -- each band ordered by the fit meter, a model that is not for the intent left out, and one line under the filter
saying why this order.

The page reads each host's catalog through one cache keyed by the catalog's mtime: `/api/tags` alone is read (at most
every 15 seconds), and the per-model `/api/show` calls run again only when a model was pulled, deleted or changed. Fleet's
Ollama panel reads its catalogs the same way since this round (it used to read every host's whole catalog each minute).

## The pages still to come

Library, Hugging Face, Benchmarks and Steward are framed: each says in one paragraph what it will hold and lists the
commands that do that work today, each copyable (`halo models`, `halo models show <ref>`, `halo local --terminal`,
`halo local import`, `halo ollama calibrate`, `halo ollama steward status`, ...). Steward also shows the steward job's
status line and its last note, read the way Fleet's Ollama panel reads them.

## Local's five ideas

Every page names which of them it carries (its head's "ideas here" line), and the section's help lists all five:

1. **The fit meter**: a small green-to-red bar wherever a model is named -- will this run here at this window
   (Hosts, Models; the Library and Hugging Face rows next).
2. **Why on every number**: each figure carries its source and a one-line cause as its title (every strip number, every
   traffic figure, the profiles).
3. **Intents, not model names**: code, chat, long documents, images, embed rank the models by fit for this card (Models;
   the Library next).
4. **Make it fit**: the fit planner's chosen option in one click, Undo beside it (Hosts).
5. **The hub as the one picture of the network**: every machine sees the same hosts, profiles, traffic and samples
   through the fleet hub (a member's samples and lines reach the hub; Hosts lists the hosts members serve).

## The routes

Studio's API under `/api/local/` (`halo_harness/studio/local_api.py`), the same loopback / origin / token guard as every
Studio route; never a model call:

| Route | What it answers |
|---|---|
| `GET local/hosts` | every host as a card (`studio/local_hosts_view.py`) |
| `POST local/host/<name>/load {model, num_ctx?, keep_alive?}` | a load from here or through the member; 409 with the reason when neither can |
| `POST local/host/<name>/unload {model}` | the same with `keep_alive: 0` |
| `POST local/host/add {url, name}` | the entry written through Setup's Ollama writer |
| `GET local/resources?host=` | the last five minutes of samples and the sampler's state |
| `POST local/resources/watch {on}` | the page's lease on the sampler |
| `GET local/traffic?host=&since=15m` | the ledger's rows, the server events, the per-host minute buckets |
| `POST local/traffic {lines, events}` | another process's ledger tap: `traffic` frames on the live feed |
| `GET local/models?host=` | every model per host with its card, its meter and its intent scores |

Live frames: `resources` (one sample) and `traffic` (`{rows}`), beside the steward's own `steward` frames. From a terminal,
`halo local hosts`, `halo local models [--host H]` and `halo local resources` print what the three built pages show
([COMMANDS-local.md](COMMANDS-local.md)).
