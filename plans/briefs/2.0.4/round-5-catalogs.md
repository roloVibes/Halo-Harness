# Halo 2.0.4 round 5: Databricks enumeration, new-labs coverage, xp: contract alignment

Repo: `<repo>` (branch master; start from HEAD after round 4). Read
`plans/WORKER-RULES.md` FIRST and follow every rule in it (test
environment: `BRIDGE_TEST_HOME=<fresh scratch dir>`,
`BRIDGE_TEST_NO_BACKGROUND_NET=1`, and `OLLAMA_HOST=http://127.0.0.1:1` so a
test never reaches a real local daemon). Three roadmap items share one
round because they all touch catalogs and the picker; `plans/CYCLE.md`
"Budget discipline" applies: one worker, touched modules plus
`python test_bridge.py`, no extra suites.

Specifications (read each in full):
- `plans/ROADMAP.md` section "ADDED 2026-10-05 ~11:40 (rolo, from the picker
  on the Kali VM): 2.0.4 provider-pack round 'Databricks enumeration'".
- `plans/ROADMAP.md` section "ADDED 2026-10-05 ~12:40 (rolo): 2.0.4 'new
  labs' coverage" (Space Bunny Alpha, Tencent, TypeSafe, NVIDIA; the five
  round-work items; note round 2 already built the `xp:` catalog mapping
  and round 3 the "varies"/"free" rendering: verify, extend, do not
  duplicate).
- `plans/ROADMAP.md` section "ADDED 2026-10-05 ~23:10: 2.0.4 round 'xp:
  contract alignment'". The gateway's machine-readable contract is at
  `https://platform.experientiallabs.ai/llms.txt`; fetch it ONCE at the
  start of the round into the scratch dir (it is public), never into the
  repo, and work from it literally.

## Deliverables

1. **Databricks rows carry context, output and prices.** The family
   fallback described in the section (strip the `databricks-` prefix,
   normalise version punctuation, parse external endpoint ids) looks the
   model up in the vendor's own models.dev entry; rows show a "vendor list
   price" marker when the figure comes from the fallback. Read what the
   serving-endpoints API exposes per endpoint (task, foundation model
   name, state) and use it to fill the model name and availability. Pinned
   by a fixture of the ids the section lists.
2. **New-labs coverage**: an `or:` or `xp:` id with no vendored catalog
   row gets a live lookup for context, price and tools instead of blank
   columns (the same gap Databricks had); `:free` variants sort beside
   their paid row; the docs/MODELS.md "How to run" table and the
   data-policy note are checked against the current catalogs.
3. **xp: contract alignment**: the full error-code table from llms.txt
   (every code, the retryable set exactly as published), the honored and
   refused parameters per endpoint (a refused parameter is a 400 that names
   it; the `x-experiential-ignored-parameters` header for dropped ones feeds
   the existing learned rule), the per-response headers (`x-request-id`,
   `x-gateway-provider`, `x-gateway-zdr`, `x-gateway-route-depth`,
   `x-gateway-route-reason`) captured and shown on the transcript line and
   in `/xp routes`, the ZDR toggle and per-request `provider.zdr` constraint
   as config keys, the two billing lanes in the cost line, and
   `GET /api/v1/generation?id=<x-request-id>` in `halo stats --experiential`
   for after-the-fact attribution. A bare `502` with no JSON body reads as
   "every route failed, try again later".
4. Docs: MODELS.md (Databricks fallback marker, the contract items),
   CONFIG.md (new keys), CHANGELOG `[2.0.4]` bullets under "### Catalogs".

## Tests (hermetic)

Fixtures only: the Databricks id list, a models.dev vendor fixture, an
OpenRouter row without a vendored entry served by the mock, the Experiential
mock extended with the headers and the error codes. The live checks
(Databricks picker on the owner's VM, an `xp:` turn showing the route
headers, a `:free` row) are the orchestrator's.

## Hard constraints (owner; not negotiable)

- No safety, refusal or "for safety" language anywhere.
- No real paths, addresses, hostnames, user names, machine names or keys in
  any repo file; `halo audit privacy` exit 0; privacy scan and invariants
  green. The llms.txt copy stays outside the repo.
- No network in tests; never read the owner's key files; never print a key.
- No new hard dependency. Keep modules under the house size conventions.

## Verification before hand-back

Touched and new test modules, `python test_bridge.py`,
`python tests/test_privacy_scan.py`, `python tests/test_invariants.py`,
`python tests/test_docs_commands.py`, `python -m halo_harness audit privacy`,
all green. Record `stat -c %s ~/.halo/history.jsonl` and
`ls ~/.halo/sessions | wc -l` at the start and confirm both unchanged.

## Hand-back format

RESULT LINES (one per deliverable 1-4: DONE / PARTIAL / ALREADY COVERED with
evidence and the pinning test names), FILES TOUCHED, WHAT YOU FOUND (what the
contract contradicted in the code, anything left open and why, the live
checks for the orchestrator). No commit, no push.
