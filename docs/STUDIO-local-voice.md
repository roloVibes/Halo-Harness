# Studio: Local -> Voice

Read this when you talk to a Halo session from Studio with your browser's microphone, start or stop the speech servers, download a speech model, turn a session's voice loop on or off, or read the last turns' latency cards.

Part of [Halo Studio](STUDIO.md), which lists every part. The other Local pages are in
[STUDIO-local.md](STUDIO-local.md); the voice loop, its latency card and the speech servers are in
[VOICE.md](VOICE.md).

## The Voice page (3.3.9.0 R3)

Local's tenth page. It reads its view when it opens and every 15 seconds while it shows; nothing starts, downloads
or records on a page load. Its first line is the glasses note: no phone app ships with Halo -- the halo host's voice
door is the contract a phone app talks to ([VOICE-glasses.md](VOICE-glasses.md)), the app is yours to build. Then
three blocks.

### Talk

**Talk** is this browser's microphone into a Halo session -- the same turn the terminal's voice loop makes, with no
PortAudio, no extra and no device on the client: the easiest way to talk to Halo from the Mac or from Kali.

- **The session.** A select of this machine's running sessions (Session's chosen one first). Beside it the session's
  own voice loop: **Voice on** / **Voice off** and **Push-to-talk** send `/voice on | off | ptt` through its control
  socket -- that loop uses the microphone of the machine the session runs on, not this browser's.
- **What it does and costs, said first.** The button's title says it, and the first press shows it before anything
  happens: the browser asks for the microphone (once, its own prompt), records until the next press (up to 30 s),
  sends it to the speech-to-text server, puts the transcript to the session exactly as typed text, and plays the
  reply's audio here; the speech servers it starts (each with its cost line: device, memory, about how many seconds to
  load) or that they are running; a local turn costs time, not dollars. **Start talking** begins; **Cancel** closes it.
- **Press, speak, press again.** After the first confirmation a press records (the button reads **Send**) and the
  next press sends: press-then-press, like the TUI's push-to-talk (a page could hold a key, but one way for both keeps
  them the same).
- **The turn.** The utterance goes as 16-bit mono PCM at the browser's rate (the server resamples it to the 16 kHz
  the stt hears) to `POST local/voice/talk`; the turn runs on Studio's side (`voice/turn.py`: the stt server, the
  session's control socket, the sentence aggregator, the tts server), and its `talk` frames come back over the live
  feed: `you said: ...`, the reply's audio played as it arrives (one audio buffer per piece, back to back, the first
  sentence while the model writes the second), the reply's text, its latency card's line. The audio element under it
  (the sink) holds the whole reply as a WAV to play again. A speech server Talk started keeps running for the next
  turn (Stop it below).

What the browser needs: a page on `127.0.0.1` or `localhost` (a secure context: `getUserMedia` is offered only
there, and Studio is served there; over SSH forward the port as `halo studio` says), the microphone permission, and
Web Audio. A browser that gives no microphone says so beside the button.

### The speech servers and the catalog

One row each for **speech-to-text** and **text-to-speech**: running (its model, device and url, **Stop** --
`halo local stop <kind>`), stopped (the model it would start -- the on voice bundle's pick, else `voice.stt_model` /
`voice.tts_model` -- and the cost line said before **Start**: `starting tts: kokoro-82m on the CPU: 0.5 GB RAM ... --
~3 s to load`), or on another halo (`voice.stt_server: stt@pc`: said with its setting; nothing to start here). The
steward's findings for that server sit under it (`stt-slow`, `tts-slow`, `voice-cpu`, `voice-load-failed`).

The catalog lists the seven speech models: kind, engine (the repo on hover, "repo unverified" until a live download
confirms it), the download size and the footprint on a GPU and on the CPU, and **present** (its folder on hover) or
**Download**. Download first shows the size line -- `faster-whisper:base.en: 0.15 GB from Systran/faster-whisper-base.en
(repo unverified) into <the model folder>` -- and starts only on its second press, as the 3.3.5.0 download job (its
progress is the Hugging Face page's, `download` frames). A declared model (Parakeet, Qwen3-TTS) says it has no engine
in this build.

### The last turns and the devices

The newest ten latency cards, newest first, each marked by where it came from (the terminal loop, Talk: `studio`,
the voice door: `the voice door`); `halo voice stats` over the newest 50 (the median and worst per stage against the
budget, the slow stage named; `link` when a server is on another halo); the steward's `voice-slow` when a stage ran
over its share three turns running. Last, this machine's microphones and speakers (`halo voice devices`): the
terminal loop's devices -- Talk uses the browser's.

## The routes

All under `local/` (studio/voice_api.py and studio/voice_act_api.py, dispatched by studio/local_api.py), the same
loopback / origin / token guard as every Studio route; never a model call -- the speech servers and the session do the
work. Each acting answer carries `cli`, the command that does the same.

| Route | Answers |
|---|---|
| `GET local/voice?session=<id>&loop=1` | `servers` (each kind: running, url, model, device, or the cost line; `remote` for another halo's; its `findings`), `catalog`, `devices`, `sessions`, `loop` (that session's `/voice status`, read only with `loop=1`: the page asks on open, on a pick and after a loop button, not on its 15 s refresh, since each ask is a line in that session's transcript), `turns` (the newest ten cards with their lines), `stats` (with its lines), `talk` (`confirm`: what Talk does and costs; `starts`), `findings` |
| `POST local/voice/server {kind, op: start \| stop, model?, device?}` | R1's `halo local serve --stt \| --tts` with the cost line in `lines` (409 with the one line when it does not start), or `halo local stop <kind>` |
| `POST local/voice/download {model, yes?}` | without `yes`: `confirm`, the size line; with `yes`: the download job's view (`download` frames); a model on disk answers `present` |
| `POST local/voice/loop {session, op: on \| off \| ptt}` | `/voice <op>` in that session through its control socket; its lines |
| `POST local/voice/talk {pcm_b64, rate, session}` | 202 `{job, session, seconds}`; refused first with one line: past 30 s, no session, a rate outside 8,000-48,000 Hz |
| `GET local/voice/talk?job=` | the job's view (a page that opened late catches up) |

The `talk` frames (`session_id: "local"`, `event: "talk"`): `{job, seq, session, done, state}` with `state` `start`
(the seconds heard), `note` (a cost line, a tts failure), `heard` (`text`: the transcript), `audio` (`audio_b64`,
`rate`, `bytes` so far: about 0.25 s of audio a frame), `done` (`transcript`, `reply`, `line`, `card`, `bytes`) or
`error` (`error`: the one line). Each Talk turn's card lands in `<state>/voice/turns.jsonl` with `via: studio`.

The page's shell serves `media-src 'self' blob:` in its CSP so the sink can play the reply's WAV; nothing else
changed in what a Studio page may load.
