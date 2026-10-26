# Local and cloud models

Read this when you set up Ollama, Hugging Face or the OpenAI API end to end.

Halo 2.0.3 adds three new ways to point Halo at a model: Ollama (on this
machine, on another machine on your network, or Ollama's own hosted
cloud), Hugging Face (its router, a dedicated endpoint, or a server you
run yourself), and the real OpenAI API.
This page is the walkthrough: what each route can do and the exact
commands to use it, in plain sentences. [docs/MODELS.md](MODELS.md) is
the exhaustive reference this page simplifies; [docs/CONFIG.md](CONFIG.md)
documents every config key named below.

Every host/model name below is a placeholder; `halo local` shows yours.

## Ollama

Ollama runs models on hardware you control, local or not. Halo always
talks to its native API, never the OpenAI-compatible shim -- only the
native API lets Halo set the context window on every request.

### Found on this machine

Install Ollama and pull a model, then just use it -- no Halo
configuration needed:

```sh
ollama pull qwen3:30b
halo -p "reply with the single word pong" --model ol:qwen3:30b
```

With no `ollama.hosts` entries configured, Halo talks to
`127.0.0.1:11434` (or whatever `OLLAMA_HOST` says) automatically.

A second daemon (another port, Docker, the other side of WSL) is found
rather than typed (Halo 3.2.3.0):

```sh
halo ollama discover            # this machine's doors, about 4 s
halo ollama discover --add      # write the new ones as ollama.hosts entries
```

`discover` asks `OLLAMA_HOST`, 127.0.0.1 and [::1] on the ports in
`ollama.discover.ports` (default `[11434]`; add `11435` and so on for a
second daemon), this machine's own LAN address, `host.docker.internal`,
and on Windows a running WSL distro (inside WSL, the Windows host). Each
one is confirmed with `/api/version` and `/api/tags`; a server that
answers on two of those addresses is one row, the loopback address kept.
One line per server, with the models it serves:

```
pc        http://127.0.0.1:11434       0.12.6    3 models: qwen3:30b, gpt-oss:20b, llama3.2:3b  configured
local-11435 http://127.0.0.1:11435     0.12.6    1 model: qwen3-coder:30b  new
```

`--add` writes the `new` rows (or `--add NAME,NAME` the named ones): an
existing host is never repointed, the first entry stays the default, no
key is written, and the models are `ol:<model>@<name>` at once. `halo
ollama` and `halo local` list a local server that is found but not added
as "found, not added (halo ollama discover --add)".

In Studio (3.3.0.0): Setup's Ollama card (`halo studio --mode setup`,
`Alt+8`) has **Find Ollama servers**, the same local pass at once. Each
server found is a row with its name, address, version and models, marked
"configured" or with a tick; **Add the ticked** writes the ticked ones the
same way `--add` does, and the Models panel then lists each new host as
`Ollama (<name>)` ([STUDIO-setup.md](STUDIO-setup.md)).

### Found on the network

