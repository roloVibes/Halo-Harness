# Voice on a box with no GPU

Read this when you want the voice loop on a machine with no GPU (a Kali VM, a laptop, a small server): which speech models to run on the CPU, how to point the loop at another halo's GPU instead, and how to read what it measures.

Two ways, and you can mix them per kind: run the speech models **on this CPU**, or hear and speak with **another
halo's speech servers** over the LAN through its `halo host`. The loop, its card and its commands are the same either
way ([VOICE.md](VOICE.md)). No figures are given here: what a CPU does is yours to measure, and this page says how.

## Ask the doctor first

```sh
halo doctor --voice
```

On a box whose engines see no CUDA device it says `CPU only (N cores)` and then the pair to run:

```
INFO  the CPU pair: faster-whisper:base.en (int8, 0.4 GB RAM; faster-whisper:small.en hears better at 0.9 GB)
      + kokoro-82m (0.5 GB) -- halo config set voice.stt_model faster-whisper:base.en; halo config set voice.device
      cpu; or a GPU halo's servers: halo config set voice.stt_server stt@<host> (docs/VOICE-cpu.md)
```

With `voice.stt_server` or `voice.tts_server` naming a host, the same step says `speech through another halo on the
LAN (stt: stt@pc)` instead.

## On this CPU

```sh
uv tool install --reinstall "halo-harness[voice]"     # the engines and sounddevice (Linux: sudo apt install libportaudio2)
halo voice download faster-whisper:base.en            # or small.en: better hearing, more work per second of audio
halo voice download kokoro-82m
halo voice download silero-vad
halo config set voice.stt_model faster-whisper:base.en
halo config set voice.device cpu
halo voice
```

- **Speech-to-text**: `faster-whisper:base.en` or `faster-whisper:small.en`, both int8 on the CPU (CTranslate2 picks
  int8 when `--device cpu`). base.en is the lighter; small.en hears names and code words better. large-v3-turbo on a
  CPU is past a voice loop's budget on most boxes.
- **Text-to-speech**: `kokoro-82m` (onnxruntime) runs on the CPU in every pairing; it is the one TTS built.
- **The VAD**: `silero-vad` is 2 MB and runs on the CPU everywhere.
- Every `halo local serve --stt | --tts` start says its cost line first: the device, the RAM, about how many seconds
  to load.

## On another halo's GPU

On the PC (the machine with the GPU): `halo local serve --stt faster-whisper:large-v3-turbo` (or small.en),
`halo local serve --tts kokoro-82m`, `halo host serve`, `halo host pair`. On this box: `halo host join <its address>
<code>`, then

```sh
halo config set voice.stt_server stt@pc
halo config set voice.tts_server tts@pc
halo voice
```

The loop hears and speaks through the PC's halo host (`POST /host/v1/voice/stt`, `voice/tts`: signed with the pair
key, one audit line each; the speech servers there keep listening on loopback only). `/voice on` says `stt on pc over
the LAN (+N ms): <model>` for each, and every latency card adds it: `voice: 0.9 s of 1.5 s (heard 0.0 · text 0.3 ·
token 0.5 · audio 0.1); stt on pc over the LAN (+1.8 ms), tts on pc over the LAN (+1.8 ms)`. The `+N ms` is the TCP
round trip to the host's port, measured once when the loop starts, the way a LAN bench measures its link. A host that
lists no stt server says the one line to start it there. Mixed works too: `voice.tts_server: local` keeps Kokoro on
this CPU while the PC hears.

On a box with no microphone at all, Studio's **Local -> Voice -> Talk** uses the browser's microphone
([STUDIO-local-voice.md](STUDIO-local-voice.md)), and `halo voice client --host pc --input-file ask.wav` sends one
turn to a session on the PC.

## What to measure, and how to read it

1. Five or six turns of ordinary speech, then `halo voice stats`: the median and the worst per stage over the newest
   50 turns against the budget (1,500 ms unless `voice.latency_budget_ms` or the bundle says), the slow stage named.
   `link` is listed beside the stages when a server is on another halo (inside text and audio already, not added).
2. Read the stages: **text** is the stt server's time (the CPU's share for speech-to-text), **audio** the tts server's
   time to the first sound, **token** the model's first token (not the CPU's when the session's model runs elsewhere).
3. `voice-slow` (the steward, `halo ollama steward findings`): a stage over its share of the budget -- heard 20 %,
   text 25 %, token 40 %, audio 15 % -- three turns running, with its fix line. On a CPU box the usual ones are `text`
   (try base.en, or `voice.stt_server: stt@<a GPU halo>`) and `audio` (`tts-slow`: Kokoro's first audio past 400 ms).
4. `halo local log stt` shows each transcription's realtime factor ("audio 4.2 s -> text in 0.31 s (13.5x
   realtime)"); under 2x realtime the steward says `stt-slow`.

Write down the CPU, the cores, the model and the medians: that is the number this page does not have yet.
