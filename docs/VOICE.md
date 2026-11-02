# Voice: the speech models and Halo's speech server

Read this when you want speech-to-text or text-to-speech on your own machine: which speech models Halo knows, how to download and serve one, where it runs, what the steward says about it, and what the voice loop of the next rounds adds.

Voice is Halo 3.3.9.0. This page describes **round R1, the speech servers**: a speech model is a file-backed local
model like any GGUF -- present or absent, downloadable, served, fitted into a bundle's verdict, and watched by the
steward. Nothing in R1 records or plays audio. The commands are in [COMMANDS-voice.md](COMMANDS-voice.md).

What the next rounds add (no dates):

- **R2, the loop**: Silero VAD -> speech-to-text -> the session's model -> a sentence aggregator -> text-to-speech,
  barge-in, `/voice` in the TUI, the latency card and the `voice-local` bundle.
- **R3, through the host, Studio and the glasses path**: the speech servers offered to peers through `halo host`,
  Local -> Voice in Studio with a browser-mic Talk button, and the phone-app contract for Meta's glasses, honest about
  what the glasses cannot do (no custom wake word, no always-on microphone, the phone always in the loop).

## The catalog

`halo voice models` lists seven models (`--json` for the same as JSON):

| Model | Kind | Engine | Download | On a GPU | On the CPU | In this build |
|---|---|---|---|---|---|---|
| `faster-whisper:large-v3-turbo` | STT | faster-whisper | 1.6 GB | 1.5 GB | 3.1 GB | built |
| `faster-whisper:small.en` | STT | faster-whisper | 0.5 GB | 0.5 GB | 0.9 GB | built (the CPU default) |
| `faster-whisper:base.en` | STT | faster-whisper | 0.15 GB | 0.2 GB | 0.4 GB | built |
| `parakeet-tdt:0.6b` | STT | parakeet-tdt | 2.5 GB | 1.2 GB | 2.4 GB | declared |
| `kokoro-82m` | TTS | kokoro-onnx | 0.34 GB | 0.3 GB | 0.5 GB | built (voice `af_heart`) |
| `qwen3-tts:0.6b` | TTS | qwen3-tts | 1.8 GB | 1.4 GB | 2.4 GB | declared |
| `silero-vad` | VAD | silero-vad | 0.002 GB | -- | 0.05 GB | R2's loop runs it |

**Built** means this build has an engine for it: faster-whisper through CTranslate2 (int8 on the CPU, float16 on
CUDA) and Kokoro through kokoro-onnx (onnxruntime). A **declared** model is listed, downloadable and fitted, but
`serve` says in one line which model serves its kind instead ("no engine for parakeet-tdt in this build;
faster-whisper:large-v3-turbo is the built STT"); nothing pretends to transcribe.

Each row names the Hugging Face repo it downloads from and the files its engine loads. The repo ids and the sizes are
written from the model cards from memory and are marked `(repo unverified)` until a live download confirms them;
a repo that does not list the files the engine loads is said so before anything moves.

The catalog is the one source for the bundles too: `VOICE_GB` and `VOICE_PREFIXES` in `packs/manifest_bundle.py`
are imported from `halo_harness/voice/catalog.py`. The Library's speech rows name their catalog row (the size, and
`halo voice download <model>` when this build serves it).

## The extra

The engines' Python packages are an optional extra:

```sh
uv tool install --reinstall "halo-harness[voice]"
```

It adds `faster-whisper`, `kokoro-onnx`, `onnxruntime`, `numpy` and `soundfile` (R2 adds `sounddevice` for the
microphone). Without it, `halo voice models`, `download`, `rm` and `halo doctor --voice` work as usual, and every
command that would load an engine (`halo voice serve`, `halo local serve --stt | --tts`) prints that one install line
and exits 2.

## Download

```sh
halo voice download faster-whisper:small.en
```

It says the size, the repo and the folder first (`faster-whisper:small.en: 0.5 GB from
Systran/faster-whisper-small.en (repo unverified) into <folder>`), then the repo's licence line and the files, and
asks. The download is the same hub path `halo local download` uses: into the first `huggingface.model_dirs` folder
(`--dir` picks another), in the hub cache layout (`models--<org>--<name>/snapshots/<commit>/`), checked against the
hub's checksums, and Ctrl+C keeps the part file so the same line resumes. Only the files the engine loads are
fetched. `HF_TOKEN` is read from the environment for a gated repo and sent to the hub only; it is never written.

A model is **present** when every file its engine loads sits in a `huggingface.model_dirs` folder, in the hub layout
or in a plain folder named after the repo (`<folder>/faster-whisper-small.en/`). `halo voice rm <model>` deletes its
files (not while a speech server serves it: `halo local stop stt` first).

## Serve

```sh
halo local serve --stt faster-whisper:small.en --device cpu
halo local serve --tts kokoro-82m
```

This starts **Halo's own speech server** as a managed subprocess, exactly like a llama-server `halo local serve`
starts: on a free loopback port, its log in `~/.halo/local/servers/stt.log` (or `tts.log`), a row of the managed
servers registry, and the `huggingface.local_servers` entry named `stt` or `tts` with `runtime: voice-stt` or
`voice-tts`, its `url`, `log`, `model`, `device` and `pid`. `halo local servers` lists it with its device, `halo local
log stt` reads its log, `halo local stop stt` stops it and takes the entry out. A second `serve --stt` while one runs
says the running one (another model: stop it first) and never restarts it silently. Without `--keep` it stops when
the last Halo process on this home exits.

