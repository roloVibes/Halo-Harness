# Halo 2.0.5 round 3: learned gateway rules + the legacy env-file drop

Repo: `<repo>` (branch master; start from HEAD after round 2). Read
`plans/WORKER-RULES.md` FIRST and follow every rule in it (test
environment: `BRIDGE_TEST_HOME=<fresh scratch dir>`,
`BRIDGE_TEST_NO_BACKGROUND_NET=1`, `OLLAMA_HOST=http://127.0.0.1:1`).
`plans/CYCLE.md` "Budget discipline" applies: one worker, touched modules
plus `python test_bridge.py`, no full suites. Two small roadmap items share
one round because both end in `providers/config.py` and the request path.

Specifications (read each in full):
- `plans/2.0.3-brief.md` item "G1. Learned gateway rules, generalised from
  the 1.0.1 gpt-6 rule".
- `plans/2.0.4-brief.md` section "5. Deprecations" (the legacy env file) and
  `plans/2.0.3-brief.md` item "G7. Deprecation". The CHANGELOG [2.0.1] and
  [2.0.2] notices announced the drop; `plans/ROADMAP.md` "REORDERED
  2026-10-05" moved it here with the same notice period.

## Where the code is

`halo_harness/providers/learned_rules.py` (the store: `learned-rules.json`
under the state dir, keyed `<provider>:<model>`, today holding
`reasoning_effort_with_tools`, ignored-parameter headers, `tools_rejected`
with a 24 h TTL, and the MCP fix signatures from 2.0.4 round 6; every
existing key and reader keeps working), its callers in
`providers/profiles.py`, `providers/request.py` and `agent/loop.py`; the 400
handling sites in `providers/http.py` (~line 817) and `providers/stream.py`
(three `result.status == 400` branches); `providers/errors.py` (the
translation table; a learned fix prints its own line, it does not replace
the translation); the legacy env file: `config/paths.py`
(`_LEGACY_ENV_DIR_NAME`, `legacy_env_file_path`, `ENV_IMPORT_MARKER`,
`env_file_has_import_marker`, `env_file_path_for_write`),
`providers/config.py` (`load_provider_env_files`, the MCP child env
stripping), `doctor.py` (`_load_env_for_doctor` or its current name),
`init_cli.py`, `bridge.py --probe`; tests `tests/test_paths.py`,
`tests/test_learned_rules*.py`.

## Deliverables

1. **One learned-rule engine for parameter rejections.** On any 400 or 422
   whose body names a request field from the list in G1 (reasoning_effort,
   temperature, top_p, tool_choice, max_tokens, max_completion_tokens,
   thinking, output_config, response_format, parallel_tool_calls, strict,
   store, stream_options, metadata, the Databricks allowlist words), one
   function plans the smallest fix (drop the field; when the message lists
   allowed values, clamp to the nearest allowed one), the request is retried
   ONCE, and the rule is persisted as
   `{"<provider>:<model>": {"params": {"<field>": {"action": "drop"|"clamp",
   "value": ..., "error": "<first 200 chars>", "date": "<ISO>"}}}}` beside the
   existing keys. The transcript prints one line in the house voice
   (`Databricks rejected thinking on this endpoint; dropped it and retried;
   remembered for this endpoint`). A `model_table.json` row still wins over
   a learned rule (today's precedence). Rules older than 30 days are tried
   once without the fix before being reapplied. The `xp:`
   `x-experiential-ignored-parameters` learning from 2.0.4 feeds the same
   store shape (migrate its reader, keep its tests green).
2. **`halo rules` and `/rules`** list the rules (endpoint, field, action,
   age); `halo rules --forget <provider:model>` and `halo models refresh
   --forget-rules` clear them; `halo doctor --probe-all --learn` pre-learns
   by sending one minimal request per optional parameter to each
   configured Databricks endpoint (opt-in, prints the cost estimate first,
   never runs without the flag).
3. **The legacy env file is no longer read.** `load_provider_env_files()`
   loads only `env_file_path()`; the import-marker logic becomes a no-op
   kept for the test seams; `halo init`'s one-time copy-forward on first
   write stays (that is the migration); the legacy file is never modified
   or deleted (other tools on the same box read it). `halo doctor` prints
   one WARN when the legacy file exists and the new file does not, naming
   `halo init` as the migration, and nothing when the new file exists.
4. **Docs and CHANGELOG**: docs/CONFIG.md (the rules store, the single env
   file), docs/COMMANDS.md and docs/SLASH-COMMANDS.md entries for `rules`,
   HANDBOOK's credentials paragraph; CHANGELOG `[2.0.5]` "### Learned
   gateway rules" and "### Deprecations" (the drop, with the two earlier
   notices named by version).

## Tests (hermetic)

The mock gateway returns each rejection shape seen so far: gpt-6
`reasoning_effort` with tools, GLM `thinking`, Claude `output_config`
`xhigh`, an unknown-field 400, an allowed-values 422 (clamp), and a 400 that
names no field (no fix, normal error translation). Pin: fix planned and
applied, exactly one retry, persistence shape, the transcript line, the
30-day re-try, `--forget`, `--forget-rules`, precedence of a table row,
the migrated `xp:` ignored-parameters reader. Env file: a scratch home with
only the legacy file -> no key loaded and the doctor WARN line; with the
new file -> loaded and no WARN; the marker helper's no-op; `init`
copy-forward unchanged. No network, no real model.

## Hard constraints (owner; not negotiable)

- No safety, refusal or "for safety" language anywhere; a learned rule
  describes what the gateway rejected, nothing more.
- No real paths, addresses, hostnames, user names, machine names or keys in
  any repo file; `halo audit privacy` exit 0; privacy scan and invariants
  green. The legacy directory name stays in exactly one constant.
- No network in tests; never read the owner's key files; never print a key.
- No new hard dependency. House size conventions (`learned_rules.py` may
  split into `learned_rules.py` + `learned_params.py`).

## Verification before hand-back

Touched and new test modules, `python test_bridge.py`,
`python tests/test_privacy_scan.py`, `python tests/test_invariants.py`,
`python tests/test_docs_commands.py`, `python tests/test_docs_slash_commands.py`,
`python -m halo_harness audit privacy`, all green. Record
`stat -c %s ~/.halo/history.jsonl` and `ls ~/.halo/sessions | wc -l` at the
start and confirm both unchanged.

## Hand-back format

RESULT LINES (one per deliverable 1-4: DONE / PARTIAL / ALREADY COVERED with
evidence and the pinning test names), FILES TOUCHED, WHAT YOU FOUND (which
rejection shapes the current code already handled, what the drop removed,
anything left open and why). No commit, no push.
