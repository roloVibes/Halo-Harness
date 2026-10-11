# Review fix pass: final sweep (after round 10)

Every numbered finding 1-92 (and the minor list) walked against the tree at
the end of round 10. Status key: FIXED rN = fixed and pinned in round N;
REJECTED = not applied, by the standing contract or because the finding does
not hold against the code; LEFT = genuinely open.

Standing contract (plans/HANDOFF.md): deny rules hold in every mode; auto
mode with no rules stays allow; classifier-shaped suggestions are rejected.

## Summary

- Fixed: 89 of 92 (rounds 1-10, plus 26 and 31 closed by the sweep itself).
- Rejected: 18 (does not hold), 3 and 4 (contract). Finding 6 was applied in
  its contract-safe form (listed as FIXED r4, contained).
- Genuinely open: none. The minor list is closed too.

## P0: permission engine

| # | Status |
|---|--------|
| 1 | FIXED r4: a here-string no longer hides the commands after it |
| 2 | FIXED r4: wrappers with options, groups, process substitution, absolute paths, eval/shell -c all reach deny matching |
| 3 | REJECTED (contract): an inert-variable allowlist is a classifier-shaped suggestion; auto mode with no rules stays allow |
| 4 | REJECTED (contract): refusing allow matches on substitution is classifier-shaped; deny-side matching of substitution bodies is covered by 2 |
| 5 | FIXED r4: git grep pager option blocked; branch and tag read-only only in list form |
| 6 | FIXED r4 (contained): sed dropped from the acceptEdits list; redirects, option=path, glob and brace tokens stop the auto-allow |
| 7 | FIXED r4: Bash paths judged against the live working directory |
| 8 | FIXED r4: Task canonicalized to Agent for rules and catalog removal |
| 9 | FIXED r4: plan-mode write ban runs before allow rules |
| 10 | FIXED r4: Read deny rules gate Bash file readers |
| 11 | FIXED r4: project and plugin agent files cannot raise their own mode or merge hooks; no child is more permissive than its parent |
| 12 | FIXED r4: the improve target path is contained in its base directory |
| 13 | FIXED r4: completion scripts emit only shell-inert words |

## P0: credential exposure

| # | Status |
|---|--------|
| 14 | FIXED r2: the proxy launch file is private and atomic (shared private-write helper) |
| 15 | FIXED r2: env-file writer atomic, private, no parent chmod |
| 16 | FIXED r2: redactor learned the missing secret shapes and no longer mangles numeric usage keys |
| 17 | FIXED r2: release script keeps the token off the process list, upload failures surface |
| 18 | REJECTED (does not hold): WebFetch only returns to plain http when the caller typed an http URL (it tries https first); an https URL is never retried as http. Pinned in round10c |

## P0: data loss

| # | Status |
|---|--------|
| 19 | FIXED r3: config writers refuse to write over a file that does not parse |
| 20 | FIXED r3: worktree removal deletes only halo-owned branches, with the safe delete |
| 21 | FIXED r3: launch no longer rewrites the Claude settings file unless content changed; atomic; honors the config-dir override |
| 22 | FIXED r3: roles edit refuses to replace a template that exists but does not load |
| 23 | FIXED r3: shadow snapshots include ignored files |

## P0: crashes and hangs

| # | Status |
|---|--------|
| 24 | FIXED r1: undefined model_ref in the sub-agent offline path |
| 25 | FIXED r1: outcome read before assignment in the background team path |
| 26 | FIXED r10 (sweep): fired jobs carry HALO_SCHEDULED_FIRE=1 and do not arm schedules again; pinned in round10c |
| 27 | FIXED r3: history search option ids are indices |
| 28 | FIXED r3: option labels rendered as Text, not markup |
| 29 | FIXED r3: slash dispatch and workers catch errors; run-slash spawns do not exit the app |
| 30 | FIXED r3: malformed MCP config entries are disabled, not fatal; string args shell-split |
| 31 | FIXED r10 (sweep): the bridge writer replaces lone surrogates instead of dying; pinned in round10c |

## P1: model calls and providers

| # | Status |
|---|--------|
| 32 | FIXED r1: small-model calls build the native Anthropic request on ant: and Databricks Claude routes |
| 33 | FIXED r7: team escalation goes through the model switch and re-pins the snapshot |
| 34 | FIXED r1: ant: and xp: branches pass the governor context (retries on 429/529) |
| 35 | FIXED r1: retried calls restore the long read timeout |
| 36 | FIXED r1: Databricks Claude 404 fallback route and error body |
| 37 | FIXED r1: 500 error bodies survive the governor's peek |
| 38 | FIXED r7: count_tokens builds per-provider auth and path |
| 39 | FIXED r7: proxy credentials become Proxy-Authorization |
| 40 | FIXED r7: a plain JSON 200 on the Anthropic stream is turned into events |

## P1: MCP

| # | Status |
|---|--------|
| 41 | FIXED r3: variables in remote url and headers expand to the real value; redacted only for display |
| 42 | FIXED r3: first-use connect holds a per-server lock |
| 43 | FIXED r7: OAuth refresh and the SSE fallback also wrap initialize |
| 44 | FIXED r7: start budgets cover both connect phases |
| 45 | FIXED r7: OAuth refresh runs off the event loop |
| 46 | FIXED r7: the TCP preflight respects a configured proxy |
| 47 | FIXED r7: a timed-out clone is never cached; the url rides behind the option terminator |
| 48 | FIXED r5: slash-command argument substitution is one pass; indexed arguments implemented |

