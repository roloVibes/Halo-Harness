# Models: guards and the off-hours refresh

Read this when you want to know how Halo keeps the record of your local models true with no effort: who else is using a card, when the battery and the bench re-run on their own, and what happens when a tag changes or is deleted.

Part of [Models](MODELS.md), which lists every part.

## The record stays true (3.3.7.0 R4)

Every number Halo shows about a local model -- its battery profile, its speed card, its window truth, its crash
fingerprints -- was measured once, on one build of one tag, at one time. Four guards keep those numbers honest without
a person doing anything: the busy wait sees clients that are not halos, an off-hours refresh measures what went
stale, the drift guard notices when a tag's digest changes, and the deletion guard names the nearest equivalent when
a tag that something points at is gone. None of them calls a model to decide anything; each line says the mechanic
and the number behind it. Nothing here changes a server setting, restarts a server, downloads, deletes or retires.

## Foreign clients and idle

`ollama_steward/idle.py` reads `/api/ps` and explains each loaded model with a Halo record of it on that host: a call
in the traffic ledger (this machine's, and every peer's that pushes `POST ledger` to a halo host here), a load the
scheduler made (`local_sched/loads.jsonl`: pivots, warms, the refresh), a battery profile or a speed card written in
the last 30 minutes (the battery and the bench load models with no ledger line), the host's residency clock, or the
duty steward's helper. A loaded model nothing explains is **a client that is not a halo**:

    foreign: 1 model, 17.3 GB, since 14:02 (a client that is not a halo; Ollama's /api/ps names the model, never the
    client)

Ollama tells us no more than that, and the line says so. The bench's busy wait (`providers/local_bench_runs.busy`,
its third reason after a recent call and a live session) and the off-hours refresh wait for it like for any other
user: "a client that is not a halo holds qwen3-coder:30b (17.3 GB) on pc since 14:02 ...". `halo ollama traffic`
prints the foreign line under each host's card line; Local -> Resources' traffic view and each Local -> Hosts card
show it too. "Since" is when a halo first saw it so (`<state>/ollama/foreign.json`).

**Idle** (`idle_since`) is the newest use of the card Halo saw -- a ledger call, a scheduler load, a load through the
host -- and it is not idle while a foreign model is resident or a session on this machine uses the card.

What idle cannot know: a halo that pushes no ledger lines here (a TUI-only peer with no Studio or hub on it) looks
like a foreign client; a foreign client that loaded a model a halo called within 30 minutes is credited to the halo;
a client whose model Ollama already unloaded leaves no trace in `/api/ps` at all.

## The residency clock

When a halo host serves the card, every peer's warm, pin and pivot lands through the host's typed operations, so the
host keeps one clock: `<state>/host/residency.json` (`host/residency.py`; a load writes the row, an unload removes it;
`GET residency`). The scheduler's minimum residency (`local.min_resident_s`) reads it: two peers pivoting on one card
share one clock instead of each keeping its own. With no host, each halo keeps its own clock and the pivot's held line
says so: "(local.min_resident_s 60; this halo's own clock: no halo host serves pc, so another halo keeps its own)".

## The off-hours refresh

On a machine that runs `halo host`, the host's loop (`host/refresh.py`) runs the capability battery and then the quick
bench, one model at a time, when:

- the refresh is on (`host.refresh.enabled`) and the local time is inside `host.refresh.window` (`22:00-07:00`; it may
  wrap midnight; `off` disables it), and
- the card has been idle `host.refresh.idle_min` (20) minutes: no call in the ledger, no scheduler load, nothing
  foreign in `/api/ps`, no session on this machine holding it.

The plan (`host/refresh_plan.py`) takes the drifted tags first (the digest changed), then the never probed (or probed
with an older probe set, or with no speed card), then the profiles older than `host.refresh.max_age_days` (14), each
with its minutes from the speed cards ("next: qwen3-coder:30b on pc (unverified: never probed here), battery + bench
~4 min, tonight 22:00+ once the card has been idle 20 min"). It stops the moment a call arrives (a ledger call on
that host since it began, a session on the card, a foreign model) and says so. A profile and a speed card it measured
carry `verified_by: "the host"` and `refreshed_at`; the speed card's head says "verified by the host". Every run is a
line in `<state>/host/refresh.jsonl`. With nothing left to measure it runs the **roster review** -- the
[roster adviser](MODELS-adviser.md) -- when the roster, an Ollama version or the hosts changed, and keeps its lines
there too.

The battery and the bench are Ollama API calls: the model loads in Ollama, never in the host process. A machine with
no halo host gets the same from `halo local refresh` by hand. `halo host refresh status | now | off | on`
([COMMANDS-host.md](COMMANDS-host.md)); the Hosts card's refresh line and the Steward page's refresh block show the
plan and the last run.

## The drift guard

Tags are mutable: `ollama pull` of the same name can bring other weights. `ollama_steward/tag_digests.py` keeps the
digest each installed tag had at the last catalog read (`<state>/ollama/digests.json`); the window truth (the learned
cap) that had no digest gets the tag's on that first read. The steward's rule `tag-drift` (`rules_drift.py`, warn)
compares each installed tag with the records measured on it:

    qwen3.8:27b on pc: the tag's digest changed (sha256:0b27 -> sha256:9f1c): its battery profile (2026-10-20), its
    speed card (2026-10-21), its window truth (the learned cap 49,152) were measured on an older build of this tag;
    its speed card no longer prices a swap or Auto's pick, and the off-hours refresh measures it first

"measured on an older build of this tag" is the speed card's stale mark too. The swap cost (`local_sched/swap_cost.py`)
and so Auto's pick stop reading a stale speed card (the weights' estimate prices the load instead), and the refresh
queues the tag first. The finding stays until the records are measured again.

## The deletion guard

A tag that a role, the active lineup's lane, a `warm:` entry or a placement (`host_for`) names, and that the host's
catalog no longer has, gets one line from one module (`ollama_steward/dead_tag.py`), with its nearest equivalent:

    `qwen3.8:27b` was deleted from pc -- nearest equivalent `qwen3.8:27b-gpu` (same family, same size, same quant,
    fits the same window): halo roles point coder ol:qwen3.8:27b-gpu@pc

"was deleted" when Halo saw it there (a profile, a speed card, a shelf line, a ledger call); else "is not on pc
(deleted, or never pulled there)". The nearest equivalent (`models_library/nearest.py`) is scored by the same family
(the name's base, else the catalog's family), the same size (parameters within 15 %), the same quant, fitting the same
window on that card and the battery's verified tool calls; nothing sharing the family or the size has no answer, and
then the closest spelling is named as such. `halo doctor --local`, `halo teams use` (the swap preview's hygiene),
`halo local warm` (the row's state is `deleted`), `halo local place`, the Roles page's Problems and the steward's
`tag-deleted` finding (error) all say the same line. "Point the role at it" is `halo roles point <role> <model>` or
`POST roles/<role>/point`: `roles.<role>` in config.json and nothing else.

## The ladder on a crash

When the model in use crashed on its host at this window in the last ten minutes (its crash fingerprint), the
degradation ladder steps before `low_confidence`'s judge is asked anything (`agent/degrade_crash.py`): past the smaller
ask (the crash is the card at this window, not the size of the ask), to another local model or a bigger one, the line
naming the fingerprint -- "rung 3: another local model -- ol:big:30b@lan (after mid:14b crashed here on 2026-10-31:
the GPU ran out of memory with q8_0 KV)". One fingerprint steps it once.
