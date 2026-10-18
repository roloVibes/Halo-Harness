# Code review: `/review` and `halo review`

Read this when you review code with `/review` or `halo review`.

Halo 2.0.10. A review runs parallel reviewers (one read-only sub-agent per
dimension), has a judge check every finding against the code, and gives
you a ranked list. It is modelled on Claude Code's `/code-review`. A review
reports; it never gates a commit, a merge or a turn.

```sh
halo review                         # this branch against its base (a dirty tree is included)
halo review main..feature           # a diff range
halo review feature                 # a branch against the default branch
halo review '#123'                  # a pull request (needs the gh CLI)
halo review src/app.py 'lib/**/*.py'  # files as they are, no diff
halo review --level high --dimensions security,correctness --json
halo review --fix                   # then fix every CONFIRMED finding in the working tree
```

In the TUI the same thing is `/review [target] [--level L] [--dimensions a,b]
[--fix] [--no-verify]`. See [COMMANDS.md](COMMANDS.md#halo-review) and
[SLASH-COMMANDS.md](SLASH-COMMANDS.md).

## Targets

| You type | What is reviewed |
|---|---|
| nothing | the current branch against its merge base with the default branch (`origin/HEAD`, else `main`, `master`, `trunk`, `develop`), plus uncommitted changes and untracked files. On the default branch itself: the working tree against `HEAD`. A clean tree says "nothing to review" (exit 2). |
| `a..b` or `a...b` | that diff range |
| a branch or other revision | that revision against the default branch (from the merge base) |
| `#123` or `123` | `gh pr diff 123` and `gh pr view 123 --json ...`; the files on disk may not be the PR head, and the reviewers are told so |
| a path, a directory or a glob (several allowed) | those files as they are, with line numbers on every line; no git needed |

A large diff is split per file and packed into shards of about 48 000
characters; each dimension reviews every shard (at most six shards; files past
that are named in the prompt so the reviewers can read them). A single file
bigger than a shard is truncated with a note.

## The pipeline

1. **Reviewers.** One sub-agent per dimension per shard, on the `reviewer`
   role. They are read-only: `Read`, `Glob`, `Grep` and `Bash` for read-only
   commands, no `Edit`/`Write`. They run in parallel under
   `agents.max_concurrent` (the same gate every sub-agent uses) and appear in
   `/tasks` while they work. Each returns a JSON array of findings; a reply
   with no parsable JSON is re-asked once ("output only the JSON array").
2. **Judge.** Every finding goes to a `judge` sub-agent with the finding and
   the diff excerpt for its file. It answers `CONFIRMED` (it traced the
   failure scenario and it happens), `PLAUSIBLE` (realistic, but it could not
   show it end to end) or `DISMISSED` (the code contradicts it) with a reason.
   Dismissed findings are dropped from the list but kept in `--json` under
   `dismissed` with their reasons. A judge that errors or cannot be parsed
   leaves the finding `PLAUSIBLE` and says so in `reason`.
3. **Dedup and ranking.** Findings with the same file, line and category merge
   into one (the higher severity wins, the summaries and dimensions are
   merged). The list is ordered by severity (`high`, `medium`, `low`), then
   verdict (`CONFIRMED` before `PLAUSIBLE`), then file and line.
4. **Fix pass (`--fix`, optional).** See below.

`--no-verify` skips step 2: everything stays `PLAUSIBLE` and nothing is
dismissed (this is cheaper and noisier). It cannot be combined with `--fix`.

## Dimensions and levels

`correctness`, `security`, `performance`, `tests` and `docs-consistency`; the
prompt for each is `halo_harness/review/prompts/<dimension>.md`.
`--dimensions security,tests` runs only those.

`--level` sets how many findings each reviewer may report and how speculative
it may be: `low` 3 (only problems it can show with a concrete failing
scenario), `medium` 8 (the default), `high` 20 (plausible risks too; the judge
sorts them out).

## The result

Text form: a header line, then one block per finding.

```
Review of feature vs main (merge base 7fdf2121)
2 findings (1 confirmed, 1 plausible) from 5 reviewers in 41 s, $0.12

1. [high] a.py:2  CONFIRMED  (logic-error)
   add() now subtracts
   Failure scenario: add(1, 2) returns -1
   Judge: traced the call and the operator
```

`--json` prints one object: `{target, findings[], dismissed[], reviewers[],
cost_usd, elapsed_s}` (plus `notes[]` when something was skipped). Each
finding uses the ReportFindings field names:

| Field | Meaning |
|---|---|
| `file`, `line` | path relative to the repo root; line in the new version (or `null`) |
| `short_summary`, `summary` | one line; what is wrong and why it matters |
| `failure_scenario` | the input or sequence that triggers it and what goes wrong |
| `verdict` | `CONFIRMED`, `PLAUSIBLE` or `DISMISSED` |
| `category`, `severity` | a short tag; `high`, `medium` or `low` |
| `outcome` | `fixed`, `skipped`, `no_change_needed`, or `null` when `--fix` did not run on it |
| `reason`, `dimensions`, `fix_note` | the judge's reason; which dimensions reported it; the fixer's note |

`reviewers[]` has one entry per reviewer run: `dimension`, `part` (`1/1`),
`ok`, `findings`, `error`, `elapsed_s`. A reviewer that fails does not end the
review; it is listed with its error. The exit code is 0 whenever the review
ran (findings never change it), 1 if every reviewer failed, 2 for usage errors
and unresolvable targets.

In the TUI the header line and one card per finding land in the transcript. The
`file:line` on each card is a link (click it, or press `c`, to copy it);
Enter or a click folds the details open (summary, failure scenario, judge
reason, fix outcome); `y` copies the whole finding. Esc aborts every reviewer
through the session's shared abort Event.

## `--fix`

For each `CONFIRMED` finding, one at a time, a `coder` sub-agent applies the
smallest change that resolves it in the working tree. It does not commit,
stage or push. The judge then re-checks the same finding against the file's
new state. Outcomes:

- `fixed`: the file changed and the judge no longer finds the problem;
- `no_change_needed`: the fixer found the problem already handled;
- `skipped`: the fixer could not or chose not to fix it, claimed a fix but the
  file did not change, or the judge still reports the problem afterwards (the
  change stays in the tree; read `fix_note`). `PLAUSIBLE` findings are never
  sent to the fixer.

From `halo review --fix` the session runs in `acceptEdits` mode so the fixer
can write files; in the TUI the fixer follows the session's permission mode
like any other sub-agent. Review the result with `git diff`.

## Choosing models: the `code-review` team

The three parts use three roles: `reviewer` (the dimension reviewers),
`judge` (verification and re-verification) and `coder` (the fixer). The
shipped team template `code-review` maps all three (as shipped, each to the
session's default model):

```sh
halo teams use code-review      # or pick it in the init wizard's Team step / /teams
halo teams edit code-review     # give each role its own model
halo roles                      # the resulting role table
```

A cheap model for the reviewers and a stronger one for the judge is the usual
split. For one run, `halo review --role reviewer=MODEL --role judge=MODEL`
overrides the table, and `--model REF` sets the model for roles that have none
of their own.

## Cost

Calls per review: `dimensions x shards` reviewers (5 by default, one shard for
most changes), plus one judge run per finding (fewer when you lower `--level`
or use `--dimensions`), plus per CONFIRMED finding one fixer run and one
re-verification with `--fix`. Each reviewer reads the diff and then explores
the code around it with tools, so a reviewer is several model turns, not one.
The header shows the real cost of the run (the session's cost meter delta,
`$0.00` when the provider reports no price). To keep a run cheap: `--level
low`, `--dimensions correctness,security`, a small model on the `reviewer`
role, or `--no-verify` (the judge pass is usually the smaller share).

## How this differs from `halo audit privacy`

`halo audit privacy` is a deterministic scan of a repository (and optionally
its history) for secrets, addresses and private terms: no model, no
judgement, the same answer every time, a non-zero exit when it finds
something. `/review` asks models to read a change and argue about it: it can
find logic errors, missing tests and stale docs, its answers vary from run to
run, and it never fails a build.

## Files

`halo_harness/review/` holds the engine: `target.py` (what to review),
`dimensions.py` and `prompts/` (the reviewer, judge and fixer prompts),
`run.py` (reviewers), `verify.py` (judge, dedup, ranking), `fix.py`,
`render.py`, `cli.py` and `slash.py`; `tui/slash_review.py` and
`tui/widgets/review_cards.py` are the TUI side.
