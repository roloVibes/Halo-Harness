"""tests.test_printed_commands_resolve -- every `halo ...` command Halo's own code tells a person to run exists.

1. The walk: every string literal under halo_harness/ (docstrings and comments left out: nobody is shown those) is read
   for a command a person is sent to -- `halo <word>` inside backticks, in parentheses, or after "run", "then", "or",
   "with", "use" -- and each must resolve: a command cli_commands.py runs (not a retired one), the one sub-verb an
   internal command lets through (cli.py's `argv[:2] == [...]`), a shipped pack's own CLI verb (its pack.yaml), or
   a flag of `halo` itself that still does something (`--team` is accepted only to say lineups are gone). A line that
   starts with its own command's name as a label ("halo coach: ...") is not advice and is not read.
   Left out on purpose: the first-run pack, which still rehearses a 3.5 lineup (docs/MOVING-from-3.5.md, "Not yet
   moved").
2. Three lines a 3.6 user met that sent them nowhere: `halo pack new`'s last line (`halo --team pack-author`),
   `halo gym propose --apply`'s (`halo roles template load ...`, which loads nothing now), and `halo roles`' own line,
   which spoke of lineups to a person asking for the model table.

Run: python -m tests.test_printed_commands_resolve
"""
from __future__ import annotations

import ast
import contextlib
import io
import os
import re
import sys
import tempfile
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO))

from tests.helpers.runner import Ctx, new_registry, print_results, run_all  # noqa: E402

test, TESTS = new_registry()

#: a command named as advice: after a backtick, "(", or one of the words a sentence sends someone with
ADVICE = re.compile(r"(?:`|\(|\brun |\bthen |\bor |\bwith |\buse )halo ((?:--?)?[a-z][a-z0-9-]*)(?: ([a-z][a-z0-9-]*))?"
                    r"(?=[\s`)\].,;:'\"|]|$)")
#: flags `halo` still parses only to say they are gone (headless.py: "--team is gone (lineups are gone) ...")
GONE_FLAGS = {"--team"}
#: not yet moved to agents and maps (docs/MOVING-from-3.5.md, "Not yet moved"): it still names the 3.5 verbs
NOT_YET_MOVED = ("halo_harness/templates/packs/first-run/",)


def _pack_verbs() -> set:
    import yaml
    verbs = set()
    for manifest in (REPO / "halo_harness" / "templates" / "packs").glob("*/pack.yaml"):
        data = yaml.safe_load(manifest.read_text(encoding="utf-8")) or {}
        for row in ((data.get("contributes") or {}).get("cli") or []):
            if isinstance(row, dict) and row.get("verb"):
                verbs.add(str(row["verb"]))
    return verbs


def _internal_sub_verbs() -> dict:
    src = (REPO / "halo_harness" / "cli.py").read_text(encoding="utf-8")
    out: dict = {}
    for cmd, sub in re.findall(r'argv\[:2\] == \["([a-z-]+)", "([a-z-]+)"\]', src):
        out.setdefault(cmd, set()).add(sub)
    return out


def _top_flags() -> set:
    from halo_harness import cli
    parser = cli._build_parser()
    return {s for a in parser._actions for s in a.option_strings}


def _strings(path: Path):
    """(line, text) of every string literal of one module that is not a docstring."""
    tree = ast.parse(path.read_text(encoding="utf-8"))
    docs = set()
    for node in ast.walk(tree):
        if isinstance(node, (ast.Module, ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)) and node.body:
            first = node.body[0]
            if isinstance(first, ast.Expr) and isinstance(first.value, ast.Constant):
                docs.add(id(first.value))
    for node in ast.walk(tree):
        if isinstance(node, ast.Constant) and isinstance(node.value, str) and id(node) not in docs:
            yield node.lineno, node.value


