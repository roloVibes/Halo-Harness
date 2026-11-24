"""halo_harness.tui.launch -- the ONE entry point `cli.py` imports (lazily,
inside the branch that actually needs a full-screen session) to start the
Textual app -- textual/rich are real imports from this point down, never
above it, so `import halo_harness` and `-p` stay dependency-free.
"""

from __future__ import annotations

import contextlib
import sys
import time
from pathlib import Path


def _show_intro_for(args) -> bool:
    """2.0.0 Launch intro gating -- real auto-detection lives HERE, never
    inside `BridgeApp` itself (which defaults `show_intro=False` and only
    ever shows what it's explicitly told to, so every test that builds one
    directly is unaffected). Off for `--demo` (a deterministic scripted
    snapshot -- the brief: "never in --demo snapshots unless asked"), off
    for `--no-intro`, off when `"intro": false` sits in `~/.halo/
    config.json`, and off whenever stdout isn't a real terminal (the
    print-mode/non-interactive case this function is never even reached
    for in practice, plus any other redirected-stdout interactive launch)."""
    if getattr(args, "demo", False):
        return False
    if getattr(args, "no_intro", False):
        return False
    if not sys.stdout.isatty():
        return False
    from halo_harness.theme import get_config_value
    return bool(get_config_value("intro", True))


def run_tui(args) -> int:
    """`args`: the argparse.Namespace `cli.py._build_parser()` produces.
    Bare `halo [PROMPT]` and `halo --demo` (without `-p`, which
    stays the scripted print-mode replay in `testing.fake_controller.
    run_demo`) both land here."""
    from halo_harness.theme import load_persisted_theme, removed_theme_notice, resolve_theme
    from halo_harness.tui.app import BridgeApp

    cwd = Path(args.cwd).resolve() if getattr(args, "cwd", None) else Path.cwd()

    if args.demo:
        controller, registry, facade, tui_setting = _build_demo_controller(args)
    else:
        from halo_harness.tui.bootstrap import build_controller
        controller, registry, facade = build_controller(args)
        cwd = controller.cwd
        tui_setting = facade.settings.tui if facade is not None and facade.settings is not None else None

    settings_theme = facade.settings.theme if facade is not None and facade.settings is not None else None
    persisted_theme = load_persisted_theme()
    theme_name = resolve_theme(cli_theme=getattr(args, "theme", None), settings_theme=settings_theme,
                                persisted_theme=persisted_theme)

    app = BridgeApp(
        controller, registry=registry, facade=facade, tool_registry=getattr(facade, "tool_registry", None),
        cwd=cwd, theme_name=theme_name, tui_setting=tui_setting,
        initial_prompt=(args.prompt if not args.demo else None),
        # H13 Part C: set only when `--resume <text>` didn't resolve to
        # exactly one session (`tui/bootstrap.py::build_controller`) -- opens
        # the resume picker, pre-filtered by that text, right after mount.
        initial_resume_filter=getattr(controller, "pending_resume_filter", None),
        no_inline_images=bool(getattr(args, "no_inline_images", False)),
        show_intro=_show_intro_for(args),
    )
    # 2.0.7 round 7c: on a Windows console Ctrl+C must only ever be a key
    # for the TUI's lifetime (inert on POSIX); restored in the `finally`.
    from halo_harness.tui import console_mode
    console_guard = console_mode.install()
    console_guard.on_ctrl_c = lambda: post_ctrl_c_key(app)  # 3.6.0.18 K: a key the console made an event
    app.console_guard = console_guard
    # 2.0.10 finding 24: an existing ~/.halo tree is made owner-only once;
    # the TUI says so in one notification (print mode stays silent).
    try:
        from halo_harness.config.paths import bridge_home as _bridge_home
        from halo_harness.privateio import tighten_state_tree
        _changed = tighten_state_tree(_bridge_home())
    except Exception:
        _changed = 0
    if _changed:
        app.startup_notice = (f"Made {_changed} entr{'y' if _changed == 1 else 'ies'} under "
                              f"{_bridge_home()} owner-only (0700 directories, 0600 files)")
    # 3.1.5.0: a saved game theme falls back with one line.
    _theme_notice = removed_theme_notice(theme_name, persisted=persisted_theme or "")
    if _theme_notice:
        _earlier = getattr(app, "startup_notice", None)
        app.startup_notice = f"{_earlier}\n{_theme_notice}" if _earlier else _theme_notice
    returned = False
    # 3.6.0.18 K: while the app has the terminal no child inherits its input (subprocess_safe._quiet_stdin); off again
    # at the end of the finally below, on every way out of it
    from halo_harness import subprocess_safe
    give_the_terminal_on_suspend(app)
    subprocess_safe.set_terminal_app(True)
    try:
        app.run()
        returned = True
    finally:
        console_guard.on_ctrl_c = None  # 3.6.0.18 K: Textual keeps its driver after run(): no key posts to a gone loop
        from halo_harness import closing
        closing.trace("app.run returned")  # fx jb12: HALO_CLOSE_TRACE (nothing when unset)
        # 3.6.0.17 Z4-1: an exception escaping app.run leaves with the code cli.main gives it; a step below that
        # raises (a second Ctrl+C in the quit's stops, a print to a gone terminal) with that one's. Whatever it is,
        # the bound is armed (the `finally` below) and the exception goes on.
        code = None if returned else _code_of(sys.exc_info()[1])
        raised = False
        try:
            interrupted = None
            try:
                join_the_pool(app)  # 3.6.0.17 Z4-1: first, as asyncio's own join was in 3.6.0.16, now bounded
            except KeyboardInterrupt as e:  # a Ctrl+C in that join: the way out still runs, then it goes on
                interrupted = e
            console_guard.restore()
            # review finding 5: `app.run()` returning (or raising) via any
            # path OTHER than the app's own `_quit_worker` (an uncaught
            # exception escaping Textual's event loop, e.g.) must still stop
            # the worker thread and close every MCP subprocess -- `quit()` is
            # already idempotent (`quit_called`), so a normal exit that
            # already called it here is a harmless no-op.
            quit_fn = getattr(controller, "quit", None)
            if callable(quit_fn):
                try:
                    quit_fn()
                except Exception:
                    pass
            # 3.2.2.0 R3: an exit that did not pass the app's own quit card
            # (`/update`, an error) still names what the quit stopped.
            line = getattr(controller, "stopped_line", "") or ""
            if line and not getattr(controller, "stopped_line_shown", False):
                print(line)
            closing.trace("app.run's finally done", done=True)  # fx jb14: the app's way out ended, nothing outlives it
            if interrupted is not None:
                raise interrupted
        except BaseException as e:
            code, raised = _code_of(e), True
            raise
        finally:
            subprocess_safe.set_terminal_app(False)
            # 3.6.0.17 Z3-1: the bound comes last. /update's restart exit still hands over to the updater (cli.py
            # `_apply_update_and_relaunch` arms it after that) unless a step here raised: then there is no hand-off.
            from halo_harness.update import RESTART_EXIT_CODE
            if code is None:
                code = app.return_code if app.return_code is not None else 0
            if raised or code != RESTART_EXIT_CODE:
                bound_the_end(code)
    return app.return_code if app.return_code is not None else 0


