"""tests.test_docs_commands -- H14b brief: docs/COMMANDS.md must document
every real CLI subcommand and flag, and never document one that doesn't
exist. Flags are gathered the same way a user would find them: by calling
each command/subcommand's own `--help` IN-PROCESS (no subprocess, no
network) and reading the SAME argparse-rendered text `halo --help`
would print -- never hand-copied into this test, so it can't silently drift
from the real flag table the way a hardcoded list would.

Two directions, per the brief:
  1. every real subcommand name, and every real flag any of them accepts,
     must appear somewhere in COMMANDS.md;
  2. every flag COMMANDS.md documents AS A FLAG (a `-x`/`--xxx`-shaped
     inline-code span inside a heading -- this doc's own per-flag section
     marker, see its own "How this file is organised" note) must be one of
     the real ones above -- never a typo or a Claude Code flag this build
     doesn't actually accept.
"""
from __future__ import annotations

import contextlib
import io
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from tests.helpers.doc_parts import doc_text  # 3.1.1.0 R2: a split doc reads with its parts
from tests.helpers.runner import Ctx, new_registry, print_results, run_all

REPO_DIR = Path(__file__).resolve().parent.parent
test, TESTS = new_registry()

_FLAG_RE = re.compile(r"(?<![\w-])(-{1,2}[A-Za-z][\w-]*)")
_HEADING_RE = re.compile(r"^#{1,4}\s+(.+)$", re.MULTILINE)
_HEADING_FLAG_RE = re.compile(r"`(-{1,2}[A-Za-z][\w-]*)")


def _capture(fn, argv) -> str:
    """Call `fn(argv)` (a `cmd_xxx(argv)`-shaped entry point) and return
    whatever it printed to stdout/stderr -- catching the SystemExit an
    argparse `--help`/`-h` action normally raises after printing."""
    buf = io.StringIO()
    try:
        with contextlib.redirect_stdout(buf), contextlib.redirect_stderr(buf):
            fn(argv)
    except SystemExit:
        pass
    return buf.getvalue()


def _flags_in(text: str) -> "set[str]":
    return set(_FLAG_RE.findall(text))