def unresolved(text: str, *, pack_verbs: set, internal: dict, flags: set) -> list:
    """The commands `text` sends a person to that do not resolve, as 'halo <word>[ <sub>]: why'."""
    from halo_harness.cli_commands import BY_NAME
    bad = []
    for m in ADVICE.finditer(text):
        word, sub = m.group(1), m.group(2)
        if word.startswith("-"):
            if word in GONE_FLAGS:
                bad.append(f"halo {word}: accepted only to say it is gone")
            elif word not in flags:
                bad.append(f"halo {word}: no such flag")
            continue
        cmd = BY_NAME.get(word)
        if cmd is None:
            if word not in pack_verbs:
                bad.append(f"halo {word}: no such command")
        elif cmd.kind == "retired":
            bad.append(f"halo {word}: retired (it only says where to go)")
        elif cmd.kind == "internal" and sub not in internal.get(word, set()):
            bad.append(f"halo {word} {sub or ''}".rstrip() + f": only `halo {word} "
                       f"{'|'.join(sorted(internal.get(word, set())))}` is let through")
    return bad


@test
def test_the_walk_reads_what_it_should(ctx: Ctx):
    """The rule itself, on lines of the shapes it must catch and must leave alone."""
    kw = dict(pack_verbs={"coach", "start"}, internal={"roles": {"point"}}, flags={"--version", "-p", "--team"})
    cases = {
        "run `halo maps use <name>`": [],
        "(halo --team pack-author)": ["halo --team: accepted only to say it is gone"],
        "`halo roles template load x`": ["halo roles template: only `halo roles point` is let through"],
        "`halo roles point coder m`": [],
        "`halo sessions`/`/resume` lists them": ["halo sessions: no such command"],
        "then halo teams use <name>": ["halo teams: retired (it only says where to go)"],
        "halo coach: no runs here": [],  # its own label, not advice
        "`halo coach --undo`": [],
        "halo is starting in your terminal": [],  # prose
        "`halo --version` answered": [],
        "`halo --nope`": ["halo --nope: no such flag"],
    }
    for text, want in cases.items():
        got = unresolved(text, **kw)
        ctx.check(f"{text!r} -> {want}, got {got}", got == want)


@test
def test_every_command_halo_prints_resolves(ctx: Ctx):
    kw = dict(pack_verbs=_pack_verbs(), internal=_internal_sub_verbs(), flags=_top_flags())
    ctx.check(f"the shipped packs' verbs are read, got {sorted(kw['pack_verbs'])}",
              {"coach", "improve", "start"} <= kw["pack_verbs"])
    ctx.check(f"roles point is the internal sub-verb read from cli.py, got {kw['internal']}",
              "point" in kw["internal"].get("roles", set()))
    bad = []
    seen = 0
    for path in sorted((REPO / "halo_harness").rglob("*.py")):
        rel = path.relative_to(REPO).as_posix()
        if rel.startswith(NOT_YET_MOVED):
            continue
        for line, text in _strings(path):
            seen += 1
            bad += [f"{rel}:{line}: {why}  <- {text.strip()[:120]!r}" for why in unresolved(text, **kw)]
    ctx.check(f"the walk read the product's strings, got {seen}", seen > 10000)
    ctx.check("every `halo ...` a line sends a person to exists:\n  " + "\n  ".join(bad), not bad)


@test
def test_security_md_names_only_commands_that_exist_and_the_listeners_that_do(ctx: Ctx):
    """SECURITY.md is the page the README sends a person to for security. 3.6 audit: it still described the fleet
    hub (`halo fleet serve / kick / leave`, gone since 3.5.0.0; its link docs/FLEET.md is gone too) and said nothing
    of the listeners that exist: `halo host serve`, `halo host rpc`, `halo local serve --lan`."""
    kw = dict(pack_verbs=_pack_verbs(), internal=_internal_sub_verbs(), flags=_top_flags())
    for name in ("SECURITY.md", "README.md"):
        text = (REPO / name).read_text(encoding="utf-8")
        bad = unresolved(text, **kw)
        ctx.check(f"every `halo ...` {name} names exists, got {bad}", not bad)
        broken = [link for link in re.findall(r"\]\(([^)#\s]+)(?:#[^)]*)?\)", text)
                  if "://" not in link and not link.startswith("mailto:") and not (REPO / link).exists()]
        ctx.check(f"every relative link of {name} resolves, got {broken}", not broken)
    sec = (REPO / "SECURITY.md").read_text(encoding="utf-8")
    for must in ("halo host serve", "halo host pair", "halo host revoke", "halo host stop", "host.allow_control",
                 "--no-tls", "halo host rpc", "halo local serve", "--lan", "docs/HOST.md"):
        ctx.check(f"SECURITY.md names {must!r}", must in sec)
    ctx.check("SECURITY.md describes no fleet hub", "halo fleet" not in sec and "fleet hub" not in sec.lower())


