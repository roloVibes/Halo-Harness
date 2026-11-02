# Models: bundles and reservations

Read this when you want to turn on a capability that holds a local model for one use (voice, a verifier, a compactor, embeddings) and need to know before anything downloads whether it fits, what it reserves and where the rest of the work goes.

Part of [Models](MODELS.md), which lists every part.

## A bundle is a pack with a resource claim (3.3.7.0 R5)

A **bundle** is a pack ([PACKS.md](PACKS.md)) with one more block in its `pack.yaml`, `bundle:`, that says four
things: what it **needs** (each role and the models that can fill it, best first, with a window and a device), what
it **reserves** (the model it holds for as long as it is on), where the **other work** goes while it is on, and its
**latency budget**. The contract is in [EXTENSION_API.md](EXTENSION_API.md#bundles); the voice bundle as Halo ships it:

```yaml
bundle:
  needs:
    chat: {any_of: [lfm3:1.7b, qwen3-coder:30b-gpu], window: 8192}
    stt:  {any_of: [faster-whisper:large-v3-turbo, faster-whisper:small.en], device: cpu-or-gpu}
    tts:  {any_of: [kokoro-82m], device: cpu}
  reservation: {model: lfm3:1.7b, vram_gb: 1.2, keep_alive: -1, priority: high}
  routing: {task_work: coder-or-cloud, never_evict: reserved}
  latency_budget_ms: 1500
```

In Studio the Pack Manager shows each bundle as a **tick** with one line under it (Packs -> Installed, the Bundles
group); from a terminal `halo pack verdict <bundle>`, `halo pack on | off <bundle>` and `halo pack list --bundles`
([COMMANDS-packs.md](COMMANDS-packs.md#bundles)).

## The honest verdict

Before anything downloads, `local_sched/bundle_fit.verdict` does the arithmetic -- no model is asked: the weights
plus the KV at each need's window plus the per-card reserve, against the usable memory (the card's budget, minus
what other programs hold, minus the duty steward's helper; a paired halo host's `route` answer when one serves the
card) minus the other bundles' reservations. A need is filled by the first of its `any_of` that is installed there
(else the first with a known size: a download); a speech need resolves through the speech catalog (see "Speech needs
resolve" below); a `verify` role never takes the coder's own family; `vision: true` takes only a model that sees. Three
outcomes, one line each:

    ready      fits today -- 1.2 GB reserved leaves ~20.8 GB, the coder (18.9 GB) still fits beside it, barely;
               latency not measured yet (...); stt (faster-whisper:small.en) and tts (kokoro-82m) on the CPU: no VRAM
    downloads  needs 1 download (0.3 GB, ~1 min): nomic-embed-text (0.3 GB, fits); then fits today -- ...
    won't work won't work -- this bundle needs 27.8 GB; you have 22.0 GB usable

With the speed card of the reserved model the line says the expected latency against the budget ("expected latency
~500 ms (first token 300 ms + a 24-token sentence at 120 tok/s) (within the 1500 ms budget)"). A card that was not
read, or a model whose size nothing knows, is "not judged" -- nothing is guessed.

Every verdict lists the ways out, each a number: a speech model on the GPU run on the CPU instead ("run stt on the
CPU instead of the GPU (-1.5 GB)"), a smaller model of the need's own list ("the 1.5B qwen2.5:1.5b instead of the
9.0B qwen3.5:9b for chat (-5.4 GB)"), a smaller window ("the coder's window 32 k -> 16 k frees 0.8 GB"), another
bundle turned off, an installed model like one it would download; and, on a bundle that fits, what would break it:
"GPU STT (faster-whisper:large-v3-turbo, 1.5 GB) would break that: the coder would no longer fit beside it".

The one button ("download 1 (0.3 GB, ~1 min)") starts the existing Download and verify job for each tag it names
(Local -> Library's: the pull, then the battery). Nothing downloads before it is pressed.

## Turning one on: the reservation

Only a ready bundle turns on. Ticking it (or `halo pack on <bundle>`) installs and enables the pack, records the
claim -- on the paired halo host when one serves the card (`control/claim`; `GET residency` answers the claims, so
every peer reads one list), else in this machine's `<state>/ollama/claims.json` -- and writes `keep_alive -1` on the
reserved model's profile, Halo-side, as a change ([scopes](MODELS-ollama-steward.md)): kept until `halo pack off`
from the CLI, undone when unticked or when that Studio exits from Studio. Nothing loads: the reserved model loads on
its first call (or `halo local warm <model>`).

While it is on, the claim counts in every budget line -- the Hosts card, `halo local hosts`, the Cost panel and the
verdicts all say "1.2 GB reserved for meta-glasses; 20.8 GB free for tasks" -- and nothing Halo does evicts it:

- the host's invariants refuse a load that would breach what is left, in the claim's own words ("qwen3.8:27b would
  need 18.9 GB with voice's 4.0 GB held; 18.0 GB free -- queued behind voice (halo pack off voice frees it)"), and an
  unload or a pivot of the reserved model ("lfm3:1.7b is reserved for meta-glasses on pc (1.2 GB held): nothing
  evicts it until the bundle is turned off");
- the scheduler's pivot never unloads it and never loads past it (the same lines, on a card no host serves);
- the degradation ladder never takes a reserved model as a rung's target, and counts the claims for a bigger one;
- the offline-only bundle turns the cloud rung off for every session while it is on (`routing.escalation` reads as
  unset: "the offline-only bundle is on: no cloud rung").

## Routing around a reservation

Task work goes elsewhere with one visible line instead of evicting the reserved model: a lane spawned on a model that
no longer fits beside the claim goes to `routing.escalation.to` (else main's model) -- "fit: coder on qwen3-coder:30b
does not fit beside main ... : voice holds 4.0 GB; sending this task to or:vendor/cloud-model rather than evicting
it"; the placement solver (`halo local place`) takes the claims as an input and moves a lane to another host -- "meta-
glasses holds 15.0 GB on pc; worker goes to samus rather than evicting it"; the warm set counts the claim and names it.

## Several reservations, a schedule, a priority (3.3.8.0 R4)

A bundle may hold more than one thing, on more than one machine, for part of the day, and say what gives way:

```yaml
bundle:
  needs:
    reasoner: {any_of: [qwen3-next-80b-a3b-q4km, gpt-oss-120b], window: 32768}
    coder: {any_of: [qwen3-coder:30b, qwen3.8:27b], window: 32768, tools: true}
  reservations:
    - {model: reasoner, host: pool}      # the pool for the reasoning lane
    - {model: coder, keep_alive: -1}     # the coder resident on this machine's card
  schedule: {hours: "09:00-18:00"}       # optional: the hours the claims are held
  priority: high
  min_free_gb: 4                         # optional: what each card keeps free for tasks
  routing: {task_work: coder, never_evict: reserved}
```

- **`reservations`**: each one a reservation (`model`, `vram_gb`, `keep_alive`, `priority`, `window`) plus `host` --
  a paired host's name, an `ollama.hosts` name, or `pool` -- and `min_free_gb`; one per host (two on one host is one
  line: merge them). The verdict judges each where it is held: the default host's needs and reservation as before, a
  paired host's on that host's card, the pool's by the pool's fit and its `route` ("the pool for reasoner:
  Qwen3-Next-80B-A3B Q4_K_M fits the pool ..."). The bundle's state is the worst of its parts. Reserving the pool
  writes a claim on host `pool` and launches nothing -- Warm starts it; while a bundle holds the pool for one model, a
  Warm of another waits in one line naming the bundle.
- **`schedule.hours`**: the claims are held inside those hours on the host's local clock (a host evaluates its own
  claims by its clock); outside them a claim is dormant -- written, never counted, never read as live. The verdict
  says "holds its claims 09:00-18:00 (the host's local clock): not held now (from 09:00)".
- **`min_free_gb`**: a claim that would leave less than that free for tasks on its card won't work, said with the
  floor ("it keeps 4 GB free for tasks (min_free_gb)").
- **`priority`** and **pre-emption**: when a bundle's claim does not fit beside the others on a card, the claims of a
  lower priority give way -- the lowest first, the fewest that make room; one of equal or higher priority never does
  ("night-batch holds 6.0 GB there at priority normal: focus's normal does not pre-empt it"). The verdict says it
  before anything happens ("pre-empts night-batch (low, 6.0 GB) on pc"), and turning the bundle on does it with one
  line naming the bundle that won and the number: "pre-empted night-batch (low) on pc: focus (high) needs its 6.0 GB --
  halo pack on night-batch claims it again once there is room". The pre-empted bundle is told: its `halo pack verdict`
  and its Pack Manager row carry the notice. The pool is one resource: any other bundle's claim on it collides.
- **The claim lease** (3.3.8.0 R3) applies to every reservation a halo process holds: each row has its `until`, the
  heartbeat renews them all, a killed Studio's claims end within `pool.claim_lease_s`.

Before 3.3.8.0 R4 a claim that did not fit beside another bundle's was simply "won't work"; now a higher priority
takes the room, said. A claim with no priority is `normal`, as it always was.

## The bundles Halo ships

`halo_harness/templates/bundles/`: **meta-glasses** (voice: the 1.7 B chat model reserved at 8 k, speech on the CPU,
task work to the coder when it fits beside, else the cloud), **bulk-worker** (a small tool-calling model reserved for
the many small jobs), **verifier** (another family than the coder), **compactor**, **embeddings** (memory search,
dedupe), **translation**, **vision** (a model that sees, loaded when an image arrives: nothing reserved),
**offline-only** (no cloud rung while it is on), **coder-first** (no reservation: the coder gets the card) and
(3.3.8.0 R4) **big-reasoner** (the pool reserved for a reasoning lane, the coder resident on this card) and (3.3.9.0
R2) **voice-local** (below). The voice bundles' speech models are the speech catalog's (3.3.9.0 R1,
[VOICE.md](VOICE.md)): present or a download in their verdict, served by `halo local serve --stt | --tts`.

## voice-local (3.3.9.0 R2)

The bundle for talking to a session on this machine ([VOICE.md](VOICE.md#the-bundle)):

```yaml
bundle:
  needs:
    chat: {any_of: [lfm3:1.7b, qwen3.8:4b, gemma4:4b], window: 8192}
    stt: {any_of: [faster-whisper:large-v3-turbo, faster-whisper:small.en], device: cpu-or-gpu}
    tts: {any_of: [kokoro-82m], device: cpu}
  reservation: {model: chat, keep_alive: -1, priority: high, window: 8192}
  routing: {task_work: coder-or-cloud, never_evict: reserved}
  latency_budget_ms: 1500
```

The reservation names the `chat` role, so it holds whichever of the three the verdict picks (the first present one).
On the fixture 24 GB card the verdict is ready: `lfm3:1.7b` resident at 8 k, `stt` on the CPU (the GPU pick,
large-v3-turbo's 1.5 GB, would break the coder's fit beside it), `tts` on the CPU. `halo pack on voice-local` claims
the reservation and says what it reserved; it starts no process. While it is on, `/voice on` (and `halo voice`) start
the speech servers with this bundle's picks, their cost line first, and measure each turn against its
`latency_budget_ms`; `meta-glasses` gives the loop the same fields (its reservation names its 8 k window).

## Speech needs resolve (3.3.9.0 R1)

A need whose models are speech models (`stt`, `tts`; runtime `voice`) resolves through the speech catalog and what is
on disk (`local_sched/bundle_voice.py`): on the CPU the smallest of its `any_of`, on the GPU the first, a present one
before an absent one. Present, it costs its footprint on the device the need allows -- `device: cpu` the CPU figure
and no VRAM, `device: gpu` the GPU figure, `cpu-or-gpu` the GPU figure when the first of its `any_of` fits beside the
bundle and the coder, else the CPU (the warning line "GPU STT (faster-whisper:large-v3-turbo, 1.5 GB) would break
that" says why). The verdict says each one: `stt: faster-whisper:small.en present (0.5 GB on the GPU, 0.9 GB on the
CPU)`. Absent, it is one download of the verdict, the class a missing Ollama model gets: `stt: not present -- halo
voice download faster-whisper:small.en (0.5 GB)`, the state "needs 1 download", the line in `halo pack verdict` and
`halo pack on`'s answer; the button pulls the Ollama tags only (a speech model comes from the hub, not a pull). A name
the catalog does not hold is said so and never sized.

## What a reservation cannot stop

The claim binds Halo: its own loads, its scheduler, its ladder, a halo host's operations. A client that talks to
Ollama directly (another app, a curl, a TUI that is not a halo) is not asked; Ollama itself decides what to unload
when such a request needs the memory, and `keep_alive -1` only stops the idle timer. Halo sees it afterwards: the
foreign line on the Hosts card ([MODELS-ollama-steward-guards.md](MODELS-ollama-steward-guards.md)) and the reserved
model gone from `/api/ps`.
