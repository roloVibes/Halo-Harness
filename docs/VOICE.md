# Voice: talk to a session, the speech models and Halo's speech server

Read this when you want to talk to a Halo session and hear it answer on your own machine, or want speech-to-text or text-to-speech locally: the voice loop, its modes, barge-in and latency card, the voice-local bundle, the speech models Halo knows, how to download and serve one, where it runs, and what the steward says about it.

Voice is Halo 3.3.9.0. **Round R2, the loop**: you talk to a Halo session and hear it answer, with no cloud in the
loop -- the microphone, Silero VAD, speech-to-text, the session's model, a sentence aggregator, text-to-speech and the
speaker, with barge-in, push-to-talk and a latency card per turn. **Round R1, the speech servers** (the second half of
this page): a speech model is a file-backed local model like any GGUF -- present or absent, downloadable, served,
fitted into a bundle's verdict, and watched by the steward. The commands are in [COMMANDS-voice.md](COMMANDS-voice.md);
**Round R3**: the speech servers and the voice door [through the host](#through-the-host), Studio's Local -> Voice
with a Talk button ([STUDIO-local-voice.md](STUDIO-local-voice.md)), and the glasses contract.

## The loop

```sh
halo voice                 # halo with voice on (the TUI, then /voice on)
```

Then speak. The loop (`halo_harness/voice/loop.py`, `speak.py`, `aggregate.py`, `latency.py`):

1. **the microphone** -- sounddevice, 16 kHz mono 16-bit PCM in 32 ms frames, the device `voice.input_device` (by
   index or part of its name; `halo voice devices` lists them and marks the one in use), else the system default;
2. **Silero VAD** -- the catalog's `silero-vad` through onnxruntime: speech starts after three voiced frames (about
   100 ms) and ends after 250 ms of quiet. Without `silero-vad` on disk a level gate stands in, said in one line with
   `halo voice download silero-vad` (2 MB);
3. **speech-to-text** -- the utterance goes to the `stt` speech server as a raw `audio/pcm;rate=16000` body; while you
   still speak, a partial transcript every second shows in the status bar (`you: what is in the ...`);
4. **the session** -- the final transcript is submitted through the session exactly as typed text: the transcript
   shows `you said: what is in the readme`, and a transcript that arrives while a turn runs **steers** it, as typed
   text would (`you said: no, the license (steers the running turn)`);
5. **the reply** -- a listener on the session's event sink takes the main agent's text as it streams; the **sentence
   aggregator** cuts it at `.`, `?` or `!` before a space, at a newline, or at 200 characters, and skips what is not
   speech: a fenced code block is said once as "a code block", tool-call lines and `[...]` markup are never said, a
   link keeps its text, markdown marks go;
6. **text-to-speech and playback** -- each sentence goes to the `tts` speech server (`voice.tts_voice`, pcm streamed)
   and plays on `voice.output_device` as its chunks arrive: the first sentence speaks while the model still writes
   the second.

Every step is a `voice` event on the session's event sink, so the TUI draws it (the status bar's `mic` chip:
`mic: listening`, `mic: speaking`; the partial transcript; the echo; the latency line) and the control socket's feed
carries it to anything subscribed.

## Voice in a session

```
/voice on          # hands-free (voice.mode), starting the speech servers it needs
/voice ptt         # push-to-talk
/voice status      # on or off, the stt and tts picks and where they run, the budget, the last turn's card
/voice off         # stops the loop and the speech servers it started
```

`halo voice on` and `halo voice off` do the same in a running session from another terminal, through its control
socket (the `slash` command the socket already carries; `--session ID` when several run). Every missing piece is one
line with its command: the extra (`uv tool install --reinstall "halo-harness[voice]"`), a microphone (`halo voice
devices`; `--input-file` without one), a speech model (`halo voice download <model>`).

## The modes

- **hands-free** (the default, `voice.mode: hands-free`): the VAD decides when you started and stopped; a pause of
  250 ms sends what you said.
- **push-to-talk** (`/voice ptt`, `voice.mode: ptt`): nothing is heard until you press `Ctrl+Space` in the TUI
  (`voice.ptt_key` binds another key); the second press sends it. A terminal sends no key release, so it is press,
  talk, press.

## Barge-in

