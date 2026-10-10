# Halo 2.0.7 fix pass, round 7b: the subscription routes are off until the user accepts the terms risk

Owner's decision (rolo, 2026-10-09 ~23:10): "if Halo discovers subscription
creds that might lead to a ban, that feature should be off by default and
then a big alert and acceptance needs to happen before that even turns on."
This is a consent gate the owner chose for his users; it is not safety or
refusal logic and must never be described as such.

Facts to state in the notice and the docs: Halo never reads the Claude
Code OAuth token (`~/.claude/.credentials.json`) or Codex's credentials; the
`cc:` route drives the official `claude` binary in its documented headless
mode and `cx:` drives the official `codex` binary; both still use the
user's personal subscription through a third-party harness, and the
provider's terms govern the account; there have been public reports of
account restrictions for tools that use subscription tokens outside the
provider's own products. No claim about individual cases.

Repo: `<repo>` (branch master; start from HEAD after round 7, clean). Read
`plans/WORKER-RULES.md` FIRST (test environment as always). `plans/CYCLE.md`
"Budget discipline" applies.

## Deliverables

1. **Off by default.** `cc:` and `cx:` are not offered until accepted:
   config key `subscription_routes` = `{accepted: false|true, accepted_at,
   accepted_version, routes: [cc, cx]}`; a fresh install and an upgraded
   install both start at `accepted: false` (no migration flips it). Until
   accepted: the model picker and `/model`, the wizard's providers and
   default-model steps, `halo models`, lineups and bios that name a `cc:`
   or `cx:` model, `--model cc:...` and the `bare subscription alias`
   (`opus`, `sonnet`, ...) all show the route as "available after
   acceptance" and open the notice instead of using it. Nothing else
   changes for API-key routes.
2. **The notice** (TUI screen and plain-text CLI form, same words): title
   "Your subscription, a third-party harness", the facts above in five
   short paragraphs, the two providers' terms named by title with their
   URLs, the sentence that the user's account is their own responsibility,
   and the acceptance: type `I accept` (exact) and Enter; Escape or anything
   else leaves the routes off. Acceptance is per machine, stored in
   config.json with the date and Halo version; a later Halo version with a
   changed notice text (`NOTICE_VERSION` constant) asks again.
3. **Surfaces**: `halo subscriptions status|accept|revoke` (accept prints the
   notice and reads the typed acceptance from stdin; non-interactive stdin
   never accepts); `/subscriptions` in the TUI; `halo doctor` and
   `/providers` show "subscription routes: off (not accepted)" or "on
   (accepted <date>, v<version>)"; the wizard providers step shows the
   state with one key to open the notice.
4. **Docs**: README gets a short warning box near the top ("Using your
   Claude Code or Codex subscription through Halo"), MODELS.md the full
   text at the `cc:`/`cx:` rows, HANDBOOK the acceptance flow, COMMANDS and
   SLASH-COMMANDS the new entries, CHANGELOG `[unreleased]` "### Subscription
   routes are off until accepted".

## Tests (hermetic)

Fresh config: picker rows marked, `/model cc:opus` opens the notice and
leaves the model unchanged; typed `I accept` flips the config with date and
version and the route works; any other input leaves it off; `revoke`
returns to off; a changed `NOTICE_VERSION` asks again; `halo subscriptions
accept` with non-interactive stdin stays off; a lineup naming `cc:` with
routes off resolves to the default model with the one-line note; doctor
and `/providers` lines; docs tests for the new commands. No network, no
real binary.

## Hard constraints

No safety or refusal language (this is "accepted" / "not accepted", a
user choice); no real paths or names; no new dependency; never read or
print any credential; never touch the stash or plans/.

## Verification before hand-back

Touched and new modules, `python test_bridge.py`, `python test_tui.py`
once, `python tests/test_invariants.py`, `python tests/test_privacy_scan.py`,
`python tests/test_docs_commands.py`, `python tests/test_docs_slash_commands.py`,
`python -m halo_harness audit privacy`, all green. Hand back RESULT LINES
(1-4), FILES TOUCHED, WHAT YOU FOUND (every place a subscription route
could previously be reached without the gate). No commit, no push.
