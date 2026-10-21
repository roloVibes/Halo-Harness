"""tests.test_ext_api -- the extension API a pack imports (Halo 3.2.0.0 R1,
halo_harness/ext/): API_VERSION 1.0; `__all__` is exactly the surface
docs/EXTENSION_API.md lists, every name importable; each contract does what
the doc says (the YAML reader and writer, the shape check, the pack's own
settings, private files in the pack's data folder and the home-write grant,
the feed frame, is_granted, Unit, the name rules); no ext module is named for
a version; and an AST walk (invariant c's shape) proves every fixture pack's
Python imports `halo_harness.ext` and nothing else of Halo.
"""

from __future__ import annotations

import ast
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from tests.helpers.packs_home import FIXTURES, PacksHome  # noqa: E402
from tests.helpers.runner import Ctx, new_registry, print_results, run_all  # noqa: E402

test, TESTS = new_registry()
REPO = Path(__file__).resolve().parent.parent
SURFACE = ("API_VERSION", "HALO_API_VERSION", "read_yaml", "write_yaml", "check_schema", "get_config", "set_config",
           "write_private", "pack_dir", "data_dir", "publish_event", "is_granted", "Unit", "is_valid_pack_id",
           "is_valid_name", "qualified_name", "split_name")


@test
def test_the_version_and_the_surface(ctx: Ctx):
    import halo_harness.ext as ext
    ctx.check("API_VERSION is 1.0, HALO_API_VERSION its alias", ext.API_VERSION == "1.0" and ext.HALO_API_VERSION == ext.API_VERSION)
    ctx.check(f"__all__ is the surface, got {ext.__all__}", tuple(ext.__all__) == SURFACE)
    ctx.check("every name is importable", all(hasattr(ext, name) for name in SURFACE))
    doc = (REPO / "docs" / "EXTENSION_API.md").read_text(encoding="utf-8")
    missing = [name for name in SURFACE if f"`{name}" not in doc]
    ctx.check(f"docs/EXTENSION_API.md names every one; missing {missing}", not missing)
    ctx.check("the doc states the version", "API_VERSION = \"1.0\"" in doc or "`1.0`" in doc)
    bad = [p.name for p in (REPO / "halo_harness" / "ext").glob("*.py") if any(ch.isdigit() for ch in p.stem)]
    ctx.check(f"no ext module is named for a version, got {bad}", not bad)
    from halo_harness.work.unit import Unit
    ctx.check("Unit is the unit of work", ext.Unit is Unit)


@test
def test_the_contracts_do_what_the_doc_says(ctx: Ctx):
    import halo_harness.ext as ext
    with PacksHome() as h:
        h.install(h.source(), enable=True)
        ctx.check("pack_dir: the installed folder", ext.pack_dir("doc-review", cwd=h.repo) == h.packs / "doc-review")
        data = ext.data_dir("doc-review")
        ctx.check("data_dir: ~/.halo/packs/.data/<id>", data == h.packs / ".data" / "doc-review")
        ctx.check("write_private: [] and a file in the data folder", ext.write_private("doc-review", "a/b.txt", "hi") == []
                  and (data / "a" / "b.txt").read_text(encoding="utf-8") == "hi")
        ctx.check("write_yaml / read_yaml round trip", ext.write_yaml("doc-review", "r.yaml", {"ok": True}) == []
                  and ext.read_yaml(data / "r.yaml") == {"ok": True})
        outside = h.home / "elsewhere.txt"
        lines = ext.write_private("doc-review", str(outside), "x")
        ctx.check(f"outside the data folder without home-write: one line, nothing written, got {lines}",
                  len(lines) == 1 and "home-write" in lines[0] and not outside.exists())
        ctx.check("a relative path never climbs out", "climb" in ext.write_private("doc-review", "../x", "x")[0])
        ctx.check("get_config: the defaults", ext.get_config("doc-review") == {"style": "short", "max_findings": 20})
        ctx.check("set_config: a value outside the schema is one line, not written",
                  len(ext.set_config("doc-review", "style", "loud")) == 1 and ext.get_config("doc-review", "style") == "short")
        ctx.check("set_config: an unknown key is one line", any("unknown key" in ln for ln in ext.set_config("doc-review", "colour", 1)))
        ctx.check("set_config: a good value is written under packs.settings.<id>", ext.set_config("doc-review", "style", "long") == []
                  and ext.get_config("doc-review", "style") == "long" and ext.get_config("doc-review", "max_findings") == 20)
        ctx.check("check_schema answers findings", ext.check_schema({"a": 1}, {"type": "object", "properties": {},
                                                                            "additionalProperties": False})[0]["check"] == "unknown-key")
        ctx.check("is_granted: nothing granted yet", not ext.is_granted("doc-review", "hooks"))
        frames = []

        class Bridge:
            def publish_local(self, frame):
                frames.append(frame)
        ctx.check("publish_event: True with a bridge", ext.publish_event("doc-review", "review.done", {"n": 1}, bridge=Bridge()))
        f = frames[0]
        ctx.check(f"the frame is tagged with the pack, got {f}", f["event"] == "pack_event" and f["pack"] == "doc-review"
                  and f["session_id"] == "pack:doc-review" and f["data"] == {"pack": "doc-review", "kind": "review.done", "data": {"n": 1}})
        ctx.check("publish_event: False when this process serves no Studio", ext.publish_event("doc-review", "review.done") is False)
        for bad in (("Doc", "x"), ("doc-review", "Bad Kind")):
            try:
                ext.publish_event(*bad, bridge=Bridge())
                raised = False
            except ValueError:
                raised = True
            ctx.check(f"publish_event{bad} raises ValueError", raised)
        ctx.check("the name rules", ext.is_valid_pack_id("doc-review") and not ext.is_valid_pack_id("doc--review")
                  and ext.qualified_name("doc-review", "writer") == "doc-review--writer"
                  and ext.split_name("doc-review--writer") == ("doc-review", "writer") and ext.split_name("writer") == (None, "writer")
                  and ext.is_valid_name("doc-review--writer"))


def _halo_imports(path: Path) -> "list[tuple[int, str]]":
    out = []
    for node in ast.walk(ast.parse(path.read_text(encoding="utf-8"), filename=str(path))):
        if isinstance(node, ast.Import):
            out += [(node.lineno, a.name) for a in node.names if a.name.split(".")[0] == "halo_harness"]
        elif isinstance(node, ast.ImportFrom) and node.module and node.module.split(".")[0] == "halo_harness":
            out.append((node.lineno, node.module))
    return out


@test
def test_fixture_packs_import_only_the_extension_api(ctx: Ctx):
    files = sorted(FIXTURES.rglob("*.py"))
    ctx.check(f"the fixture packs hold Python ({len(files)} file(s))", len(files) >= 2)
    problems, used = [], 0
    for path in files:
        for line, module in _halo_imports(path):
            used += 1
            if module != "halo_harness.ext":
                problems.append(f"{path.relative_to(REPO).as_posix()}:{line}: imports {module}")
    ctx.check("the fixtures do import the API", used >= 2)
    ctx.check("only halo_harness.ext:\n  " + "\n  ".join(problems), not problems)


if __name__ == "__main__":
    ctx = Ctx()
    results, passed, failed, skipped = run_all(TESTS, ctx)
    sys.exit(print_results(results, passed, failed, skipped))
