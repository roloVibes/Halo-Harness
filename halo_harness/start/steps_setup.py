"""halo_harness.start.steps_setup -- the steps of `halo start` around the run:
1 the lineup (3.3.15.0 R7: yours, read as it is), 2 the repo, 7 where to go next (Halo 3.1.1.0 R1). Each
`<step>(run)` returns the step's lines; `<step>_command(run)` is the command
its screen shows."""

from __future__ import annotations

from halo_harness.start import steps as S
from halo_harness.start.engine import StepFailed


def lineup_command(run) -> str:
    from halo_harness.start.lineup import LineupError, pick
    try:
        name = pick(run.opts.lineup, state_dir=run.state_dir)
    except LineupError:
        name = run.opts.lineup.strip() or "<your lineup>"
    return f"halo teams show {name}"


def lineup(run) -> "list[str]":
    """3.3.15.0 R7: the active lineup (or `--lineup`'s), read as it is: nothing is copied or written."""
    from halo_harness.start.lineup import LineupError, card_rows, card_table, no_coder_line, parts, pick, who_lines
    try:
        name = pick(run.opts.lineup, state_dir=run.state_dir)
    except LineupError as e:
        raise StepFailed(str(e))
    p = parts(name, state_dir=run.state_dir)
    if not p["lanes"]:
        raise StepFailed(no_coder_line(name))
    run.lineup, run.parts = name, p
    named = run.opts.lineup.strip() and not run.opts.extra.get("active")  # Studio's job passes the active one by name
    source = "named with --lineup" if named else "your active lineup"
    lines = [f"the run rehearses {name} ({source}); it is read, not changed"] + who_lines(p)
    lines += [p["short"]] if p["short"] else []
    rows = card_rows(name, state_dir=run.state_dir)
    tiers = sorted({r["tier"] for r in rows}, key=[r["tier"] for r in rows].index)
    lines += ["", f"{name}: {len(rows)} card(s) in {len(tiers)} tier(s) ({', '.join(tiers)})"]
    lines += card_table(rows)
    lines.append("a member spawns only into the next tier down; with no tiers every card sits in one, `all`")
    return lines


def repo_command(run) -> str:
    if run.opts.repo:
        return f"git -C {run.opts.repo} rev-parse --show-toplevel"
    return f"write {run.state_dir / 'start' / '<today>' / 'basket'} (git init, one commit)"


def repo(run) -> "list[str]":
    from halo_harness.start import sample_repo as R
    try:
        if run.opts.repo:
            run.repo = R.use_repo(run.opts.repo, list(run.opts.files))
            return [f"your repo: {run.repo}", f"the goal's files: {', '.join(run.opts.files)}"]
        run.repo = R.make_sample_repo(run.state_dir, today=run.opts.today)
    except R.RepoError as e:
        raise StepFailed(str(e))
    return R.describe(run.repo)


def next_command(run) -> str:
    return "; ".join(cmd for _name, _what, cmd in S.NEXT)


def next_steps(run) -> "list[str]":
    lines = [f"{name:<6} {what}: {cmd}" for name, what, cmd in S.NEXT]
    lines += ["", "halo explain <thing> says what any word here means (halo explain lists them all)."]
    if run.repo is not None:
        lines.append(f"the sample run stays in {run.repo}: halo orchestra runs --repo {run.repo}")
    return lines
