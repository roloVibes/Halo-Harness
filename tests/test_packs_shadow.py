"""tests.test_packs_shadow -- a folder or a source never stands in for a pack Halo ships (Halo 3.4.1.2, the 2026-11-12
review's PACKS-1; packs/fetch.py `source_for`, packs/fleet_migrate.py, packs/fleet_door.py):

1. a repo holding `./coach/pack.yaml` in the current directory: `halo pack install coach` installs the
   pack Halo ships and records its full path; a bare id never reaches the folder, and `fetched` of a bare id (an
   older record's) does not either; `./coach` still names the folder when the owner means it.
2. a configured `packs.sources` folder holding `coach` does not shadow the shipped one: the shipped pack is installed
   and one line says so; `--from <source>` takes that source.
3. the core's door to a shipped pack (packs/fleet_door.py) opens only the pack Halo ships (or one granted
   studio-routes): the same id from another folder
   is not imported, and the door's line says why.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from tests.helpers.packs_home import SHIPPED, PacksHome  # noqa: E402
from tests.helpers.runner import Ctx, new_registry, print_results, run_all  # noqa: E402

test, TESTS = new_registry()
EVIL = ("id: {id}\nname: Evil\nversion: 9.9.9\ndescription: a repo's folder under a shipped id\nauthor: x\nlicense: MIT\n"
        "halo_api: {{min: \"1.0\"}}\n")


def _plant(folder: Path, pack_id: str) -> Path:
    (folder / pack_id).mkdir(parents=True, exist_ok=True)
    (folder / pack_id / "pack.yaml").write_text(EVIL.format(id=pack_id), encoding="utf-8")
    return folder / pack_id


class _Cwd:
    def __init__(self, path: Path):
        self.path, self.was = path, os.getcwd()

    def __enter__(self):
        os.chdir(self.path)

    def __exit__(self, *exc):
        os.chdir(self.was)


@test
def test_packs_1_a_cwd_folder_never_stands_in_for_a_shipped_id(ctx: Ctx):
    from halo_harness.packs import state as S
    from halo_harness.packs.fetch import fetched, source_for
    from halo_harness.packs.install import install
    with PacksHome() as h, _Cwd(h.repo):
        _plant(h.repo, "coach")
        ctx.check(f"source_for('coach') is the shipped folder, got {source_for('coach')}",
                  Path(source_for("coach")).resolve() == (SHIPPED / "coach").resolve())
        ok, lines = install("coach", cwd=h.repo, state_dir=h.state)
        rec = S.entry("coach", h.state) or {}
        ctx.check(f"installed the shipped coach, got {ok} {lines[:1]} {rec.get('version')}", ok and rec.get("version") != "9.9.9"
                  and Path(rec.get("source", "")).resolve() == (SHIPPED / "coach").resolve())
        _plant(h.repo, "nopack-here")
        with fetched("nopack-here", state_dir=h.state) as (src, problem):
            ctx.check(f"fetched of a bare id no source holds: none, never ./nopack-here, got {src} {problem!r}",
                      src is None and "./nopack-here" in problem)
        with fetched("./nopack-here", state_dir=h.state) as (src, _problem):
            ctx.check("./nopack-here names the folder when the owner means it", src is not None and src.name == "nopack-here")
        from halo_harness.packs.cli_test import folder_of
        got, _why = folder_of("coach", cwd=h.repo)
        ctx.check(f"the same mistake in `halo pack test coach`: the installed or shipped coach, got {got}",
                  got is not None and got.resolve() != (h.repo / "coach").resolve())
        ctx.check("`halo pack test ./coach` still tests the folder", folder_of("./coach", cwd=h.repo)[0] == (h.repo / "coach").resolve())
        ctx.check("a bare id nobody ships or installed may still be a folder here",
                  folder_of("nopack-here", cwd=h.repo)[0] == (h.repo / "nopack-here").resolve())


@test
def test_packs_1_a_configured_source_does_not_shadow_a_shipped_id_unless_named(ctx: Ctx):
    from halo_harness.packs import state as S
    from halo_harness.packs.install import install
    with PacksHome() as h:
        _plant(h.sources, "coach")
        code, _o, err = h.cli("sources", "add", str(h.sources))
        ctx.check(f"the source is added, got {code} {err}", code == 0)
        ok, lines = install("coach", cwd=h.repo, state_dir=h.state)
        rec = S.entry("coach", h.state) or {}
        ctx.check(f"the shipped coach is installed, not the source's 9.9.9, got {rec.get('version')}",
                  ok and rec.get("version") != "9.9.9")
        ctx.check(f"one line says the source holds it too and how to take it, got {lines}",
                  any("also holds a pack coach" in ln and "--from" in ln for ln in lines))
        h.cli("remove", "coach")
        code, out, err = h.cli("install", "coach", "--from", str(h.sources))
        rec = S.entry("coach", h.state) or {}
        ctx.check(f"--from takes that source, got {code} {err} {rec.get('version')}", code == 0 and rec.get("version") == "9.9.9")


if __name__ == "__main__":
    ctx = Ctx()
    results, passed, failed, skipped = run_all(TESTS, ctx)
    sys.exit(print_results(results, passed, failed, skipped))
