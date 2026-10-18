# One unit of work

Read this when you want the one model under an Orchestra lane, a mission part, a team stage and a flow step.

Halo 3.1.2.0. A team stage, a mission part, an Orchestra lane and a flow
step are all the same thing: a piece of work with an owner, claims, a
gate and a hand-off. Four engines grew them separately, each with its own
ledger, its own report shape and its own coach rules. This round puts one
model underneath (`halo_harness/work/`) and keeps the four front doors:
every command, route and file on disk is exactly as it was.

## The unit

A `Unit` (`work/unit.py`) is what all four are:

```json
{"kind": "lane|part|stage|step", "id": "2", "title": "...", "run_id": "<run id>",
 "owner": "the bio / member / harness that runs it",
 "claims": {"keys": ["basket.py#total"], "mode": "unit|path|block|none"},
 "needs": [{"from": "job-1", "take": "summary"}], "gives": [{"name": "summary", "kind": "summary", "path": "..."}],
 "after": ["job-1"], "base": "<the commit it started from>" | null,
 "state": "<machine word>", "native": "<the engine's own word>",
 "gate": {"mode": "required|optional|none", "id": "<open gate>" | null, "round": 0, "answer": {"action", "text", "ts"} | null},
 "acceptance": {"prompt", "expect", "ok", "note"} | null,
 "cost_usd": 0.0, "started": ts | null, "ended": ts | null, "attempts": 0, "error": "",
 "refs": {"sessions", "run", "worktree", "branch", "head", ...}, "extra": {what only one kind has}}
```

`owner` is the bio, member or harness that runs it; `claims` the parts of
a file, repo path or block it may write; `needs` / `gives` / `after` /
`base` the hand-offs (what it takes, what it leaves, what it starts after
and from which commit); `attempts` the pieces returned or redo rounds;
`extra` holds what only one kind has (a lane's `written` and `history`, a
part's `outputs`, a step's `output`), so nothing an engine keeps is lost.

## The state machine

One machine, ten states:

    pending -> ready -> running -> {gated -> ...} -> done | failed | skipped | stopped
                         \-> waiting -> running             done -> merged

`waiting` is a unit that cannot go on until something outside it happens
(an upstream lane, a harness owner's card); `gated` is a unit whose result
waits for an answer (the merge and quality gate, a team stage's gate, a
flow's human gate); `merged` is a unit whose work was merged into the run's
result. A finished unit may re-open (a redo, a piece the gate sent back).

Each engine keeps its own words on disk; `work/states.py` maps them onto
the machine with a per-kind alias table (and back, so a file is written in
the engine's own word). Every engine word round-trips.

| machine | lane | part | stage | step |
|---|---|---|---|---|
| pending | (new) | pending | pending | pending |
| ready | joined | — | ready | — |
| running | writing | running | running | running |
| waiting | waiting | asked | — | — |
| gated | in_review | — | gated | waiting |
| done | written | done | done | done |
| failed | failed | failed | failed | failed |
| skipped | — | skipped | skipped | skipped |
| stopped | — | stopped | — | — |
| merged | merged | merged | — | — |

(A dash is a machine state that kind never writes; it still maps to the
nearest engine word when a unit is set to it.)

## The ledger line and the report row

Every engine log line reads as a `LedgerLine` (`work/ledger.py`):

```json
{"ts": 1760300000.1, "kind": "state|claim|gate|change|handoff|note", "unit": "2" | null,
 "run": "<run id>", "by": "<who>", "key": "<claim key>" | null, "text": "...", "native": "<the engine's word>", "data": {...}}
```

and every unit has one report row, a `UnitRow` (`work/report.py`):

```json
{"unit": "2", "kind": "lane", "title": "...", "owner": "...", "state": "<machine>", "native": "<engine>",
 "cost_usd": 0.0031, "attempts": 0, "gate": "required|optional|none", "base": "<sha>" | null,
 "gave": [{"name", "kind", "path"}], "error": ""}
```

Each engine's report keeps its own rows and now carries the unit rows
beside them under a new `units` key (report.json for an Orchestra run, a
mission and a flow run; the board for a team run); nothing was removed.

## `halo work` and the route

```sh
halo work [RUN] [--json]     the units of any run of any kind, as one table
```

`RUN` is a run folder, a run id or an id prefix; with no `RUN`, the latest
run of this repo (an Orchestra run, else a flow run, team run or mission).
`GET /api/work/<kind>/<run>` serves the same rows (`<kind>` is `orchestra`,
`mission`, `team` or `flow`). Read only; no model is called.

## What is not shared yet

R1 is the model, the ledger, the report row and the read views; the four
engines still run their own schedulers and the Studio panels keep their own
routes. R2 ("Scheduling") is the one scheduler over this model: parallel
stages under a tier's `max_parallel`, a lane or stage run on a fleet
member, a stale downstream re-based before the merge, and a cost forecast
on the plan. See [ROADMAP](../plans/ROADMAP.md) 3.1.2.0 R2.
