"""tests.test_packs_failures -- every failure mode of the pack lifecycle, one
line each, in the same words on the CLI and in Studio (Halo 3.2.0.0 R7;
docs/PACKS.md "When a pack cannot run"). The fixtures are
tests/fixtures/packs/{bad-yaml, no-id, bad-id, api-too-new, api-too-old,
halo-too-new, needs-base, cycle-a, cycle-b} and copies of the shipped
doc-review made in the test (an update whose new manifest is bad, a new
version that requests a grant not given, a source that vanishes mid-copy).
Studio's words are the Pack Manager's: the `problems` of a refused action and
a pack's `compat` / `health` lines. Every home is a fresh BRIDGE_TEST_HOME.
"""

from __future__ import annotations

import json
import shutil
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from tests.helpers.packs_studio import PackStudio  # noqa: E402
from tests.helpers.runner import Ctx, new_registry, print_results, run_all  # noqa: E402

test, TESTS = new_registry()
ID_LINE = ("id 'Doc_Review' is not a pack id: lower-case letters, digits and single hyphens, starting with a letter, "
           "at most 64 characters (doc-review)")


def _both(ctx, s, source: str, want: "list[str]", what: str) -> None:
    """The CLI's stderr and Studio's Install answer the same lines, and nothing is installed."""
    code, _out, err = s.cli("install", source)
    got = [ln.removeprefix("halo pack: ") for ln in err.splitlines()]
    ctx.check(f"{what}: the CLI's line(s), got {got}", code == 1 and got == want)
    status, body, _ = s.call("POST", "pack/install", {"source": source})
    ctx.check(f"{what}: Studio's Install answers the same, got {status} {body.get('problems')}",
              status in (404, 422) and body["problems"] == want and body["error"] == want[0])
    ctx.check(f"{what}: nothing installed", not [p for p in s.packs.iterdir() if p.is_dir() and not p.name.startswith(".")]
              if s.packs.is_dir() else True)


@test
def test_a_malformed_manifest(ctx: Ctx):
    with PackStudio() as s:
        _both(ctx, s, str(s.source("bad-yaml")), ["bad-yaml: pack.yaml: it does not read as a YAML mapping (key: value)"], "bad YAML")
        _both(ctx, s, str(s.source("no-id")), ["no-id: pack.yaml: id: required"], "a missing id")
        _both(ctx, s, str(s.source("bad-id")), [f"Doc_Review: pack.yaml: {ID_LINE}"], "a bad id")


@test
def test_an_api_or_halo_range_outside_this_halo(ctx: Ctx):
    from halo_harness import __version__
    with PackStudio() as s:
        _both(ctx, s, str(s.source("api-too-new")), ["pack api-too-new needs extension API 1.2 to 1.9; this Halo has 1.0"], "API too new")
        _both(ctx, s, str(s.source("api-too-old")), ["pack api-too-old needs extension API 0.5 to 0.9; this Halo has 1.0"], "API too old")
        _both(ctx, s, str(s.source("halo-too-new")), [f"pack halo-too-new needs Halo >= 9.0; this is {__version__}"], "Halo too old")


def _doctor_and_manager(ctx, s, pack_id: str, text: str, what: str) -> None:
    code, out, _err = s.cli("doctor")
    ctx.check(f"{what}: halo pack doctor's row, got {out}", code == 1 and f"[ERROR] {text} -> until this is fixed the pack contributes nothing" in out)
    _st, body, _h = s.call("GET", "pack/manager")
    row = next(p for p in body["packs"] if p["id"] == pack_id)
    ctx.check(f"{what}: the Manager's Details says the same, got {row['compat']}", text in row["compat"]
              and text in [h["text"] for h in row["health"]] and row["running"] is False)


@test
def test_a_missing_dependency_and_a_cycle(ctx: Ctx):
    with PackStudio() as s:
        for name in ("needs-base", "cycle-a", "cycle-b"):
            s.install(s.source(name), enable=True)
        _doctor_and_manager(ctx, s, "needs-base", "needs-base requires base-docs, which is not installed", "a missing dependency")
        _doctor_and_manager(ctx, s, "cycle-a", "cycle-a is in a requires cycle: cycle-a -> cycle-b -> cycle-a", "a cycle")


@test
def test_an_install_that_fails_half_way(ctx: Ctx):
    from halo_harness.packs import journal as J
    with PackStudio() as s:
        for via in ("cli", "studio"):
            src = s.source(folder=f"vanishing-{via}")
            real, calls = J._write_bytes, []

            def vanish(path, data, mode=None, _src=src):
                calls.append(path)
                if len(calls) == 3:
                    shutil.rmtree(_src)  # the source folder goes away mid-copy
                return real(path, data, mode)
            J._write_bytes = vanish
            try:
                if via == "cli":
                    code, _out, err = s.cli("install", str(src))
                    line = err.splitlines()[0].removeprefix("halo pack: ") if err else ""
                else:
                    status, body, _ = s.call("POST", "pack/install", {"source": str(src)})
                    code, line = (1 if status == 422 else 0), body.get("error", "")
            finally:
                J._write_bytes = real
            ctx.check(f"{via}: one line, got {line!r}", code == 1 and line.startswith("install of doc-review stopped: ")
                      and line.endswith("; every file it wrote is removed again"))
            ctx.check(f"{via}: nothing of it is left", not (s.packs / "doc-review").exists()
                      and not (s.packs / ".backup").exists())
            ctx.check(f"{via}: no record", "doc-review" not in json.loads((s.packs / "state.json").read_text(encoding="utf-8"))["installed"]
                      if (s.packs / "state.json").is_file() else True)