## P1: agent loop

| # | Status |
|---|--------|
| 49 | FIXED r8: reads queued before an Agent call finish first |
| 50 | FIXED r5 (whitelist half) and r8 (the model's own timeout is honored in the read-only pool) |
| 51 | FIXED r8: text typed during compact or clear is delivered in order |
| 52 | FIXED r8: the forced tool-choice retry no longer feeds the overflow sentinel to usage accounting |
| 53 | FIXED r8: Esc does not start the queued read-only batch; waiter slots do not leak |

## P1: sub-agents and roles

| # | Status |
|---|--------|
| 54 | FIXED r8: the concurrent-resume guard is claimed under a lock |
| 55 | FIXED r8: a Stop-hook continuation on cc: routes is read in the same turn |
| 56 | FIXED r8: resume keeps the original role, model, effort and org overrides |
| 57 | FIXED r8: team max_parallel survives each batch |
| 58 | FIXED r8: the role table is recomputed on role and model switches |
| 59 | FIXED r5: resolve_role_ref accepts inherit and unresolvable values |
| 60 | FIXED r8: team-defined role names are accepted |
| 61 | FIXED r8: an agent file's Agent(X) tool restriction reaches children |
| 62 | FIXED r8: agent export writes the keys the loader reads |
| 63 | FIXED r5: cron weekday 7 is Sunday; day-of-month and weekday are ORed |
| 64 | FIXED r8: worktree leak on a failed model resolve, org budget on resume, non-string reports |

## P1: TUI

| # | Status |
|---|--------|
| 65 | FIXED r5: in-TUI resume and the session picker switch the live session |
| 66 | FIXED r5: lineup editor commits on submit, blur or pick |
| 67 | FIXED r9: xclip/xsel copies are no longer reported as failed |
| 68 | FIXED r9: a typed slash command keeps pending image attachments |
| 69 | FIXED r9: shadow snapshots run on one worker thread, restore waits for them |
| 70 | FIXED r9: roles editor save with the effort prompt open keeps the picked model |
| 71 | FIXED r9: pending-card hand-offs serialized |
| 72 | FIXED r9: recalled pasted prompts restore their paste contents |
| 73 | FIXED r9: deleting an image chip drops its image |
| 74 | FIXED r9: invalid YAML in the lineup editor stops the save and names the section |
| 75 | FIXED r9: title counter reset on clear; stream-json notices cleared per result; final line written on budget stop |

## P1: CLI, session, doctor

| # | Status |
|---|--------|
| 76 | FIXED r9: -p -c with no prior session fails with exit 2; a foreign transcript is imported on resume |
| 77 | FIXED r9: providers setup for the listed providers no longer dies in argument parsing; doctor suggests valid values |
| 78 | FIXED r9: doctor --json modes print only JSON |
| 79 | FIXED r1: doctor's permission-mode check calls the real settings resolver |
| 80 | FIXED r9: PATH check uses a clean login shell and the rc file a login shell reads |
| 81 | FIXED r5: preflight identifies the lane from env, config or routes and fails loudly when it cannot |
| 82 | FIXED r9: a fork made with no-session-persistence is deleted |
| 83 | FIXED r9: -w validates session flags before creating the worktree |

## P1: telemetry, stats, other modules

| # | Status |
|---|--------|
| 84 | FIXED r10: rollup nodes carry the child's model; stats and /stats charge the child's row; legacy rollups get a (sub-agents) row |
| 85 | FIXED r10: schema-versioned stats cache; deleted sessions pruned |
| 86 | FIXED r10: replay skips every user kind the log writes |
| 87 | FIXED r10: start-time fingerprint from ps where there is no /proc; finished runs are never "ours" |
| 88 | FIXED r10: recall temp file unique, prune only vanished sources, unchanged logs not re-read |
| 89 | FIXED r10: log readers split at newline only (replay, fork truncation, recall, session readers, history) |
| 90 | FIXED r10: digest-less gym results keyed by model; never-raises made true; scratch removed |
| 91 | FIXED r10: piped stdin spooled and handed to the detached child |
| 92 | FIXED r10: advisory lock plus unique temp files for state, update cache and history; history 0600 and torn-line safe |

## Minor list (P2)

| Item | Status |
|------|--------|
| ollama JSON getter and HTTP exceptions | FIXED r7 |
| Databricks 404 connection leak and cached failing route | FIXED r7 |
| OpenRouter cache-write tokens billed as input | FIXED r7 |
| canary estimate counting base64 image data | FIXED r5 |
| OAuth callback accepting any path or a single request | FIXED r7 |
| mcp disable/enable writing one project-key form | FIXED r7 |
| privacy-rule ci: terms with capitals | FIXED r5 |
| gym tool-task docstring versus code | FIXED r7 |
| NotebookEdit categorization reading the wrong key | FIXED r5 |
| unreachable return in the models catalog module | FIXED r5 |

## Notes for the orchestrator

- Closed by the sweep itself (not in the round 10 brief): 26 and 31, both
  small and both pinned in tests/test_review2_round10c.py; revert them
  together with their tests if the tag should carry only the briefed items.
- Rounds 6 and 7 have no changelog section; their fixes are recorded in the
  commit messages and the round tests (tests/test_review2_round7.py).
- Round 1-5 evidence is the changelog bullets plus tests/test_review2_round1
  through round5; findings 11, 21, 22, 29, 65 and 66 have no dedicated
  round test (changelog bullet plus the code comment at the fix site).
