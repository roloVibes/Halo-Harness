# Models: Strata, a big Mixture-of-Experts model on Windows, Linux or the Mac

Read this when you want to run a Mixture-of-Experts model bigger than your graphics card on one machine with Strata -- natively on Windows, Linux or an Apple Silicon Mac -- and need to know how to install it, which sets it serves and how big their downloads are, whether one fits your RAM and card, and what the steward says about it.

Part of [Models](MODELS.md), which lists every part. Its Linux-only sibling: [MODELS-freetoken.md](MODELS-freetoken.md); the other local servers: [MODELS-steward-servers.md](MODELS-steward-servers.md); the pool, which spreads one model across several machines instead: [POOL.md](POOL.md).

## What it is (3.3.9.2)

[Strata](https://github.com/Niko1221/Strata) (MIT) runs one big Mixture-of-Experts (MoE) model on one consumer
machine: the experts sit in host RAM, the rest of the model on the graphics card, and what does not fit -- for
Qwen3.8-Flash-Next its 29 GB n-gram table -- is read from the SSD. It is FreeToken's family (expert paging from RAM and
disk), and the first of that family that runs **natively on Windows**: the PC's 4090 runs it without WSL2. It ships a
desktop app and a Terminal (`strata`); Halo uses the Terminal. Its server speaks the OpenAI and Anthropic APIs on
`http://127.0.0.1:8080` by default and has a browser chat and a `/metrics` monitor.

To Halo it is one more local runtime, `strata`, beside llama-server, LM Studio, mlx_lm.server and FreeToken: an
OpenAI-compatible local server reached as `hf:local/<model>@strata` on its machine and `hf:local/<model>@<host>` from a
peer.

Every Strata fact on this page is from its README, AGENTS.md, docs (`TERMINAL_LAUNCH.md`, `AI_SETUP.md`, `MODELS.md`,
`DETAILS.md`) and source (`serve/server.py`, `strata_cli/launch/`, `strata_control/runtime.py`), read 2026-11-02 at
main ffa80d73, and **unverified against a live run**: no Strata has run against Halo yet. The log lines the steward
reads are written from that source; a live log may word them otherwise.

## Install

Strata's installer needs no administrator rights and puts `strata` on your PATH (these are its own lines):

```powershell
# Windows PowerShell (then open a new terminal)
irm https://github.com/Niko1221/Strata/releases/latest/download/install.ps1 | iex
```

```sh
# Linux and the Mac
curl -fsSL https://github.com/Niko1221/Strata/releases/latest/download/install.sh -o install.sh && sh install.sh
strata --version
```

The packages are x86-64 on Windows and Linux and Apple Silicon (macOS 15 or newer) on the Mac. Cards: NVIDIA RTX 20 to
50, AMD Radeon RX 7000 / 9000 and AI PRO R9700, Intel Arc on Linux, Apple Silicon, Ryzen AI Max (Strix Halo). The
engine for your card comes with the first model: `strata launch` fetches it from the same release and test-starts it.

Halo finds `strata` on PATH, or the program `huggingface.strata_bin` names (a path, or the program and its first
arguments). Halo does not search Strata's install folders; an install the desktop app made lives in
`%LOCALAPPDATA%\Strata\install` (Windows) or `$XDG_DATA_HOME/strata/install` (Linux, macOS) -- point
`huggingface.strata_bin` at its `strata` when it is not on PATH. When `strata` is missing, `halo local serve --runtime
strata` and `halo doctor --local` say so in one line with the install route for this machine's OS.

## The first launch is your download

A Strata set is tens to hundreds of GB, and its first launch downloads it. That download is yours to run, never
Halo's: `halo local serve --runtime strata` asks `strata launch --plan --output json` first (nothing is downloaded or
changed) and, when the plan says anything is to fetch -- the set, the engine for your card, the draft layer -- it
starts nothing and prints one line with the GB and the command:

```
the first launch downloads about 76.0 GB (About 76.0 GB to download: ...) -- Strata's download, yours to run:
strata launch --family qwen --model IQ3_XXS --yes --no-tui --access local; then halo local serve --runtime strata
again (or the auto-detect names it on its port)
```

Run it yourself (it resumes when interrupted). Or start Strata entirely on your own -- `strata launch` with its
screens -- and Halo's loopback sweep finds it on its port.

## Serve

```sh
halo local serve --runtime strata --model qwen/IQ3_XXS       # <family>/<set>, as strata launch takes them
halo local serve --runtime strata --model-path D:\models\IQ3_XXS   # files you already have
halo local serve --runtime strata --model qwen/IQ3_XXS --plan     # Strata's own plan and the fit here; nothing starts
halo local servers                     # strata  strata  http://127.0.0.1:P  ready  hf:local/<model>@strata  ...
halo local log strata                  # the server's own log
halo local stop strata                 # strata launch --stop for the launch serving its port
```

