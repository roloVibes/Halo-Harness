"""halo_harness.cli -- command-line entry point (`halo` console
script / `python -m halo_harness`). U0 scope A: the single argparse surface
mirroring `docs/harness/claude-help-2.1.281.txt` flag-for-flag (the flag-
parity rule: every flag `claude` accepts is accepted here with the same
name/arity/meaning; a flag whose FEATURE isn't built yet is still parsed
and gets one `halo_harness.not_yet` stderr line, never an argparse error --
so an actually-unknown flag really is unknown and remains an argparse
error, exit 2). Subcommands `proxy`/`models`/`mcp`/`config`/`doctor` are
dispatched before the main parser ever sees the rest of argv (each has its
own, separate flag surface). Bare `halo` (no `-p`) opens the U2
full-screen TUI (`halo_harness/tui/launch.py`, imported lazily so `-p`/
`import halo_harness` never pull in textual); a positional PROMPT without
`-p` opens the TUI and submits it as the first turn.
"""

from __future__ import annotations

import argparse
import os
import signal
import sys
from pathlib import Path
from typing import Optional

from halo_harness import __version__
from halo_harness.cli_flags import cli_flags_from_args
from halo_harness.not_yet import print_not_applicable, print_not_yet
from halo_harness.providers.routing import InvalidModelError

_STDIN_CAP_BYTES = 10 * 1024 * 1024  # 10 MB, matches Claude Code's own -p stdin cap


# =============================================================================
# The flag table (flag-parity rule). Every entry: (flag strings, add_argument
# kwargs incl. an explicit dest=). `_REAL_FLAGS` behave identically to
# Claude Code; `_NOT_YET_FLAGS` additionally carry (canonical label,
# milestone) and get one `not_yet` stderr line the first time their value
# differs from "never touched" (see `_flag_was_set`).
# =============================================================================

