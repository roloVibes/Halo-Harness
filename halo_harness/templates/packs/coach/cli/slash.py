"""The coach pack's slash commands (`contributes.slash`): `/coach` and `/improve` in a session, each the pack's verb
of the same name with its output as the answer (Halo 3.1.3.0 R1 as commands/builtins.py `_cmd_coach`; the TUI's
`/improve` card review left with the core in 3.4.0.0 B2, so `/improve` prints what `halo improve` prints).

    /coach [run] [--model] [--apply ID] [--probe [--k N]] [--undo [ID]]   the card for a run of any kind
    /coach library [list|show|forget|fetch] ...                            the improvement library
    /improve [--since 7d|30d|all] [--apply FILE#ID]                         draft candidates, or write one

No y/N prompt in a session: `--apply` and `--probe` show the confirm card or the cost line first, and the same
command with `--yes` does it (`--probe --yes` runs the probe on a thread; `/coach` shows its card when it ends).
"""

from __future__ import annotations

import contextlib
import io
import shlex


def _capture(fn, argv: list) -> str:
    out, err = io.StringIO(), io.StringIO()
    with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
        try:
            fn(argv)
        except SystemExit:
            pass
    return (out.getvalue() + err.getvalue()).strip()


def _cwd(facade):
    session = getattr(facade, "session", None)
    return getattr(session, "cwd", None) or getattr(facade, "cwd", None)


def coach(args_text: str, facade) -> str:
    from .coach import cmd_coach
    try:
        argv = shlex.split(args_text or "")
    except ValueError as e:
        return f"/coach: {e}"
    library = argv[:1] == ["library"]  # 3.1.6.0 R3: `halo coach library` (no run, no --repo)
    if library and argv[1:2] == ["forget"] and "--yes" not in argv:
        return f"/coach {' '.join(argv)}: nothing deleted yet; add --yes to delete the entry's folder"
    if ("--apply" in argv or "--probe" in argv) and "--yes" not in argv:
        argv.append("--preview")  # no y/N prompt here: the confirm card (or the cost line), then `... --yes` does it
    elif "--probe" in argv:
        argv.append("--background")
    cwd = _cwd(facade)
    if cwd and "--repo" not in argv and "--undo" not in argv and not library:
        argv += ["--repo", str(cwd)]
    return _capture(cmd_coach, argv) or "/coach: nothing to show"


def improve(args_text: str, facade) -> str:
    from .improve import cmd_improve
    try:
        argv = shlex.split(args_text or "")
    except ValueError as e:
        return f"/improve: {e}"
    cwd = _cwd(facade)
    if cwd and "--cwd" not in argv:
        argv += ["--cwd", str(cwd)]
    return _capture(cmd_improve, argv) or "/improve: nothing to show"


def run(args_text: str, facade) -> str:
    """`/coach` (the default module entry); /improve is cli/slash_improve.py."""
    return coach(args_text, facade)