def post_ctrl_c_key(app) -> None:
    """3.6.0.18 K: ONE Ctrl+C key to the app, posted from any thread the way the Windows driver's reader thread posts
    the keys it reads (`Driver.process_message`: thread-safe onto the app's loop), so focus and screens decide what it
    does exactly as for the key itself. Nothing while the app has no driver yet. Textual keeps the driver after
    `app.run()` returns, so run_tui takes this hand away (`console_guard.on_ctrl_c = None`) the moment it does."""
    driver = getattr(app, "_driver", None)
    if driver is None:
        return
    from textual import events
    driver.process_message(events.Key("ctrl+c", "\x03"))


def give_the_terminal_on_suspend(app) -> None:
    """3.6.0.18 K: while the app is suspended (`with app.suspend():` around the person's editor: Ctrl+E, /editor,
    /improve's edit, the /mcp dialog) the person has the terminal. 3.6.0.18 L: the hand-over is for the THREAD that
    suspends (its child, the editor, inherits the terminal's input); every other thread's child (a tool's command, the
    branch worker's git) still gets the null device. And no Ctrl+C the console made into an event is posted to the
    app meanwhile (the guard's `on_ctrl_c` is None for the suspend, put back after). An app without `suspend` is
    left as it is."""
    suspend = getattr(app, "suspend", None)
    if not callable(suspend):
        return
    from halo_harness import subprocess_safe

    @contextlib.contextmanager
    def suspended(*args, **kw):
        with suspend(*args, **kw):
            was = subprocess_safe.hand_the_terminal_here(True)
            guard = getattr(app, "console_guard", None)
            on_ctrl_c = getattr(guard, "on_ctrl_c", None)
            if guard is not None:
                guard.on_ctrl_c = None
            try:
                yield
            finally:
                subprocess_safe.hand_the_terminal_here(was)
                if guard is not None:
                    guard.on_ctrl_c = on_ctrl_c

    app.suspend = suspended


