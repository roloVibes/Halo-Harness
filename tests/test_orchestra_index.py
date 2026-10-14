"""tests.test_orchestra_index -- Halo 3.0.3.0 round R1: the claimable units of
a file (orchestra/index.py): Python functions, classes, methods, nested defs
and decorators; Markdown headings (fences skipped, units never share a
line); the regex pass for other languages; the whole-file fallback;
unit_for_line; and the overlaps matrix.
"""
from __future__ import annotations

import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from tests.helpers.provider_env_defaults import ensure_scoped_state_dir_once
from tests.helpers.runner import Ctx, new_registry, print_results, run_all

ensure_scoped_state_dir_once()
test, TESTS = new_registry()

PY = '''"""basket"""
import os

TAX = 0.2


def add_item(basket, item):
    basket.append(item)


@decorated
def remove_item(basket, item):
    def inner():
        return item
    basket.remove(inner())


class Basket:
    def total(self):
        return 0

    async def refresh(self):
        pass
'''

MD = """intro line
# Basket
text
## Install
```sh
# not a heading
```
## Use it!
last
"""

JS = """const x = 1;
export async function addItem(basket, item) {
  basket.push(item);
}

function total(basket) {
  return 0;
}
"""


def _write(name: str, text: str):
    root = Path(tempfile.mkdtemp(prefix="orch-index-"))
    path = root / name
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
    return root, path


@test
def test_python_functions_classes_methods_and_nested(ctx: Ctx):
    from halo_harness.orchestra.index import index_file
    root, path = _write("src/basket.py", PY)
    units = index_file(path, root=root)
    keys = [u.key for u in units]
    ctx.check(f"keys, got {keys}", keys == [
        "src/basket.py", "src/basket.py#add_item", "src/basket.py#remove_item",
        "src/basket.py#remove_item.inner", "src/basket.py#Basket", "src/basket.py#Basket.total",
        "src/basket.py#Basket.refresh"])
    by = {u.key: u for u in units}
    ctx.check("the whole file spans every line", (by["src/basket.py"].start_line, by["src/basket.py"].end_line) == (1, 23))
    ctx.check("a decorated def starts at its decorator", by["src/basket.py#remove_item"].start_line == 11)
    ctx.check("kinds", by["src/basket.py#Basket"].kind == "class" and by["src/basket.py#add_item"].kind == "function")
    ctx.check("end lines come from ast", by["src/basket.py#add_item"].end_line == 8
              and by["src/basket.py#Basket.refresh"].end_line == 23)


@test
def test_unit_for_line_picks_the_innermost(ctx: Ctx):
    from halo_harness.orchestra.index import index_file, unit_for_line, units_for_lines
    root, path = _write("basket.py", PY)
    units = index_file(path, root=root)
    ctx.check("module-level line -> whole file", unit_for_line(units, 4).key == "basket.py")
    ctx.check("inside add_item", unit_for_line(units, 8).key == "basket.py#add_item")
    ctx.check("inside the nested def", unit_for_line(units, 14).key == "basket.py#remove_item.inner")
    ctx.check("the outer def's own line", unit_for_line(units, 15).key == "basket.py#remove_item")
    ctx.check("a method", unit_for_line(units, 19).key == "basket.py#Basket.total")
    ctx.check("units_for_lines dedupes in order",
              [u.key for u in units_for_lines(units, [8, 8, 19, 4])] == ["basket.py#add_item", "basket.py#Basket.total", "basket.py"])
    ctx.check("an empty list gives None", unit_for_line([], 3) is None)


@test
def test_markdown_headings_skip_fences_and_never_share_lines(ctx: Ctx):
    from halo_harness.orchestra.index import index_file
    root, path = _write("README.md", MD)
    units = index_file(path, root=root)
    got = [(u.key, u.start_line, u.end_line) for u in units]
    ctx.check(f"heading units, got {got}", got == [
        ("README.md", 1, 9), ("README.md#basket", 2, 3), ("README.md#install", 4, 7), ("README.md#use-it", 8, 9)])


@test
def test_regex_pass_for_other_languages_and_whole_file_fallback(ctx: Ctx):
    from halo_harness.orchestra.index import index_file, index_text
    root, path = _write("web/basket.js", JS)
    keys = [(u.key, u.start_line, u.end_line) for u in index_file(path, root=root)]
    ctx.check(f"js functions, got {keys}", keys == [
        ("web/basket.js", 1, 8), ("web/basket.js#addItem", 2, 4), ("web/basket.js#total", 6, 8)])
    go = index_text("package x\nfunc (b *Basket) Total() int {\n}\nfunc add(a int) {\n}\n", "b.go")
    ctx.check("go methods and funcs", [u.name for u in go] == ["", "Total", "add"])
    rs = index_text("pub fn total(b: &B) -> u32 {\n}\nfn helper<T>(t: T) {}\n", "b.rs")
    ctx.check("rust pub fn and generics", [u.name for u in rs] == ["", "total", "helper"])
    txt = index_text("just words\nno functions\n", "notes.txt")
    ctx.check("no match -> whole file only", [u.key for u in txt] == ["notes.txt"])
    broken = index_text("def ok(:\n    pass\ndef fine(x):\n    return x\n", "broken.py")
    ctx.check("a Python syntax error falls back to the regex pass", [u.name for u in broken] == ["", "ok", "fine"])
    dup = index_text("def a():\n    pass\ndef a():\n    def b():\n        pass\n", "d.py")
    ctx.check(f"repeated names get ~2, got {[u.key for u in dup]}",
              [u.key for u in dup] == ["d.py", "d.py#a", "d.py#a~2", "d.py#a~2.b"])
    missing = index_file(root / "nope.py", root=root)
    ctx.check("a missing file is one whole-file unit", [u.key for u in missing] == ["nope.py"])


@test
def test_overlaps_matrix(ctx: Ctx):
    from halo_harness.orchestra.index import covers, overlaps
    cases = [
        ("b.py", "b.py#total", True), ("b.py#total", "b.py", True), ("b.py", "b.py", True),
        ("b.py#total", "b.py#total", True), ("b.py#Basket", "b.py#Basket.total", True),
        ("b.py#Basket.total", "b.py#Basket", True), ("b.py#Basket.total", "b.py#Basket.refresh", False),
        ("b.py#total", "b.py#totals", False), ("b.py#add", "b.py#remove", False),
        ("b.py", "c.py", False), ("b.py#total", "c.py#total", False),
        ("README.md#install", "README.md#use-it", False), ("README.md", "README.md#install", True),
    ]
    for a, b, want in cases:
        ctx.check(f"overlaps({a!r}, {b!r}) == {want}", overlaps(a, b) is want)
    ctx.check("covers is one-way", covers("b.py#Basket", "b.py#Basket.total")
              and not covers("b.py#Basket.total", "b.py#Basket"))


if __name__ == "__main__":
    ctx = Ctx()
    results, passed, failed, skipped = run_all(TESTS, ctx)
    sys.exit(print_results(results, passed, failed, skipped))