Speak over a reply and it stops: speech that starts while a reply is queued, playing or still being written stops the
playback at once -- within the three voiced frames the VAD needs, about 100 ms, inside the ~250 ms Part K asks -- and
the rest of that reply is never spoken. The transcript says `(interrupted while speaking)`, and what you say next goes
to the session as a steer when the turn still runs (else as the next turn). The speaker stays quiet until the
session's next model call, so the old reply's tail never sneaks out. The loop has no echo canceller of its own: on
open speakers the microphone can hear the reply and stop it, so use a headset (or the system's echo cancellation),
or push-to-talk.

## The latency card

Each turn leaves one card: the stages, each in ms --

| Stage | From -> to |
|---|---|
| `heard` | your last speech -> the VAD's end (the 250 ms of quiet, mostly) |
| `text` | the VAD's end -> the transcript back from the `stt` server |
| `token` | the transcript -> the reply's first text (the model, its load if it was not resident) |
| `audio` | the first text -> the first sound (the aggregator's first sentence through the `tts` server) |
| `last` | the first sound -> the last one (how long it spoke) |

The total is your last speech to the first sound, against the budget: `voice.latency_budget_ms`, else the voice
bundle's `latency_budget_ms`, else 1,500 ms (Part K's measured fully local loop is 750-900 ms: the target). After each
turn the status bar says it in one line:

```
voice: 1.0 s of 1.5 s (heard 0.2 · text 0.3 · token 0.4 · audio 0.1)
voice: 1.7 s, over the 1.5 s budget (heard 0.2 · text 0.3 · token 1.1 · audio 0.1) -- slow: token
```

A stage's share of the budget is heard 20 %, text 25 %, token 40 %, audio 15 %. The cards are kept in
`~/.halo/voice/turns.jsonl`; `halo voice stats` prints the median and the worst per stage over the newest 50 turns and
names the slow stage. When one stage runs over its share three turns running the steward says **`voice-slow`** (on the
Steward page and in `halo ollama steward findings`), with the fix line: `text` on the CPU -> `--device cuda` or
`faster-whisper:small.en`; `token` -> the chat model was loading: a voice bundle's reservation keeps it resident
(`halo pack on voice-local`); `audio` -> Kokoro on the CPU is ~100 ms, check `tts-slow`; `heard` -> `halo voice
download silero-vad`.

## The servers the loop starts

`/voice on` uses the `stt` and `tts` speech servers that run; for a kind with none it starts R1's server (`halo local
serve --stt | --tts`), the cost line first -- the device, the RAM or VRAM and the seconds to load:

```
starting stt: faster-whisper:small.en on the CPU: 0.9 GB RAM, the GPU keeps its 22,000 MiB for the chat model (auto: the engines see no CUDA device) -- ~5 s to load (halo local serve --stt faster-whisper:small.en --device cpu)
```

The picks: a voice bundle that is on (`voice-local`, `meta-glasses`) picks with its verdict's rule -- a present model of
its `any_of`, on the device its need allows; else `voice.stt_model` and `voice.tts_model` on `voice.device`. `/voice
off` stops the servers this loop started and never one it found running. A bundle never starts a process: a claim is
a claim, and the loop starts what it needs.

## The bundle

`voice-local` (`templates/bundles/voice-local/pack.yaml`) is the bundle for talking to a session on this machine: a
small chat model kept resident (`any_of: [lfm3:1.7b, qwen3.8:4b, gemma4:4b]`, window 8192, `keep_alive: -1`, priority
high), `stt` on `cpu-or-gpu` (`faster-whisper:large-v3-turbo` or `small.en`), `tts` on the CPU (`kokoro-82m`),
`latency_budget_ms: 1500`, task work to the coder when it fits beside it, else the cloud.

```sh
halo pack verdict voice-local     # ready, needs downloads, or won't work -- before anything downloads
halo pack on voice-local          # claims the reservation and says what it reserved
```

With the bundle on, `/voice on` takes its speech picks and its budget, and says which model it keeps resident when the
session answers with another (`/model ol:lfm3:1.7b@<host>` answers from it). `meta-glasses` carries the same fields
(its reservation names its 8 k window); the glasses reach the loop through a phone app and the host's voice door
([VOICE-glasses.md](VOICE-glasses.md): the phone app is yours, the door is here).

## Without a microphone

```sh
halo voice --input-file ask.wav                          # one turn from a WAV, the reply on the speaker
halo voice --input-file ask.wav --output-file reply.wav  # no audio device at all
```

The WAV (any rate, mono or stereo, 16-bit) goes through the same loop as one utterance: the echo, the reply (spoken,
or written to `--output-file` at 24 kHz), its card in `turns.jsonl`. It is the headless path and the one the tests use
(`HALO_VOICE_AUDIO=fake`, see [DEVELOPMENT.md](DEVELOPMENT.md#the-fake-audio-3390-r2)).

## Through the host

(3.3.9.0 R3.) A paired `halo host` lists its `stt` / `tts` servers among its served rows (`kind: speech`, their
model), and serves them to its peers through two signed routes, `POST /host/v1/voice/stt` and `voice/tts` -- the
speech servers keep listening on loopback only. A box with no GPU sets `halo config set voice.stt_server stt@pc` (and
`voice.tts_server tts@pc`): its loop hears and speaks with the PC's models, `/voice on` says `stt on pc over the LAN
(+1.8 ms): faster-whisper:large-v3-turbo`, and every latency card adds the `link` stage (the TCP round trip to the
host's port, measured once when the loop starts) beside heard, text, token and audio. [VOICE-cpu.md](VOICE-cpu.md) is
the whole CPU-box story.

The host's **voice door**, `POST /host/v1/voice/turn` (the `control` grant), takes one utterance -- 16-bit mono PCM
at 8-48 kHz or a WAV, up to 30 s -- runs it through a session on the host machine exactly as `/voice` does (its stt
server, the session's control socket, the sentence aggregator, its tts server) and streams the reply's audio back
(framed: the transcript, the rate, PCM pieces, the trailer with the reply and the card). `halo voice client --host
pc --input-file ask.wav` is its reference client from any halo; `GET me` lists the door, its grant, the speech servers
and the sessions it reaches. It is the one door a phone app for Meta's glasses needs: the contract, its wire shape
and the glasses' limits are [VOICE-glasses.md](VOICE-glasses.md) -- no phone app ships with Halo.

In Studio, **Local -> Voice** ([STUDIO-local-voice.md](STUDIO-local-voice.md)) shows the servers, the catalog, the
last cards, and **Talk**: the browser's microphone into the same turn, the reply played in the page. Later: the
one-model options (`lfm3-omni`, `phonon`) and a cloned voice (Qwen3-TTS from a ~3 s reference).


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
| `silero-vad` | VAD | silero-vad | 0.002 GB | -- | 0.05 GB | built (the loop's VAD, no server) |

**Built** means this build has an engine for it: faster-whisper through CTranslate2 (int8 on the CPU, float16 on
CUDA), Kokoro through kokoro-onnx (onnxruntime) and Silero VAD through onnxruntime in the loop. A **declared** model is listed, downloadable and fitted, but
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

It adds `faster-whisper`, `kokoro-onnx`, `onnxruntime`, `numpy`, `soundfile` and (R2) `sounddevice` for the
microphone and the speaker; on Linux sounddevice needs PortAudio from the system (`sudo apt install libportaudio2`,
[INSTALL.md](INSTALL.md)). Without it, `halo voice models`, `download`, `rm`, `devices`, `stats` and `halo doctor
--voice` work as usual, and every command that would load an engine or open a device (`halo voice`, `/voice on`,
`halo voice serve`, `halo local serve --stt | --tts`) prints that one install line and exits 2.

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
it takes. Other audio formats (mp3, ogg) are not decoded: the voice loop sends PCM.

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

A fifth, `voice-slow` (R2), reads the loop's own cards: [the latency card](#the-latency-card). `halo ollama explain
stt-slow` prints each row. See [MODELS-steward-servers.md](MODELS-steward-servers.md).

## Doctor

`halo doctor --voice` says, one line each: the extra installed or the install line; each catalog model present (its
folder) or the download line with its GB; CUDA visible to the engines or `CPU only (N cores)`; the microphone and the
speaker the loop opens (or the install line); and the speech servers Halo runs, with their model, device, url and
`/health`.

## Settings

| Key | Default | What |
|---|---|---|
| `voice.stt_model` | `faster-whisper:small.en` | the STT model the loop starts when no voice bundle is on |
| `voice.tts_model` | `kokoro-82m` | the TTS model the loop starts when no voice bundle is on |
| `voice.device` | `auto` | where a speech server runs when `--device` is not given |
| `voice.tts_voice` | `af_heart` | the Kokoro voice a request that names none speaks with |
| `voice.input_device` / `voice.output_device` | the system's | the microphone and the speaker, by index or name |
| `voice.mode` | `hands-free` | `hands-free` (the VAD) or `ptt` (push-to-talk) |
| `voice.ptt_key` | `ctrl+space` | the TUI's push-to-talk key |
| `voice.latency_budget_ms` | the bundle's, else 1500 | what the latency card measures a turn against |
| `huggingface.voice_server_cmd` | unset | the speech server program (the tests point it at a fake) |

They are in Studio's Settings -> Local and Settings -> Providers, from the settings catalog.