`halo ollama discover --lan` also sweeps the network: the /24 of this
machine's LAN address plus every CIDR in `ollama.discover.subnets` (a
network wider than a /24 is skipped with one line), a 0.3 s TCP connect
on each address and port, 64 at a time, about 10 s in all. Responders are
confirmed the same way and named from reverse DNS, else
`ollama-<last octet>`. The scan runs only when you ask (this command,
**Scan this network** in the wizard's Ollama tab, or the same button in
Studio Setup's Ollama card), never on its own, and not in offline mode.
In Studio the scan is a background job with a live line ("scanning
192.0.2.0/24 · 3 s") and a Stop; its rows join the found table, ticked and
added like the local ones.

```sh
halo ollama discover --lan
halo ollama discover --lan --add gpubox
halo -p "reply with the single word pong" --model ol:qwen3:30b@gpubox
```

A host the scan cannot reach (another network, a cloud host) still goes
in by hand, as an `ollama.hosts` entry referenced with `@<name>`:

```sh
halo config set ollama.hosts '[{"name": "lan", "url": "http://<lan-host>:11434"}]'
halo -p "reply with the single word pong" --model ol:qwen3:30b@lan
```

Ollama itself has no authentication; a reverse proxy in front of a LAN
host needs its own `api_key` on that host entry, same as a cloud host
(below). A daemon bound to loopback only reports as "not reachable from
here" rather than an error -- see "Where settings live" for the switch
(`OLLAMA_HOST=0.0.0.0` on the server is what makes the scan find it).

### Measured after finding

`halo ollama discover --add --calibrate` then measures every model of the
hosts it just added (and of a configured host you name in `--add`) with
the same calibration `halo ollama calibrate` runs: each model is loaded at
a few windows and the largest one that sits fully in GPU memory is
recorded in `~/.halo/ollama-fit.json`, one progress line per model:

```
qwen3:30b on gpubox: 32k fits, 65k does not (2 min 10 s)
```

So the first real turn on a found model already knows its window instead
of finding out mid-prompt. `--timeout S` sets the per-step budget; the
wizard offers the same measurement after its Save adds hosts, and Studio
Setup's Ollama card has **Measure the found models** after Add the ticked
(the models of the hosts just added, each with a tick, one log line per
model and a summary).

Both then ask "make tuned twins of the models that fit? (Enter / n)"
(`--twins` answers yes without asking, `--no-twins` skips it). A tuned
twin is a derived model on the same server, `<name>-halo:<tag>` (for
`qwen3:30b`, `qwen3-halo:30b`), that shares the original's weights and
sets the window just measured as safe plus every layer on the GPU as its
defaults, so Ollama stops moving part of the model to the CPU past its
own cautious window; `halo ollama tune MODEL --host NAME` makes one at
any time and `--remove` deletes it. The twin is listed under its original
and offered first where models are picked. See
[MODELS-ollama-tuning.md](MODELS-ollama-tuning.md)'s "A tuned twin".

### Ollama Cloud

Get a key from `ollama.com/settings/keys`, then either set
`OLLAMA_API_KEY` in your environment (Halo picks it up for the
synthesized default host) or add a named cloud host:

```sh
halo config set ollama.hosts '[{"name": "cloud", "url": "https://ollama.com", "api_key": "<your key>"}]'
halo -p "reply with the single word pong" --model ol:gpt-oss:120b@cloud
```

Structured output (`format`) does not work against Ollama Cloud (Ollama's
own docs say so); tools and streaming are expected to behave like a
local host, but that parity is unconfirmed (see "Still unconfirmed").

### OpenAI-dialect hosts: a proxy in front of Ollama

A gateway that serves only the OpenAI paths (`/v1/chat/completions`,
`/v1/models`) -- a no-think proxy in front of Ollama, for instance --
has no native `/api/chat` for the `ol:` dialect to post to. Add
`"dialect": "openai"` to that host entry and the whole `ol:` route rides
the OpenAI wire shape instead: requests go through the same
openai-chat machinery `or:`/`dbx:` use, with the entry's own `url` (a
`/v1` segment is added for you) and `api_key` as the bearer, and model
enumeration (`halo models`, `/model`, `/local`) reads `/v1/models`.

```json
{"ollama": {"hosts": [{"name": "lan", "url": "http://host:11435", "api_key": "<token>", "dialect": "openai"}]}}
```

```sh
halo -p "reply with the single word pong" --model ol:qwen3-coder:30b@lan
```

The `ol:` provider identity is kept throughout (picker grouping, balances
reporting, error mapping), unlike routing the same gateway through an
`or:` alias. Everything native stays native: a host entry with no
`dialect` field behaves exactly as before, `halo doctor` names the
dialect per host, and an unrecognized dialect value falls back to native
with a WARN line. Context sizing note: a gateway reports no trained
context (there is no `/api/show`), so `num_ctx`/fit calibration do not
apply -- set `max_ctx` on the entry or a routes.json profile if you need
a specific window.

### `ollama.hosts`, calibration, and learned caps

A host entry is `{name, url, default, keep_alive, max_ctx,
num_parallel_hint, api_key, kv_cache_type, ssh}`. Halo computes and sends
`options.num_ctx` -- the context size for that one request -- from the
model's own trained context, the host's `max_ctx` if set, a memory
estimate and a saved calibration, never above 131072.

**The prompt floor.** Ollama does not refuse a prompt longer than the
request's `num_ctx`: it trims it (the oldest messages go first) and
answers anyway. So before every Ollama call Halo estimates the request
-- its serialized characters (system text, messages, tool definitions)
divided by 3.5, plus the reply's room (the request's `num_predict`, 1,024
at least: prompt and reply both have to fit the window, a reply that
reaches its end is cut there) -- and `num_ctx` is never below that. When
only the prompt (and 1,024 for the reply) fits the largest window, the
window is that largest one and the reply's `num_predict` is lowered to
the room left. The floor raises the window above a saved calibration, the
remote default or a fallback, up to the trained context, the memory
estimate, `max_ctx` and 131072. When even that cannot hold the request
(one large tool result can do it), the turn compacts first and says so
in one line: "the request (14k tokens, 9k of it tool output) is larger
than qwen3.8:27b's window on pc (8k): compacted". When Ollama still reads
far fewer tokens than were sent (`prompt_eval_count` under 70 % of the
estimate), answers 500 "no user query found in messages", or stops the
reply at the window's end (`done_reason: "length"` with prompt + reply
filling `num_ctx`; Ollama still answers 200), the request did not fit: Halo raises the window and sends it again when there is room
("pc trimmed the request (4.1k of 11k tokens): re-sent with a 16k
window"), else compacts and sends it again -- once per turn; a second trim
in the same turn is an error line.

**Calibration measures or says unknown.** `halo ollama calibrate` loads
the model at candidate windows (every layer asked onto the GPU) and reads
`/api/ps` back:

```sh
halo ollama calibrate qwen3-coder:30b
halo ollama calibrate qwen3-coder:30b --timeout 180
```

A load counts only when it finished within its budget and `/api/ps` lists
the model at that very window; a load that ran out of time, or an
`/api/ps` without the model (or with it at another size), is unknown. An
unknown step is tried once more with twice the budget, then the run ends
**inconclusive** and nothing is saved -- a slow host is never recorded as
a small window. The budget per load: 20 s + 4 s per GB of the model on
this machine, 40 s + 6 s per GB over the network, 60 s when the size is
unknown; `--timeout S` sets it.

**The headroom rule.** A window fully on the GPU is **safe** when the
card keeps at least 8 % of its memory (or 1.5 GB, the larger) free, and
**tight** above that; the saved window is the largest safe one and the
line names the tight one too ("65k safe, 98k tight (22.1 of 23 GB), 131k
does not fit (6 min 10 s)"). With the headroom rule a `max_ctx` on the
host is normally unnecessary; it stays the hard ceiling when you set one.

The result is saved (`~/.halo/ollama-fit.json`) and used from then on --
it changes when you re-pull the model or upgrade Ollama, and a saved
window below the current request's floor is discarded and measured
again. The first time you use a model on a host with no saved
measurement, Halo runs this automatically: the turn waits up to 20 s, the
measurement keeps its own budget in the background and its one line
appears when it finishes (the next turn uses it). Turn that off with
`halo config set ollama.auto_calibrate false` if you'd rather calibrate
by hand only.

### The host panel and `halo ollama doctor`

```sh
halo ollama              # or /ollama in the TUI
halo ollama doctor       # the same page, plus tuning recommendations
```

`halo ollama` shows, per host: reachable or not, version, each loaded
model's memory use as one sentence ("fully loaded in GPU memory" or
"partially offloaded: ... the rest in system RAM (slower)"), and what
context it fits at, with the one-phrase reason (learned cap, host
`max_ctx`, fit estimate...). `halo ollama doctor` adds the server-side
settings Halo can't read back (flash attention, KV cache type,
keep-alive) and where to set each one for your OS (below).

