# Halo 2.0.9 Signal remote control, round 1: research refresh (docs only)

Repo: `<repo>` (branch master; start from HEAD after the v2.0.8 tag,
clean). Read `plans/WORKER-RULES.md` FIRST. This round writes DOCS ONLY:
one file, `docs/harness/SIGNAL-RESEARCH.md` (rewrite in place, <= 250
lines per write, split the write in two if needed), plus a scratch
directory of your own for any hands-on check. Nothing under
`halo_harness/` or `tests/` changes.

The design to research for is `plans/2.0.8-signal-brief.md` (read it in
full; "2.0.8" in its title is historical -- the feature ships as 2.0.9).
The existing `docs/harness/SIGNAL-RESEARCH.md` was written 2026-10-02
against signal-cli v0.14.8; its section 7 lists nine open questions.

## Deliverables

1. **Refresh to today.** Find the current signal-cli release (GitHub
   releases, the wiki, the man page in the repo), the current JSON-RPC
   method list and daemon flags (`--socket`, `--tcp`, `--http`,
   `--trust-new-identities`, `--receive-mode`, anything new since
   0.14.8), the native-build matrix per OS, and the JRE requirement. Every
   claim carries its URL and the date you read it. Mark what changed
   since the 2026-10-02 pass.
2. **Answer the nine open questions** in section 7, each with a source
   or a hands-on result; where neither exists, say "unresolved" and name
   the cheapest live check that would settle it. The hands-on check that
   IS available here: download the current signal-cli release archive
   into your own scratch directory (never into the repo), and if a Java
   runtime is on this box (`java -version`), run `signal-cli --help`,
   `signal-cli daemon --help` and `signal-cli jsonRpc --help` to capture
   the real flag list (question 1 and question 7 at least). Do not
   register, link, or send anything; do not install anything system-wide;
   do not touch `~/.halo`. If there is no Java, record that and move on.
3. **Limits and shapes the bridge will code against**: the message size
   limit and the long-text-as-attachment behaviour, attachment caps,
   typing-indicator and receipt methods, the exact envelope JSON for a
   dataMessage, a syncMessage (Note to Self) and an identity-change
   notification, the exit codes the bridge must map (4 untrusted/changed
   key, 5 rate limit, others), and how `listIdentities` exposes safety
   numbers. Quote the JSON shapes from the source tree with file paths.
4. **Design adjustments**: a new section 8 "What the brief should change"
   -- bullet list, each tied to a finding above (for example: Windows
   needs `--tcp` on loopback; the attachment fallback changes the
   chunking rule; a flag was renamed). Keep the brief's security layers
   intact; this section only adjusts mechanics.
5. **Round 2 inputs**: a new section 9 listing, for the control-socket
   round, the exact `Controller` methods and `events.Command` kinds the
   socket maps onto (verify them in `halo_harness/controller.py` and
   `halo_harness/events.py` as they are TODAY -- the brief's list is from
   2026-10-02) and the per-session run-dir files the `cc:` route already
   uses under `~/.halo/run/` (find them in `halo_harness/agent/cc_*.py`
   and `ccbridge/`), so round 2's brief can be written from this doc alone.

## Hard constraints

Docs only. No real phone numbers, no real names, no account identifiers,
no secrets; the Databricks host convention and the privacy scan apply
(`python -m tests.test_privacy_scan` and `python -m tests.test_docs_links`
must stay green -- run them). No safety or refusal language. Plain
English, URLs inline, no copied tables from the wiki longer than ten rows.

## Verification before hand-back

`python -m tests.test_privacy_scan`, `python -m tests.test_docs_links`,
`python -m tests.test_docs_hygiene` (if present) green; `git status`
shows ONLY `docs/harness/SIGNAL-RESEARCH.md` modified. Hand back ONCE,
under 50 lines, then end your run: RESULT LINES (1-5), the nine
questions each as "resolved: <one line>" or "unresolved: <cheapest live
check>", and WHAT YOU FOUND (anything that invalidates the brief's
design). No commit, no push.
