"""tests.test_packs_update_cli -- `halo pack update` asks before the swap in a
terminal (Halo 3.2.1.0 R4, halo_harness/packs/cli.py `_update`,
packs/update.py `confirm` and `file_lines`): with a terminal on both ends it
prints the dry run's lines (the migration notes, the files that change, the
settings it renames) and asks "Apply? [y/N]"; "y" swaps and prints the rest
once, "n", Enter or end of input print "<id> <version> stays as it is" and
exit 1 with nothing touched; `--yes`, `--json`, `--dry-run`, a pipe and an
up-to-date pack ask nothing (as before). The dry run (and so Studio's Update
confirm) lists the files that change.

A TTY stub stands in for the terminal: a StringIO whose isatty() is True, as
stdin (holding the answer) and stdout. Nothing reaches the real home
(PacksHome scopes BRIDGE_TEST_HOME); no model is called.
"""

from __future__ import annotations

import contextlib
import io
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from tests.helpers.packs_home import PacksHome  # noqa: E402
from tests.helpers.runner import Ctx, new_registry, print_results, run_all  # noqa: E402

test, TESTS = new_registry()
NOTE = "  - {from: 1.0.0, to: 1.1.0, note: the reviewer now reads README files too}\n"
ASK = "Apply? [y/N] "


class _Tty(io.StringIO):
    def isatty(self) -> bool:
        return True


def _run(h, answer, *argv, tty: bool = True) -> "tuple[int, str, str]":
    """`halo pack update doc-review <argv>` with `answer` on stdin; `tty`: both ends a terminal."""
    from halo_harness.packs.cli import cmd_pack
    out, err = (_Tty() if tty else io.StringIO()), io.StringIO()
    old = sys.stdin
    sys.stdin = _Tty(answer) if tty else io.StringIO(answer)
    try:
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
            code = cmd_pack(["update", "doc-review", *argv, "--cwd", str(h.repo)])
    finally:
        sys.stdin = old
    return code, out.getvalue(), err.getvalue()


def _bumped(h) -> Path:
    """doc-review installed (enabled) from a source that then holds 1.1.0: pack.yaml and README.md changed, one new file."""
    src = h.source()
    h.install(src, enable=True, grants=["hooks"])
    text = (src / "pack.yaml").read_text(encoding="utf-8").replace("version: 1.0.0", "version: 1.1.0")
    (src / "pack.yaml").write_text(text + NOTE, encoding="utf-8")  # the shipped pack.yaml ends in its `migrations:` list
    (src / "README.md").write_text((src / "README.md").read_text(encoding="utf-8") + "\nMore.\n", encoding="utf-8")
    (src / "CHANGES.md").write_text("# Changes\n\n1.1.0: README files too.\n", encoding="utf-8")
    return src


def _tree(root: Path) -> dict:
    return {p.relative_to(root).as_posix(): p.read_bytes() for p in sorted(root.rglob("*")) if p.is_file()}


def _version(h) -> str:
    return json.loads((h.packs / "state.json").read_text(encoding="utf-8"))["installed"]["doc-review"]["version"]


@test
def test_a_terminal_run_asks_and_y_swaps(ctx: Ctx):
    with PacksHome() as h:
        _bumped(h)
        code, out, err = _run(h, "y\n")
        look, _, after = out.partition(ASK)
        lines = look.splitlines()
        ctx.check(f"exit 0, got {code} {err}", code == 0 and not err)
        ctx.check(f"the note first, got {lines[:1]}", lines[:1] == ["doc-review 1.0.0 -> 1.1.0: the reviewer now reads README files too"])
        ctx.check(f"then what it would do, got {lines[1:2]}", lines[1].startswith("would update doc-review 1.0.0 -> 1.1.0 (3 file(s) changed; "))
        ctx.check(f"the files that change, one line each, got {lines[2:]}",
                  lines[2:5] == ["  CHANGES.md (new)", "  README.md (changed)", "  pack.yaml (changed)"])
        ctx.check(f"the question once, after the look, got {out.count(ASK)}", out.count(ASK) == 1 and ASK in out)
        rest = after.splitlines()
        ctx.check(f"then the swap's own line, got {rest[:1]}", rest[:1] and rest[0].startswith("updated doc-review 1.0.0 -> 1.1.0 (3 file(s) changed)"))
        ctx.check("the note is not printed twice", out.count("the reviewer now reads README files too") == 1)
        ctx.check("1.1.0 is in place, 1.0.0 kept as doc-review.previous",
                  _version(h) == "1.1.0" and (h.packs / "doc-review.previous" / "pack.yaml").is_file()
                  and (h.packs / "doc-review" / "CHANGES.md").is_file())


