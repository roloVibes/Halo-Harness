# Knowledge: findings and decisions

Read this when you want what Halo verified or decided to outlive the session that found it: findings and decisions, who writes them, the files, the agents' tools, citing what was reused and the fleet.

Halo 3.1.8.0 R4. Knowledge Halo verified should outlive the session that
found it. Two recall kinds hold it: a **finding** -- a fact established with
evidence: what, where, the evidence lines, who found it, when -- and a
**decision** -- a choice taken with its reason: what, why, the
alternatives, who took it, when. They are written by the places that
already know them (the Orchestra judge and gate, the coach's Apply, the
supervisor's answered decisions) and by you or an agent, as Markdown files
with a small front matter under `~/.halo/knowledge/`. Recall indexes them
like memory and sessions ([RECALL.md](RECALL.md)), they travel over the
fleet like the coach library, and an agent that reuses one cites its id.
Nothing here is a classifier: no model is asked to confirm anything, and
every entry says who wrote it and from what evidence.

## The two kinds

| Kind | Id | Holds | Confidence |
|---|---|---|---|
| `finding` | `f-<yyyymmdd>-<6 hex>` | what was found, where, the evidence lines | `checked` when an evidence line names a test run or a reproduction (its command), else `said` |
| `decision` | `d-<yyyymmdd>-<6 hex>` | what was chosen, why, the alternatives | -- |

## The files

One file per entry, `~/.halo/knowledge/<kind>/<yyyy-mm>/<id>.md`, and beside
it `<id>._meta.json` (`halo_harness/knowledge/store.py`):

```
---
id: f-20261024-3c9a1e
kind: finding
title: basket.py#subtotal, basket.py#total passes `python -m unittest -q test_basket` at 25610ecfa0e2
when: '2026-10-24T05:32:46Z'
by: gate
run: 20261024-003244-9382
repo: basket
evidence:
- 'tests: `python -m unittest -q test_basket` exit 0, 5 passed'
confidence: checked
tags:
- orchestra
- gate
---
What: lane 2's piece (write subtotal and total) is merged, and the goal's test passes on the finished branch.

Where: orchestra/20261024-003244-9382 at 25610ecfa0e2 in run 20261024-003244-9382; the units basket.py#subtotal, basket.py#total.

Why: the gate ran `python -m unittest -q test_basket` on the finished branch: exit 0, 5 passed.
```

- `by`: `judge`, `gate`, `coach`, `supervisor`, `user` or `agent:<session>/<agent>` -- the role that knew, never
  the person who answered; an entry fetched over the fleet adds `@<harness id>` (`gate@9f3a...`).
- A decision carries `alternatives` instead of `confidence`; `supersedes: <id>` names the entry one replaces;
  `tags` are lower-case words.
- `_meta.json` is a pack memory entry's provenance shape ([EXTENSION_API.md](EXTENSION_API.md)):
  `{source, run, stage, written, retention: keep, shared: []}`, plus `{from, harness_name, fetched,
  read_only: true}` for an entry fetched from another harness.
- An entry is never edited in place. `halo knowledge supersede <id> "<title>"` writes a new entry naming the
  old one; the old one stays on disk, is listed as superseded and is left out of recall. `halo knowledge
  forget <id>` removes the file and its `_meta.json`; the recall index prunes it on its next build.
- A write never overwrites an id that is here. A title is one line (at most 300 characters), a body at most
  20 000 characters, at most 40 evidence lines.

## Who writes them

Each writer is one call from the place that already knows the thing, behind
`knowledge.write` (default `true`; `false` turns every writer off). A writer
never stops its caller and never changes what the caller wrote elsewhere
(`halo_harness/knowledge/writers.py`):

| Writer | When | Writes | By |
|---|---|---|---|
| the Orchestra judge ([ORCHESTRA.md](ORCHESTRA.md)) | a merge conflict the fresh judge resolved, with the lanes' evidence, and the tests held | a finding per file, "<file>: hunk <k> resolved for lane <n> because <evidence line>", with the lanes' evidence lines and the tests after the merge | `judge` |
| the gate | a run finished and the goal's test passes on the finished branch | a finding per lane, "<units> passes <test> at <sha>" | `gate` |
| the gate | it sent a lane's piece back (missing evidence, failing tests, a workflow's outputs) | a decision, "lane <n> sent back: <reason>", alternatives "merge the piece as it is" and "stop the run" | `gate` |
| the coach's Apply ([ORCHESTRA.md](ORCHESTRA.md#the-library)) | a card's change (or a probe card's group) is applied | a decision, "coach: <bio, lineup or plan> <field> -> <value>", the card's why and `halo coach --undo <id>` | `coach` |
| the supervisor ([SUPERVISE.md](SUPERVISE.md)) | you answer a parked `goal_plan`, `goal_gate`, `goal_budget` or `goal_replan` row (not "open", not a `goal_ask` card) | a decision, "<what> -> <your answer>", your text as the why and the other answers as alternatives | `supervisor` |
| you | `halo knowledge add finding "<title>"` (or `decision`) | what you give it | `user` |
| an agent | the `knowledge_add` tool | what it gives it | `agent:<session>/<agent>` |

## The tools

Every session has two tools, allowed in every mode like TodoWrite (an
explicit deny or ask rule still wins; `halo_harness/tools/knowledge.py`):

- `knowledge_add {kind, title, body?, evidence?: [..], alternatives?: [..], tags?: [..]}` -- saves a finding or
  a decision; answers with its id and, for a finding, its confidence.
- `knowledge_search {query, kind?, k?}` -- the entries that rank for the words, one line each (id, kind, who,
  day, confidence, title), then the line that tells the agent to cite the id of any it reuses. Read-only.

## Searching

`halo knowledge search <words>`, `knowledge_search` and the worker's brief
rank the current entries through recall (`recall.search` over the index,
kept to the two kinds) when embeddings are configured; when they are not, a
plain word match over the titles, bodies, evidence and tags answers instead
(the share of your words an entry holds). `halo recall` shows them among
everything else, each with its chip ([RECALL.md](RECALL.md#kinds)).

## Citing what was reused

When an agent receives knowledge hits -- the `knowledge_search` answer, or
an Orchestra worker's brief, which carries up to three findings and
decisions recall ranks for its job and the goal (score 0.35 or more; only
with embeddings configured and the store holding an entry; `knowledge.brief:
false` leaves the block out) -- the block ends:

```
When you reuse one of these, cite its id in your answer, e.g. (f-20261024-a1b2c3): the run records what was reused.
```

The evidence gatherer ([OUTCOMES.md](OUTCOMES.md)) records `cited: [<ids>]`
when the agent's final text names an id this harness holds (an id it does
not hold is not recorded), its evidence lines say `cited: f-...`, and its
row in `outcomes.jsonl` carries `cited: <n>`. `halo knowledge show <id>`
lists "reused by": every agent task whose evidence cites it. Nothing asks a
model whether it reused anything; the id in its answer is the record.

## Over the fleet

`halo recall --fleet` finds another box's findings and decisions (each hit
with `ref`, the entry's id, `by` and `when`). `halo knowledge fetch <harness>
<id>` -- or `--all finding|decision` for every current entry of a kind --
asks the hub this machine runs (the admin route `local/knowledge`), which
sends the read-only `knowledge` fleet command to one live session of that
member, over the coach library's transport. The member answers from its own
store under the recall switch (`fleet.recall.share: false` answers none;
`fleet.recall.hide: [knowledge]`, `[finding]` or `[decision]` keeps them in),
scrubbed like the capabilities catalog: every absolute path cut to its last
part, the home to `~`, every secret-shaped text redacted, `by` naming the
harness id. At most 256 KB go in one answer (`--all` sends the newest that
fit and counts the rest). Each answer is a `knowledge_asked` line in the
member's journal. The entry is written here under the same id, read-only:
its `_meta.json` says `source: fleet`, `from` (the harness id),
`harness_name` and `fetched`; a fetch never writes over an entry already
here. See [FLEET.md](FLEET.md#recall-across-the-fleet-3120-r3).

## Config

| Key | Default | Meaning |
|---|---|---|
| `knowledge.write` | `true` | the judge, the gate, the coach's Apply and the supervisor write findings and decisions; `false`: none of them does (yours and the agents' still do) |
| `knowledge.brief` | `true` | an Orchestra worker's brief carries the findings and decisions recall ranks for its job; `false` leaves the block out |

## Two examples

**A finding the next run reuses.** An Orchestra run on `basket` finishes:
the gate ran `python -m unittest -q test_basket` on the finished branch and
it passed, so `~/.halo/knowledge/finding/2026-10/f-20261024-3c9a1e.md` says
`basket.py#subtotal, basket.py#total passes ... at 25610ecfa0e2`, by `gate`,
`checked`. A week later a run on the same repo asks a worker to change
`total`; its brief lists that finding with the cite line, the worker's answer
says "kept the rounding (f-20261024-3c9a1e)", its evidence records `cited:
f-20261024-3c9a1e`, and `halo knowledge show f-20261024-3c9a1e` prints
`reused by: lane 1 of 20261031-091500-7b2c (auto-coder, passed)`.

**A decision another box takes.** The supervisor parks a `goal_gate` row:
lane 2 reached the return cap. You answer "raise the cap by N" with `2 --
the flaky test is fixed upstream`. `~/.halo/knowledge/decision/2026-10/
d-20261024-8e41f0.md` holds `Goal g-7: the gate sent a piece back past the
return cap -> raise the cap by N`, by `supervisor`, your text as the why and
"raise the cap by 1 and resume", "stop" as the alternatives. On the Kali box,
`halo recall --fleet "flaky test return cap"` finds it with `ref:
d-20261024-8e41f0`, and `halo knowledge fetch win@studio d-20261024-8e41f0`
writes it there, read-only, `by: supervisor@<your harness id>`.
