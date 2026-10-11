# Halo 2.0.10 review, round 1: `/review` and `halo review` as a Halo feature

Repo: `<repo>` (branch master; start from HEAD after the v2.0.9 tag,
clean). Read `plans/WORKER-RULES.md` FIRST and follow every rule in it
(test environment: `BRIDGE_TEST_HOME=<fresh scratch dir>`,
`BRIDGE_TEST_NO_BACKGROUND_NET=1`, `OLLAMA_HOST=http://127.0.0.1:1`).
`plans/CYCLE.md` "Budget discipline" applies.

Design: `plans/2.0.9-review-privacy-brief.md` section A (the feature),
modelled on Claude Code's `/code-review`: parallel dimension reviewers,
a verification pass that adjudicates every finding, a ranked result in
the ReportFindings shape, an optional fix pass. Built on what exists:
the `reviewer`, `judge` and `coder` roles (`halo_harness/roles.py`
ROLE_NAMES; templates under `halo_harness/templates/agents/`), the team
templates (`templates/teams/*.yaml`, `teams_yaml.py`), the sub-agent
fan-out (`agent/subagent.py` `run_agent_call` for one child; study how
an org runs several positions in `run_org_call` and how the tasks panel
`/tasks` + `tui/dialogs/tasks.py` shows them), `agents.max_concurrent`,
the existing read-only code-review agent prompt in
`config/agents_md.py` (reuse its wording where it fits), the `gh` helper
(`grep -rn '"gh"' halo_harness/` for the existing subprocess pattern),
and the print-mode JSON output conventions (`output.py`).

## Deliverables

1. **Target resolution** (`halo_harness/review/target.py`): `[target]` =
   nothing (current branch vs its merge base with the default branch; a
   dirty tree adds the working-tree diff), a diff range (`a..b`), a
   branch name, a PR number (`#123` or `123` -> `gh pr diff` + `gh pr
   view --json`), a path or glob (review those files as-is). Produces a
   `ReviewTarget {kind, label, diff_text, files[], base, head}` with the
   unified diff and the list of touched files; large diffs are split per
   file for the reviewers. Pin each form with a scratch git repo (and a
   fake `gh` on PATH for the PR form).
2. **Reviewers** (`review/dimensions.py` + `review/run.py`): dimensions
   `correctness`, `security`, `performance`, `tests`, `docs-consistency`
   (each a prompt file under `halo_harness/review/prompts/<dim>.md`, <= 60
   lines, in the house voice, asking for typed findings only); one
   sub-agent per dimension on the `reviewer` role, run in parallel
   through the sub-agent runtime under `agents.max_concurrent`, each
   returning JSON findings `{file, line, severity: high|medium|low,
   category, short_summary, summary, failure_scenario}` (parsed
   tolerantly: a fenced JSON block anywhere in the reply; repair once by
   re-asking "output only the JSON array" on a parse failure). `--level
   low|medium|high` scales how many findings a reviewer may report (3 /
   8 / 20) and how speculative it may be. `--dimensions a,b` restricts.
3. **Verification + ranking** (`review/verify.py`): every finding goes to
   the `judge` role with the diff excerpt and the finding, which returns
   `verdict: CONFIRMED|PLAUSIBLE|DISMISSED` + `reason`; dismissed ones are
   dropped (kept in `--json` under `dismissed` with reasons); the rest
   are deduplicated (same file+line+category -> keep the higher
   severity, merge summaries) and ranked severity-first, then verdict.
   Verification runs in parallel under the same gate. `--no-verify`
   skips it (findings stay PLAUSIBLE).
4. **Surfaces**: `/review [target] [--level] [--dimensions] [--fix]
   [--no-verify]` in the TUI (a `review` builtin): the reviewers appear
   in `/tasks` live; the result renders as finding cards in the
   transcript (file:line clickable the way tool cards show paths, the
   short summary, the verdict badge, the failure scenario folded) with a
   one-line header "N findings (c confirmed, p plausible) from d
   reviewers in t s, $cost"; `halo review [target] ...` in print mode
   prints the same as text, or `--json` as `{target, findings[],
   dismissed[], reviewers[], cost_usd, elapsed_s}` in the ReportFindings
   field names. `--fix`: for each CONFIRMED finding, one `coder`
   sub-agent applies a minimal fix in the working tree (never commits),
   then the judge re-verifies the same finding against the new diff;
   the result lists `outcome: fixed|skipped|no_change_needed` per
   finding. A team template `templates/teams/code-review.yaml` maps the
   three roles so the user can change which model does which part; the
   wizard's Team step lists it. Concurrency, cost and cancellation (Esc
   aborts every reviewer through the shared abort Event) follow the
   existing sub-agent behaviour.
5. **Tests + docs**: `tests/test_review_target.py`, `test_review_run.py`
   (scripted reviewer and judge replies through the mock upstream the
   sub-agent tests already use -- find `tests/test_agents_*.py` for the
   pattern: dimensions run in parallel under the gate, tolerant JSON
   parse + one repair, level caps, dedup and ranking, dismissed kept in
   JSON, `--no-verify`, `--fix` applies and re-verifies, Esc aborts),
   `test_review_cli.py` (print mode text and `--json` shape; the PR form
   with a fake `gh`), a TUI pilot test for the cards and the `/tasks`
   rows; `docs/REVIEW.md` (what it does, the dimensions, the shape, the
   team template, the cost expectations, how it differs from `/audit`);
   docs/COMMANDS.md, docs/SLASH-COMMANDS.md, HANDBOOK a short section,
   README one bullet; CHANGELOG `## [2.0.10] - unreleased` "### /review:
   parallel dimension reviewers, a judge, an optional fix pass". A LIVE
   acceptance run is the orchestrator's, after hand-back.

## Hard constraints

No safety or refusal language (a review reports; it never gates). No
real paths or names; no new dependency; never block the UI thread; the
reviewers are read-only sub-agents (`tools:` restricted to Read/Glob/
Grep/Bash read-only, the way the existing code-review agent prompt
declares); every file write <= 250 lines (split `run.py` / `verify.py` /
`render.py` / `cli.py` as needed under `halo_harness/review/`).

## Verification before hand-back

The new test modules, `tests.test_agents_teams`, `tests.test_teams_runtime`,
the subagent suites (`ls tests | grep -i -E "subagent|agents_"`),
`tests.test_commands_builtins`, `tests.test_completion_cli`, every touched
module's tests, `python test_bridge.py`, `python test_tui.py` once (revert
snapshot churn with `git checkout -- <file>` and say which),
`python -m tests.test_invariants`, `python -m tests.test_privacy_scan`,
`python -m tests.test_docs_commands`, `python -m tests.test_docs_slash_commands`,
`python -m tests.test_docs_links`, `python -m halo_harness audit privacy`,
and `python -m pyflakes halo_harness/ bridge.py | grep "undefined name"`
printing nothing. Hand back ONCE, under 60 lines, then end your run:
RESULT LINES (1-5), FILES TOUCHED, WHAT YOU FOUND (the exact command for
a live acceptance run on this repo; anything left open and why). No
commit, no push.