_REAL_FLAGS = [
    (["-p", "--print"], dict(dest="print_mode", action="store_true")),
    (["--model"], dict(dest="model", default=None)),
    (["--small-model"], dict(dest="small_model", default=None)),
    (["--cwd"], dict(dest="cwd", default=None)),
    (["--output-format"], dict(dest="output_format", choices=["text", "json", "stream-json"], default="text")),
    (["--input-format"], dict(dest="input_format", choices=["text", "stream-json"], default="text")),
    (["--include-partial-messages"], dict(dest="include_partial_messages", action="store_true")),
    (["--max-turns"], dict(dest="max_turns", type=int, default=None)),  # opt-in; no cap unless given
    (["--append-system-prompt"], dict(dest="append_system_prompt", default=None, metavar="TEXT")),
    (["--append-system-prompt-file"], dict(dest="append_system_prompt_file", default=None, metavar="FILE")),
    (["--system-prompt"], dict(dest="system_prompt", default=None, metavar="PROMPT")),
    (["--system-prompt-file"], dict(dest="system_prompt_file", default=None, metavar="FILE")),
    (["--settings"], dict(dest="settings", default=None, metavar="JSON_OR_PATH")),
    (["--setting-sources"], dict(dest="setting_sources", default=None, metavar="SOURCES")),
    (["--effort"], dict(dest="effort", choices=["low", "medium", "high", "xhigh", "max"], default=None)),
    (["--verbose"], dict(dest="verbose", action="store_true")),
    (["--version", "-v"], dict(dest="version", action="store_true")),
    (["--allowedTools", "--allowed-tools"], dict(dest="allowed_tools", default=None, metavar="TOOLS")),
    (["--disallowedTools", "--disallowed-tools"], dict(dest="disallowed_tools", default=None, metavar="TOOLS")),
    (["--permission-mode"], dict(dest="permission_mode", default=None,
        choices=["default", "acceptEdits", "plan", "auto", "dontAsk", "bypassPermissions", "manual"])),
    # W4a: `--allow-dangerously-skip-permissions` is Claude Code's own alias
    # for this same flag ("as an option, without it being enabled by
    # default" -- this harness has always treated the two identically, so
    # the second flag string is the whole fix).
    (["--dangerously-skip-permissions", "--allow-dangerously-skip-permissions"],
        dict(dest="dangerously_skip_permissions", action="store_true")),
    (["--tools"], dict(dest="tools", default=None, metavar="TOOLS")),
    (["--max-budget-usd"], dict(dest="max_budget_usd", type=float, default=None)),
    (["--json-schema"], dict(dest="json_schema", default=None, metavar="SCHEMA")),
    (["--add-dir"], dict(dest="add_dir", nargs="+", default=None, metavar="DIRECTORY")),
    (["--theme"], dict(dest="theme", default=None)),
    (["--demo"], dict(dest="demo", action="store_true")),
    (["--stress"], dict(dest="stress", type=int, default=None, metavar="N")),
    (["--bare"], dict(dest="bare", action="store_true")),
    (["--disable-slash-commands"], dict(dest="disable_slash_commands", action="store_true")),
    (["--session-id"], dict(dest="session_id", default=None, metavar="UUID")),
    (["--replay-user-messages"], dict(dest="replay_user_messages", action="store_true")),
    # H3: real now (were "not yet" -- MCP client + frozen catalog/lazy
    # load + the claude-in-chrome/playwright dynamic servers land this
    # milestone).
    (["--chrome"], dict(dest="chrome", action="store_true")),
    (["--no-chrome"], dict(dest="no_chrome", action="store_true")),
    (["--playwright"], dict(dest="playwright", action="store_true")),
    (["--playwright-cdp"], dict(dest="playwright_cdp", default=None, metavar="ENDPOINT")),
    (["--playwright-headless"], dict(dest="playwright_headless", action="store_true")),
    (["--mcp-config"], dict(dest="mcp_config", nargs="+", default=None, metavar="CONFIG")),
    (["--strict-mcp-config"], dict(dest="strict_mcp_config", action="store_true")),
    # H13 Part B: forces the plain type/size/dimensions caption for every
    # image tool result this run, same as `images: "caption"`/`"off"` in
    # ~/.halo/config.json but for just this one invocation -- the
    # TUI only (print mode has no inline-image concept to disable).
    (["--no-inline-images"], dict(dest="no_inline_images", action="store_true")),
    # 2.0.0 Launch intro: skips the one-time typewriter intro line (2.0.3:
    # a random pick from tui/intro_lines.py) a fresh interactive launch
    # otherwise shows -- same effect as `"intro": false` in
    # ~/.halo/config.json, see tui/launch.py's own show_intro resolution.
    (["--no-intro"], dict(dest="no_intro", action="store_true")),
    # Halo 2.0.3 round 5e: enforced offline mode for this one process --
    # never persisted (see `main()`'s own handling, right after parsing:
    # sets `HALO_OFFLINE=1` in THIS process's environment only); `/offline
    # on` is the persisted equivalent (`network.offline` in
    # `~/.halo/config.json`). Not a Claude Code flag -- Halo-only, same as
    # `--demo`/`--stress`/`--bare` just above.
    (["--offline"], dict(dest="offline", action="store_true")),
    # Halo 3.0.5.0 (Fleet): this session registers nothing and opens no
    # control socket -- Studio and `halo remote` never see it
    # (sets HALO_PRIVATE for THIS process; `/private on|off` in the
    # TUI, `control.private` in ~/.halo/config.json).
    (["--private"], dict(dest="private", action="store_true")),
    # Halo 3.3.11.0 R2: a session with no terminal (headless_session.py): the TUI's loop and session log, the
    # control socket its only door; Studio's "New session" starts one with `--session-for studio`.
    (["--headless"], dict(dest="headless", action="store_true")),
    (["--session-for"], dict(dest="session_for", default=None, metavar="WHO")),
    # Halo 2.0.3.1 (clipboard image paste): `-p`'s own way to attach an
    # image to the one turn it sends, Claude Code stream-json parity for
    # a plain `-p`/`--input-format text` run -- repeatable (several
    # `--image` flags attach several images to the same turn). A path
    # that doesn't exist, or isn't a recognized image extension, is a
    # clean `halo: ...` stderr line + exit 2 (`headless.run_print_mode`'s
    # own handling), never a provider 400 later.
    (["--image"], dict(dest="image", action="append", default=None, metavar="PATH")),
    # H6: real now (agent definitions + the Agent tool + plan mode +
    # sessions land this milestone).
    (["--agent"], dict(dest="agent", default=None, metavar="AGENT")),
    (["--agents"], dict(dest="agents", default=None, metavar="JSON_OR_FILE")),
    # 3.6.0.0 R5: lineups are gone; the old flag still parses, says so in one line, and the session runs on the map in
    # use (headless.build_session). `--map <name>` picks the map.
    (["--team"], dict(dest="team", default=None, metavar="TEAM")),
    # 3.6.0.0 R3: run THIS session on a map (`halo maps list`): main, its lines and the agents on it; over config's
    # `crew.map` for this one run, never persisted. A map with a problem: its lines on stderr, the session runs on starter.
    (["--map"], dict(dest="map", default=None, metavar="MAP")),
    # V2c (H15), widened Halo 2.0.2: repeatable NAME=MODEL[:EFFORT] override
    # for one of the ten built-in roles (or a currently-known custom one)
    # (orchestrator|coder|reviewer|researcher|small) -- validated in main()
    # right after parsing, so a bad NAME=MODEL is a clean exit-2 usage error
    # before either run_print_mode or the TUI ever starts building a Session.
    (["--role"], dict(dest="role", action="append", default=None, metavar="NAME=MODEL[:EFFORT]")),
    (["-c", "--continue"], dict(dest="continue_", action="store_true")),
    (["-r", "--resume"], dict(dest="resume", nargs="?", const="", default=None)),
    (["--fork-session"], dict(dest="fork_session", action="store_true")),
    (["-n", "--name"], dict(dest="name", default=None)),
    # H8 scope B: real now for a local path (attached as a log snapshot
    # before the first turn; image when the model has vision, text
    # otherwise). Claude Code's own file_id:relative_path cloud-resource
    # form gets a clear "not available here" notice instead -- see
    # headless.attach_cli_files.
    (["--file"], dict(dest="file", nargs="+", default=None, metavar="SPEC")),
    # Real now: `-d/--debug [FILTER]` turns on DEBUG file logging for the
    # whole run (TUI or print mode) at <state dir>/bridge.log, `--debug-file
    # PATH` picks the file. Found missing live: a blank TUI on a Linux box
    # had no log to look at because --debug still printed the "planned"
    # notice. The optional FILTER value is accepted for Claude Code parity
    # and ignored (everything is logged).
    (["-d", "--debug"], dict(dest="debug", nargs="?", const="", default=None)),
    (["--debug-file"], dict(dest="debug_file", default=None, metavar="PATH")),
    # W4a: real now -- the 21 flags the 2.0.1 gap list named as
    # implementable in a standalone harness (plans/2.0.1-w4-plan.md W4a
    # item 2). Each one's actual behaviour is wired in `_cli_flags_from_
    # args` below plus `headless.build_session`/`agent/loop.Session`; a few
    # reuse an existing knob outright (`--autocompact` is `CLAUDE_CODE_
    # AUTO_COMPACT_WINDOW`, already read by `agent/compact.resolve_knobs`).
    (["--autocompact"], dict(dest="autocompact", default=None, metavar="AUTO_OR_TOKENS")),
    (["--ax-screen-reader"], dict(dest="ax_screen_reader", action="store_true")),
    (["--bg", "--background"], dict(dest="background", action="store_true")),
    (["--betas"], dict(dest="betas", nargs="+", default=None, metavar="BETA")),
    (["--brief"], dict(dest="brief", action="store_true")),
    # W4a: repurposed for a standalone harness (no cloud sessions exist to
    # run "on a self-hosted environment") -- one or more KEY=VALUE pairs
    # merged into the tool child env, the one piece of claude's own
    # `--environment` that still means something here.
    (["--environment"], dict(dest="environment", action="append", default=None, metavar="KEY=VALUE")),
    (["--exclude-dynamic-system-prompt-sections"], dict(dest="exclude_dynamic_system_prompt_sections", action="store_true")),
    (["--fallback-model"], dict(dest="fallback_model", default=None, metavar="MODEL")),
    (["--forward-subagent-text"], dict(dest="forward_subagent_text", action="store_true")),
    (["--include-hook-events"], dict(dest="include_hook_events", action="store_true")),
    (["--no-session-persistence"], dict(dest="no_session_persistence", action="store_true")),
    (["--permission-prompt-tool"], dict(dest="permission_prompt_tool", default=None, metavar="TOOL")),
    (["--permission-prompts"], dict(dest="permission_prompts", choices=["host", "none"], default=None)),
    (["--plugin-dir"], dict(dest="plugin_dir", action="append", default=None, metavar="PATH")),
    (["--plugin-url"], dict(dest="plugin_url", action="append", default=None, metavar="URL")),
    (["--prompt-suggestions"], dict(dest="prompt_suggestions", nargs="?", const="true", default=None,
        choices=["true", "false", "1", "0", "yes", "no", "on", "off"])),
    (["--restricted"], dict(dest="restricted", action="store_true")),
    (["--system-prompt-snapshot"], dict(dest="system_prompt_snapshot", choices=["on", "off"], default=None)),
    (["--tmux"], dict(dest="tmux", nargs="?", const="default", default=None)),
    (["-w", "--worktree"], dict(dest="worktree", nargs="?", const="", default=None)),
]

