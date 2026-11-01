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
(else the first with a known size: a download); a speech model on `cpu-or-gpu` runs on the CPU (the smallest of its
list: no VRAM); a `verify` role never takes the coder's own family; `vision: true` takes only a model that sees. Three
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

## The bundles Halo ships

`halo_harness/templates/bundles/`: **meta-glasses** (voice: the 1.7 B chat model reserved at 8 k, speech on the CPU,
task work to the coder when it fits beside, else the cloud), **bulk-worker** (a small tool-calling model reserved for
the many small jobs), **verifier** (another family than the coder), **compactor**, **embeddings** (memory search,
dedupe), **translation**, **vision** (a model that sees, loaded when an image arrives: nothing reserved),
**offline-only** (no cloud rung while it is on) and **coder-first** (no reservation: the coder gets the card). The
speech models of the voice bundle arrive with 3.3.8.0 Voice; this round ships the claim and the verdict.

## What a reservation cannot stop

The claim binds Halo: its own loads, its scheduler, its ladder, a halo host's operations. A client that talks to
Ollama directly (another app, a curl, a TUI that is not a halo) is not asked; Ollama itself decides what to unload
when such a request needs the memory, and `keep_alive -1` only stops the idle timer. Halo sees it afterwards: the
foreign line on the Hosts card ([MODELS-ollama-steward-guards.md](MODELS-ollama-steward-guards.md)) and the reserved
model gone from `/api/ps`.