With nothing to download, Halo runs `strata launch --family F --model S --yes --no-tui --access local --port <a free
loopback port> --api-key-env HALO_SECRET_STRATA_API_KEY`. The key is one Halo generates and keeps in its env file,
handed to the launch in its environment -- never on a command line, never in `config.json`. The launch's output goes
to `~/.halo/local/servers/strata.log` after Halo's `--- halo starts:` line; it is the registry row `strata` and the
`huggingface.local_servers` entry `strata` (url, log, runtime, model, `api_key_env`).

- `strata launch --no-tui` starts the server under Strata's own supervisor and returns: the server keeps running
  after Halo exits; `halo local stop strata` stops it. Once the launch returns Halo reads what it printed: the
  address, the model id the server reports (`/v1/models`), and the server's own log (`<Strata's state>/runtime/
  launch-<name>.server.log`, beside the "Engine log" the launch prints), which `halo local log strata` and the steward
  read from then on.
- A launch still loading after three minutes goes on in the background: the line says the last thing it printed.
- A launch that finds no engine for this computer ("Strata couldn't find an engine for this computer") returns
  without serving: Halo says Strata's line and keeps no entry.
- `--lan` is `--access lan`: every address, behind Halo's key, so a peer can reach it (Strata's own advice is to keep
  the server on 127.0.0.1 unless you ask for more).
- A Strata server you started by hand is found by the loopback sweep on its port (8080 is the first one it asks) and
  named by its runtime: its `/health` says `"service": "strata"` and its window comes from `meta.n_ctx` on
  `/v1/models`.

## The sets

The sets Strata names are the Library's Strata download targets (Models -> Hugging Face, `halo models browse --source
hf strata`), each with the Strata fit as its badge and the `strata launch` command as its pull line (your download).
They are listed when the search names Strata or the runtime is configured. From Strata's README and docs/MODELS.md:

| Family / set | Model | Download | In RAM (Strata's figure) |
|---|---|---:|---|
| `qwen/Q2_0`, `IQ2_XS`, `IQ3_XXS`, `IQ3_S` (ISTA-DASLab) | Qwen3.8-Flash-Next (125B MoE) | 66, 68, 76 GB; IQ3_S not stated | experts 34 / 35.5 / 43 / 50 GB + about 10 GB; the 29 GB n-gram table on the SSD |
| `coder/IQ1_M` | the Coder (256 of 512 experts, for code) | not stated | 23 GB of experts |
| `swift/IQ2_XS` | Swift 1.5 (a fine-tune that thinks shorter) | not stated | as IQ2_XS |
| `unsloth/UD-IQ4_XS` ... `Q8_0` | Qwen3.8-Flash-Next (Unsloth) | 94 to 188 GB | every expert: ~72 to ~136 GB |
| `gyro/Gyro-S`, `Gyro-M` | Qwen3.8-Flash-Next (agentionai) | 58.5, 92 GB | 27.6, 35 GB of VRAM + RAM |
| `nvfp4/NVFP4`, `NVFP4-NVIDIA`, `NVFP4-QAD` | Qwen3.8-Flash-Next (NVIDIA only) | 128, 128, 102 GB | about 80 GB |
| `qwen36/UD-Q4_K_XL`, `UD-Q6_K_XL`, `Q8_0` | Qwen3.6-35B-A3B (no Mac engine) | 22.9, 32.6, 37.8 GB | Strata plans 32, 44, 52 GB |
| `deepseek41/ist-das-1.75bpw`, `2.00bpw`, `2.25bpw`, `ist-das-coder`, `ud-q8_k_xl` | DeepSeekV4.1-Flash-1017 | 239, 257, 274, 191, 508 GB | a 12 GB card or more, 46 GB of RAM at least (64 the tested size); keep the download free on an NVMe |

The first start of a Flash-Next set also fetches its draft layer (about 6 GB). DeepSeek answers one request at a time
and checks an 8K window.

## The fit: FreeToken's rule with Strata's figures

The fit for a Strata server (`local_sched/fit_st.py`) has FreeToken's shape -- one deterministic line per set and
host, `fits`, `tight`, `no` or `unknown`, the Library badge's why -- with Strata's own statements:

- **The card:** the parallel requests by Strata's VRAM guide: 12 GB runs 1, 20 GB 2, 24 GB 3, 32 GB and more 4
  (DeepSeek: one at a time; under 12 GB: one, and DeepSeek does not fit).
- **Host RAM for the experts:** fits when RAM holds the experts plus about 10 GB; under 6 GB to spare is "tight" (the
  server's own RAM-tight warning); short of that Strata maps the experts from the model files and reads what RAM
  cannot hold from the SSD -- "fits, slower"; under half the experts' size it does not fit. Unsloth and NVFP4 read
  their "every expert in RAM" figure, Gyro its VRAM + RAM, Qwen3.6 the RAM Strata plans.
- **The SSD for the rest:** Flash-Next's n-gram table, and for DeepSeek the download's GB kept free on an NVMe.
- **The speed:** Strata's measured table on the nearest card at or under yours, as the extrapolated figure ("expect
  62 tok/s class (Strata's table: RTX 5070 12 GB ...), not measured here yet"); "N tok/s measured" once `halo local
  bench --host strata` kept a card for that set.
- **The platform:** NVFP4 only on NVIDIA; Qwen3.6 not on the Mac; a box with no graphics card does not fit.

On the fixture boxes (pc: a 24 GB 4090, 64 GB, Windows; samus: a 10 GB 3080, 64 GB; small: an 8 GB 3060, 32 GB):

```
fits: Qwen3.8-Flash-Next IQ3_XXS on pc: 3 slots on the 4090 (the VRAM guide: 24 GB runs 3), 43 GB of experts in 64 GB of RAM, its 29 GB n-gram table streams from the SSD; expect 62 tok/s class (Strata's table: RTX 5070 12 GB, 64 GB RAM (engine 0.1.26, short chat)), not measured here yet; the first launch downloads 76 GB (yours to run)
fits, slower: Qwen3.8-Flash-Next UD-Q4_K_XL on pc: ... every expert needs ~88 GB of RAM, 64 GB here, so Strata keeps what fits and reads the rest from the SSD ...
fits: DeepSeekV4.1-Flash-1017 ist-das-2.00bpw on pc: 1 slot on the 4090 (DeepSeek answers one at a time), 64 GB of RAM ...; keep about 257 GB free on an NVMe ...
does not fit: DeepSeekV4.1-Flash-1017 ist-das-2.00bpw needs a 12 GB card or more, 10 GB on the 3080
fits, slower: Qwen3.8-Flash-Next IQ3_XXS on small: 1 slot on the 3060 ..., 43 GB of experts against 32 GB of RAM, so Strata maps them from the model files and reads what RAM cannot hold from the SSD ...
```

The table's figures were measured on Strata's own hardware: only the speed card says what yours does.

## The speed card

`halo local bench --host strata [--quick] [--yes]` runs FreeToken's speed card against the Strata server -- the
battery's windows and the reply reserve over the OpenAI route, two calls per window, an untimed warm-up first (the
first request after a start fills the GPU's expert cache) -- with its cost line first ("local: ~N s on strata (its
GPU, CPU and the SSD are busy for it) ..."). The card lands under the server's name (`strata|<model>`) and, for a set
Halo started, under the set's name too, which the fit line reads.

## In placement and through the host

- **Through the host:** a Strata server on the host machine is a host-served local server: the join and the announce
  list it (`kind: server`, `runtime: strata`, its model), and with `--lan` the host's catalog offers its entry and key,
  so the Mac and Kali reach the PC's Strata as `hf:local/<model>@pc`. A loopback-only server is not offered.
- **Placement** (`halo local place`, the adviser) sees each Strata server beside the Ollama hosts, the pool and
  FreeToken: the set it serves is warm (no load); another set Strata names is a restart with the loading tax said ("a
  restart onto Qwen3.8-Flash-Next Q2_0, ~23 s reading its experts into RAM, the first launch's 66 GB download if the
  set is not there (yours to run), evicts ..."); any other model is out. Nothing restarts a server by itself.

## What the steward says

The steward reads the server's own log like any local server's: the load (the experts into RAM, under a RAM budget,
or mapped from the model files; the window from the `ready:` line), each request's `done:` line (tok/s, the expert
cache's hit rate, the share read over PCIe), the engine's request summary, the parallel-slot lines, the RAM-tight
warnings, and in the launch's output the download lines. Three findings, keyed `<server>|<model>`, each with a stated
fix that is never applied by itself (`halo ollama steward findings`, the Steward page, `halo ollama explain <kind>`):

| Finding | When | What it says |
|---|---|---|
| `strata-disk-bound` (warn) | the experts are mapped from the model files, under a RAM budget or beside a RAM-tight warning, and the newest replies decode under 8 tok/s; or the RAM-budget warning alone | the expert reads from the SSD dominate: the next set down (its experts' GB said), or more RAM |
| `strata-slots` (warn) | the engine runs fewer parallel slots than asked, or a request waited for a free slot | past the VRAM guide the rest queue: at most that many of Halo's lanes on the server at once, `--parallel` by the guide next launch |
| `strata-download` (info) | the launch is downloading (the set, the engine, a drafter), until the server is ready | the GB and the share; Strata's own download, never a timeout |

## What is not taken

Strata's Anthropic-compatible API (Halo speaks OpenAI-compatible to local servers); its desktop app and its MCP server
(the Terminal is the route an agent takes); reading its `/metrics` and `/v1/telemetry` endpoints (the log carries what
the findings need this round); tuning (`strata launch --tune`) and `strata connect`; replacing llama.cpp or Ollama for
dense models.
