"""tests.test_packs_shipped_newer -- Halo 3.4.1.0 R5 (live re-check defect 30): an installed pack older than the one this
Halo ships. The live check: after `halo update` to 3.4.0.1 both machines kept the fleet pack 1.0.0 while Halo shipped
1.0.1, and `pack list`, `pack inspect`, `pack doctor`, `halo doctor` and Studio's Packs said nothing of it; `halo pack
install fleet` (the pairing recipe's step 1) exited 1 on a machine that had it.

Here the shipped reference pack doc-review is installed by its bare id (from the shipped folder), then made older (its
recorded and installed version lowered): every surface says it in one line with `halo pack update doc-review`; the
install of the same id says "already installed ... update" (exit 1) while older, "nothing to do" (exit 0) once current.
A pack installed from another folder is never called older.
Run: python -m tests.test_packs_shipped_newer
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from tests.helpers.packs_home import PacksHome  # noqa: E402
from tests.helpers.runner import Ctx, new_registry, print_results, run_all  # noqa: E402

test, TESTS = new_registry()
PID = "doc-review"


def _older_install(h, version: str = "0.0.1") -> str:
    """Install doc-review as an older Halo shipped it: a copy at <old>/templates/packs/doc-review with an older version,
    then the record's source pointed at this Halo's shipped folder (a `halo update` reinstalls Halo in place)."""
    import shutil
    from halo_harness.packs import registry, state as S
    from halo_harness.packs.shipped_newer import ships
    from halo_harness.packs.sources import shipped_dir
    old = h.home / "old-halo" / "templates" / "packs" / PID
    shutil.copytree(shipped_dir() / PID, old, ignore=shutil.ignore_patterns("__pycache__"))
    text = (old / "pack.yaml").read_text(encoding="utf-8")
    (old / "pack.yaml").write_text(text.replace(f"version: {ships(PID)}", f"version: {version}", 1), encoding="utf-8")
    h.install(old)
    S.put(PID, {"source": str(shipped_dir() / PID)})
    registry.invalidate()
    return ships(PID)


@test
def test_every_surface_says_an_older_shipped_pack_in_one_line(ctx: Ctx):
    with PacksHome() as h:
        code, out, err = h.cli("install", PID)
        ctx.check(f"installed by its bare id from the shipped folder, got {code} {err!r}", code == 0)
        code, out, err = h.cli("install", PID)
        ctx.check(f"the same version again: exit 0, nothing to do (the recipe's step 1 on a used machine), got {code} {out!r} {err!r}",
                  code == 0 and "is already installed at" in out and "nothing to do" in out)
        code, out, _ = h.cli("list")
        ctx.check(f"current: no word of a newer one, got {out!r}", code == 0 and "ships with this Halo" not in out)
        h.cli("remove", PID)
        new = _older_install(h)
        line = f"{PID} 0.0.1 is older than the {new} this Halo ships: halo pack update {PID}"
        code, out, _ = h.cli("list")
        ctx.check(f"pack list: one line says it, got {out!r}", f"({new} ships with this Halo: halo pack update {PID})" in out)
        code, out, _ = h.cli("list", "--json")
        ctx.check("pack list --json: `ships`", json.loads(out)["packs"][0].get("ships") == new)
        code, out, _ = h.cli("inspect", PID)
        ctx.check(f"pack inspect, got {out[:300]!r}", f"  {line}" in out.splitlines())
        code, out, _ = h.cli("doctor")
        ctx.check(f"pack doctor warns once with the fix, got {out!r}", out.count(line) == 1 and "0 problem(s)" not in out)
        from halo_harness.packs.contrib_doctor import entries_of
        rows = [r for _cid, r in entries_of(h.repo)]
        ctx.check(f"halo doctor (disabled pack too), got {rows}", any(r == f"[WARN] From packs, {PID}: {line}" for r in rows))
        from halo_harness.packs.manager import payload
        row = next(p for p in payload(cwd=h.repo)["packs"] if p["id"] == PID)
        ctx.check(f"Studio's Packs row: ships {row.get('ships')!r}", row.get("ships") == new)
        code, out, err = h.cli("install", PID)
        ctx.check(f"install while older: exit 1, already installed, the update command, got {code} {err!r}",
                  code == 1 and "0.0.1 is already installed at" in err and f"holds {new}: halo pack update {PID}" in err)
        code, out, err = h.cli("update", PID, "--yes")
        ctx.check(f"halo pack update brings it to {new}, got {code} {out[-200:]!r} {err[-200:]!r}", code == 0)
        code, out, _ = h.cli("list")
        ctx.check(f"then nothing more to say, got {out!r}", "ships with this Halo" not in out)


@test
def test_a_pack_from_another_folder_is_never_called_older(ctx: Ctx):
    from halo_harness.packs.shipped_newer import newer, ships
    with PacksHome() as h:
        src = h.source(PID)  # a copy in a folder of the owner's, not a Halo's shipped folder
        h.install(src)
        code, out, _ = h.cli("list")
        ctx.check(f"installed from {src.parent.name}/: no shipped line, got {out!r}", "ships with this Halo" not in out)
        from halo_harness.packs import state as S
        ctx.check("and with an older version recorded, still none", newer(PID, "0.0.1", S.entry(PID)["source"]) == "")
    ctx.check("any Halo's shipped folder counts (an older install's path)",
              newer(PID, "0.0.1", "/old/site-packages/halo_harness/templates/packs/" + PID) == ships(PID))
    ctx.check("a newer copy than Halo ships is not older", newer(PID, "99.0.0", "/x/templates/packs/" + PID) == "")


if __name__ == "__main__":
    ctx = Ctx()
    results, passed, failed, skipped = run_all(TESTS, ctx)
    sys.exit(print_results(results, passed, failed, skipped, label="packs shipped newer tests"))