def _gather_real_flags() -> "dict[str, set]":
    """`{command_label: {flag, ...}}` -- one entry per subcommand (plus the
    bare top-level command), each the exact flag tokens its own real
    `--help` text contains (which, for the top-level parser, already
    includes every `_NOT_YET_FLAGS` entry too -- they're ordinary
    argparse options on the SAME parser, just ones whose FEATURE isn't
    built yet, so they show up in `--help` exactly like a real one)."""
    from halo_harness import cli as cli_mod
    from halo_harness import mcp_cli, catalog_cli, doctor as doctor_mod, stats_cli, export_cli, improve_cli, init_cli
    from halo_harness import ollama_cli, update_cli
    from halo_harness import work_matrix as work_matrix_mod
    from halo_harness.config_cli import cmd_config
    import bridge

    out: "dict[str, set]" = {}
    out["halo"] = _flags_in(cli_mod._build_parser().format_help())
    out["halo ollama"] = _flags_in(_capture(ollama_cli.cmd_ollama, ["--help"]))
    out["halo ollama discover"] = _flags_in(_capture(ollama_cli.cmd_ollama, ["discover", "--help"]))  # 3.2.3.0 R2
    out["halo ollama tune"] = _flags_in(_capture(ollama_cli.cmd_ollama, ["tune", "--help"]))  # 3.2.3.0 R3
    out["halo ollama hardware"] = _flags_in(_capture(ollama_cli.cmd_ollama, ["hardware", "--help"]))  # 3.3.4.0 R1
    for sub in ("traffic", "events"):  # 3.3.4.0 R2: the ledger's rollups, the server's events
        out[f"halo ollama {sub}"] = _flags_in(_capture(ollama_cli.cmd_ollama, [sub, "--help"]))
    for sub in ("findings", "plan", "run"):  # 3.3.4.0 R3: the steward
        out[f"halo ollama steward {sub}"] = _flags_in(_capture(ollama_cli.cmd_ollama, ["steward", sub, "--help"]))
    out["halo mcp"] = _flags_in(_capture(mcp_cli.cmd_mcp, ["--help"]))
    out["halo mcp list"] = _flags_in(_capture(mcp_cli._cmd_list, ["--help"]))
    out["halo mcp get"] = _flags_in(_capture(mcp_cli._cmd_get, ["--help"]))
    out["halo mcp add"] = _flags_in(_capture(mcp_cli._cmd_add, ["--help"]))
    out["halo mcp add-json"] = _flags_in(_capture(mcp_cli._cmd_add_json, ["--help"]))
    out["halo mcp remove"] = _flags_in(_capture(mcp_cli._cmd_remove, ["--help"]))
    out["halo models"] = _flags_in(_capture(catalog_cli.cmd_models, ["--help"]))
    out["halo config"] = _flags_in(_capture(cmd_config, ["--help"]))
    out["halo config where"] = _flags_in(_capture(cmd_config, ["where", "--help"]))  # 3.1.1.0 R2
    out["halo doctor"] = _flags_in(_capture(doctor_mod.cmd_doctor, ["--help"]))
    out["halo update"] = _flags_in(_capture(update_cli.cmd_update, ["--help"]))
    out["halo stats"] = _flags_in(_capture(stats_cli.cmd_stats, ["--help"]))
    out["halo export"] = _flags_in(_capture(export_cli.cmd_export, ["--help"]))
    from halo_harness.session_trace_cli import cmd_session  # 3.3.0.0 R6: the Markdown trace
    out["halo session export"] = _flags_in(_capture(cmd_session, ["export", "--help"]))
    out["halo improve"] = _flags_in(_capture(improve_cli.cmd_improve, ["--help"]))
    out["halo init"] = _flags_in(_capture(init_cli.cmd_init, ["--help"]))
    out["halo proxy"] = _flags_in(_capture(bridge.main, ["--help"]))
    out["halo work-matrix"] = _flags_in(_capture(work_matrix_mod.cmd_work_matrix, ["--help"]))
    out["halo work-matrix show"] = _flags_in(_capture(work_matrix_mod.cmd_work_matrix, ["show", "--help"]))
    out["halo work-matrix apply"] = _flags_in(_capture(work_matrix_mod.cmd_work_matrix, ["apply", "--help"]))
    # 2.0.6 rounds: the new surfaces join the table
    from halo_harness import teams_cli, gym_cli, replay_cli
    out["halo teams"] = _flags_in(_capture(teams_cli.cmd_teams, ["--help"]))
    out["halo gym"] = _flags_in(_capture(gym_cli.cmd_gym, ["--help"]))
    out["halo replay"] = _flags_in(_capture(replay_cli.cmd_replay, ["--help"]))
    # 2.0.10 round 1: `halo review`
    from halo_harness.review import cli as review_cli
    out["halo review"] = _flags_in(_capture(review_cli.cmd_review, ["--help"]))
    # 3.0.4.0 round R1: `halo media` (ComfyUI)
    from halo_harness.media.cli import cmd_media
    for sub in ("init", "doctor", "inspect", "models", "workflows"):
        out[f"halo media {sub}"] = _flags_in(_capture(cmd_media, [sub, "--help"]))
    # 3.0.5.0 round R2: `halo fleet` (the hub, pairing, join and the live table)
    from halo_harness.fleet.cli import cmd_fleet
    from halo_harness.fleet.table import cmd_table
    out["halo fleet"] = _flags_in(_capture(cmd_table, ["--help"]))
    for sub in ("serve", "pair", "join", "leave", "status", "members", "kick", "record", "digest",  # record, digest: R4
                "capabilities", "who"):  # 3.0.6.0 R6
        out[f"halo fleet {sub}"] = _flags_in(_capture(cmd_fleet, [sub, "--help"]))
    for sub in ("new", "plan", "edit", "approve", "run", "status", "stop", "report", "open"):  # 3.0.6.0 R7
        out[f"halo fleet mission {sub}"] = _flags_in(_capture(cmd_fleet, ["mission", sub, "--help"]))
    # 3.0.8.0 round R1: `halo team` (members, blocks, stages, the board)
    from halo_harness.team.cli import VERBS as TEAM_VERBS, cmd_team
    for sub in TEAM_VERBS:
        out[f"halo team {sub}"] = _flags_in(_capture(cmd_team, [sub, "--help"]))
    from halo_harness.start_cli import cmd_start  # 3.1.1.0 R1: the guided first run and the glossary
    out["halo start"] = _flags_in(_capture(cmd_start, ["--help"]))
    from halo_harness.explain_cli import cmd_explain
    out["halo explain"] = _flags_in(_capture(cmd_explain, ["--help"]))
    from halo_harness.check_cli import cmd_check  # 3.2.2.0 R2: the checks after setup
    out["halo check"] = _flags_in(_capture(cmd_check, ["--help"]))
    from halo_harness.studio.server import cmd_studio  # 3.1.1.0 R3: --edit (Studio is the editor)
    out["halo studio"] = _flags_in(_capture(cmd_studio, ["--help"]))
    from halo_harness.settings_cli import cmd_settings  # 3.3.3.0 R2: the door into Studio's Settings
    out["halo settings"] = _flags_in(_capture(cmd_settings, ["--help"]))
    # 3.1.8.0 R1: the supervisor and its goal queue
    from halo_harness.supervise.cli import cmd_supervise
    from halo_harness.supervise.goal_cli import cmd_goal
    out["halo supervise"] = _flags_in(_capture(cmd_supervise, ["--help"]))
    for sub in ("status", "stop"):
        out[f"halo supervise {sub}"] = _flags_in(_capture(cmd_supervise, [sub, "--help"]))
    out["halo goal"] = _flags_in(_capture(cmd_goal, ["--help"]))
    for sub in ("add", "list", "show", "rm", "hold", "release", "pause", "resume", "cancel"):
        out[f"halo goal {sub}"] = _flags_in(_capture(cmd_goal, [sub, "--help"]))
    from halo_harness.outcomes.cli import cmd_outcomes  # 3.1.8.0 R3: every agent task's outcome
    out["halo outcomes"] = _flags_in(_capture(cmd_outcomes, ["--help"]))
    out.update({f"halo outcomes {v}": _flags_in(_capture(cmd_outcomes, [v, "--help"])) for v in ("learned", "forget")})  # 3.1.9.0 R3
    from halo_harness.knowledge.cli import VERBS as KNOWLEDGE_VERBS, cmd_knowledge  # 3.1.8.0 R4: `halo knowledge`
    out.update({f"halo knowledge {v}": _flags_in(_capture(cmd_knowledge, [v, "--help"])) for v in KNOWLEDGE_VERBS})
    from halo_harness.packs.cli import VERBS as PACK_VERBS, cmd_pack  # 3.2.0.0 R1: `halo pack`
    out.update({f"halo pack {v}": _flags_in(_capture(cmd_pack, [v, "--help"])) for v in PACK_VERBS})
    from halo_harness.workflows.cli import cmd_workflow  # 3.2.0.0 R5: `halo workflow`
    out.update({f"halo workflow {v}": _flags_in(_capture(cmd_workflow, [v, "--help"])) for v in ("list", "show", "check", "run")})
    from halo_harness.isolation.cli import cmd_isolation  # 3.1.8.0 R5: `halo isolation`, `halo secrets`
    from halo_harness.isolation.secrets import cmd_secrets
    out.update({f"halo isolation {v}": _flags_in(_capture(cmd_isolation, [v, "--help"])) for v in ("image", "build", "check")})
    out["halo secrets check"] = _flags_in(_capture(cmd_secrets, ["check", "--help"]))
    return out


