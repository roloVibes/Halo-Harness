# The Governor

One shared, adaptive rate limiter per gateway **host**, visible to every
halo process on the machine. Two models served by one gateway share one
limit, because the gateway enforces it per machine, not per model. The
problem it solves: every terminal, session and sub-agent on the box
hitting the same gateway until *all* of them trip the same 429.

Five properties:

1. **Cross-process** -- state lives on disk under
   `<state dir>/governor/` (`~/.halo/governor/`), file-lock-guarded
   (flock on POSIX, byte-range locks on Windows, one lock-timeout
   fallback), so three terminals share one limit. `GOVERNOR_STATE_DIR`
   overrides the location so Halo and another tool on the same box can
   share one limiter.
2. **Adaptive (AIMD)** -- a 429/529/502/503/504 cuts the allowed rate
   (`rate *= backoff_mult`, floored at `rate_floor`) and sets a cooldown
   honouring `Retry-After` (delta-seconds or HTTP-date, capped at
   `retry_after_cap`); `ramp_after` consecutive successes add `ramp_inc`
   back toward the ceiling. A plain 500 is neutral unless the body says
   overloaded -- a server bug must not slow the whole fleet.
3. **Concurrency-capped** -- a hard cross-process in-flight cap per host;
   a killed caller's permit is reaped (its pid is gone), a live one's
   only after 30 minutes.
4. **Priority-fair** -- when permits are scarce the highest-priority
   live waiter goes first: the main session and `orchestrator` 0;
   `judge`, `reviewer`, `verifier`, `tester`, `planner` 1; every other
   agent 2. `governor.priorities` (config) overrides the role table; an
   agent bio's `limits.priority` (0-2) wins over the role. So the
   orchestrator always gets through and records state for the others.
5. **Observable** -- every call is logged (agent, role, session, model,
   status). `/gov` in the TUI and `halo gov [host]` print every bucket
   and one host's recent calls; `halo doctor` shows each gateway's
   health; the status bar shows `gov 4.0 rps / cooldown 12 s` while a
   bucket is paced below its ceiling.

Fail-open is ONE half-open probe for the front waiter after `max_wait`
-- never a bail-out, and never past the in-flight cap. Transport errors
release the permit neutrally (a dead network is not an overloaded
gateway); two caller-side timeouts in a row count as overload. If the
state directory becomes unwritable the Governor warns once, emits a
`governor_state_unpersisted` event, and keeps enforcing in-process
rather than silently resetting to full budget.

## What is governed

Every remote model request -- Databricks (`dbx:`), OpenRouter (`or:`),
Anthropic (`ant:`), OpenAI (`oai:`), Hugging Face (`hf:`), Experiential
(`xp:`) and Ollama (`ol:`, including LAN hosts: a keyless host keys on
the provider name plus host, so a LAN model server is its own bucket) --
goes through one choke point in `providers/http.py`. The `cc:` and `cx:`
routes drive a CLI child process, not HTTP: **not governed**.

The Governor owns the 429/overload backoff and retry ladder for
governed routes; the agent loop's own ladder steps aside for those
(it still retries everything else -- a spurious 404, an empty
completion). The Experiential gateway's published retryable codes map
onto Governor events the same way: an `xp:` 429 is paced and retried by
the Governor; a retryable non-overload code (the 409 idempotency
replay, for instance) keeps the loop's ladder.

Two accounts on one host share a bucket **on purpose** -- the gateway
throttles per machine. Which is also why a fallback model on the same
host as the primary cannot help: `halo roles` warns when
`roles.<name>.fallbacks` configures one.

## Failover

When a role's primary gateway is in trouble, new work reroutes to a
healthy alternate so every agent keeps running: fallback candidates
(the model itself, the CLI `--fallback-model` list, then
`roles.<name>.fallbacks`) are ordered by gateway health -- `open`
circuit-breakers (a cooldown over 8 s or three consecutive errors) are
skipped, `degraded` ones are usable, and when every host is open the
least-cooled one is chosen and the Governor paces it. The switch notice
names the health that caused it.

## Lanes

A lane is a role-to-tier rule: models carry a `tier` (1 strongest ..
3 cheapest; sane family defaults, an explicit `tier` in the model table
wins, the gym score is the tie-breaker for local models), and
`roles.lanes` maps a role to the weakest tier it may use. The standing
rule: **reviewer, judge and tester must never resolve to a weaker tier
than coder** -- the roles validator refuses such a configuration with
one line naming the role to raise, and the team-template loader runs
the same check over a lineup's resolved assignments.

## Config

`governor.*` in config.json, per-host overrides under
`governor.hosts.<netloc>`:

| key | default | meaning |
|---|---|---|
| `enabled` | `true` | the one switch (`HALO_GOVERNOR=0/1` forces it) |
| `rate_rps` | 8.0 | the ceiling, requests/second |
| `burst` | 8 | token bucket size |
| `max_inflight` | 6 | hard cross-process in-flight cap |
| `rate_floor` | 0.25 | the AIMD floor |
| `ramp_after` / `ramp_inc` | 5 / 0.5 | additive ramp-back |
| `backoff_mult` / `cooldown_base` | 0.5 / 2.0 | multiplicative cut, exponential ladder base (capped at 2^6) |
| `max_wait` | 120 | fail-open horizon for the front waiter |
| `max_retries` | 5 | overload retries the Governor owns |
| `retry_after_cap` | 120 | the most one `Retry-After` header can ask |

## Reading a 429 storm

`/gov` (or `halo gov`) shows the rate cut and the cooldown; the
status bar's `gov` segment carries it live; `recent_calls` for the host
shows which agents and models were hitting it. The priority-0 caller
still completes (priority fairness), and once the cooldown elapses the
half-open probe lets the front waiter through -- successes ramp the
rate back toward the ceiling.