@test
def test_n_enter_or_end_of_input_leave_it_as_it_is(ctx: Ctx):
    for answer in ("n\n", "\n", "no\n", ""):
        with PacksHome() as h:
            _bumped(h)
            root = h.packs / "doc-review"
            before, journal = _tree(root), (h.packs / "journal.jsonl").read_bytes()
            code, out, err = _run(h, answer)
            ctx.check(f"{answer!r}: asked, exit 1, the one line, got {code} {err!r}", code == 1 and ASK in out
                      and err.strip() == "halo pack: doc-review 1.0.0 stays as it is")
            ctx.check(f"{answer!r}: nothing touched (files, journal, version, no .previous, no staging folder)",
                      _tree(root) == before and (h.packs / "journal.jsonl").read_bytes() == journal and _version(h) == "1.0.0"
                      and sorted(p.name for p in h.packs.iterdir()) == ["doc-review", "journal.jsonl", "state.json"])


@test
def test_yes_json_dry_run_and_a_pipe_ask_nothing(ctx: Ctx):
    with PacksHome() as h:
        _bumped(h)
        code, out, _ = _run(h, "n\n", "--dry-run")
        lines = out.splitlines()
        ctx.check(f"--dry-run in a terminal: no question, the files listed, got {code} {lines}", code == 0 and ASK not in out
                  and "  README.md (changed)" in lines and lines[-1].startswith("dry run: nothing is changed") and _version(h) == "1.0.0")
        code, out, _ = _run(h, "n\n", "--json")
        data = json.loads(out)
        ctx.check(f"--json in a terminal: no question, it updates, got {code} {data.get('lines', [])[:2]}", code == 0 and data["ok"]
                  and data["lines"][1].startswith("updated doc-review 1.0.0 -> 1.1.0") and _version(h) == "1.1.0")
    with PacksHome() as h:
        _bumped(h)
        code, out, _ = _run(h, "n\n", "--yes")
        lines = out.splitlines()
        ctx.check(f"--yes in a terminal: no question, the note then the swap, got {code} {lines[:2]}", code == 0 and ASK not in out
                  and lines[1].startswith("updated doc-review 1.0.0 -> 1.1.0") and _version(h) == "1.1.0")
        code, out, _ = _run(h, "n\n")
        ctx.check(f"up to date in a terminal: no question, got {code} {out.splitlines()[:1]}",
                  code == 0 and ASK not in out and out.startswith("doc-review 1.1.0 is up to date"))
    with PacksHome() as h:
        _bumped(h)
        code, out, _ = _run(h, "n\n", tty=False)
        ctx.check(f"a pipe (no terminal): no question, it updates as before, got {code} {out.splitlines()[:2]}",
                  code == 0 and ASK not in out and out.splitlines()[1].startswith("updated doc-review") and _version(h) == "1.1.0")


@test
def test_the_file_lines_and_the_help(ctx: Ctx):
    from halo_harness.packs.cli import USAGE, cmd_pack
    from halo_harness.packs.update import file_lines
    root = Path("packs") / "p"
    rows = [(root / "b.md", "1", None), (root / "a" / "x.py", None, "2"), (root / "c.yaml", "1", "2")]
    ctx.check(f"changed, new and dropped, sorted, got {file_lines(root, rows)}",
              file_lines(root, rows) == ["  a/x.py (new)", "  b.md (dropped)", "  c.yaml (changed)"])
    many = [(root / f"f{i:02}.md", "1", "2") for i in range(25)]
    got = file_lines(root, many)
    ctx.check(f"twenty, then how many more, got {got[-2:]}", len(got) == 21 and got[-1] == "  ... and 5 more file(s)")
    out = io.StringIO()
    with contextlib.redirect_stdout(out), contextlib.redirect_stderr(io.StringIO()):
        rc = cmd_pack(["update", "--help"])
    ctx.check("--yes is in halo pack update --help", rc == 0 and "--yes" in out.getvalue())
    ctx.check("and in the usage, with the question", "halo pack update <id> [--dry-run] [--yes] [--json]" in USAGE
              and '"Apply? [y/N]"' in USAGE)


if __name__ == "__main__":
    ctx = Ctx()
    results, passed, failed, skipped = run_all(TESTS, ctx)
    sys.exit(print_results(results, passed, failed, skipped))