@test
def test_every_subcommand_is_documented(ctx: Ctx):
    text = doc_text("COMMANDS.md")
    for name in ("init", "doctor", "update", "models", "mcp", "config", "stats", "export", "improve", "proxy",
                 "work-matrix", "ollama", "review", "media", "fleet", "team", "start", "explain", "pack", "workflow",
                 "isolation", "secrets", "session", "settings"):
        label = f"halo {name}"
        ctx.check(f"COMMANDS.md documents {label!r} (as a heading)",
                  re.search(rf"^#{{1,3}}\s+.*`?{re.escape(label)}`?", text, re.MULTILINE) is not None)


@test
def test_every_real_flag_is_documented_somewhere(ctx: Ctx):
    text = doc_text("COMMANDS.md")
    real = _gather_real_flags()
    missing: "list[str]" = []
    for command, flags in real.items():
        for flag in sorted(flags):
            if flag in ("-h", "--help"):
                continue  # documented once, globally -- see the doc's own front matter note
            pattern = re.compile(rf"(?<![\w-]){re.escape(flag)}(?![\w-])")
            if not pattern.search(text):
                missing.append(f"{command} {flag}")
    ctx.check(f"every real flag has a mention in COMMANDS.md; missing: {missing}", not missing)
    ctx.check("COMMANDS.md mentions -h/--help at least once (front matter note)",
              "-h" in text and "--help" in text)


