# Commands: halo voice, the voice loop and the speech servers

Read this when you talk to a session from the command line (`halo voice`, `halo voice on|off`, an input file, `halo voice client` through a halo host), list the microphones, read the voice turns' latency, or list, download, remove or serve a speech model.

`halo voice` (3.3.9.0 R2) opens a session with voice on; `halo voice on|off` turns it on or off in a running one,
`devices` and `stats` read the microphones and the turns' latency cards. `halo voice models | download | rm | serve`
(R1) are the speech catalog and its files; `halo local serve --stt | --tts` runs Halo's own speech server for one of
them. What the loop does, the models, the routes, the device choice and the steward's findings are in
[VOICE.md](VOICE.md). Part of [Commands](COMMANDS.md), which lists every part. Exit codes: 0 done, 1 could not (the
reason printed), 2 nothing to run (a declared model with no engine, the voice extra not installed: the one install
line `uv tool install --reinstall "halo-harness[voice]"`).

## `halo voice`

```sh
halo voice [halo flags]          # halo with voice on: the TUI, then /voice on (voice.mode ptt: /voice ptt)
halo voice --model ol:lfm3:1.7b@pc
```

The flags are `halo`'s own. Without the voice extra it prints the one install line and exits 2 before anything
starts. In the session, `/voice off`, `/voice ptt` and `/voice status` work as typed
([SLASH-COMMANDS-session.md](SLASH-COMMANDS-session.md)).

## `halo voice --input-file`

```sh
halo voice --input-file ask.wav [--output-file reply.wav] [halo flags]
```

One turn from a WAV, no microphone: the file goes through the loop as one utterance, then `you said: ...`, the reply
(spoken on the speaker, or written to `--output-file` as a 24 kHz WAV, no audio device opened), `reply: ...` and the
turn's latency line. It starts the speech servers it needs like `/voice on` and stops them after. Exit 0 with a
reply, 1 without one.

## `halo voice on` and `halo voice off`

```sh
halo voice on [ptt] [--session ID]
halo voice off [--session ID]
```

Voice on or off in a halo that runs here, through its control socket (`/voice on` arrives there as typed). With
several sessions running it lists them and asks for `--session`; with none it says `halo voice` opens one.

## `halo voice client`

```sh
halo voice client --host pc --input-file ask.wav [--output-file reply.wav] [--session ID] [--voice af_heart] [--json]
halo voice client --host pc --mic
```

(3.3.9.0 R3.) One turn through a paired halo host's voice door (`POST /host/v1/voice/turn`,
[HOST.md](HOST.md#the-voice-door-3390-r3)): the utterance -- a 16-bit WAV at any rate from 8 to 48 kHz, or `--mic`,
the microphone until a 250 ms pause (the voice extra) -- goes to the host; it prints `you said: ...`, plays the reply's
audio as it streams (or writes it to `--output-file` as a WAV), then `reply: ...` and the latency card measured on
the host. `--session` picks a session there (default: the one running), `--json` prints the trailer. It needs the
`control` grant on the host; each refusal is the host's one line (exit 1). It is the reference a phone app for the
glasses is checked against ([VOICE-glasses.md](VOICE-glasses.md)).

## `halo voice devices`

```sh
halo voice devices [--json]
```

The microphones and the speakers, the ones the loop opens marked `*` (`voice.input_device`, `voice.output_device`,
else the system default); no microphone says `halo voice --input-file <wav>`. Without sounddevice: the install line,
exit 2.

## `halo voice stats`

```sh
halo voice stats [-n 50] [--json]
```

The newest turns' latency cards (`~/.halo/voice/turns.jsonl`): the total and each stage (heard, text, token, audio,
last) with its median and worst in ms, each stage's share of the budget, and the slow stage named; 3.3.9.0 R3: `link`,
the LAN round trip, when a speech server is on another halo (`voice.stt_server: stt@pc`).

## `halo voice models`

```sh
halo voice models --json
```

The seven speech models with their kind (stt, tts, vad), engine, repo (marked `(repo unverified)` while the id is from
memory), footprint on a GPU and on the CPU, built or declared, and present or the download line with its GB; the last
line says whether the engines are installed.

## `halo voice download`

```sh
halo voice download faster-whisper:small.en [--dir <huggingface.model_dirs folder>] [--yes]
```

The size, the repo and the folder first, then the licence line and the files, then it asks (`--yes` does not; with no
terminal it prints the line to run). The hub download `halo local download` makes, cut to the files the engine loads;
Ctrl+C keeps the part file and the same line resumes. A present model says where it is.

## `halo voice rm`

```sh
halo voice rm faster-whisper:small.en [--force]
```

Deletes the model's files (its hub repo folder). Not while a speech server serves it: `halo local stop stt` first.

## `halo voice serve`

```sh
halo voice serve faster-whisper:small.en [--device auto|cpu|cuda] [--port 0] [--log <file>] [--voice af_heart]
```

The speech server in the foreground (Ctrl+C stops it): `listening on 127.0.0.1:<port>`, then the model loads and the
OpenAI audio routes answer. `--path` names the model's folder when it is not where `halo voice download` put it.

## `halo local serve --stt` and `--tts`

```sh
halo local serve --stt faster-whisper:small.en --device cpu
halo local serve --tts kokoro-82m [--port P] [--keep] [--json]
```

Runs the speech server in the background as the managed server `stt` or `tts`: the device line ("faster-whisper:
small.en on the CPU: 0.9 GB RAM, the GPU keeps its 22,000 MiB for the chat model"), the command line, the URL and the
route. `--device` defaults to `voice.device` (`auto`). It registers the `huggingface.local_servers` entry of the same
name (runtime `voice-stt` / `voice-tts`); `halo local servers` lists it with its device, `halo local log stt` reads
its log, `halo local stop stt` stops it. A second `serve --stt` while one runs says the running one.

## `halo doctor --voice`

```sh
halo doctor --voice [--json]
```

The speech side, one line each: the extra or the install line, each catalog model present or its download line, CUDA
visible to the engines or `CPU only (N cores)` -- then (3.3.9.0 R3) the recommended CPU pair with its commands, or
the other halo's speech servers it uses ([VOICE-cpu.md](VOICE-cpu.md)) -- and the running speech servers with their
`/health`.
