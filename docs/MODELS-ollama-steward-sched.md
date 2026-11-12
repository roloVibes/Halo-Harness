# Models: scheduling the local models

Read this when a lineup runs several local models on one card (or across machines) and you want to know what stays loaded, when a model is swapped in, what each swap costs and where each lane should run.

Part of [Models](MODELS.md), which lists every part.

## The scheduler (3.3.7.0 R3)

Every piece of a local-model orchestra was there before -- the window truth, the fit plan, the switch step, the
degradation ladder, the measured cards, a halo host's `route` answer -- and nothing scheduled them: a lineup of five
lanes on one 24 GB card swapped blindly and paid the load time invisibly. `halo_harness/local_sched/` schedules
them. It is arithmetic over what Halo already reads (the hardware card, the catalog rows, `/api/ps`, the traffic
ledger, the speed cards, the hosts' `route` answers); no model is called to decide anything, every line it prints
says the number behind it, and a swap it avoids is a line in the session, never a silent choice. Loads go through
the Ollama API, or through a paired halo host's typed operations when a host serves the model
([HOST.md](HOST.md)); nothing changes a server setting.

## The warm set

Per card, the models of a lineup that co-reside. `local_sched/warm_set.pack` takes the lineup's `ol:` lanes on
that host (main first: the session comes back to it after every hand-off), gives each model the largest window
its lanes ask (the lane's own profile, `<host>|<model>|<role>`, then `<host>|<model>`, then the host's `max_ctx`,
else 32,768, held to the most it fits alone), and packs them: main's model first, then the models more lanes use,
then the lineup's order -- a lineup's own `warm:` list goes first, in its order. A model joins the set when the set
with it fits the card: its weights (the catalog row from `/api/show`, else the packaged library snapshot) plus the
KV at its window, with the per-card reserve, against the card's budget (its total minus what other programs hold)
minus the duty steward's helper while that model is resident (the host's invariant, [HOST.md](HOST.md)).

    warm on pc: qwen3-coder:30b (main, coder), qwen2.5:1.5b (small) -- 20.8 of 21.5 GB; qwen3.8:27b (reviewer)
    pivots; 2 swaps a pass, ~50 s of loading

A model that does not fit is a pivot ("does not fit beside qwen3-coder:30b, qwen2.5:1.5b (20.8 + 18.4 of 21.5
GB)", or "does not fit the card at 32,768 even alone"); one with no catalog row or no card read is "not judged" --
nothing is guessed. The swaps a pass: one pass of the lineup is main, then each lane and back to main; the count is
the loads that pass needs in the steady state (two passes from the warm set, the second counted), each load
evicting the residents used furthest ahead and keeping back any that still fit beside it.

