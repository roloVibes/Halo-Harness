# Commands: halo voice and the speech servers

Read this when you list, download, remove or serve a speech model from the command line, or check the speech side of this machine.

`halo voice` (3.3.9.0 R1) is the speech catalog and its files; `halo local serve --stt | --tts` runs Halo's own speech
server for one of them. What the models are, the routes, the device choice and the steward's findings are in
[VOICE.md](VOICE.md). Part of [Commands](COMMANDS.md), which lists every part. Exit codes: 0 done, 1 could not (the
reason printed), 2 nothing to run (a declared model with no engine, the voice extra not installed: the one install
line `uv tool install --reinstall "halo-harness[voice]"`).

## `halo voice models`

```sh
halo voice              # the same as halo voice models
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
visible to the engines or `CPU only (N cores)`, and the running speech servers with their `/health`.