### Tool reliability

Small models mostly fail at tool calling by sending a malformed call, not
by picking the wrong tool. Halo never forces a rigid output format on an
ordinary turn -- a model always gets to answer in plain prose first.
Only when a call actually fails to parse does Halo send one isolated,
schema-constrained repair request before giving up with a plain error.
Three identical tool calls in a row stops the turn instead of looping.

### Roles for local models

A local model defaults to a supporting role (`small`, `researcher`,
`judge`, `subagent_default`) -- never main -- the moment you give it
one; press `u` on a model in the picker to set its role. You can still
pick one as your main model directly; if it can't call tools, Halo says
so and lets you proceed anyway.

### The gym and `halo doctor --local`

`halo gym` runs a fixed set of tasks against your own local models, on
your own hardware, and scores them:

```sh
halo gym --models ol:qwen3-coder:30b,ol:gpt-oss:20b
halo gym show                 # print saved cards
halo gym propose --apply      # turn the scores into a role table
```

Scores: tool-call accuracy, edit success, context recall,
instruction-following, tokens per second -- measured here, never a
vendor claim. `halo doctor --local` is the 60-second "does this work"
check for one model: load it, one real tool call, one structured-output
call, summarize a fixture transcript, PASS/FAIL per step. Run this
first on any new local model.