STUCK_GRACE_S = 0.5  # 3.6.0.17 Z4-1: hard_exit's grace once the pool's join gave up on a stuck worker
_POOL: dict = {"stuck": False}  # 3.6.0.17 Z4-1: whether join_the_pool gave up (bound_the_end's grace)
_clock = time.monotonic


def join_the_pool(app) -> bool:
    """3.6.0.17 Z4-1: the pool the app took from the loop at its unmount (`BridgeApp._bound_the_way_out`, a real halo
    only) is shut down without waiting (nothing new starts; work not yet started is cancelled) and its threads are
    joined within ONE bound for all of them: `closing.EXIT_GRACE_S`, never past the closing deadline. A worker only in
    flight (the git branch probe, the status line command, the launch's `claude auth status`) so ends by itself, its
    child with it, before anything of the way out runs (the closing procedure's marker scan would end that child and
    say so), as asyncio's join of that pool at the end of `app.run()` did in 3.6.0.16. A worker still running at the
    bound (a network read that never answers) is abandoned: False, and `bound_the_end` then arms the short grace."""
    from halo_harness import closing
    pool = getattr(app, "_pool_at_unmount", None)
    if pool is None:
        return True
    pool.shutdown(wait=False, cancel_futures=True)
    end = _clock() + closing.time_left(closing.EXIT_GRACE_S)
    for t in list(getattr(pool, "_threads", ())):
        while t.is_alive():
            left = end - _clock()
            if left <= 0:
                _POOL["stuck"] = True
                closing.trace("the app's pool still has a worker running: abandoned")
                return False
            t.join(min(left, 0.05))
    return True


def _code_of(exc) -> int:
    """3.6.0.17 Z4-1: the exit code an exit that raises `exc` out of run_tui leaves with: a Ctrl+C 130 (3.6.0.18 L:
    on every system; cli._run_full_screen catches it once this bound is armed, prints cli.main's one line and returns
    130, so no traceback and no Python's own code for it), SystemExit its code, a config file that does not parse or a file in Halo's own folders 2
    (cli.main's one line), anything else Python's 1 (a traceback)."""
    if isinstance(exc, KeyboardInterrupt):
        return 130
    if isinstance(exc, SystemExit):
        return exc.code if isinstance(exc.code, int) else (0 if exc.code is None else 1)
    try:
        from halo_harness.state_home import line_for_error
        from halo_harness.theme import CorruptConfigError
        if isinstance(exc, CorruptConfigError) or line_for_error(exc) is not None:
            return 2
    except Exception:
        pass
    return 1


def bound_the_end(code: int) -> None:
    """3.6.0.17 Z3-1: the end of the terminal app's way out, where the process has nothing left to do but leave (a
    real halo only, never a test's app). The exit hooks run here on the main path exactly as the normal exit runs them
    (`atexit._run_exitfuncs()`: last registered first, so a hook registered after closing, a pack policy's `stop_all`,
    stops its own child its own way before the closing procedure, which runs last with its own `say`; Python then
    clears them, so the exit runs none twice). The lines a quit prints at its close ("halo: left running on purpose:
    ...") are so printed also when a thread worker is stuck in a network read (the interpreter joins that thread
    before atexit). Then `closing.hard_exit(code)` with its own grace: only the interpreter's own ending is inside it,
    and a stuck thread is abandoned, never joined.
    3.6.0.17 Z4: the hooks run while pool threads `join_the_pool` abandoned may still run (a worker stuck in a network
    read); nothing here waits on them. When that join gave up, the grace is STUCK_GRACE_S (the interpreter cannot end
    by itself then: its own join of that thread would wait), else the plain EXIT_GRACE_S."""
    import atexit
    from halo_harness import closing
    if not closing._STATE.get("installed"):
        return
    atexit._run_exitfuncs()
    closing.hard_exit(code, STUCK_GRACE_S if _POOL["stuck"] else closing.EXIT_GRACE_S)


def _build_demo_controller(args):
    """`--demo [--stress N]` without `-p`: the same scripted transcript
    `testing.fake_controller.run_demo` prints, driven through the real
    App/FakeController pair instead -- the manual "stays responsive" check
    (D-TUI/acceptance: `--demo --stress 500`)."""
    from halo_harness.testing.fake_controller import FakeController, stress_turns

    turns = stress_turns(args.stress) if args.stress else None
    controller = FakeController(turns=turns)
    return controller, None, None, None
