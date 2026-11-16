"""tests.test_docs_say_what_3600_does -- the help and the pages a 3.5 user reads say what 3.6.0.0 does.

1. `halo init --no-launch` does not return while it serves the Setup it started (3.6.0.0 R10: no detached Studio --
   setup_door.cli_door holds it, launch.HOLD_LINE): its help, `halo init`'s description, COMMANDS-init.md and
   WIZARD.md say so; Ctrl+C at init's wait prints init_wait.INTERRUPTED_LINE, and COMMANDS-init.md quotes that line;
   no page says a Studio started by `halo init` outlives it; `halo studio --stop`'s help does not speak of a Studio in
   the background that the wizard's buttons start; TROUBLESHOOTING.md has the page's "Studio has stopped".
2. The pack guide does not send a session to `halo --team pack-author` (no lineup is read; no pack-author map ships).
3. No page offers `halo roles template ...` or `halo roles on|off` as working (only `halo roles point` is let through).
4. MOVING-from-3.5.md also names the other changes a 3.5 user meets: Studio closing with its command, the steward's
   job off, `halo --version`'s one line, the sweep at start and `halo ps` / `halo stop`, the updater, and what
   replaced `halo roles` / `roles on|off` / `roles template`.

Run: python -m tests.test_docs_say_what_3600_does
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO))

from tests.helpers.runner import Ctx, new_registry, print_results, run_all  # noqa: E402

test, TESTS = new_registry()
DOCS = REPO / "docs"


def _flat(text: str) -> str:
    return " ".join(text.split())


def _doc(name: str) -> str:
    return _flat((DOCS / name).read_text(encoding="utf-8"))


def _reader_docs() -> dict:
    """README, SECURITY and docs/*.md (not docs/harness: the build notes of past rounds), flattened."""
    out = {p.name: _flat(p.read_text(encoding="utf-8")) for p in sorted(DOCS.glob("*.md"))}
    for name in ("README.md", "SECURITY.md"):
        out[name] = _flat((REPO / name).read_text(encoding="utf-8"))
    return out


@test
def test_no_launch_says_it_serves_setup_here(ctx: Ctx):
    from halo_harness.init_cli import _build_parser
    parser = _build_parser()
    action = next(a for a in parser._actions if "--no-launch" in a.option_strings)
    ctx.check(f"--no-launch's help does not promise to return at once, got {action.help!r}",
              "return at once" not in action.help and "Ctrl+C" in action.help)
    ctx.check(f"halo init's description does not either, got {parser.description!r}",
              "returns at once" not in parser.description)
    for name in ("COMMANDS-init.md", "WIZARD.md"):
        text = _doc(name)
        said = [m.group(0) for m in re.finditer(r".{0,80}(?:return|returns) at once.{0,40}", text)
                if "no-launch" in m.group(0) or "for scripts" in m.group(0)]
        ctx.check(f"{name}: no line says --no-launch returns at once, got {said}", not said)


@test
def test_ctrl_c_line_is_the_one_init_prints(ctx: Ctx):
    from halo_harness.init_wait import INTERRUPTED_LINE
    text = _doc("COMMANDS-init.md")
    ctx.check(f"COMMANDS-init.md quotes init's Ctrl+C line {INTERRUPTED_LINE!r}", _flat(INTERRUPTED_LINE) in text)
    ctx.check("and not the 3.5 one", "Setup stays open in the browser" not in text)


@test
def test_no_page_says_a_studio_outlives_the_command_that_started_it(ctx: Ctx):
    stale = {
        "STUDIO.md": ("start it detached, so it outlives them", "stop the Studio running in the background"),
        "WIZARD.md": ("keeps running after setup until `halo studio --stop`",),
        "COMMANDS-studio.md": ("ends a Studio running in the background (the wizard's Open Studio buttons start one, "
                               "detached)",),
    }
    for name, phrases in stale.items():
        text = _doc(name)
        for phrase in phrases:
            ctx.check(f"{name} no longer says {phrase!r}", phrase not in text)
    ctx.check("STUDIO.md points at PROCESSES.md for who owns a Studio", "PROCESSES.md" in _doc("STUDIO.md"))


@test
def test_studio_stop_help_is_the_r10_rule(ctx: Ctx):
    src = (REPO / "halo_harness" / "studio" / "server.py").read_text(encoding="utf-8")
    m = re.search(r'add_argument\("--stop".*?help="([^"]*)"', src)
    ctx.check(f"halo studio --stop has its help, got {m and m.group(1)!r}", m is not None)
    ctx.check(f"--stop's help speaks of no Studio in the background that the wizard starts, got {m and m.group(1)!r}",
              m is not None and "in the background" not in m.group(1) and "wizard" not in m.group(1))


@test
def test_processes_says_what_halo_cannot_end_on_macos(ctx: Ctx):
    """jb10 batch 3: a program a tool command detaches from Halo's process group that is also an Apple system binary
    (`ssh -fN`) is found by nothing on macOS (`ps -E` hides its environment): the page says so and what to do."""
    text = (DOCS / "PROCESSES.md").read_text(encoding="utf-8")
    m = re.search(r"^## What Halo cannot end on macOS\n(.*?)(?=^## |\Z)", text, re.MULTILINE | re.DOTALL)
    ctx.check("a section 'What Halo cannot end on macOS'", m is not None)
    body = m.group(1) if m else ""
    for need in ("ssh -fN", "ps -E", "HALO_OWNER=kept-", "halo ps", "setsid"):
        ctx.check(f"it names {need!r}", need in body)


@test
def test_troubleshooting_has_studio_has_stopped(ctx: Ctx):
    text = (DOCS / "TROUBLESHOOTING.md").read_text(encoding="utf-8")
    ctx.check("a heading names the page's \"Studio has stopped\"",
              re.search(r"^## .*Studio has stopped", text, re.MULTILINE) is not None)
    ctx.check("it points at PROCESSES.md", "PROCESSES.md" in text)


@test
def test_no_page_sends_a_session_to_team_pack_author(ctx: Ctx):
    bad = [name for name, text in _reader_docs().items() if "--team pack-author" in text or "--team <id>--crew" in text]
    ctx.check(f"no page names `halo --team pack-author` or `--team <id>--crew`, got {bad}", not bad)
    ctx.check("PACK-AUTHORING.md says how a session follows HALO-PACK.md",
              "ask it to follow `HALO-PACK.md`" in _doc("PACK-AUTHORING.md"))
    glossaries = [REPO / "halo_harness" / "templates" / "glossary" / "GLOSSARY.md", DOCS / "GLOSSARY.md"]
    bad = [p.name for p in glossaries if "The `pack-author` lineup is the session" in p.read_text(encoding="utf-8")]
    ctx.check(f"the glossaries name no pack-author lineup, got {bad}", not bad)


@test
def test_no_page_offers_roles_template_or_roles_on_off(ctx: Ctx):
    gone = re.compile(r"`halo roles (?:template|on\b|off\b|on\|off)[^`]*`")
    bad = []
    for name, text in _reader_docs().items():
        for m in gone.finditer(text):
            around = text[max(0, m.start() - 160): m.end() + 160]
            if name == "MOVING-from-3.5.md" or re.search(r"\bgone\b|\bwent\b|3\.5|no longer", around):
                continue  # a page saying it went is right
            bad.append(f"{name}: ...{text[max(0, m.start() - 60): m.end() + 40]}...")
    ctx.check("no page offers `halo roles template ...` / `halo roles on|off` as working:\n  " + "\n  ".join(bad), not bad)


@test
def test_moving_from_35_names_the_other_changes(ctx: Ctx):
    text = _doc("MOVING-from-3.5.md")
    for word, why in (("Studio has stopped", "Studio closes with the command that started it"),
                      ("PROCESSES.md", "where that rule lives"),
                      ("ollama.steward.job", "the steward's background job is off"),
                      ("halo --version", "the one line"),
                      ("halo ps", "seeing what runs"),
                      ("halo stop", "stopping it"),
                      ("halo config get roles", "the model table"),
                      ("halo maps use --none", "one model for everything, what `halo roles off` was"),
                      ("halo roles template", "named as gone"),
                      ("halo gym propose --apply", "what replaced loading a template")):
        ctx.check(f"MOVING-from-3.5.md names {word!r} ({why})", word in text)
    readme = _flat((REPO / "README.md").read_text(encoding="utf-8"))
    m = re.search(r"\[([^\]]*)\]\(docs/MOVING-from-3\.5\.md\)", readme)
    ctx.check(f"the README's link does not promise only lineups, bios and blocks, got {m and m.group(1)!r}",
              m is not None and "Studio" in m.group(1))


#: the pages a 3.6 user reads first (3.6.0.1 setup-words): they teach agents, workflows and maps
FIRST_PAGES = ("README.md", "WIZARD.md", "PACKS.md", "ISOLATION.md", "MODELS-ollama-steward-sched.md")
OLD_WORD = re.compile(r"(?i)\blineups?\b|\bbios?\b")
SAYS_OLD = re.compile(r"(?i)\bgone\b|\b3\.5\b|no longer|\b1\.x\b|MOVING-from-3\.5")


@test
def test_first_pages_teach_agents_workflows_maps(ctx: Ctx):
    """3.6.0.1 setup-words: docs/README.md, WIZARD.md, PACKS.md, ISOLATION.md and MODELS-ollama-steward-sched.md still
    taught lineups and bios as the way Halo works; 3.6.0.0 reads neither. A line may name the old words only as old:
    the line itself says so, or its section does (its heading, or a `>` note among the section's first two lines: a
    section about the 3.5 files or a 1.x pack)."""
    left = []
    for name in FIRST_PAGES:
        old, probe, code = False, 0, False
        for n, line in enumerate((DOCS / name).read_text(encoding="utf-8").splitlines(), 1):
            if line.startswith("```"):
                code = not code
            elif line.startswith("#") and not code:
                old, probe = bool(SAYS_OLD.search(line)), 2
                continue
            elif line.strip() and probe:
                probe -= 1
                old = old or (line.startswith(">") and bool(SAYS_OLD.search(line)))
            if OLD_WORD.search(line) and not SAYS_OLD.search(line) and not old:
                left.append(f"{name}:{n}: {line.strip()[:110]}")
    ctx.check(f"the first pages speak of lineups and bios only as old ({len(left)}):\n  " + "\n  ".join(left), not left)


if __name__ == "__main__":
    ctx = Ctx()
    results, passed, failed, skipped = run_all(TESTS, ctx)
    sys.exit(print_results(results, passed, failed, skipped))
