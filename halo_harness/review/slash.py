"""halo_harness.review.slash -- the text form of `/review` (print mode, `-p
"/review ..."`, and any facade without a TUI). The TUI intercepts `/review`
first (tui/slash_review.py) and renders cards instead.
"""

from __future__ import annotations

USAGE = ("Usage: /review [target] [--level low|medium|high] [--dimensions a,b] [--fix] [--no-verify]\n"
         "target: a..b range, branch, PR number (#123), or paths/globs; default: this branch against its base.")


def cmd_review(args: str, facade) -> str:
    from halo_harness.review.cli import _ArgError, parse_args, split_args
    from halo_harness.review.render import render_text
    from halo_harness.review.run import run_review
    from halo_harness.review.target_model import TargetError
    try:
        _ns, opts = parse_args(split_args(args), cli=False, prog="/review")
    except (_ArgError, ValueError) as e:
        return f"/review: {e}\n{USAGE}"
    session = getattr(facade, "session", None)
    if session is None or getattr(session, "agent_runtime", None) is None:
        return "/review can only run once a session is running."
    try:
        result = run_review(session.agent_runtime, opts)
    except TargetError as e:
        return f"/review: {e}"
    return render_text(result)