## Hugging Face

Hugging Face covers three different things Halo treats as separate
routes: a shared router, a dedicated endpoint you pay for by compute
time, and a server running on a machine you control.

### The router (`HF_TOKEN`)

```sh
export HF_TOKEN=...
halo -p "reply with the single word pong" --model hf:Qwen/Qwen3-32B
halo -p "..." --model hf:openai/gpt-oss-120b:cheapest
```

`HF_TOKEN` is the only env var name Halo reads here (not
`HUGGING_FACE_HUB_TOKEN`/`HF_API_TOKEN`). An optional `:fastest`/
`:cheapest`/`:preferred`/`:<provider-name>` suffix picks the partner;
with none, the router decides. `huggingface.bill_to` (a Team/Enterprise
org name) adds the router's own billing header, router requests only.

### Dedicated endpoints

A model you've provisioned onto its own compute, with its own URL and
token -- a separate product from the router, never sharing credentials:

```sh
halo config set huggingface.endpoints '[{"name": "my-prod", "url": "https://...", "token": "..."}]'
halo -p "..." --model hf:endpoint/my-prod
```

### Local servers

`llama-server`, vLLM, `transformers serve`, LM Studio and TGI all speak
the same OpenAI-compatible shape; Halo looks for one on this machine's
documented default ports automatically:

```sh
halo local                    # or /local in the TUI -- shows what it found
halo -p "..." --model hf:local/qwen3-30b
```

A server on another machine, or one needing a bearer token, needs a
manual entry instead (`huggingface.local_servers`, same shape as
`ollama.hosts`) -- auto-detection only ever checks this machine.

### Model folders

`halo local` also lists model files it finds on disk, even ones nothing
is currently serving: the Hugging Face Hub cache, LM Studio's own model
folder, and any folder you add yourself:

```sh
/local add /path/to/your/models     # or: halo local add /path/to/your/models
```

Each file's own header -- a GGUF's metadata block, or a safetensors
folder's `config.json` -- tells Halo its trained context length and
quantization without loading it.

### Serve a file with the managed runtime

```sh
halo local serve /path/to/model.gguf
halo local serve mlx-community/Qwen2.5-7B-Instruct-4bit --runtime mlx_lm   # Apple Silicon
```

Starts a small background server on your own machine, sized to what
fits, and gives you an `hf:local/<name>` reference for the rest of the
session. If `llama-server` isn't already on your machine, Halo offers to
download the right build for your OS/GPU, names the size, and waits for
a yes.

### Import into Ollama

Often simpler than serving a GGUF separately, if you already run Ollama:

```sh
halo local import /path/to/model.gguf --name my-model
```

Halo names the file's size and waits for your yes; the result is an
ordinary `ol:my-model` with every Ollama feature above (fit, calibration,
roles). Only `.gguf` files are offered this path.

### Apple Silicon (the MLX extra)

On an Apple Silicon Mac only, an optional extra routes straight to a
Hugging Face Hub repo, no file management needed:

```sh
uv tool install "halo-harness[mlx]"
halo -p "..." --model hf:mlx/mlx-community/Qwen2.5-7B-Instruct-4bit
```

Experimental, off by default, and unavailable to install on any other
OS/CPU combination. See [docs/MAC.md](MAC.md) for the full walkthrough
and what's still unverified about it.

## The OpenAI API

**Verified against the fake only until a key is available.** `oai:`
drives the real OpenAI API with `OPENAI_API_KEY`:

```sh
export OPENAI_API_KEY=...
halo -p "reply with the single word pong" --model oai:gpt-5
```

Two models (`gpt-6-astra`, `gpt-6.1-sol`) need a different request shape
for tool calling to work; Halo switches to it for exactly those two ids.

## Offline mode, escalation, and the savings meter

```sh
halo --offline -p "..." --model ol:qwen3-coder:30b   # works -- loopback
halo --offline -p "..." --model or:anything            # refused, one sentence
/offline on                                             # the persisted equivalent
```

Offline mode refuses any connection that isn't loopback or a local host
you've configured yourself (an Ollama host, a Hugging Face local
server) -- every route on this page except the local ones.

A local-first session can name a cloud fallback and the conditions that
should trigger it:

```sh
halo config set routing.escalation '{"to": "or:anthropic/claude-haiku-4.5", "when": ["low_confidence", "tool_failures", "context_overflow"], "ask": true}'
/escalation
```

`ask: true` (default) only ever notifies you; Halo switches models on
its own only if you set `ask: false`. For every local turn, the cost
meter also prices the same tokens against your escalation target (or a
median cloud price) and shows it as "saved $x"; `/cost` prints the total.

## Where settings live, per OS

Halo's own files (`~/.halo/config.json`, the env file, cached catalogs)
live under your home directory the same way on every OS -- you never
need to type the OS-specific form of `~` yourself.

**Windows**: the Ollama tray app's "Expose Ollama to the network" switch
(its Settings screen) decides whether the LAN can reach it -- setting
`OLLAMA_HOST` yourself has no effect until that switch is also on. Set
an Ollama env var as a user-scope environment variable, then quit and
relaunch the tray app.