def _home() -> str:
    home = tempfile.mkdtemp(prefix="halo-printed-commands-")
    os.environ["BRIDGE_TEST_HOME"] = home
    os.environ.setdefault("OLLAMA_HOST", "http://127.0.0.1:9")
    os.environ.setdefault("HALO_NO_UPDATER", "1")
    return home


@test
def test_pack_new_points_a_session_at_halo_pack_md_with_a_command_that_works(ctx: Ctx):
    from halo_harness.packs.scaffold import new
    out = Path(tempfile.mkdtemp(prefix="halo-pack-new-")) / "my-pack"
    ok, lines = new("my-pack", folder=out, github=False)
    ctx.check(f"the pack was made, got {lines[-3:]}", ok)
    text = "\n".join(lines)
    ctx.check(f"no line names --team, got {lines[-1]!r}", "--team" not in text)
    ctx.check(f"the last line says how a session follows HALO-PACK.md, got {lines[-1]!r}",
              "HALO-PACK.md" in lines[-1] and "`halo`" in lines[-1])


@test
def test_gym_propose_apply_writes_the_role_table_and_names_what_shows_it(ctx: Ctx):
    _home()
    from halo_harness import gym_cli
    from halo_harness.theme import get_config_value
    import halo_harness.gym as G
    import halo_harness.gym_propose as GP
    keep = (G.iter_results, GP.propose_role_table)
    G.iter_results = lambda state_dir: [{"model": "or:x/y"}]
    GP.propose_role_table = lambda results, **kw: ({"coder": "or:x/y"}, ["coder: or:x/y scored best"])
    buf = io.StringIO()
    try:
        with contextlib.redirect_stdout(buf), contextlib.redirect_stderr(buf):
            rc = gym_cli.cmd_gym(["propose", "--apply", "--name", "gym-test"])
    finally:
        G.iter_results, GP.propose_role_table = keep
    said = buf.getvalue()
    ctx.check(f"exit 0, got {rc}: {said!r}", rc == 0)
    ctx.check(f"the proposal is the role table now, got {get_config_value('roles.coder', None)!r}",
              get_config_value("roles.coder", None) == "or:x/y")
    ctx.check(f"it names `halo config get roles`, not a verb that loads nothing, got {said!r}",
              "halo config get roles" in said and "roles template load" not in said)
    kw = dict(pack_verbs=_pack_verbs(), internal=_internal_sub_verbs(), flags=_top_flags())
    ctx.check(f"what it printed resolves, got {unresolved(said, **kw)}", not unresolved(said, **kw))
    helptext = io.StringIO()
    with contextlib.redirect_stdout(helptext), contextlib.redirect_stderr(helptext):
        try:
            gym_cli.cmd_gym(["propose", "--help"])
        except SystemExit:
            pass
    ctx.check(f"--apply's help says what it does, got {helptext.getvalue()!r}",
              "roles template load" not in helptext.getvalue() and "role table" in helptext.getvalue())


@test
def test_halo_roles_names_the_model_table_and_one_model_for_everything(ctx: Ctx):
    from halo_harness.cli import GONE_VERBS
    line = GONE_VERBS["roles"]
    for want in ("halo config get roles", "halo roles point", "halo maps use --none"):
        ctx.check(f"`halo roles` names {want!r}, got {line!r}", want in line)


if __name__ == "__main__":
    ctx = Ctx()
    results, passed, failed, skipped = run_all(TESTS, ctx)
    sys.exit(print_results(results, passed, failed, skipped))
