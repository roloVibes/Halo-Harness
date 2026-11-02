# Voice through Meta's glasses: the phone-app contract

Read this when you want to build the phone app that carries Meta's Ray-Ban or Oakley glasses into a Halo session -- what the app has to do step by step, the host's voice door it talks to with a worked example, the latency budget, and the honest limits of the glasses.

**No phone app ships with Halo 3.3.9.0.** This page is the contract: the halo host's **voice door**
(`POST /host/v1/voice/turn`, [HOST.md](HOST.md#the-voice-door-3390-r3)) takes one utterance and streams the
reply's audio back, and `halo voice client --host <host>` ([COMMANDS-voice.md](COMMANDS-voice.md)) is its reference
client from any halo. The app between the glasses and that door -- an iOS or Android app on Meta's Wearables Device
Access Toolkit -- is yours to build; nothing here runs on the glasses or the phone. The loop itself is
[VOICE.md](VOICE.md).

## What is written from memory

Every line below about Meta's toolkit (the Wearables Device Access Toolkit, "DAT") comes from the research in the
plan (late 2026), not from Meta's documentation read for this page: the supported glasses, the HFP and in-stream
microphone paths and their rates, A2DP out, the fixed wake word and the "Hey Meta, start <app>" invocation, the
beta status of in-stream audio. Check each against Meta's current DAT documentation before you build on it. The
door's wire shape, the rates it takes and the latency it measures are Halo's own and are tested.

## The path, end to end

```
glasses mic --HFP or in-stream--> phone app --LAN, signed--> halo host on the PC --> stt server
                                                                  |                   session (its control socket)
glasses speakers <--A2DP-- phone app <--framed PCM stream------  <-- tts server
```

The PC does the work: its `halo host serve` holds the pairing, its speech servers hear and speak, a `halo` session on
it answers. The phone records, sends, and plays. The glasses are the phone's Bluetooth peripheral.

## What a phone app has to do

1. **Pair once.** The door is a signed route of `halo host`: the app holds a pair key the way a peer harness does.
   On the PC, `halo host pair` prints a six-word code; the app runs the same exchange `halo host join` runs
   (`POST /host/v1/join`, the fleet protocol's code-authenticated key exchange: `halo_harness/fleet/hub_join.py`,
   `host/join.py`) and keeps the key in the phone's keychain. On the PC, `halo host grant <app name> control`: the
   door needs the `control` grant. The key never leaves the phone and never goes in a log.
2. **Open the microphone.** Two ways, from the toolkit (from memory, see above):
   - **HFP Bluetooth capture**: mono 8-16 kHz, two-way. While HFP is open the glasses' A2DP output drops to voice
     quality: the reply plays through the same narrow link.
   - **In-stream PCM** alongside a camera stream: 16 kHz mono and A2DP stays full quality, but it is **beta and
     cannot ship in a production app**.
3. **Cut one utterance.** The app decides where speech starts and ends: a button, a tap on the glasses, or a VAD on
   the phone (the door does not listen continuously). Up to 30 seconds.
4. **Send it.** `POST /host/v1/voice/turn` with the PCM as the body (below). Resampling is the door's: send the rate
   you captured at (8,000-48,000 Hz) and say it in the Content-Type; the door resamples to the 16 kHz the stt hears.
5. **Play the reply as it streams.** Read the frames: the transcript first (show it), the audio rate, then PCM
   pieces as the tts server makes them -- play each on A2DP as it arrives; the first sentence plays while the
   session still writes the second. The trailer ends the turn.
6. **Start it.** A tap on the phone, or "Hey Meta, start <app>" -- that invocation exists but is experimental and
   unpublished (from memory): treat it as a bonus, not the way in. A custom wake word has to be detected on the
   phone, on audio the app streams itself.

## The door's wire shape

```
POST /host/v1/voice/turn?session=<id>&voice=<name>
Content-Type: audio/pcm;rate=16000          (16-bit little-endian mono; any rate 8,000-48,000) or audio/wav
X-Halo-Fleet-Member / -Ts / -Nonce / -Sig   the fleet protocol's HMAC headers (halo_harness/fleet/protocol.py)
<the utterance's bytes>
```

`session` is a session id (or its start) from `GET /host/v1/me`'s `voice.sessions`; with none, the one interactive
session on the PC. `voice` is a Kokoro voice (default: the PC's `voice.tts_voice`).

The timestamp must be within 120 s of the PC's clock and the nonce new (the replay guard). The answer is `200` with `Content-Type: application/x-halo-voice` and a stream of frames, each **one byte of kind,
four bytes of big-endian length, then the payload**:

| Kind | Payload | When |
|---|---|---|
| `J` | `{"heard": "what is in the readme"}` | first: the transcript the stt server made |
| `J` | `{"rate": 24000}` | before the first audio frame (again only if the rate changes) |
| `A` | PCM16 mono at that rate | the reply's audio, piece by piece, as the tts server makes it |
| `N` | `{"note": "..."}` | a line the audio does not say (a tts failure, the reply not ending within 600 s) |
| `J` | `{"done": true, "transcript", "reply", "rate", "audio_bytes", "card", "line", "session"}` | last: the trailer |

A refusal comes **before** any frame, as plain JSON `{"error": "<one line>"}`: `403` no `control` grant (the line
names the `halo host grant` command), `409` no session running on the PC, or no stt / tts server there (the line
names the `halo local serve` command), `413` past 30 s, `400` / `415` an audio shape the door does not read. A
failure after the stream started ends it with `J {"done": true, "error": "<line>"}`.

### A worked example

A 1.2 s question at 16 kHz is 38,400 bytes. The phone sends:

```
POST /host/v1/voice/turn HTTP/1.1
Host: 192.0.2.10:7431
Content-Type: audio/pcm;rate=16000
Content-Length: 38400
X-Halo-Fleet-Member: <the app's harness id>   X-Halo-Fleet-Ts: 1793600000.000   X-Halo-Fleet-Nonce: <16 bytes, hex>
X-Halo-Fleet-Sig: <HMAC-SHA256 with the pair key over the seven lines: halo-fleet-v1, POST, the path with its
                   query, the member, the ts, the nonce, the body's sha256 in hex -- joined by newlines>
```

and reads, in order: `J` (27 bytes) `{"heard": "what is in the readme"}`; `J` `{"rate": 24000}`; `A` frames of
4,800 bytes each (0.1 s of 24 kHz audio) -- play them; `J` `{"done": true, "transcript": "what is in the readme",
"reply": "The readme says how to install Halo. ...", "rate": 24000, "audio_bytes": 182400, "card": {"total_ms":
940, "stages": {"heard": 0, "text": 210, "token": 610, "audio": 120, "last": 3800}, "budget_ms": 1500}, "line":
"voice: 0.9 s of 1.5 s (heard 0.0 · text 0.2 · token 0.6 · audio 0.1)"}`. The PC's `halo voice stats` counts the
turn (`via: host`); its audit has one line `op: voice_turn` with the seconds and the session.

`halo voice client --host pc --input-file ask.wav --output-file reply.wav` does exactly this from any halo: the
reference to compare an app against.

## The latency budget

From the glasses' end of speech to the first sound back, **2-3 s** against Meta's own cloud path at about 1 s:

| Leg | Typical |
|---|---|
| glasses -> phone (Bluetooth) | 50-150 ms |
| phone -> PC (the LAN) | a few ms wired, more on Wi-Fi |
| stt on the PC | 50-300 ms |
| the model's first token | 0.1-1.3 s |
| tts to the first audio | 300-700 ms (Kokoro on a GPU is faster) |
| PC -> phone -> glasses (A2DP) | 150-300 ms |

The door's card measures the PC's part (text, token, audio); the Bluetooth and LAN legs are the app's to add. The
budget figures are the plan's research, not measured on glasses here: rolo's live check is where they get numbers.

## The limits, plainly

- No custom wake word on the glasses: "Hey Meta" is fixed; anything else is detected on the phone.
- No always-on background microphone stream from the glasses.
- In-stream audio is beta: not in a production app. HFP is the shippable path, and it narrows A2DP while open.
- No code and no UI on the glasses: the phone is always in the path.
- Meta AI stays on the glasses (their setup needs a Meta account); while the app owns the audio loop, Meta's servers
  are not in it.
- The door hears one utterance per request: barge-in is the app's (stop playing and send the next utterance; the
  session takes it as a steer when a turn is still running).
- Every number above is from the plan's research and from memory of the toolkit; none is measured on glasses yet.

## Prior art

Hobby projects that carry the glasses to a computer (names from the plan's research; their licences are not checked
here -- read each repository's own licence file before you reuse any of it):

- `charlie-robison/glasscode` -- glasses -> phone -> a Mac running faster-whisper and a coding agent: the closest
  match to this contract.
- `rayl15/OpenVision` -- iOS with local MLX models.
- `straff2002/OpenGlasses`.
- `farmountain/SmartGlass-AI-Agent`.

## See also

[VOICE.md](VOICE.md) (the loop, the latency card, the speech servers), [VOICE-cpu.md](VOICE-cpu.md) (a box with
no GPU), [HOST.md](HOST.md#the-voice-door-3390-r3) (the door among the host's routes), the `meta-glasses` bundle
([MODELS-bundles.md](MODELS-bundles.md)) -- it holds the small chat model and the speech picks; the phone app is
yours, the host door is here.
