"""halo_harness.check_cli -- `halo check`, the checks Halo offers after setup
(Halo 3.2.2.0 R2; the list is halo_harness/start/checks.py).

    halo check                       the default-on checks: doctor, catalog, hello
    halo check --all                 all five, in order
    halo check --doctor --catalog --hello --gym --start   the ones named
    halo check --gym --models REF,REF                     the gym on these models
    halo check --explain             the five rows (what, cost, time, writes) and exit

Each check prints its title, its what / cost / time line, then its result
lines. Exit 0 when every check that ran passed, 1 when one failed, 2 on a
usage error. The TUI's `/check` takes the same flags (`cmd_check_text`).
"""

from __future__ import annotations

import argparse
import contextlib
import io
import sys

from halo_harness.start import checks as C

MARK = {True: "[ok]", False: "[failed]"}


def _parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="halo check", description="Run the checks Halo offers after setup. Each says "
                                "what it does, what it costs, how long it takes and what it writes; with no flag the "
                                "default-on ones run (doctor, catalog, hello).")
    p.add_argument("--all", action="store_true", help="run all five checks, in order")
    for c in C.CHECKS:
        p.add_argument(f"--{c['key']}", dest=c["key"], action="store_true",
                       help=f"{c['title']}: {c['what']} ({c['cost']}; {c['time']})")
    p.add_argument("--models", default=None, metavar="REF,REF",
                   help="the models --gym runs on (default: your default model and the start lineup's models)")
    p.add_argument("--explain", action="store_true", help="print the five checks (what, cost, time, writes) and exit")
    return p


def _out(text: str, stream) -> None:
    try:
        stream.write(text + "\n")
        stream.flush()
    except UnicodeEncodeError:
        stream.write(text.encode("ascii", "replace").decode("ascii") + "\n")


def selected(args) -> "list[str]":
    """The keys the flags name: --all, the named ones, or the default-on ones."""
    if args.all:
        return list(C.KEYS)
    named = [k for k in C.KEYS if getattr(args, k, False)]
    return named or list(C.DEFAULT_KEYS)


def run(argv, stream=None, ctx=None) -> int:
    stream = stream or sys.stdout
    try:
        args = _parser().parse_args(list(argv))
    except SystemExit as e:
        return int(e.code or 0) if isinstance(e.code, int) else 2
    gym = [m.strip() for m in (args.models or "").split(",") if m.strip()] or None
    ctx = ctx or C.default_ctx(gym_models=gym)
    if gym is not None:
        ctx.gym_models = gym
    keys = selected(args)
    if args.explain:
        for line in C.explain(keys, ctx):
            _out(line, stream)
        return 0
    failed = []

    def each(key, ok, lines) -> None:
        c = C.check(key)
        if ok is None:
            _out("", stream)
            _out(f"{c['title']} ({key})", stream)
            _out(f"  {C.detail_line(c, ctx)}", stream)
            return
        for line in lines:
            _out(f"  {line}", stream)
        _out(f"  {MARK[ok]}", stream)
        if not ok:
            failed.append(key)
    C.run_many(keys, ctx, on_each=each)
    _out("", stream)
    _out(f"halo check: {len(keys) - len(failed)} of {len(keys)} passed" + (f"; failed: {', '.join(failed)}" if failed
                                                                            else ""), stream)
    return 1 if failed else 0


def cmd_check(argv) -> int:
    return run(argv)


def cmd_check_text(args_text: str, cwd=None) -> str:
    """The TUI's `/check [flags]`: the same run, its lines as one text. `--start` says where the start runs."""
    argv = (args_text or "").split()
    note = ""
    if "--start" in argv or "--all" in argv:
        argv = [a for a in argv if a != "--start"]
        if "--all" in argv:
            argv = [a for a in argv if a != "--all"] + [f"--{k}" for k in C.KEYS if k != "start"]
        note = "\nThe guided first run runs in a panel here: /start (halo start in a terminal)."
        if not argv:
            return note.strip()
    out = io.StringIO()
    with contextlib.redirect_stdout(out), contextlib.redirect_stderr(out):
        run(argv, stream=out, ctx=C.default_ctx(cwd))
    return (out.getvalue().strip() + note) or "/check: nothing to show"