@test
def test_an_update_whose_new_manifest_is_bad(ctx: Ctx):
    with PackStudio() as s:
        src = s.source()
        s.install(src, enable=True)
        root = s.packs / "doc-review"
        before = {p.relative_to(root).as_posix(): p.read_bytes() for p in root.rglob("*") if p.is_file()}
        text = (src / "pack.yaml").read_text(encoding="utf-8").replace("version: 1.0.0", "version: 1.1.0")
        (src / "pack.yaml").write_text(text + "colour: blue\n", encoding="utf-8")
        code, _out, err = s.cli("update", "doc-review")
        got = [ln.removeprefix("halo pack: ") for ln in err.splitlines()]
        ctx.check(f"the CLI: the manifest's line, then that the old version stays, got {got}", code == 1 and len(got) == 2
                  and got[0].startswith("doc-review: pack.yaml: ") and "colour" in got[0] and got[1] == "doc-review 1.0.0 stays as it is")
        status, body, _ = s.call("POST", "pack/doc-review/update", {})
        ctx.check(f"Studio's Update answers the same lines, got {status} {body.get('problems')}", status == 422 and body["problems"] == got)
        after = {p.relative_to(root).as_posix(): p.read_bytes() for p in root.rglob("*") if p.is_file()}
        ctx.check("the old version is untouched, nothing kept aside", after == before and not (s.packs / "doc-review.previous").exists())


@test
def test_a_removed_source(ctx: Ctx):
    with PackStudio() as s:
        src = s.source("studio-bundle")
        folder = src.parent.as_posix()
        code, _out, _err = s.cli("sources", "add", str(src.parent))
        code, out, err = s.cli("install", "studio-bundle")
        ctx.check(f"installed by id from the source, got {code} {err}", code == 0)
        s.cli("remove", "studio-bundle")
        shutil.rmtree(src.parent)
        want = [f"no folder studio-bundle here, and no pack studio-bundle in the sources searched: {folder} (not a folder), "
                "the packs Halo ships (halo pack sources add <folder|git url>)"]
        _both(ctx, s, "studio-bundle", want, "a packs.sources folder that is gone")
        s.cli("sources", "remove", str(src.parent))
        want = ["no folder studio-bundle here, and no pack studio-bundle in the sources searched: packs.sources (empty), "
                "the packs Halo ships (halo pack sources add <folder|git url>)"]
        _both(ctx, s, "studio-bundle", want, "a removed packs.sources entry")
        src = s.source()
        s.install(src)
        shutil.rmtree(src)
        code, _out, err = s.cli("update", "doc-review")
        line = (f"doc-review's source {src} is not there any more; nothing is changed (install it from its new place, "
                "or see halo pack sources)")
        ctx.check(f"update from a source that is gone: one line, got {err!r}", code == 1 and err.strip() == f"halo pack: {line}")
        status, body, _ = s.call("POST", "pack/doc-review/update", {})
        ctx.check("Studio's Update: the same line", status == 422 and body["problems"] == [line])


@test
def test_a_new_version_that_needs_a_grant_not_given(ctx: Ctx):
    with PackStudio() as s:
        src = s.source()
        s.install(src, enable=True, grants=["hooks", "mcp:lint", "bash"])
        text = (src / "pack.yaml").read_text(encoding="utf-8").replace("version: 1.0.0", "version: 1.1.0")
        (src / "pack.yaml").write_text(text.replace('permissions: ["mcp:lint", hooks, bash]', 'permissions: ["mcp:lint", hooks, bash, network]'),
                                       encoding="utf-8")
        code, out, _err = s.cli("update", "doc-review")
        ctx.check(f"update says what it now asks for, got {out}", code == 0
                  and "1.1.0 also requests network, not granted: halo pack grant doc-review network" in out.splitlines())
        text_ = "doc-review 1.1.0 requests network, which 1.0.0 did not; it is not granted, so what needs it does not run"
        code, out, _err = s.cli("doctor")
        ctx.check(f"halo pack doctor names the grant, got {out}", f"[WARN] {text_} -> halo pack grant doc-review network" in out)
        _st, body, _h = s.call("GET", "pack/manager")
        row = next(p for p in body["packs"] if p["id"] == "doc-review")
        ctx.check(f"the Manager's Details names it in the same words, got {row['compat']}", text_ in row["compat"]
                  and any(h["text"] == text_ and h["fix"] == "halo pack grant doc-review network" for h in row["health"]))
        s.cli("grant", "doc-review", "network")
        code, out, _err = s.cli("doctor")
        ctx.check("granted: the row goes", text_ not in out)


if __name__ == "__main__":
    ctx = Ctx()
    results, passed, failed, skipped = run_all(TESTS, ctx)
    sys.exit(print_results(results, passed, failed, skipped))
