# Models: the roster adviser

Read this when you want Halo to tell you which local models you are missing, which overlap, which do not suit their roles and which have a newer line -- with the numbers and one click each.

Part of [Models](MODELS.md), which lists every part.

## What it reviews (3.3.7.0 R4)

The roster adviser (`models_library/advise.py`) reviews the installed local models against the roles, each host's
memory budget, the capability profiles and the host log, then says what is missing, what overlaps, what is mismatched
and what has a newer line -- in plain words, with the numbers, and with one action that does one named thing. It is a
deterministic review: no model is asked anything, and nothing downloads, deletes or retires until you press the
button (or run the command) that names it.

Its inputs: the installed models per host (the Ollama panel's cached catalog), the battery profiles, the host budget
(the card's total minus other programs: `fit.card_budget`), the active lineup's lanes and its roles with no model of
their own (`role_gaps.gaps`), the swap preview's pivots (`local_sched/preview.py`), the crash fingerprints, and the
packaged library snapshot (sizes, families, dates) for what to add.

## The four kinds

- **gap** -- "you have no embedding model, so memory search, dedupe and "find similar" are unavailable"; "nothing here
  reads images, so a screenshot or a pasted image goes to the cloud or to nobody"; a lineup role with no model of its
  own. Each names an option from the library that fits the budget and a one-click add.
- **overlap** -- two or more installed models of one family root, one purpose and one size (within 20 %): "3 qwen
  models of about 27.3B (...) cover the same ground (chat); keep qwen3.8:27b-gpu (measured best here)" -- the one with
  verified tool calls, agentic readiness and the higher measured tok/s -- and what retiring the others frees. A model a
  lane names is never offered for retirement ("qwen3.8:27b stays while main, verify name it").
- **mismatch** -- the verifier on the coder's family ("so their blind spots overlap": point it at an installed model of
  another family, else add one); "every summary costs a 16.9 GB pivot (...) because there is no compactor that
  co-resides" (add a small model); a lane whose model crashed here twice or more.
- **placement** (3.3.8.0 R4) -- a lineup lane a cheaper candidate would serve: every configured host, each paired
  host's card and the pool are scored (`halo local place`'s rule) and the line says both scores and what each costs
  to place -- "compactor (qwen3.5:9b) on pc scores 75 (evicts qwen3-coder:30b, pivots beside qwen3-coder:30b); sagan
  scores 116 (18 s to load)"; Place is `halo local place --apply`. Under the suggestions, the **placement scores**:
  each lane on every candidate with its loading tax (the load seconds, the switch, the pool's decode penalty).
- **freshness** -- a family the library has a newer line of ("gemma3:12b's family has a newer line in the library:
  gemma4 (updated 2 weeks ago); when the two measure the same, prefer the newer"), offered at the same size; a newer
  line already installed is the overlap's to judge, not freshness.

Each suggestion carries what it unlocks or frees, what it costs -- the download (with the minutes at 40 MB/s), the
VRAM, at which window, co-reside or pivot -- and one action: **add** (the Library's Download and verify: the pull,
then the battery, then the role offer), **retire** (the shelf's retire: the uses card first, a note with the re-pull
line), **point** (the role write, `halo roles point`), or none with the command to read. They are ranked by value per
gigabyte: each kind's stated worth divided by its download (a retire or a point downloads nothing).

## When it runs

`halo local advise [--host H] [--lineup L] [--json]` ([COMMANDS-local-guards.md](COMMANDS-local-guards.md)) and the
Adviser block on Local -> Models (Add, Retire, Point, Review again) say the same lines. It is re-run when the roster
(each tag's digest), an Ollama version or the hosts change -- its fingerprint is kept in `<state>/ollama/advise.json`
-- and the off-hours refresh runs it as the nightly **roster review** when nothing is left to measure
([MODELS-ollama-steward-guards.md](MODELS-ollama-steward-guards.md#the-off-hours-refresh)).

## What it cannot know

It reads what is installed and measured, not how you use a model outside Halo; a family root is the name's leading
letters (`qwen`, `gemma`), so two lines of one vendor count as one family; the library's "newer" is its version
number and date, not a measured comparison -- the line says "when the two measure the same" for that reason.
