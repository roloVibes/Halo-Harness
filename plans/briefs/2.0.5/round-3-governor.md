# Halo 2.0.5 round 3: the Governor (cross-process adaptive rate limiting, priority fairness, failover, lanes)

Repo: `<repo>` (branch master; start from HEAD after round 2). Read
`plans/WORKER-RULES.md` FIRST and follow every rule in it (test
environment: `BRIDGE_TEST_HOME=<fresh scratch dir>`,
`BRIDGE_TEST_NO_BACKGROUND_NET=1`, `OLLAMA_HOST=http://127.0.0.1:1`; never
export `BRIDGE_STATE_DIR` for a whole run). `plans/CYCLE.md` "Budget
discipline" applies: one worker, touched modules plus `python
test_bridge.py`, no full suites. This is the largest round of 2.0.5; the
owner's rule is that it lands LAST among the control-pack features.

Specification: `plans/2.0.2-round8-governor-brief.md` IN FULL (sections 1-5
and "The gate"), `plans/governor-import/README.md` (the owner's report),
`plans/governor-import/REVIEW.md` (its numbered items are part of this
brief) and the vendored kit under `plans/governor-import/governor-kit/`
(port it; never import from `plans/`). The deltas below override the older
brief where they differ.

## Deltas since that brief was written

- State lives under the Halo state dir (`~/.halo`, resolved by the existing
  state-dir helper that `BRIDGE_TEST_HOME` scopes): `<state dir>/governor/`.
- Routes today: `dbx:` `or:` `ant:` `oai:` `hf:` (router and endpoints)
  `xp:` and `ol:` go through `providers/http.py` and are governed, bucket
  key = gateway host (`ol:` and other keyless kinds: provider name plus
  host, so a LAN Ollama host is its own bucket). `cc:` and `cx:` drive a
  CLI child, not HTTP: not governed; say so in the docs.
- One owner of overload retries per route: for governed hosts the Governor
  owns 429/529/5xx backoff and the retry ladder in `agent/loop.py` stops
  retrying those statuses itself; the `xp:` client's published retryable
  codes (`providers/errors.py`, 2.0.4 round 5) map onto Governor events
  instead of a second backoff loop; the W2 steer-restart counter stays
  separate. Transport errors release the permit without cutting the rate;
  two caller-side timeouts in a row count as overload (REVIEW item 7).
- Priorities come from roles and the agent bios: the main session and the
  `orchestrator` kind 0; `judge`, `reviewer`, `verifier`, `tester`,
  `planner` 1; every other agent 2; `governor.priorities` overrides;
  `agents/<name>.yaml` may set `limits.priority` (0-2) explicitly.
- Lanes (section 4): tiers are declared per model row (`tier` 1-3, defaults
  for the known families, local `ol:`/`hf:` local models default to tier 2
  or 3 by size with the gym score as the tie-breaker when one exists);
  `roles.lanes` maps roles to the weakest tier they may use; the roles
  validator refuses a configuration where reviewer, judge or tester resolve
  to a weaker tier than coder, with one line naming the role to raise. The
  team-template loader (`teams_yaml.py`) runs the same validator over a
  template's assignments and reports one plain line per problem.
- Config keys exactly as the older brief lists them (`governor.*`, per host
  under `governor.hosts.<netloc>`); CHANGELOG section is `[2.0.5]`
  "### Governor"; docs/GOVERNOR.md new, linked from HANDBOOK, COMMANDS,
  MODELS, ROLES and the agents/teams doc.
- Surfaces: `/gov` and `halo gov [host]` print `inspect_all()` and the
  recent calls of one host; the status bar's overflow cascade shows
  `gov <rate> rps / cooldown <n> s` only while a bucket is below its
  ceiling; `halo doctor` shows each known gateway's health; the failover
  notice names the health that caused the switch.

## Deliverables

1. `providers/governor.py` (+ `providers/governor_state.py` for locking and
   persistence if the module passes ~700 lines) and
   `providers/gateway_routing.py`: the port with REVIEW items 1-15 and the
   eight improvements from the older brief's section 1 applied.
2. Integration at `providers/http.py` (one choke point) carrying role,
   agent id and priority; the retry-ownership change in `agent/loop.py`.
3. Failover (section 3) wired into the fallback-model mechanism and
   `roles.<name>.fallbacks`; the config loader warns when a fallback shares
   the primary's host.
4. Lanes (section 4, with the deltas above).
5. Surfaces: `/gov`, `halo gov`, status-bar cascade, doctor health line,
   telemetry event `governor_state_unpersisted`.
6. Docs and CHANGELOG as above.

## Tests (hermetic)

Port the kit's twelve tests to the house runner (`tests/helpers/`, the
`Ctx`/`run_all`/`print_results` pattern), then add: the gate (six fake
processes against the mock upstream returning a 429 storm with
`Retry-After`: rate cut, cooldown set, the priority-0 waiter still
completes, failover lands on the fallback host), Windows locking
(`msvcrt`) and POSIX locking behind one context manager, corrupt-state
recovery, `Retry-After` as HTTP-date, timeout counting, clock-skew clamp,
log rotation, the lane validator (roles table and team template), `/gov`
output, doctor's health line, the `agent/loop.py` retry-ownership change,
and the `xp:` retryable-code mapping. No network, no real model.

## Hard constraints (owner; not negotiable)

- No safety, refusal or "for safety" language anywhere: the Governor paces
  and fails over, it never declines a request. Fail-open is one half-open
  probe for the front waiter after `max_wait`, never a bail-out.
- No real paths, addresses, hostnames, user names, machine names or keys in
  any repo file (the kit's README mentions the owner's other projects by
  placeholder only; keep it that way in docs); `halo audit privacy` exit 0;
  privacy scan and invariants green.
- No network in tests; never read the owner's key files.
- Stdlib only, no new hard dependency. House size conventions.
- Never block the UI thread: `acquire()` runs on the request worker with
  the cancellation hook REVIEW item 3 asks for, so `/stop` and a steer
  interrupt a waiting request.

## Verification before hand-back

Touched and new test modules, `python test_bridge.py`,
`python tests/test_privacy_scan.py`, `python tests/test_invariants.py`,
`python tests/test_docs_commands.py`, `python tests/test_docs_slash_commands.py`,
`python -m halo_harness audit privacy`, all green. Record
`stat -c %s ~/.halo/history.jsonl` and `ls ~/.halo/sessions | wc -l` at the
start and confirm both unchanged.

## Hand-back format

RESULT LINES (one per deliverable 1-6: DONE / PARTIAL / ALREADY COVERED with
evidence and the pinning test names), FILES TOUCHED, WHAT YOU FOUND (which
REVIEW items changed behaviour versus the kit, the retry paths you removed
from the loop, anything left open and why, the live check for the
orchestrator: a two-session run against one gateway host showing the shared
bucket in `/gov`). No commit, no push.