@test
def test_no_documented_flag_is_fictional(ctx: Ctx):
    """Every `-x`/`--xxx`-shaped inline-code span inside a HEADING (this
    doc's own per-flag section marker) must be a real, existing flag --
    catches a typo'd flag name or a Claude Code flag this build never
    accepted at all. Prose elsewhere in the doc (worked examples, running
    text) is intentionally not scanned here -- only headings are load-
    bearing "this flag exists" claims."""
    text = doc_text("COMMANDS.md")
    real_all: "set[str]" = set()
    for flags in _gather_real_flags().values():
        real_all |= flags

    bogus: "list[str]" = []
    for heading in _HEADING_RE.findall(text):
        for flag in _HEADING_FLAG_RE.findall(heading):
            if flag not in real_all:
                bogus.append(f"{flag!r} in heading {heading!r}")
    ctx.check(f"no fictional flag in a COMMANDS.md heading; found: {bogus}", not bogus)


@test
def test_not_yet_flags_are_listed_honestly(ctx: Ctx):
    """The brief: '"not supported yet" flags listed honestly'. W4a moved
    every flag that used to be in `_NOT_YET_FLAGS` into either `_REAL_FLAGS`
    (21 of them, including `--worktree`) or `_NOT_APPLICABLE_FLAGS` (7,
    including `--ide`/`--teleport`) -- the table itself is now empty BY
    DESIGN (kept, never removed, for whatever a future Claude Code release
    adds that genuinely isn't built yet; see cli.py's own comment), so this
    test's OWN sanity checks moved with them rather than asserting on an
    empty set forever."""
    from halo_harness.cli import _NOT_APPLICABLE_FLAGS, _NOT_YET_FLAGS
    text = doc_text("COMMANDS.md").lower()
    ctx.check("cli._NOT_YET_FLAGS is empty by design after W4a", _NOT_YET_FLAGS == [])
    not_applicable_names = {flags[-1] for flags, _kw, _label, _reason in _NOT_APPLICABLE_FLAGS}
    for sample in ("--ide", "--teleport", "--safe-mode"):
        ctx.check(f"{sample!r} is in cli._NOT_APPLICABLE_FLAGS (sanity)", sample in not_applicable_names)
        ctx.check(f"COMMANDS.md mentions {sample!r}", sample in text)
    ctx.check("COMMANDS.md documents --worktree as a real flag (moved out of not-yet in W4a)",
              "-w`, `--worktree" in text or "--worktree [name]" in text or "--worktree [worktree]" in text)
    ctx.check("COMMANDS.md says 'not applicable' at least once (the W4a notice wording)",
              "not applicable" in text)


if __name__ == "__main__":
    ctx = Ctx()
    results, passed, failed, skipped = run_all(TESTS, ctx)
    sys.exit(print_results(results, passed, failed, skipped))