A speech server never serves a chat model: a bare `hf:local/<model>` never picks the `stt` or `tts` entry, and the
model lists leave them out. It runs beside Ollama, never inside `halo host` (R3 offers it to peers).

`halo voice serve <model>` runs the same server in the foreground; underneath both is
`python -m halo_harness.voice.server --kind stt --model <name> --device cpu --port 0 --log <path>`, which prints
`listening on 127.0.0.1:<port>`.

## The server

stdlib `http.server` with a thread per request; one request reaches the engine at a time. The routes are OpenAI's
audio shapes:

| Route | Request | Answer |
|---|---|---|
| `GET /health` | | `{"status": "ok", "device", "model", "kind"}`; 503 `loading` while the model loads; 500 `failed` |
| `GET /v1/models` | | the one model it serves |
| `POST /v1/audio/transcriptions` (STT) | a multipart `file` (a 16-bit PCM WAV) with `response_format` json or text, or a raw `audio/pcm;rate=16000` (16-bit mono) or `audio/wav` body | `{"text", "segments": [{start, end, text}], "duration", "ms"}` |
| `POST /v1/audio/speech` (TTS) | `{"model", "input", "voice", "response_format": "pcm" or "wav"}` | `pcm` streams each sentence as it is made (`audio/pcm;rate=24000`); `wav` is sent whole |

A route of the other kind answers 404 naming the server it is; a body that is not audio answers 400 with the formats
it takes. Other audio formats (mp3, ogg) are R2's.

```sh
curl -s http://127.0.0.1:<port>/v1/audio/transcriptions -F file=@hello.wav
curl -s http://127.0.0.1:<port>/v1/audio/speech -H 'Content-Type: application/json' \
     -d '{"input": "Hello there.", "response_format": "wav"}' -o hello.wav
```

## The device

`--device auto | cpu | cuda` (else `voice.device`, else `auto`). **auto** is CUDA when the engines see a CUDA device
and this machine's card has the model's GPU footprint free, else the CPU, said in one line either way:

```
faster-whisper:small.en on the CPU: 0.9 GB RAM, the GPU keeps its 22,000 MiB for the chat model (auto: the engines see no CUDA device)
faster-whisper:small.en on the GPU: 0.5 GB of its 22,000 MiB free (auto)
```

The card is the one the steward reads for the Ollama host served here. `--device cuda` is honoured even when the
engines see no CUDA device (the line says the load may fail; the log then says why).

## The fit

A bundle's speech needs (`stt`, `tts`) resolve through the catalog and what is on disk, so `halo pack verdict
meta-glasses` says each one: present, with its footprint on the device the need allows (`device: cpu` -> the CPU
figure, no VRAM; `cpu-or-gpu` -> the GPU figure when the first of its `any_of` fits beside the bundle and the coder,
else the CPU), or absent:

```
stt: faster-whisper:small.en present (0.5 GB on the GPU, 0.9 GB on the CPU)
stt: not present -- halo voice download faster-whisper:small.en (0.5 GB)
```

An absent speech model is a download of the verdict, the same class a missing Ollama model gets ("needs 1
download"); the verdict's button pulls Ollama tags only, and `halo pack verdict` prints each `halo voice download`
line beside it. See [MODELS-bundles.md](MODELS-bundles.md).

## What the steward says

The steward reads a speech server's log like a llama-server's (runtime `voice-stt` / `voice-tts`): the load line
(model, device, the GPU's free MiB the launcher read) and one line per request:

```
voice stt: audio 4.2 s -> text in 0.31 s (13.5x realtime) on cpu
voice tts: text 84 chars -> audio 3.9 s, first audio 92 ms, in 0.40 s on cpu
```

Four findings, keyed `stt|<model>` / `tts|<model>`, on the Steward page, in `halo ollama steward findings` and the
host's events, each with a stated fix that is never applied by itself:

- `stt-slow` -- the newest transcriptions run under 2x realtime: `--device cuda` when the GPU has the room, else a
  smaller built model;
- `tts-slow` -- the first audio comes after 400 ms: the same two ways out;
- `voice-cpu` -- a speech model on the CPU while the GPU had its footprint free: `--device cuda` (info -- a bundle may
  keep speech on the CPU on purpose);
- `voice-load-failed` -- the load failed: the install line when the extra was the cause, `--device cpu` for a CUDA
  library, else download it again.

`halo ollama explain stt-slow` prints each row. See [MODELS-steward-servers.md](MODELS-steward-servers.md).

## Doctor

`halo doctor --voice` says, one line each: the extra installed or the install line; each catalog model present (its
folder) or the download line with its GB; CUDA visible to the engines or `CPU only (N cores)`; and the speech
servers Halo runs, with their model, device, url and `/health`.

## Settings

| Key | Default | What |
|---|---|---|
| `voice.stt_model` | `faster-whisper:small.en` | the STT model the voice loop transcribes with (R2 reads it) |
| `voice.tts_model` | `kokoro-82m` | the TTS model the voice loop speaks with (R2 reads it) |
| `voice.device` | `auto` | where a speech server runs when `--device` is not given |
| `voice.tts_voice` | `af_heart` | the Kokoro voice a request that names none speaks with |
| `huggingface.voice_server_cmd` | unset | the speech server program (the tests point it at a fake) |

They are in Studio's Settings -> Local and Settings -> Providers, from the settings catalog.