**macOS**: the menu-bar app has the same switch, worded "Expose to
network," off by default. Setting an env var yourself is `launchctl
setenv <VAR> <value>` plus relaunching the app -- community knowledge,
not independently confirmed (see "Still unconfirmed"). Apple Silicon has
no separate GPU memory to query, so its GPU-usable RAM share is only an
estimate until `halo ollama calibrate` measures it for real.

**Linux**: `sudo systemctl edit ollama`, one `Environment="VAR=value"`
line per variable under `[Service]`, then `sudo systemctl daemon-reload`
and restart the service.

Every OS: the Hugging Face Hub cache is `~/.cache/huggingface/hub`
(or `$HF_HUB_CACHE`/`$HF_HOME/hub` if you've set either), and LM
Studio's own model folder is `~/.lmstudio/models` by default.

## What to expect

- A local model's first response takes longer than a cloud model's --
  prefill (processing your prompt before the first output token) runs on
  your own hardware, not a data center's.
- Compaction (summarizing older turns to make room) happens more often
  on a small context window than a large one -- a 16k window fills up
  faster than a 128k one, by definition.
- A one-word turn's very first request is not free: on a 16k window, the
  system prompt plus the 24 built-in tools cost about 10,000 prompt
  tokens before you've said anything, measured on a 27B model -- a larger
  window makes this proportionally smaller, not literally cheaper.
- A model with no reliable tool support can still answer questions as
  your main model -- it just can't edit files or run commands; Halo says
  so in one sentence when you pick one.

## Known limits in 2.0.3

Open items from the live runs that made this release, not promises of
when they'll be fixed:

- Reading a host's full catalog (`halo ollama`, `/local`) costs one
  request per model -- slow on a host with dozens of them.
- A provider error under `-p --output-format json` has no error text in
  the JSON `result` field yet (stderr only, text mode).
- `halo doctor` reads an unconfigured host and a configured-but-down one
  the same way ("not reachable"); the second deserves a stronger warning
  and doesn't get one yet.
- The fit estimate assumes an uncompressed (f16) KV cache; a host running
  a quantized cache (`OLLAMA_KV_CACHE_TYPE=q8_0`/`q4_0`) gets a
  smaller-than-necessary estimate unless you set `kv_cache_type` yourself.
- `halo local serve` doesn't validate a model file before launching a
  server with it -- a bad download fails with "didn't answer in time,"
  not a named reason; `halo local`'s listing doesn't skip it either.
- Auto-calibration can load a model two or three times on first use
  (about a minute for a 27B-class model); whether it should skip that
  step-up by default is still an open question.
- Escalation's "ask" mode is a plain notification, not yet a full
  accept/keep-local/turn-this-off card.
- The "saved $x" figure isn't in `-p --output-format json`'s result
  object yet (status bar and session log only).
- Offline mode stays silent about its one intentional exception: an MCP
  server with a remote URL.
- The gym counts a redundant-but-valid tool call (the same call made
  twice) as a pass -- it can read better than it should.
- **The lean prompt for small windows did not ship in 2.0.3** -- a
  compact tool-description mode for 16k-and-under windows (the source of
  the ~10,000-token cost above) moved to 2.0.6 hardening instead; this
  release ships the measurement, not the fix.

## Still unconfirmed after 2.0.3

Halo's own research for this release could not confirm these from a
primary source; each still matters if you hit it, and each has a way to
check it yourself:

- **Apple's GPU-usable memory share** ("about two-thirds to
  three-quarters of total RAM") isn't from an Apple/mlx-lm document --
  `halo ollama calibrate` on a Mac gives the real measured number instead.
- **Setting Ollama's env vars on macOS** (`launchctl setenv <VAR> <value>`
  plus relaunching the menu-bar app) is community knowledge, not Ollama's
  own docs -- try it, then check `halo ollama doctor`.
- **`mlx_lm.server`'s own flags** beyond `--model`/`--port` aren't in its
  README -- [docs/MAC.md](MAC.md) step 8 shows how to check what the
  managed server actually started with.
- **AMD/Intel GPU memory probes** (`rocm-smi`'s exact flags, `xpu-smi`'s
  exact JSON keys) aren't confirmed -- run `halo ollama` and see whether
  the GPU-memory line fills in or stays estimate-only.
- **Jan's default port** isn't confirmed, so Halo never guesses it -- run
  `halo local` and see whether it's auto-detected or needs a manual
  `huggingface.local_servers` entry.
- **Ollama Cloud's tool-calling/streaming parity** with a local host
  isn't confirmed (structured output IS confirmed unsupported) -- send a
  real tool-call turn to an `ol:<model>@cloud` host and see what comes back.
- **Exactly which OpenAI models need the Responses dialect** -- only
  `gpt-6-astra`/`gpt-6.1-sol` are confirmed; a silent tool-call failure on
  another `oai:` model is the sign to check `openai.dialect_overrides`.

## See also

[docs/MODELS.md](MODELS.md) (exhaustive reference), [docs/CONFIG.md](CONFIG.md)
(config keys), [docs/COMMANDS.md](COMMANDS.md)/[docs/SLASH-COMMANDS.md](SLASH-COMMANDS.md)
(commands), [docs/ROLES.md](ROLES.md) (roles), [docs/MAC.md](MAC.md) (Apple Silicon).