# W4a: the 7 flags whose Claude Code feature is a cloud/IDE concept with no
# standalone-harness equivalent -- parsed and answered with one `not_
# applicable_line` (never "planned", since there is no future milestone
# that would change this), both here and in docs/COMMANDS.md.
_NOT_APPLICABLE_FLAGS = [
    (["--cloud"], dict(dest="cloud", nargs="?", const="", default=None),
        "--cloud", "halo has no cloud session service -- every session runs on this machine"),
    (["--teleport"], dict(dest="teleport", nargs="?", const="", default=None),
        "--teleport", "teleport sessions are a claude.ai cloud feature halo has no equivalent of"),
    (["--remote-control"], dict(dest="remote_control", nargs="?", const="", default=None),
        "--remote-control", "Remote Control pairs a session with the claude.ai mobile/web app, which halo does not integrate with"),
    (["--remote-control-session-name-prefix"], dict(dest="remote_control_session_name_prefix", default=None),
        "--remote-control-session-name-prefix", "only meaningful alongside --remote-control, which is not applicable here"),
    (["--from-pr"], dict(dest="from_pr", nargs="?", const="", default=None),
        "--from-pr", "resuming a session linked to a PR is a claude.ai cloud-session feature halo does not have"),
    (["--ide"], dict(dest="ide", action="store_true"),
        "--ide", "needs Anthropic's IDE extension protocol, which halo does not implement"),
    # D-CFG/no-cyber-blocks: Halo has no safety/refusal heuristics to
    # disable by design -- accepted for CLI compatibility, no effect
    # whatsoever (never gated, never even inspected past this point).
    (["--safe-mode"], dict(dest="safe_mode", action="store_true"),
        "--safe-mode", "halo has no safety heuristics to disable by design -- accepted for compatibility, no effect"),
]

# Kept as an empty list rather than removed outright: `_build_parser`/`main`
# below still iterate it uniformly alongside `_NOT_APPLICABLE_FLAGS`, so a
# FUTURE flag that is genuinely not-yet-built again (a new Claude Code
# release) has a ready home and a test (`test_cli_flags.py`) already
# asserting the invariant "every entry here really does print the not-yet
# line, never an argparse error" without needing to reinvent the mechanism.
_NOT_YET_FLAGS = []


def _enable_debug_logging(debug_file: Optional[str]) -> None:
    """`--debug` / `--debug-file PATH`: DEBUG file logging for the whole run,
    TUI or print mode. Default file = <state dir>/bridge.log (rotating,
    secrets redacted by RedactingFormatter); `--debug-file` picks the path.
    Never raises -- a logging problem must not stop the harness."""
    import logging
    try:
        from halo_harness.config.paths import bridge_home
        from halo_harness.providers.config import RedactingFormatter, setup_logging
        if debug_file:
            log_path = Path(debug_file).expanduser()
            log_path.parent.mkdir(parents=True, exist_ok=True)
            logger = logging.getLogger("bridge")
            for hdlr in logger.handlers[:]:
                logger.removeHandler(hdlr)
            handler = logging.FileHandler(str(log_path), encoding="utf-8")
            handler.setFormatter(RedactingFormatter("%(asctime)s - %(name)s - %(levelname)s - %(message)s"))
            logger.addHandler(handler)
            logger.propagate = False
        else:
            logger = setup_logging(bridge_home())
            log_path = bridge_home() / "bridge.log"
        logger.setLevel(logging.DEBUG)
        for name in ("halo_harness", "halo_harness.tui", "halo_harness.agent", "halo_harness.mcp"):
            child = logging.getLogger(name)
            child.setLevel(logging.DEBUG)
            if not child.handlers:
                for hdlr in logger.handlers:
                    child.addHandler(hdlr)
        logger.debug("debug logging enabled (halo %s, argv=%s)", __version__, sys.argv[1:])
        print(f"halo: debug log -> {log_path}", file=sys.stderr)
        # 2.0.1 launch-hang investigation: one [timeline] line per startup
        # phase (settings, instructions, session build, MCP discovery,
        # first paint), each with milliseconds elapsed since THIS call --
        # see halo_harness/debug_timeline.py. A no-op cost everywhere else
        # (`mark()` is a bool check unless `enable()` ran).
        from halo_harness import debug_timeline
        debug_timeline.enable()
    except Exception as e:  # pragma: no cover - defensive
        print(f"halo: could not enable debug logging: {e}", file=sys.stderr)


def _flag_was_set(value) -> bool:
    """True iff argparse gave `value` something other than an untouched
    flag's own default (every not-yet flag above is defined with default
    None/False, so this one check works uniformly for store_true, nargs="?"
    with a const, nargs="+"/append lists, and plain single values alike)."""
    return value not in (None, False)


