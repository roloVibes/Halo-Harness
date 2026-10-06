# Halo 2.0.4 round 3: picker columns, balances, enumeration, error translation, catalog refresh, command consolidation

Repo: <repo> (branch master; start
from HEAD, which includes round 2's Experiential route). Read
`plans/WORKER-RULES.md` FIRST and follow every rule in it (test environment:
`BRIDGE_TEST_HOME=<fresh scratch dir>` and `BRIDGE_TEST_NO_BACKGROUND_NET=1`
only).

The specification is `plans/2.0.3-brief.md` (the old 2.0.3 brief whose
generic items moved to 2.0.4): sections **A** (OpenRouter: enumerate
everything, pick hierarchically: the three picker columns), **B** (balances
and usage per provider), **C** (enumerate the other routes like Databricks:
`cc:`/`ant:` enumeration), and **G** (learned rules, error translation,
catalog auto-refresh, command consolidation, group labels). Skip C2, D, E, F
and H: C2 shipped in 2.0.3, D (jev) is removed, H (cc: v2) is 2.0.5. Where a
G item already landed in 2.0.3 or in round 2 (OpenAI and Experiential
catalog refresh hooks, the Experiential error-code translation, the learned
ignored-parameters rule), extend rather than duplicate; say so in the
hand-back. Also read `plans/ROADMAP.md`'s "ADDED 2026-10-05 ~12:40" section
(price `-1` as "varies", 1M/2M contexts, live lookup for ids without a
catalog row) and note round 2 already fixed the price rendering in the
shared formatter.

## Deliverables

1. **Three picker columns for every group** (A): price per million (in and
   out), context, and speed (tokens per second where a provider or Halo's
   own measurement knows it; blank otherwise), the same layout in every
   group (OpenRouter, Anthropic, Databricks, Hugging Face, OpenAI, Codex,
   Ollama, local servers, Experiential), hierarchical pick for OpenRouter
   (vendor, then model), sort and filter keys documented in the picker
   footer, `u` still working from default focus (C-2 wired it). Unknown
   values render as "?" never as a blank that looks like zero.
2. **Balances and usage per provider** (B): one shared `balances` surface:
   `halo balances` (CLI), `/balances` (TUI and headless), a cached
   background refresh feeding a status-bar chip for the active provider
   when its API offers a balance or credit endpoint (OpenRouter key
   endpoint, Experiential credits, Databricks and Anthropic where the API
   exposes one; otherwise "not offered"). Never blocks the UI thread; cache
   under the state dir with a TTL; the doctor reuses the same fetch.
3. **`cc:`/`ant:` enumeration** (C): `halo models --cc` and `--ant` list
   real, reachable models the way `--dbx` does (Anthropic via the models
   endpoint with the key; Claude Code via the cached `cc-models.json`
   probe already present), each row with the three columns, and the
   picker groups read the same cache.
4. **Error translation** (G): every provider's error shapes map to one plain
   Halo sentence through the single `errors.map_upstream_error` table
   (round 2 added the Experiential codes; cover OpenRouter, Anthropic,
   Databricks, Hugging Face, OpenAI, Ollama's `exceed_context_size_error`
   already handled, and the generic status table), with the raw text in
   the debug dump only. The print-mode result for an unconfigured provider
   must carry that sentence as `result` (the empty-result bug noted in
   plans/2.0.3-release-notes-for-fix-pass.md), never an empty string.
5. **Catalog auto-refresh** (G): one scheduler for every catalog (vendored
   snapshot, cache TTL, refresh at launch off-thread, `/models refresh`,
   `halo models --refresh`), each provider registering its fetcher; a
   failed refresh keeps the previous cache and says so once; `halo doctor`
   reports each catalog's age.
6. **Command consolidation and group labels** (G): the overlapping
   commands named in section G fold into their canonical forms with
   aliases kept and documented; picker group labels consistent across the
   picker, `halo models`, `halo providers` and the docs.

## Tests (hermetic, no network)

- Picker: a row-format test per group with known, unknown and sentinel
  values; a pilot test for the hierarchical OpenRouter pick.
- Balances: a fake endpoint per provider in the mock helpers, the cache
  TTL, the chip through the status event, "not offered" rows.
- Enumeration: `--cc`/`--ant` against mocks, the shared cache.
- Error translation: a table-driven test across every provider's shapes;
  the print-mode unconfigured-provider result.
- Catalog refresh: the scheduler with fake fetchers, failure keeps the old
  cache, doctor age line.
- Docs: tests/test_docs_commands.py and test_docs_slash_commands.py stay
  green with the new commands and aliases documented.

## Hard constraints (owner; not negotiable)

- No safety, refusal or "for safety" language anywhere. Describe behaviour.
- No real paths, addresses, hostnames, user names, machine names or keys in
  any repo file; `halo audit privacy` stays at exit 0; privacy scan and
  invariants green.
- No new hard dependency. Never block the UI thread with a network call.
- Keep modules under the house size conventions; split rather than grow.

## Verification before hand-back

Every test module you touched or added, `python test_bridge.py`,
`python tests/test_privacy_scan.py`, `python tests/test_invariants.py`,
`python tests/test_docs_commands.py`, `python tests/test_docs_slash_commands.py`,
`python -m halo_harness audit privacy`, all green. Record
`stat -c %s ~/.halo/history.jsonl` and `ls ~/.halo/sessions | wc -l` at the
start and confirm both unchanged.

## Hand-back format

RESULT LINES (one per deliverable 1-6: DONE / PARTIAL / ALREADY COVERED with
evidence and the pinning test names), FILES TOUCHED, WHAT YOU FOUND (anything
in the old brief that no longer matches the code, anything left open and why,
and the live checks the orchestrator should run per provider). No commit, no
push.

## Added after the round 2 live checks (2026-10-05 evening)

- Deliverable 4 also covers: a turn that exhausts its retries on repeated
  upstream errors (the gateway answered HTTP 502 "error code: 502" six
  times with backoff) ended with an EMPTY print-mode result and nothing on
  stderr. The last upstream status and the translated sentence must be the
  result text (and the stderr line); the TUI shows the same line. Pin it
  with the mock returning 502 on every attempt.
- Translate the Experiential `model_requires_purchase` 429 ("<model> is
  locked on your account until you make a purchase") into one plain line
  that names the model, and treat it as non-retryable.