`halo local warm [<lineup>]` loads the warm set at session start ([COMMANDS-local.md](COMMANDS-local.md)): one row
per model (loaded in N s at its window, already warm, or pivots later with its load time), then the total. A lineup
may declare its warm set (`warm: [coder, qwen2.5:1.5b]`, [AGENTS.md](AGENTS.md#team-template-lineup-fields)); `halo teams use` says when it cannot
co-reside. Studio: the Roles lineup tab's Local models block has Warm; each Local -> Hosts card has the active
lineup's warm-set line.

## The pivot

When a lane needs a model that does not fit beside the resident one, the unload -> load is one visible step
(`local_sched/pivot.py`):

    pivot: main (qwen3-coder:30b) -> coder (qwen3.8:27b) on pc, ~25 s (the ledger), fits history to 32 k
    pivoted in 24 s: qwen3.8:27b loaded on pc at 32,768 (asked)

A host-served model pivots through the host's `pivot` operation (its invariants first, one event each); a local one
through the Ollama API (unload, then load at the lane's window). The child's first request is fitted to the new
window by the switch step as before. Two rules of its own: one pivot at a time per card (a second waits: "pivot:
qwen3.8:27b waits -- a pivot is already running on pc (one at a time per card)"), and a minimum residency
(`local.min_resident_s`, 60): a model the scheduler loaded is not unloaded before that many seconds, so two lanes
cannot thrash one card -- the pivot waits the rest and says how long. A host's fix guards and rate limit count fixes
only, so these are the scheduler's own.

## The switch cost and the swap preview

How long a load takes (`local_sched/swap_cost.load_s_for`), the first source with a number winning and named: the
ledger (the median of the newest five calls of that model on that host whose `load_ms` was over 2 s), the speed card
(the bench's cold load, else the battery profile's), the weights (the catalog row's size at ~0.7 GB/s: "an estimate
from the weights"). `model_switch.plan` carries it (`load_s`, `load_source`) and the switch line says it ("· ~25 s to
load when cold (the ledger)").

`halo teams use <lineup>` prints the swap preview under the roles, and the Roles lineup tab shows the same lines:

    Local models (the swap preview, one pass of the lineup):
      warm on pc: qwen2.5:1.5b (main), qwen3-coder:30b (worker) -- 20.8 of 21.5 GB; qwen3.8:27b (verify) pivots; ...
      this lineup swaps 2x on one card ~ 50 s of loading a pass
      [!] verify (qwen3.8:27b) and worker (qwen3-coder:30b) run on different weights that do not co-reside on pc:
          each hand-off between them is a swap (~26 s); one model for both lanes makes it 0
      [!] verify (qwen3.8:27b) never fits beside main (qwen2.5:1.5b) on pc: ...; every hand-off to it is a pivot

The hygiene lines: verify and worker sharing weights ("0 swaps between them"), on different weights (both warm: no
swap; else each hand-off a swap), a lane that never fits beside main, a lane that could not be judged, a `warm:`
list that cannot co-reside.

## The local -> local hop

Under escalation's triggers -- `low_confidence`, `tool_failures`, `context_overflow` -- the next bigger local model
is tried before any cloud rung, so "switch when needed" stays offline (`agent/local_hop.py`). The candidates are
the probed local models that call tools (the battery profile) whose placement verdict for the role is not a no,
heavier than the model in use, that fit their card alone at the lane's window; the next size up wins. It is the
ladder's `bigger-local` rung (after `other-local`, before `cloud`) and runs at the escalation points too, with or
without a `routing.escalation` policy (no policy: `tool_failures` and `context_overflow`; `low_confidence` needs the
judge's call, so only when the policy names it). On the same card and not beside the model in use, it is a pivot.

    rung 4: a bigger local model -- ol:qwen3.8:27b@pc (27.0B over 9.0B; a pivot ~25 s (the ledger))

`routing.local_hop` (default: on for a local-first session) turns it off; the rung then says so and the ladder goes on.

## The spawn-time verdict and a lane's own profile

Before a child spawns on a different local model on main's card, its first event says whether it fits beside main,
what it evicts and the swap time (`roles_fit.py`; the four roles `vram_aware_override` redirects stay as they are):

    fit: coder on qwen3-coder:30b does not fit beside main (qwen3.8:27b) on pc (18.4 + 18.9 of 21.5 GB): evicts
    qwen3.8:27b, ~25 s to load (the ledger)

When it does not fit, the pivot follows (one at a time, the minimum residency). A lane carries its own profile:
`ollama.profiles["<host>|<model>|<role>"]` (window, keep_alive, tools_max, host_for) is read first and field by
field over `<host>|<model>`; `halo ollama profile set <host> <model> <field> <value> --role <r>` writes it.

## Auto's pick

`models_auto.pick` weighs fit and warm state (`models_auto_local.py`): a local candidate that does not fit beside
main is left out while another remains ("skipped ...: it does not fit beside main, so every hand-off would swap");
one that needs a load keeps 1 - 0.005 x its load seconds of its score (never under 0.75); a warm one keeps it whole.
The pick line says which it was: "auto: ol:qwen3-coder:30b@pc -- ...; already warm" (or "fits beside main, ~25 s
to load", "does not fit beside main: needs a swap, 25 s").

## The loading tax

Cloud cost is dollars; local cost is seconds of loading. `local_sched/loads.tally` counts a session's loads -- its
ledger calls that paid a load (over 2 s) plus the scheduler's own pivots and warms -- and their seconds, per model:
"loading: 7 loads, 3 m 02 s (qwen3.8:27b 4, qwen3-coder:30b 3)". It is on `/cost` beside "Saved vs cloud", on the
session's Cost panel (LOADING) and in `halo session show <id>`; a lineup's per-pass cost is in its swap preview.

## Placement across machines

`halo local place [<lineup>]` (`local_sched/place.py`) says where each lane's model should run. Every configured
Ollama host is a candidate: one a paired halo host serves answers with its `route` (the helper's footprint counted:
`usable_with_helper_gb`), any other -- this machine's own included, with no `halo host` running -- from the local
reads. Lane by lane (main stays on its host), a host where the profile says the model cannot call tools, or where it
does not fit, is out; the rest are scored on warm, fitting beside what the plan already put there (shared weights
best), fitting now, the lane's own host, the load seconds, what it evicts, whether it is pulled there:

    halo local place spread: main on pc (fits, warm), coder on pc (fits, shares weights with a lane placed there,
    warm), compactor on sagan (fits, fits now, 18 s load), small on box (fits, fits now, 1 s load)

`--apply` writes `host_for` on each moved lane's `<host>|<model>|<role>` profile, Halo-side only: nothing is pulled
and nothing loads until the lane asks. Studio: Local -> Hosts' Place block (Place, Apply).

## What the arithmetic cannot know

Before a model was ever loaded on a host, its footprint is the weights from `/api/show` (or the library snapshot)
plus the KV the fit arithmetic computes for its shape at the window; the projector and Ollama's own graph overhead
are estimates, so a set that packs at 95 % may still spill. The load time of a model never loaded there is the
weights at a typical disk rate until the ledger or a bench measures it. The warm set is per lineup; another
program (a ComfyUI that starts) changes the budget between two reads.
