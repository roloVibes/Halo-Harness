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

## The state machine is enforced

Halo 3.1.2.0 R2. Every engine write of a unit's state goes through
`Unit.move(state)` (`work/unit.py`; an engine setter calls
`move_word(kind, id, was, word)` with its own words): a lane's
`lanes/<n>.json` (work/adapters/lane.py), a mission part's `mission.json`
(work/adapters/part.py), a team stage's board row (team/board.py
`set_stage`, and the run's stop) and a flow step's `flow.json`
(flows/state.py `Flow.set`). A move the machine has no edge for raises
`IllegalMove` (a `ValueError`) naming the unit, from and to, and nothing is
written:

    lane 2 of run 20261018-120000-ab12 cannot move from merged to ready (from merged it moves to waiting)

Moving a unit to the state it is in is no edge: it is the engine saying the
state again with a new line (a lane `waiting` with a new reason), always
allowed. The edges (`work/states.py` `EDGES`):

| from | to |
|---|---|
| pending | ready, running, waiting, failed, skipped, stopped |
| ready | pending, running, waiting, failed, skipped, stopped |
| running | waiting, gated, done, failed, skipped, stopped |
| waiting | pending, ready, running, gated, **done**, failed, skipped, stopped |
| gated | ready, running, waiting, done, failed, skipped, stopped, merged |
| done | ready, running, waiting, gated, merged |
| failed | **ready, running** |
| skipped | **ready** |
| stopped | (none: it is over) |
| merged | **waiting** |

The edges in bold are the ones R2 added, each because an engine needs it
(`states.ADDED`):

- `failed -> ready`: a failed team stage runs again when asked (`halo team
  run <stage>`, a trigger);
- `failed -> running`: a lane whose worker fell over gets its one more run
  in the same worktree, and a resumed run's failed lane or flow step runs again;
- `skipped -> ready`: a stage skipped at its budget line is asked to run again;
- `merged -> waiting`: the gate sends a merged piece back (the tests fail on
  the finished branch), and a downstream lane of it goes stale;
- `waiting -> done`: a mission part's result lands while the hub still
  shows it `asked` (the member ran it before the hub saw the card answered).

A team member's own state (the stage row's `members_state`, team/parallel.py)
walks the same edges. `tests/test_work_states.py` replays each engine's real
fixture history (an Orchestra run with a hand-off, a team run through its
gate, a local mission, a flow run with a redo) through `Unit.move`.

## Scheduling on the unit model

R2 schedules on this model: the members of a team stage run in parallel
under their tiers' `max_parallel` ([TEAM.md](TEAM.md#stages-triggers-and-gates)),
an orchestra or flow stage may run on a fleet member
([TEAM.md](TEAM.md#delegating-a-member-to-the-fleet)), a downstream lane
whose upstream the gate sent back is re-based before the merge
([ORCHESTRA.md](ORCHESTRA.md#stale-lanes)), a plan carries a cost forecast
([ORCHESTRA.md](ORCHESTRA.md#the-forecast); the shapes are
`work/forecast.py`'s) and a team file a budget line ([TEAM.md](TEAM.md#budgets)).

## The ledger line and the report row

Every engine log line reads as a `LedgerLine` (`work/ledger.py`):

```json
{"ts": 1760300000.1, "kind": "state|claim|gate|change|handoff|note", "unit": "2" | null,
 "run": "<run id>", "by": "<who>", "key": "<claim key>" | null, "text": "...", "native": "<the engine's word>", "data": {...}}
```

and every unit has one report row, a `UnitRow` (`work/report.py`):

```json
{"unit": "2", "kind": "lane", "title": "...", "owner": "...", "harness": "<name>" | null, "state": "<machine>",
 "native": "<engine>", "cost_usd": 0.0031, "attempts": 0, "gate": "required|optional|none", "base": "<sha>" | null,
 "gave": [{"name", "kind", "path"}], "error": ""}
```

`harness` (3.1.2.0 R3) is the fleet harness a delegated unit ran on -- a
mission part's harness, a team stage whose lead member is on a member or
whose orchestra / flow run is delegated (`refs.harness`); `null`/absent and
`halo work`'s table reads `here` for a unit that ran on this machine, so a
report of a delegated run reads where each unit ran.

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

The four engines still run their own loops over the shared model (R2 put
the parallel members, the delegated runs, the re-base and the forecasts into
them), and the Studio panels keep their own routes. R3 checks delegation on
two real machines and shares the recall index across the fleet. See
[ROADMAP](../plans/ROADMAP.md) 3.1.2.0 R3.
