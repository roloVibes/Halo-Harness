"""halo_harness.review.cli -- `halo review [target] [options]` (print mode).

Builds a bare, non-interactive session (the same construction `-p` uses) to
act as the review's caller, runs `run_review`, and prints the ranked findings
as text or, with `--json`, as one JSON object. The exit code is 0 whenever the
review ran; findings never change it.
"""

from __future__ import annotations

import argparse
import os
import shlex
import sys
from pathlib import Path

from halo_harness.review.dimensions import DEFAULT_LEVEL, DIMENSIONS, LEVELS, parse_dimensions, validate_level


class _ArgError(ValueError):
    pass


class _Parser(argparse.ArgumentParser):
    def error(self, message: str):   # raise instead of printing usage and exiting (the slash command reuses this)
        raise _ArgError(message)


def build_parser(prog: str = "halo review", *, cli: bool = True) -> argparse.ArgumentParser:
    p = _Parser(prog=prog, add_help=cli, description="Review a diff, branch, pull request or files with parallel "
                "dimension reviewers and a judge. A review reports; it never gates anything.")
    p.add_argument("target", nargs="*", help="a..b range, branch, PR number (#123), or paths/globs; "
                   "default: the current branch against its base")
    p.add_argument("--level", default=DEFAULT_LEVEL, choices=list(LEVELS),
                   help="findings per reviewer: low 3, medium 8, high 20 (default medium)")
    p.add_argument("--dimensions", default=None, help=f"comma-separated subset of {', '.join(DIMENSIONS)}")
    p.add_argument("--fix", action="store_true", help="apply a minimal fix per CONFIRMED finding in the working tree, "
                   "then re-verify (never commits)")
    p.add_argument("--no-verify", action="store_true", help="skip the judge; findings stay PLAUSIBLE")
    if cli:
        p.add_argument("--json", action="store_true", help="print one JSON object instead of text")
        p.add_argument("--model", default=None, help="model for roles with no model of their own")
        p.add_argument("--role", action="append", default=None, metavar="NAME=MODEL[:EFFORT]",
                       help="set a role's model for this run (reviewer, judge or coder); repeatable")
        p.add_argument("--cwd", default=None, help="repository or directory to review (default: here)")
    return p


def parse_args(argv: "list[str]", *, cli: bool = True, prog: str = "halo review"):
    """Returns `(namespace, ReviewOptions)`; raises `_ArgError` (a ValueError) on bad input."""
    from halo_harness.review.run import ReviewOptions
    ns = build_parser(prog, cli=cli).parse_args(argv)
    try:
        dims = parse_dimensions(ns.dimensions)
        level = validate_level(ns.level)
    except ValueError as e:
        raise _ArgError(str(e)) from None
    if ns.fix and ns.no_verify:
        raise _ArgError("--fix applies fixes to CONFIRMED findings, so it cannot be combined with --no-verify")
    opts = ReviewOptions(target=list(ns.target), level=level, dimensions=dims, fix=ns.fix, verify=not ns.no_verify)
    return ns, opts


def split_args(text: str) -> "list[str]":
    """Shell-like split of a slash command's argument text; quotes are removed
    on every platform and Windows backslashes survive."""
    tokens = shlex.split(text or "", posix=(os.name != "nt"))
    return [t[1:-1] if len(t) >= 2 and t[0] == t[-1] and t[0] in "\"'" else t for t in tokens]


def _emit(text: str) -> None:
    try:
        sys.stdout.write(text if text.endswith("\n") else text + "\n")
    except UnicodeEncodeError:
        enc = getattr(sys.stdout, "encoding", None) or "utf-8"
        sys.stdout.write((text + "\n").encode(enc, "replace").decode(enc, "replace"))
    sys.stdout.flush()


def cmd_review(argv: "list[str]") -> int:
    try:
        ns, opts = parse_args(list(argv))
    except _ArgError as e:
        print(f"halo review: {e}", file=sys.stderr)
        return 2
    from halo_harness import headless
    from halo_harness.review.render import render_json, render_text
    from halo_harness.review.run import run_review
    from halo_harness.review.target_model import TargetError
    from halo_harness.roles import parse_role_flags

    try:
        parse_role_flags(ns.role)
    except ValueError as e:
        print(f"halo review: {e}", file=sys.stderr)
        return 2
    cwd = Path(ns.cwd).resolve() if ns.cwd else Path.cwd()
    build = headless.build_session(cwd=cwd, bare=True, print_mode=True, model_ref_raw=ns.model,
                                   roles_flag=ns.role, permission_mode="acceptEdits" if opts.fix else None)
    session = build.session
    try:
        result = run_review(session.agent_runtime, opts, progress=lambda m: print(f"halo review: {m}", file=sys.stderr))
    except TargetError as e:
        print(f"halo review: {e}", file=sys.stderr)
        return 2
    finally:
        try:
            session.job_registry.kill_all()
        except Exception:
            pass
    _emit(render_json(result) if ns.json else render_text(result))
    return 1 if (result.reviewers and not any(r.get("ok") for r in result.reviewers)) else 0