def _json_or_file_problem(flag: str, spec, base: Path) -> str:
    """'' when `spec` (a flag's JSON-or-path value) is inline JSON that parses or a file that exists and parses;
    else the one line naming the flag. A relative path is read from `base`, as the flag's own loader reads it."""
    import json
    text = str(spec)
    if not text.lstrip().startswith("{"):
        path = Path(text) if Path(text).is_absolute() else base / text
        try:
            if not path.is_file():
                return f"{flag}: {text}: no such file"
            text = path.read_text(encoding="utf-8-sig")
        except (OSError, ValueError) as e:
            return f"{flag}: {spec}: could not read ({e})"
    try:
        json.loads(text)
    except ValueError as e:
        return f"{flag}: {spec if len(str(spec)) <= 60 else str(spec)[:57] + '...'}: not valid JSON ({e})"
    return ""


def _flag_file_problem(args) -> str:
    """fix pass 2 (sessions-storage batch 2): `--cwd`, `--settings`, `--mcp-config` and `--agents` naming a folder or
    file that is not there, or JSON that does not parse, were ignored and the run went ahead without them."""
    cwd_flag = getattr(args, "cwd", None)
    if cwd_flag and not Path(cwd_flag).is_dir():
        return f"--cwd: {cwd_flag}: no such folder"
    base = Path(cwd_flag).resolve() if cwd_flag else Path.cwd()
    checks = [("--settings", getattr(args, "settings", None), base)]
    checks += [("--mcp-config", spec, base) for spec in (getattr(args, "mcp_config", None) or [])]
    checks.append(("--agents", getattr(args, "agents", None), Path.cwd()))  # parse_agents_json reads from the process cwd
    for flag, spec, where in checks:
        if spec is not None and str(spec) != "":
            problem = _json_or_file_problem(flag, spec, where)
            if problem:
                return problem
    return ""


class _HelpFormatter(argparse.HelpFormatter):
    """3.6.0.0 R16: wraps the description as before; a text with its own line breaks (the commands block) keeps them."""

    def _fill_text(self, text, width, indent):
        if "\n" in text:
            return "".join(indent + line for line in text.splitlines(keepends=True))
        return super()._fill_text(text, width, indent)


def _epilog() -> str:
    """3.6.0.0 R16: every command from the one registry (cli_commands.py), grouped, each with its purpose."""
    from halo_harness.cli_commands import help_text
    return (help_text() + "\n\nThe GUI: `halo studio --mode agents` -- your agents, workflows and the map your sessions run"
            "\non, lit while one runs; in the TUI, /studio. A fresh box: `halo init` opens Studio's Setup."
            "\nDesign is a pack: halo pack install design.")


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="halo", add_help=True,
        description="halo - The multi-agent, multi-workflow harness you can watch: every model's thinking, hand-offs "
                    "and cost, live, and yours to steer. It starts an interactive session by default; use -p/--print "
                    "for non-interactive output",
        epilog=_epilog(), formatter_class=_HelpFormatter,
    )
    try:
        parser._positionals.title = "Arguments"
        parser._optionals.title = "Options"
    except AttributeError:
        pass
    parser.add_argument("prompt", nargs="?", default=None, metavar="PROMPT",
                         help="The prompt text; reads stdin (UTF-8, 10 MB cap) if omitted")
    for flags, kwargs in _REAL_FLAGS:
        parser.add_argument(*flags, **kwargs)
    for flags, kwargs, _label, _milestone in _NOT_YET_FLAGS:
        parser.add_argument(*flags, **kwargs)
    for flags, kwargs, _label, _reason in _NOT_APPLICABLE_FLAGS:
        parser.add_argument(*flags, **kwargs)
    return parser


def version_line() -> str:
    """`halo --version`'s one line, update.format_version_line's shape (`halo update` prints its before and after lines
    the same way): `halo 3.6.0.0 (1a2b3c4, master)`, `halo 3.6.0.0 (1a2b3c4)` with no branch known, `halo 3.6.0.0`
    when the commit is not known either."""
    try:
        from halo_harness.update import format_version_line, installed_build
        return format_version_line(installed_build())
    except Exception:
        return f"halo {__version__}"


def _make_streams_utf8_safe() -> None:
    """A model's reply may contain any Unicode character; a Windows
    console/pipe commonly defaults stdout/stderr to a legacy codepage that
    can't represent most of them -- reconfigure to UTF-8 with lossy-safe
    replacement, guarded since reconfigure() doesn't exist on every stream
    (e.g. a test harness's io.StringIO)."""
    for stream in (sys.stdout, sys.stderr):
        reconfigure = getattr(stream, "reconfigure", None)
        if callable(reconfigure):
            try:
                reconfigure(encoding="utf-8", errors="replace")
            except (ValueError, OSError):
                pass


def _read_stdin_prompt() -> "tuple[Optional[str], Optional[str]]":
    """Read stdin as UTF-8 with a 10 MB cap. Returns (text, error) -- exactly
    one is non-None. Reads `.buffer` in bytes mode and decodes ourselves so
    a legacy-codepage terminal's default text-mode codec never mangles a
    piped UTF-8 prompt/stream-json line."""
    buf = getattr(sys.stdin, "buffer", None)
    if buf is not None:
        raw = buf.read(_STDIN_CAP_BYTES + 1)
        if len(raw) > _STDIN_CAP_BYTES:
            return None, f"stdin prompt exceeds the {_STDIN_CAP_BYTES // (1024 * 1024)} MB cap"
        return raw.decode("utf-8", "replace"), None
    return sys.stdin.read(), None  # fallback for a replaced (non-buffer) stdin, e.g. some test harnesses


def _stdin_is_terminal() -> bool:
    try:
        return sys.stdin is None or sys.stdin.isatty()
    except (OSError, ValueError):
        return True


def _read_stdin_bytes() -> "tuple[Optional[bytes], Optional[str]]":
    """Piped stdin as raw bytes under the same cap `_read_stdin_prompt`
    has: `(data, None)`, or `(None, error)` past the cap."""
    buf = getattr(sys.stdin, "buffer", None)
    try:
        raw = buf.read(_STDIN_CAP_BYTES + 1) if buf is not None else sys.stdin.read().encode("utf-8")
    except (OSError, ValueError):
        return b"", None
    if len(raw) > _STDIN_CAP_BYTES:
        return None, f"stdin prompt exceeds the {_STDIN_CAP_BYTES // (1024 * 1024)} MB cap"
    return raw, None


