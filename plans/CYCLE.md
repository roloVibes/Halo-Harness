# The Halo development cycle (how a release is built, round by round)

Written 2026-10-06 so the cycle that produced 2.0.3, 2.0.3.1 and the 2.0.4
rounds can be repeated by anyone (or any later session) without the
original conversation. Everything here lives in the repo except the
owner's machine-specific scripts and keys, which are described, not stored.

## The shape of a release

1. `plans/ROADMAP.md` is the authority for WHAT ships in which version; its
   last dated "ADDED"/"CUT"/"REORDERED" sections override anything above
   them. `plans/STATUS.md` is the board (one line per round, ticked with the
   commit hash). `plans/HANDOFF.md` is the resume point for a new session.
2. A version is a sequence of ROUNDS. Each round has a BRIEF
   (`plans/briefs/<version>/<round>.md`: deliverables, pinning tests, hard
   constraints, verification, hand-back format), one implementation WORKER
   at a time on the tree (a Sonnet-class agent given the brief path and
   `plans/WORKER-RULES.md`), and one COMMIT per round by the orchestrator
   after verification. Docs-only or research rounds may run in parallel.
3. After the last round: three-platform suites (CI runs Linux and Windows
   on every push; the owner's Linux VM runs them for the tag), one live
   check on real hardware and real keys, then `python scripts/release.py
   <version> [--remote user@host --identity <key>]` (changelog date,
   release commit, annotated tag, push, install refresh; the remote step
   runs ssh non-interactively, so name the key), then the next version.

## One round, step by step

1. **Brief.** Copy the closest brief in `plans/briefs/` and edit: cite the
   ROADMAP section(s) and the research docs by path, list numbered
   deliverables each with the test that pins it, repeat the hard
   constraints verbatim (no safety or refusal language anywhere; no real
   paths, addresses, hostnames, user names, machine names or keys in any
   repo file; no network in tests; no new hard dependency without a
   decision; never block the UI thread), the verification list and the
   hand-back format. Keep the live checks (real keys, real hardware) for
   the orchestrator; the worker never reads a key file.
2. **Spawn.** One worker, Sonnet class, with the brief path, the rules file,
   the starting commit, and the test environment rules
   (`BRIDGE_TEST_HOME=<fresh scratch>` and `BRIDGE_TEST_NO_BACKGROUND_NET=1`
   only; never `BRIDGE_STATE_DIR` for a whole run). No commit, no push by
   the worker.
3. **Watch.** Judge progress by the working tree (changed-file count and
   newest file times), never by transcript size. One resume message after
   15 quiet minutes, a respawn with the same brief after 10 more. Workers
   run only the modules they touched plus `python test_bridge.py`.
4. **Hand-back.** Read the RESULT LINES. Partial items get a decision now
   (do it, defer to a named version in
   `plans/2.0.3-release-notes-for-fix-pass.md`-style notes, or drop it with
   the reason in STATUS). Decisions the owner already made win over a
   brief's wording.
5. **Verify.** Privacy scan, invariants, the doc checks, the touched
   modules, `python test_bridge.py`, `python -m halo_harness audit privacy`.
   TUI changes: the relevant pilots through a filtered runner (`test_tui.py`
   registers `(name, fn)` tuples; filter by name), never the whole file
   unless shared TUI infrastructure changed. Revert
   `docs/harness/tui-snapshots/` after any TUI run.
6. **Commit** with a message that names the brief items and the pinning
   tests; push. CI runs the three suites on Linux and Windows; commits that
   touch only `plans/` do not trigger it. A push cancels the previous
   in-progress run, so hold pushes while a verdict is wanted.
7. **Live check** for anything that talks to a real provider or real
   hardware: print mode, a scratch state dir, keys only in the environment
   (read from the owner's key file with a pattern match, never echoed), the
   shared env file copied into the scratch home when provider resolution
   needs it. Do NOT export `BRIDGE_TEST_NO_BACKGROUND_NET` in a live run: it
   also disables the local GPU probe.
8. **Record**: tick STATUS, note decisions and deferrals, keep the ROADMAP
   the authority.

## Reading CI

- Results: `GET https://api.github.com/repos/<org>/<repo>/actions/runs?per_page=5`
  and `/actions/runs/<id>/jobs` (public, no token). Each suite step uses
  `continue-on-error`, so the job's own "Fail the job if any suite failed"
  step is the verdict.
- Logs need a token: `git credential fill` on the owner's machine yields
  the stored GitHub credential; use it only in an Authorization header for
  `/actions/jobs/<id>/logs`, never print it. Then
  `grep -a 'RESULT:\|\[FAIL\]'`.
- Known runner facts (fixed in the workflow): hosted Windows denies
  CREATE_BREAKAWAY_FROM_JOB (the bridge spawn retries without it), its
  TEMP is an 8.3 short path (the job sets TEMP/TMP to the runner temp), no
  claude/codex binaries (the cc:/cx: modules set their fakes), slow timing
  (lazy-start 4 s, background jobs 20 s).

## The owner's machine-specific pieces (never in the repo)

- Key file for the Experiential and Hugging Face keys, read with
  `grep -oE 'xpl_[A-Za-z0-9_-]+'` / `grep -oE 'hf_[A-Za-z0-9]+'` into an env
  var; the shared env file under `~/.config/<vendor>/env` for the rest.
- `~/.halo/privacy-terms.txt`: the owner's machine, gear and name terms for
  `halo audit privacy` (one per line, `ci:` switching to case-insensitive);
  the repo never carries them.
- Linux VM runner: `git archive <commit> | ssh <host> 'tar -x'` into a
  scratch tree, `source <the suite venv>/bin/activate` (the system Python's
  Debian `mcp` 1.x breaks the bridge), then the three suites with
  `timeout`. Live checks there use `OLLAMA_HOST=<the LAN host>` with a
  print-mode pong and a Read round trip.
- Build-host live check: `python -m halo_harness -p "..." --model <ref>
  --cwd <scratch project> --output-format json`, a pong and a Read round
  trip per route, `halo doctor --local`, `halo ollama`, `halo balances`.

## History rewrite (done once, 2026-10-05; repeatable)

`halo audit privacy --history --json` -> `plans/2.0.4-history-rewrite-plan.md`
-> mirror backup (`git clone --mirror`) -> a fresh `git clone --no-local`
-> `git filter-repo --invert-paths --path ... --replace-text <resolved
file>` (regex lines use Python regex; a replacement with backslashes must
double them) -> audit the clone FROM THE MAIN TREE with `--cwd <clone>`
(running inside the clone imports the clone's own rewritten rule file) ->
force-push master and `--tags` -> `git reset --hard origin/master` in every
clone, `git fetch --force --tags`. The owner runs the filter-repo step
(the orchestrator's permission classifier refuses it).

## Budget discipline

The owner pays per token. Fewer, larger rounds; workers run only touched
modules; CI is the Linux and Windows verification (no per-round VM module
runs once CI is green); live checks once per round at most, suites on the
VM only for the tag; status posts only when asked; watchdogs only while a
worker is quiet. Keep notes like this one current so a cold session can
resume from `plans/HANDOFF.md`, `plans/STATUS.md` and the newest brief.
