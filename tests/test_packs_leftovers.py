"""tests.test_packs_leftovers -- Halo 3.6.0.0 R0a-finish (item 4): `halo pack remove` leaves no half pack behind.
A pack whose modules Python imported has `__pycache__/<module>.<tag>.pyc` beside them; remove deletes that bytecode
with the modules Halo wrote (the folder goes, `halo pack list` is clean), while a file of yours is kept and named and a
`__pycache__` holding anything else stays whole. A folder under the packs folder with no pack.yaml is not a pack:
`halo pack list` has no row for it and `halo pack doctor` names it once ("a leftover folder, not a pack"). Install
writes pack.yaml last, so a list read while it copies never sees a half-written pack "found in place".
A scratch home, the shipped doc-review pack as the source (its hooks/note.py and mcp/lint_server.py compiled the way
an import writes them: py_compile to importlib's cache path).
Run: python -m tests.test_packs_leftovers
"""

from __future__ import annotations

import json
import py_compile
import sys
from importlib.util import cache_from_source
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from tests.helpers.packs_home import PacksHome  # noqa: E402
from tests.helpers.runner import Ctx, new_registry, print_results, run_all  # noqa: E402

test, TESTS = new_registry()
MODULES = ("hooks/note.py", "mcp/lint_server.py")


def _compiled(root: Path) -> "list[Path]":
    """The bytecode an import of each module writes, where it writes it."""
    out = []
    for rel in MODULES:
        out.append(Path(py_compile.compile(str(root / rel), cfile=cache_from_source(str(root / rel)), doraise=True)))
    return out


def _rows(h) -> list:
    code, out, _err = h.cli("list", "--json")
    return json.loads(out).get("packs") if code == 0 and out.strip() else [{"error": code}]


@test
def test_remove_takes_the_bytecode_python_wrote(ctx: Ctx):
    with PacksHome() as h:
        h.install(h.source())
        root = h.packs / "doc-review"
        pyc = _compiled(root)
        ctx.check(f"the imports' bytecode is there, got {[p.relative_to(root).as_posix() for p in pyc]}",
                  all(p.is_file() and p.parent.name == "__pycache__" for p in pyc))
        code, out, err = h.cli("remove", "doc-review")
        ctx.check(f"remove exits 0 and says the folder is gone, got {code} {out!r} {err!r}",
                  code == 0 and "its folder is gone" in out and ".pyc" not in out and "Halo did not write it" not in out)
        ctx.check("the folder is gone", not root.exists())
        ctx.check(f"halo pack list is clean, got {_rows(h)}", _rows(h) == [])
        code, out, _err = h.cli("doctor")
        ctx.check(f"the doctor names no leftover, got {out!r}", "leftover" not in out)


@test
def test_a_file_of_yours_and_a_cache_with_more_stay(ctx: Ctx):
    with PacksHome() as h:
        h.install(h.source())
        root = h.packs / "doc-review"
        _compiled(root)
        (root / "my-notes.txt").write_text("mine\n", encoding="utf-8")
        mine = cache_from_source(str(root / "mcp" / "mine.py"))  # bytecode of a module Halo did not write
        Path(mine).write_bytes(b"\0")
        code, out, _err = h.cli("remove", "doc-review")
        ctx.check(f"your file is kept and named, got {out!r}", code == 0 and "kept my-notes.txt in " in out
                  and (root / "my-notes.txt").is_file())
        hooks_cache = Path(cache_from_source(str(root / "hooks" / "note.py"))).parent
        ctx.check("a cache of only the pack's bytecode goes", not hooks_cache.exists())
        ctx.check(f"a cache holding anything else stays whole, and is named, got {out!r}",
                  Path(mine).is_file() and len(list(Path(mine).parent.iterdir())) == 2 and Path(mine).name in out)
        ctx.check(f"what stays is not a pack: no row, got {_rows(h)}", _rows(h) == [])


@test
def test_a_folder_with_no_manifest_is_not_a_pack(ctx: Ctx):
    with PacksHome() as h:
        left = h.packs / "leftover"
        (left / "server").mkdir(parents=True)
        (left / "server" / "x.txt").write_text("x\n", encoding="utf-8")
        ctx.check(f"halo pack list has no row for it, got {_rows(h)}", _rows(h) == [])
        code, out, _err = h.cli("doctor")
        ctx.check(f"the doctor names it once, in plain words, got {code} {out!r}",
                  out.count(f"a leftover folder, not a pack: {left}") == 1)
        from halo_harness.packs.manager import payload
        ctx.check("Studio's Pack Manager lists no pack and no problem for it",
                  payload(cwd=h.repo)["packs"] == [] and not any("leftover" in p["text"] for p in payload(cwd=h.repo)["problems"]))


@test
def test_install_writes_its_manifest_last(ctx: Ctx):
    with PacksHome() as h:
        h.install(h.source())
        rows = [json.loads(ln) for ln in (h.packs / "journal.jsonl").read_text(encoding="utf-8").splitlines()]
        paths = [Path(r["path"]).name for r in rows if r.get("op") == "install"]
        ctx.check(f"pack.yaml is the last file the install wrote, got {paths[-3:]}", len(paths) > 3 and paths[-1] == "pack.yaml"
                  and paths.count("pack.yaml") == 1)


if __name__ == "__main__":
    ctx = Ctx()
    results, passed, failed, skipped = run_all(TESTS, ctx)
    sys.exit(print_results(results, passed, failed, skipped))