def _apply_update_and_relaunch(argv: list) -> int:
    """`/update`: `run_tui(args)` returned `update.RESTART_EXIT_CODE`
    (Textual torn down, `Controller.quit` done). 3.2.2.0 R3: the install
    no longer runs inside this halo process -- on Windows its `halo.exe`
    parent holds the tool venv ("Scripts: Access is denied"). A detached
    updater (update_detached.py) waits for this process to end, stops what
    still runs, reinstalls and logs to `~/.halo/update.log`; this prints
    where that log is and how to pick the session up again, and exits."""
    from halo_harness.update_detached import run_after_exit
    hint = " ".join(["halo", "--continue", *_relaunch_flags(argv)])
    try:
        return run_after_exit(resume_hint=hint)
    except Exception as e:
        print(f"halo: the update did not start: {e}; run `halo update` from a shell", file=sys.stderr)
        return 1


def _relaunch_flags(argv: list) -> list:
    """`argv` for the post-update `halo --continue` (the hint `/update` prints): the original flags
    without `--continue`/`-c`, without `--fork-session` (the continued
    session would fork a second time) and without the positional PROMPT
    (the continued session would send it as a brand new turn). The prompt
    is found by dropping each argv token equal to it and keeping the first
    removal after which the parser sees no prompt and every other value
    unchanged -- so a flag value that happens to read the same stays."""
    import contextlib
    import io
    argv = [a for a in argv if a not in ("--continue", "-c", "--fork-session")]
    parser = _build_parser()
    sink = io.StringIO()

    def parse(a: list):
        try:
            return parser.parse_intermixed_args(a)
        except TypeError:
            return parser.parse_known_args(a)[0]

    try:
        with contextlib.redirect_stderr(sink):
            ns = parse(argv)
            if ns.prompt is None:
                return argv
            for i, tok in enumerate(argv):
                if tok != ns.prompt:
                    continue
                trial = argv[:i] + argv[i + 1:]
                alt = parse(trial)
                if alt.prompt is None and {**vars(alt), "prompt": ns.prompt} == vars(ns):
                    return trial
    except SystemExit:
        pass
    return argv


def _run_full_screen(args, argv: list) -> int:
    """The full-screen session: `run_tui(args)`, then `/update`'s restart exit code handed to the detached updater."""
    from halo_harness.tui.launch import run_tui
    code = run_tui(args)
    from halo_harness.update import RESTART_EXIT_CODE
    if code == RESTART_EXIT_CODE:
        return _apply_update_and_relaunch(argv)
    return code


def launch_bare(cwd=None) -> int:
    """3.3.3.0 R1: what bare `halo` does, from another command (`halo init` once Setup's Done is pressed): the
    default args of `main([])` and the full-screen session, the intro included. `cwd` other than this process's
    own is passed as `--cwd`."""
    args = _build_parser().parse_intermixed_args([])
    if cwd is not None and Path(cwd).resolve() != Path.cwd().resolve():
        args.cwd = str(cwd)
    return _run_full_screen(args, [])


#: 3.6.0.0 R5: the verbs of the lineups, bios and squares, and the one line each prints (help, then exit 0)
GONE_VERBS = {
    "teams": "lineups are gone: halo maps use <name> picks the map your sessions run on (halo maps list)",
    "roles": ("the model table: halo config get roles shows it, halo roles point <role> <model> sets one; one model "
              "for everything: halo maps use --none; lineups are gone: halo maps use <name> (halo maps list)"),
    "blocks": "shipped workflows: halo workflows new <name> --from <a shipped one> (halo workflows list)",
    "workflow": "use halo workflows (list / show / new / edit / try / run)",
}


def _run_command(argv: list) -> Optional[int]:
    """`halo <command> ...` from the registry (cli_commands.py): its exit code, or None when argv[0] is no command
    (a pack's own verb, or a prompt). `roles point` is the one internal word; a retired verb says where to go."""
    import importlib
    from halo_harness.cli_commands import BY_NAME
    if argv[:2] == ["roles", "point"]:  # the role write a steward or adviser line offers (until the next round moves it)
        from halo_harness.roles_cli import cmd_roles
        return cmd_roles(argv[1:])
    if argv[0] in GONE_VERBS:  # 3.6.0.0 R5: lineups, bios and squares are gone; each old verb says where to go
        print(f"halo {argv[0]}: {GONE_VERBS[argv[0]]}")
        return 0
    if argv[0] == "design":  # 3.3.13.0 R2: Design is the design pack's (studio/modes.py MOVED)
        from halo_harness.studio.modes import moved_line
        print(f"halo design: {moved_line('design')}", file=sys.stderr)
        return 2
    if argv[0] == "replay":  # 3.6.0.3 B (Z12): replays left Halo; never a prompt
        from halo_harness.cli_commands import REPLAY_LEFT
        print(REPLAY_LEFT, file=sys.stderr)
        return 2
    cmd = BY_NAME.get(argv[0])
    if cmd is None or not cmd.target:
        return None
    module, func = cmd.target.split(":")
    rc = getattr(importlib.import_module(module), func)(argv[1:])
    return rc if isinstance(rc, int) else 0


NEAR_MISS_HINTS = {"theme": "halo config set theme <name>"}


def _one_slip(a: str, b: str) -> bool:
    """True when `a` differs from `b` by one letter changed, added or dropped, or two neighbours swapped."""
    if a == b or abs(len(a) - len(b)) > 1:
        return False
    i = 0
    while i < min(len(a), len(b)) and a[i] == b[i]:
        i += 1
    return (a[i + 1:] == b[i + 1:] or a[i + 1:] == b[i:] or a[i:] == b[i + 1:]
            or (a[i + 2:] == b[i + 2:] and a[i:i + 2] == b[i:i + 2][::-1]))


