# Halo 2.0.4 round 2: Experiential Labs `xp:` route, fully integrated

Repo: <repo> (branch master; start
from HEAD = 36dd433 or later). Read `plans/WORKER-RULES.md` FIRST and follow
every rule in it (test environment: `BRIDGE_TEST_HOME=<fresh scratch dir>`
and `BRIDGE_TEST_NO_BACKGROUND_NET=1` only).

The specification is already written; this brief points at it and adds the
2.0.4 items:

1. `plans/2.0.3-ollama-round2-brief.md`, section "## Round 5h: Experiential
   Labs, fully integrated" (starts near line 608) -- the deliverables, the
   `xp:` ref grammar, the picker group, the dialect choice, the settings and
   docs. Read it in full. Where 5h cites "Round 5g findings", those are in
   `docs/harness/EXPERIENTIAL-RESEARCH.md` (sections 1-12: what differs from
   `or:`, auth and key handling, request grammar, the catalog, the waterfall,
   cost and credits, errors, the local gateway, embeddings, jev-latest, the
   feature-to-surface map, corrections to the roadmap bullets). The research
   doc is the source of truth over any older summary.
2. `plans/ROADMAP.md`, section "ADDED 2026-10-05 ~12:40 (rolo): 2.0.4 'new
   labs' coverage" -- the catalog fields the gateway really publishes
   (`context_window_tokens`, `maximum_output_tokens`,
   `pricing.*_nano_usd_per_million_tokens` divided by 1e9 for $/M with 0 =
   free and null = unknown shown differently, `supported_reasoning_efforts`
   and the default `reasoning_effort`, `reasoning_output_hidden`,
   `supports_tools`, `data_policy.no_training` / `zdr` as a picker badge),
   and the "How to run" docs table (Space Bunny Alpha, Nemotron 3.5
   Lightning, hy4-preview, jev-router) with the data-policy note.
3. Round 5h's own amendments recorded in that section: thinking is native
   only on the Anthropic-shaped rung; the inference key versus the
   provisioning key; `defer_loading` tool search behaviour.

## Deliverables (in the order to build them)

1. Provider: `halo_harness/providers/experiential.py` (+ a request/stream
   module if the existing OpenAI-shaped builders cannot be reused as is):
   `xp:<slug>` refs, base URL `https://api.experientiallabs.ai/v1`, bearer
   inference key from `EXPLABS_API_KEY` (env or the shared env file, the
   same resolution every other provider uses; never log it), the gateway's
   two dialects (OpenAI-shaped chat completions for most slugs, the
   Anthropic shape for Claude slugs with native thinking), tool calling,
   structured output, streaming with usage, the gateway's error shapes
   (`unsupported_capability` etc.) translated into Halo's one-line
   messages, the retry/overflow behaviour the research doc describes.
2. Catalog: `halo_harness/providers/experiential_catalog.py`: `GET
   /v1/models` cached under the state dir with the fields listed above,
   refresh on `/models refresh`, `halo models --refresh` and the launch
   auto-refresh (the same hooks round B-2 wired for OpenAI); vendored
   fallback snapshot `halo_harness/catalog/experiential-models.json`
   (fetch it once with the key and commit the JSON; it carries no secret).
3. Picker and `/model`: an "Experiential" group with the same columns as
   the other groups (price in $/M, context, speed where known), `free` and
   `varies` rendered as words, the data-policy badge, and tab completion
   for `xp:` slugs. Also the OpenRouter price `-1` rendering fix ("varies")
   and the "1M"/"2M" context format from the roadmap section, since the
   same column code is touched.
4. Enablement and doctor: `halo providers` row, `halo doctor` section
   (key present, catalog reachable, balance when the account endpoint
   answers), the init wizard tab (key only; stored the way C-1 stores
   secrets: env file + reference), `halo audit privacy` already knows the
   `xpl_` token shape.
5. Cost: the saved-versus-cloud meter and the cost line read the gateway's
   per-model prices; a $0 preview model shows "free (preview)".
6. Docs: docs/MODELS.md "Experiential Labs" section and the "How to run"
   table, docs/CONFIG.md, docs/COMMANDS.md, the enablement prefix table
   (which still lacks `hf:`, `oai:`, `cx:` rows: add `xp:` and those three),
   CHANGELOG `[2.0.4]` "### Experiential Labs" bullets.

## Tests (hermetic)

- A mock gateway in tests/helpers (extend mock_openai if its shape fits:
  the gateway is OpenAI-compatible plus its own error codes and catalog
  fields) covering chat completions with tools, streaming usage, the
  Anthropic-shaped rung, `unsupported_capability` 400, the catalog
  endpoint with the real field names (use the vendored snapshot as the
  fixture), and an account/balance endpoint.
- tests/test_experiential_provider.py, tests/test_experiential_catalog.py,
  picker/column tests extended, enablement and doctor tests extended.
- No network in tests. The live check against the real gateway with the
  owner's key is the orchestrator's job after hand-back; you never read
  the key file (`vibes/Exp key.md`) and never print a key.

## Hard constraints (owner; not negotiable)

- No safety, refusal or "for safety" language anywhere. Describe behaviour.
- No real paths, addresses, hostnames, user names, machine names or keys in
  any repo file (`halo audit privacy` must still return 0; the privacy scan
  and invariants tests must stay green).
- No new hard dependency.
- Keep each file under the house size conventions (split modules rather
  than growing one past ~400 lines).

## Verification before hand-back

The new test modules, every test module you touched, `python test_bridge.py`,
`python tests/test_privacy_scan.py`, `python tests/test_invariants.py`,
`python -m halo_harness audit privacy` (exit 0), all green. Record
`stat -c %s ~/.halo/history.jsonl` and `ls ~/.halo/sessions | wc -l` at the
start and confirm both unchanged.

## Hand-back format

RESULT LINES (one per deliverable 1-6: DONE / PARTIAL with evidence and the
pinning test names), FILES TOUCHED, WHAT YOU FOUND (anything the research doc
got wrong, anything left open and why, and the exact live checks the
orchestrator should run with the real key: slugs, prompts, expected shapes).
No commit, no push.