def _near_miss_command(argv: list) -> Optional[int]:
    """A first word that is no command but is one slip of the keys off a listed one (`docter`, `initt`, `map`), or a
    word with a known home (`theme`): say so and exit 2 instead of sending it to the model as a prompt. A prompt of
    several words in one argument, or a word near no command, is left alone (None)."""
    import difflib
    import re
    from halo_harness.cli_commands import COMMANDS
    word = argv[0]
    if not re.fullmatch(r"[a-z][a-z0-9-]{2,}", word):  # three letters at least: `halo go` / `halo hi` stay prompts
        return None
    hint = NEAR_MISS_HINTS.get(word)
    if hint is None:
        # One slip of the keys (a letter wrong, missing, extra or two swapped) and the same first letter: `lint` is
        # not `init`, `port` is not `report`, `start` is not `stats`. Those stay prompts.
        names = [c.name for c in COMMANDS if not c.kind and c.name[:1] == word[0] and _one_slip(word, c.name)]
        close = difflib.get_close_matches(word, names, n=1, cutoff=0)
        if not close:
            return None
        hint = f"halo {close[0]}"
    print(f"halo: no command '{word}' -- did you mean `{hint}`? (to send it as a prompt: halo -- \"{word}\")",
          file=sys.stderr)
    return 2


def main(argv: Optional[list] = None) -> int:
    """Entry point. A config.json that does not parse (`CorruptConfigError`
    from a config writer anywhere below) is reported as one `halo: ...`
    line and exit 2, never a traceback; library callers still get the
    exception from `theme.set_config_value` itself."""
    # 3.6.0.0 R10: the real process (console script, `python -m`) installs the closing procedure (closing.py).
    # A launch that only prints (`--help`, `--version`) starts nothing, so it skips it and stays light (R16).
    if argv is None and sys.argv[1:] not in (["--help"], ["-h"], ["--version"]):
        from halo_harness import closing
        closing.install()
        # Halo's own folder unusable (read-only, root-owned after `sudo halo`, a file): one plain line before
        # anything starts in it; `halo doctor` shows the same line as its first row instead.
        if not any(a in ("-h", "--help") for a in sys.argv[1:]) and sys.argv[1:2] != ["doctor"]:
            from halo_harness.state_home import problem
            home_problem = problem()
            if home_problem:
                print(home_problem, file=sys.stderr)
                return 2
    try:
        return _main(argv)
    except Exception as e:  # 3.6.0.0 R16: theme is imported only here, so `halo --help` stays light
        from halo_harness.theme import CorruptConfigError
        if not isinstance(e, CorruptConfigError):
            from halo_harness.state_home import line_for_error
            own = line_for_error(e)  # a file in Halo's own folders it cannot read or write: the plain line
            if own is None:
                raise
            print(own, file=sys.stderr)
            return 2
        print(f"halo: {e}", file=sys.stderr)
        return 2


def _main(argv: Optional[list] = None) -> int:
    _make_streams_utf8_safe()
    def signal_exit(code: int):  # 3.6.0.0 R10: unwinds, and a bound behind it (calls in flight). closing.py is
        def handler(signum, frame):  # imported when a signal arrives, so `halo --help` stays light (R16)
            from halo_harness.closing import signal_exit as real
            return real(code)(signum, frame)
        return handler
    try:  # best-effort: SIGTERM -> exit 143 (not available on every platform/thread)
        signal.signal(signal.SIGTERM, signal_exit(143))
    except (ValueError, AttributeError, OSError):
        pass
    # H9 whole-tree review finding 3: SIGHUP (closing the terminal, an SSH
    # drop) used to kill the process at once, no `finally` ran and a `-p`
    # run's background job kept running (seen on WSL). No SIGHUP on Windows
    # (AttributeError, caught as above); a real `sys.exit()` unwinds every
    # `finally: job_registry.kill_all()` / `mcp_manager.close_all()`.
    try:  # 3.6.0.0 fx: an ignored SIGHUP (`nohup halo ... &`) stays ignored, as every nohup-aware program does
        if signal.getsignal(signal.SIGHUP) is not signal.SIG_IGN:
            signal.signal(signal.SIGHUP, signal_exit(129))
    except (ValueError, AttributeError, OSError):
        pass
    argv = sys.argv[1:] if argv is None else list(argv)

    if argv and not argv[0].startswith("-"):  # 3.6.0.0 R16: every command is one row of cli_commands.py
        rc = _run_command(argv)
        if rc is not None:
            return rc
    if argv and not argv[0].startswith("-"):  # 3.4.0.0 B: a pack's own verb; a verb that left says where it went
        from halo_harness.packs.contrib_cli import dispatch
        rc = dispatch(argv)
        if rc is not None:
            return rc
        rc = _near_miss_command(argv)  # 3.6.0.0 fix pass: `halo docter` is a typo, not a prompt
        if rc is not None:
            return rc

    parser = _build_parser()
    try:
        args = parser.parse_intermixed_args(argv)
    except TypeError:
        # documented limitation of parse_intermixed_args on some
        # optional/positional shapes; fall back rather than crash (only
        # changes behavior for argv shapes that would have been ambiguous
        # anyway -- an genuinely-unknown flag still raises SystemExit(2)
        # from WITHIN parse_intermixed_args itself, before this except ever runs).
        args, _ = parser.parse_known_args(argv)

    if args.version:
        # 3.6.0.0 R16: one line, `halo <version> (<commit>, <branch>)`, nothing else -- a script reads it; the banner is the
        # interactive start's (tui/intro_lines.py). The commit once the install's own is known (PEP 610
        # direct_url.json, or git in a live checkout: update.installed_build); without it, `halo <version>`.
        print(version_line())
        return 0

    for _flags, kwargs, label, milestone in _NOT_YET_FLAGS:
        if _flag_was_set(getattr(args, kwargs["dest"])):
            print_not_yet(label, milestone)
    for _flags, kwargs, label, reason in _NOT_APPLICABLE_FLAGS:
        if _flag_was_set(getattr(args, kwargs["dest"])):
            print_not_applicable(label, reason)

    if _flag_was_set(getattr(args, "debug", None)) or getattr(args, "debug_file", None):
        _enable_debug_logging(getattr(args, "debug_file", None))

    # Halo 2.0.3 round 5e: `--offline` -- sets `HALO_OFFLINE=1` for THIS
    # PROCESS ONLY (never written to `~/.halo/config.json`; `providers.
    # http.offline_mode_enabled()` checks this env var first, ahead of the
    # persisted `network.offline` key, same "env overrides the file"
    # convention every other knob here already uses). Set as early as
    # possible, before either run_print_mode or the TUI ever builds a
    # Session or makes a single network call (an update check, a catalog
    # refresh, ...).
    if getattr(args, "offline", False):
        os.environ["HALO_OFFLINE"] = "1"
    if getattr(args, "private", False):  # 3.0.5.0: a private session (see the flag's own comment)
        os.environ["HALO_PRIVATE"] = "1"

    # review finding 34: `--autocompact <auto|tokens>` used to write
    # straight into `os.environ["CLAUDE_CODE_AUTO_COMPACT_WINDOW"]`, the
    # LOWEST (shell) layer of `settings.effective_env` -- a settings.json
    # `env` block setting the SAME name silently outranked this explicit
    # flag. The raw value already reaches `cli_flags["autocompact"]`
    # (`cli_flags_from_args`) unconditionally; `agent/compact.resolve_
    # knobs` now parses it itself and gives it top precedence, so nothing
    # needs doing here at all any more.

    if getattr(args, "role", None):
        # V2c (H15): validated ONCE, here, before either run_print_mode or
        # the TUI ever starts building a Session -- a bad NAME=MODEL is a
        # clean exit-2 usage error, same treatment as a bad --session-id.
        from halo_harness.roles import parse_role_flags
        try:
            parse_role_flags(args.role)
        except ValueError as e:
            print(f"halo: {e}", file=sys.stderr)
            return 2

    flag_problem = _flag_file_problem(args)  # fix pass 2: a flag naming a missing file or bad JSON stops the run
    if flag_problem:
        print(f"halo: {flag_problem}", file=sys.stderr)
        return 2

    if args.demo and args.print_mode:
        from halo_harness.testing.fake_controller import run_demo
        demo_format = args.output_format if args.output_format in ("text", "json") else "text"
        return run_demo(output_format=demo_format, stress=args.stress)

    # W4a: `--bg`/`--background` -- spawn THIS SAME invocation (minus the
    # flag itself, and forced to -p since a detached child has no terminal
    # a TUI could render into) as a detached background process, print its
    # id + log path, and return immediately. A scoped-down v1 of Claude
    # Code's own `--bg` (no `attach`/`logs`/`stop`/`rm` subcommands yet --
    # the log file and the OS's own process tools cover the same ground
    # for this round; see the worker report for what's left).
    if _flag_was_set(getattr(args, "background", False)):
        from halo_harness.bg_run import start_background_run
        filtered = [a for a in argv if a not in ("--bg", "--background")]
        # review finding 91: the detached child cannot read this terminal's
        # pipe, so piped input (the prompt, or stream-json lines) is read
        # here -- under the same 10 MB cap a foreground `-p` has -- and
        # handed over as the child's stdin.
        stdin_data = None
        if (args.prompt is None or args.input_format == "stream-json") and not _stdin_is_terminal():
            stdin_data, stdin_err = _read_stdin_bytes()
            if stdin_err is not None:
                print(f"halo: {stdin_err}", file=sys.stderr)
                return 2
        info = start_background_run(filtered, stdin_data=stdin_data, launched=True)
        print(f"halo: started in the background, id={info['id']}", file=sys.stderr)
        print(f"halo: log -> {info['log_path']}", file=sys.stderr)
        return 0

    if getattr(args, "headless", False):  # 3.3.11.0 R2: a session with no terminal (headless_session.py)
        from halo_harness.headless_session import run as run_headless
        return run_headless(args)
    if not getattr(args, "bare", False) and sys.stderr.isatty():  # 3.6.0.0 R5: the old files' one line, once
        from halo_harness.crew.old_files import terminal_once
        terminal_once(Path.cwd())
    if not args.print_mode:
        # U2: bare `halo [PROMPT]` and `halo --demo` (without
        # -p) both open the full-screen TUI; textual/rich become real
        # imports only from this lazy import down. A full-screen session
        # needs a real terminal to render into and read keys from -- stdin
        # not being a tty (piped/redirected input, or a subprocess with no
        # console at all, e.g. a headless test or CI runner) means nothing
        # could ever drive it, so this is a deterministic one-line notice
        # + exit 2 rather than Textual hanging trying to set up a terminal
        # that doesn't exist.
        if not sys.stdin.isatty():
            print("halo: a full-screen session requires an interactive terminal "
                  "(stdin is not a tty) -- use -p/--print for a non-interactive run",
                  file=sys.stderr)
            return 2
        # W4a: `--tmux` -- a simpler, tmux-only reading of Claude Code's own
        # version (no iTerm2 native-pane backend here): re-exec this same
        # launch inside a new tmux window when tmux exists and we are not
        # ALREADY inside one (`$TMUX` set) -- never an error when tmux is
        # missing, just a notice and the ordinary in-process launch.
        if _flag_was_set(getattr(args, "tmux", None)) and "TMUX" not in os.environ:
            from halo_harness.bg_run import run_in_tmux
            tmux_argv = [a for a in argv if a != "--tmux" and not a.startswith("--tmux=")]
            code = run_in_tmux(tmux_argv)
            if code is not None:
                return code
            print("halo: --tmux requires the `tmux` binary on PATH -- continuing without it",
                  file=sys.stderr)
        # W4a: `--ax-screen-reader` -- plain, line-oriented output instead
        # of the full Textual UI (flat text, no borders/animations/spinners).
        if _flag_was_set(getattr(args, "ax_screen_reader", False)):
            from halo_harness.ax_mode import run_ax_screen_reader_mode
            return run_ax_screen_reader_mode(args)
        return _run_full_screen(args, argv)

    system_prompt_text = args.system_prompt
    if args.system_prompt_file and system_prompt_text is None:
        try:
            system_prompt_text = Path(args.system_prompt_file).read_text(encoding="utf-8")
        except OSError as e:
            print(f"halo: could not read --system-prompt-file: {e}", file=sys.stderr)
            return 2
    append_system_prompt_text = args.append_system_prompt
    if args.append_system_prompt_file:
        try:
            file_text = Path(args.append_system_prompt_file).read_text(encoding="utf-8")
        except OSError as e:
            print(f"halo: could not read --append-system-prompt-file: {e}", file=sys.stderr)
            return 2
        append_system_prompt_text = f"{append_system_prompt_text}\n\n{file_text}" if append_system_prompt_text else file_text

    setting_sources = [s.strip() for s in args.setting_sources.split(",") if s.strip()] if args.setting_sources else None

    stdin_lines = None
    prompt_text = args.prompt
    if args.input_format == "stream-json":
        # finding 10 (major, h4-h5-h3c review): stdin is read
        # INCREMENTALLY, on a background thread, by run_print_mode itself
        # -- reading it all here, to EOF, before the first turn even
        # starts, deadlocked an SDK-style client that writes one line and
        # waits for that turn's `result` before writing the next one.
        # `stdin_lines=None` for stream-json now just means "headless.py
        # owns stdin for this run", not "nothing was piped".
        pass
    elif prompt_text is None:
        if sys.stdin.isatty():
            print("halo: -p requires a prompt (inline or piped via stdin)", file=sys.stderr)
            return 2
        prompt_text, err = _read_stdin_prompt()
        if err is not None:
            print(f"halo: {err}", file=sys.stderr)
            return 2
        if not prompt_text:
            print("halo: -p requires a prompt (inline or piped via stdin)", file=sys.stderr)
            return 2

    from halo_harness.headless import run_print_mode
    from halo_harness import closing
    closing.arm_second_ctrl_c()  # 3.6.0.0 R10: Windows, a second Ctrl+C ends a turn whose call never answers
    try:
        return run_print_mode(
            prompt=prompt_text,
            model_ref_raw=args.model,
            small_model_ref_raw=args.small_model,
            cwd=Path(args.cwd) if args.cwd else None,
            output_format=args.output_format,
            input_format=args.input_format,
            max_turns=args.max_turns,
            append_system_prompt=append_system_prompt_text,
            system_prompt=system_prompt_text,
            settings_flag=args.settings,
            setting_sources=setting_sources,
            verbose=args.verbose,
            effort=getattr(args, "effort", None),
            allowed_tools=args.allowed_tools,
            disallowed_tools=args.disallowed_tools,
            permission_mode=args.permission_mode,
            dangerously_skip_permissions=args.dangerously_skip_permissions,
            tools=args.tools,
            add_dir=args.add_dir,
            bare=args.bare,
            disable_slash_commands=args.disable_slash_commands,
            session_id=args.session_id,
            include_partial_messages=args.include_partial_messages,
            max_budget_usd=args.max_budget_usd,
            json_schema=args.json_schema,
            replay_user_messages=args.replay_user_messages,
            stdin_lines=stdin_lines,
            chrome=args.chrome, no_chrome=args.no_chrome, playwright=args.playwright,
            playwright_cdp=args.playwright_cdp, playwright_headless=args.playwright_headless,
            mcp_config=args.mcp_config, strict_mcp_config=args.strict_mcp_config,
            continue_=bool(getattr(args, "continue_", False)), resume=getattr(args, "resume", None),
            fork_session_flag=bool(getattr(args, "fork_session", False)),
            agent=getattr(args, "agent", None), agents_flag=getattr(args, "agents", None),
            roles_flag=getattr(args, "role", None),
            name=getattr(args, "name", None), file_specs=getattr(args, "file", None),
            cli_flags=cli_flags_from_args(args),
        )
    except InvalidModelError as e:
        # a bad --model/alias must be a clean config error (exit 2), not an
        # uncaught traceback (exit 1 is reserved for a request that ran and
        # failed, not a bad invocation).
        if args.model:
            print(f"halo: invalid --model: {e}", file=sys.stderr)
        else:  # fix pass 2: no --model was given; name where the model came from instead
            try:
                from halo_harness.doctor import _effective_default_model
                origin = _effective_default_model(Path(args.cwd) if args.cwd else None, args.settings)[1]
            except Exception:
                origin = "your saved settings"
            print(f"halo: invalid model (from {origin}): {e}", file=sys.stderr)
        if args.model:
            from halo_harness.catalog_cli import near_miss_slug
            from halo_harness.config.paths import bridge_home
            from halo_harness.providers.databricks import load_models_json
            try:
                known = load_models_json(bridge_home())
                matches = near_miss_slug(args.model, known)
                if matches:
                    print(f"halo: did you mean: {', '.join('or:' + m for m in matches)}", file=sys.stderr)
            except Exception:
                pass
        return 2
    except KeyboardInterrupt:
        # Ctrl+C during a print-mode turn: POSIX exit-code convention
        # (128 + SIGINT's 2 = 130), never an uncaught-traceback exit 1.
        print("\nhalo: interrupted", file=sys.stderr)
        if closing._STATE.get("installed"):  # 3.6.0.0 R10: a sub-agent's call in flight never holds the exit up
            closing.hard_exit(130)
        return 130


def main_deprecated_alias(argv: Optional[list] = None) -> int:
    """`rolo-claude`'s deprecated-alias entry point: one notice line to
    stderr, then exactly `main(argv)` -- same process, same parser, same
    behavior, so every flag/subcommand (including `rolo-claude proxy`)
    keeps working under the old name. Never prints the notice more than
    once per process (there's only ever one entry into argv handling per
    invocation).

    2.0.1: no longer a `pyproject.toml` console-script entry point (an old,
    separately-installed `rolo-claude` tool owning that name made a fresh
    `uv tool install --editable .` of Halo fail outright -- see CHANGELOG
    [2.0.1]). `bin/rolo-claude` (the no-install-at-all POSIX fallback) does
    NOT call this -- it prints its own notice and execs `bin/halo` directly
    -- this function is kept only as a small, still-tested, directly
    callable building block for any future reuse."""
    print("halo: 'rolo-claude' is deprecated, use 'halo' instead", file=sys.stderr)
    return main(argv)


if __name__ == "__main__":
    sys.exit(main())
