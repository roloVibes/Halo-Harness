"""tests.test_pack_fleet -- the fleet as the shipped `fleet` pack (Halo 3.4.0.0 C: "Fleet doesn't really fit anymore
... it can be a pack"). Off: `halo fleet`, `halo mission`, `/fleet`, `/mission` are one line each naming the pack,
Studio's `GET fleet` is this harness alone with `fleet_pack: false`, a command for another harness is 409 and a fleet
route of the pack's 404, both with the line; Settings has no Fleet group. On (`halo pack install fleet`,
`--grant-all`): the verbs, the slash commands and the routes are the pack's. The core imports nothing of the pack;
a halo that had a fleet gets the pack once on its next run (packs/fleet_migrate.py), with nothing deleted. The
fleet's own behaviour: every tests/test_fleet_*.py, run against the pack (tests/helpers/fleet_pack.py).
Run: python -m tests.test_pack_fleet
"""

from __future__ import annotations

import ast
import contextlib
import io
import json
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from tests.helpers.packs_home import PacksHome  # noqa: E402
from tests.helpers.runner import Ctx, new_registry, print_results, run_all  # noqa: E402

test, TESTS = new_registry()
REPO = Path(__file__).resolve().parent.parent
LINE = "is a pack now: halo pack install fleet, then halo pack enable fleet --grant-all"


def _main(argv: list, cwd: Path) -> "tuple[int, str, str]":
    from halo_harness.cli import main
    out, err = io.StringIO(), io.StringIO()
    here = os.getcwd()
    os.chdir(cwd)
    try:
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
            rc = main(argv)
    finally:
        os.chdir(here)
    return rc, out.getvalue(), err.getvalue()


def _slash(name: str, cwd: Path, args: str = "") -> str:
    from types import SimpleNamespace
    from halo_harness.commands.registry import Registry
    from halo_harness.packs import registry
    registry.invalidate()
    cmd = Registry.discover(cwd).resolve(name)
    return cmd.run(args, SimpleNamespace(session=None, cwd=cwd)) if cmd is not None else ""


def _studio(h, method: str, path: str, body=None) -> "tuple[int, dict]":
    from halo_harness.studio.api import Request, dispatch

    class _Server:
        fleet_hub = None
        cwd = h.repo
        state_dir = h.state
    req = Request(owner=True, method=method, path=path, query={}, body=body or {}, cwd=h.repo, state_dir=h.state, server=_Server())
    got = dispatch(req)
    return got[0], got[1]


@test
def test_off_every_fleet_door_is_one_line_and_studio_shows_this_harness(ctx: Ctx):
    from halo_harness.settings_catalog import catalog_json
    with PacksHome() as h:
        for argv in (["fleet", "status"], ["fleet"], ["mission", "status"]):
            rc, out, err = _main(argv, h.repo)
            ctx.check(f"halo {' '.join(argv)}: one line naming the pack, exit 2, got {rc} {err!r}",
                      rc == 2 and not out and LINE in err and len(err.strip().splitlines()) == 1)
        for name in ("fleet", "mission"):
            line = _slash(name, h.repo)
            ctx.check(f"/{name}: the same line, got {line!r}", line.startswith(f"/{name}: ") and LINE in line)
        status, view = _studio(h, "GET", "fleet")
        ctx.check(f"GET fleet: this harness alone, fleet_pack false, got {status} {sorted(view)}",
                  status == 200 and view.get("fleet_pack") is False and len(view.get("harnesses") or []) == 1
                  and view["harnesses"][0].get("local"))
        ctx.check(f"3.4.0.1 defect 29: and the CLI's line for Studio's banner, got {view.get('fleet_line')!r}", LINE in str(view.get("fleet_line")))
        status, body = _studio(h, "POST", "fleet/other-harness/s1/command", {"cmd": "steer", "text": "hi"})
        ctx.check(f"a command for another harness: 409 with the line, got {status} {body}", status == 409 and LINE in body["error"])
        status, body = _studio(h, "GET", "fleet/missions")
        ctx.check(f"a route of the pack's: 404 with the line, got {status} {body}", status == 404 and LINE in body["error"])
        cat = catalog_json()
        ctx.check("Settings: no Fleet group and no row of it",
                  "fleet" not in [g["id"] for g in cat["groups"]] and not any(r["group"] == "fleet" for r in cat["rows"]))
        ctx.check("the core keys stay under Remote", any(r["key"] == "fleet.enabled" and r["group"] == "remote" for r in cat["rows"]))


@test
def test_on_the_verbs_the_slash_commands_and_the_routes_are_the_packs(ctx: Ctx):
    from halo_harness.settings_catalog import catalog_json
    with PacksHome() as h:
        # --link: the pack read in place, so this process keeps ONE copy of its modules (a copy installed here would
        # re-point `halo_packs.fleet` and leave the next test module's aliases on the old objects); the copy install of
        # the shipped id is the migration test's
        code, out, err = h.cli("install", str(REPO / "halo_harness" / "templates" / "packs" / "fleet"), "--link")
        ctx.check(f"halo pack install <the shipped folder> --link, got {code} {err[-300:]!r}", code == 0)
        ctx.check(f"3.4.0.1 defect 2: it says what it offers, not 'nothing', got {out!r}",
                  "it offers: 2 CLI verbs, 2 slash commands, 1 doctor row, 5 Studio server modules" in out)
        code, out, err = h.cli("inspect", "fleet")
        offered = out.split("offers:\n", 1)[-1].split("\n")[:4]
        ctx.check(f"3.4.1.0 R5 (defect 2): `pack inspect` lists them under offers:, got {offered}", code == 0
                  and offered[0] == "  CLI verbs: fleet, mission" and offered[1] == "  slash commands: /fleet, /mission"
                  and offered[2] == "  doctor rows: fleet" and offered[3].startswith("  Studio server modules: "))
        code, out, err = h.cli("enable", "fleet", "--grant-all")
        ctx.check(f"enable --grant-all grants cli:fleet and cli:mission, got {out!r}",
                  code == 0 and "cli:fleet" in out and "cli:mission" in out)
        rc, out, err = _main(["fleet", "--once", "--json"], h.repo)
        ctx.check(f"halo fleet --once --json: the table as JSON, got {rc} {out[:200]!r} {err[-200:]!r}",
                  rc == 0 and isinstance(json.loads(out or "null"), (dict, list)))
        rc, out, err = _main(["mission", "status", "--json"], h.repo)
        ctx.check(f"halo mission status: the pack's missions, got {rc} {out[:200]!r} {err[-200:]!r}", rc == 0)
        line = _slash("fleet", h.repo, "text")
        ctx.check(f"/fleet: the table, got {line[:120]!r}", line.startswith("Fleet ("))
        status, view = _studio(h, "GET", "fleet")
        ctx.check(f"GET fleet: fleet_pack true, got {status} {view.get('fleet_pack')}", status == 200 and view.get("fleet_pack") is True)
        status, body = _studio(h, "GET", "fleet/missions")
        ctx.check(f"the pack's mission route answers, got {status}", status == 200 and "missions" in body)
        ctx.check("Settings: the Fleet group is back", "fleet" in [g["id"] for g in catalog_json()["groups"]])
        rc, out, err = _main(["recall", "--fleet", "test"], h.repo)  # 3.4.0.1 defect 4: it asked the pack for a core module
        ctx.check(f"halo recall --fleet runs with the pack on (no hub joined: its own error), got {rc} {err!r}",
                  rc == 3 and "is a pack now" not in err and "pack" not in err.split(":", 1)[-1][:40])
        from halo_harness.packs.contrib_doctor import rows as doctor_rows  # 3.4.0.1 defect 7: a fleet row in halo doctor
        doc = [r for r in doctor_rows(h.repo, h.state) if "From packs, fleet:" in r]
        ctx.check(f"halo doctor: the fleet pack runs, no hub here, no hub joined, got {doc}", len(doc) >= 2
                  and "the fleet pack runs; no hub runs here" in doc[0] and any("joined no hub" in r for r in doc))
        said = _slash("recall", h.repo, "--fleet test")
        ctx.check(f"/recall --fleet: the same, got {said!r}", "is a pack now" not in said and said.startswith("/recall --fleet"))
        h.cli("disable", "fleet")
        rc, _out, err = _main(["fleet"], h.repo)
        ctx.check(f"disabled: one line, installed but off (3.4.0.1 defect 3), got {rc} {err!r}", rc == 2
                  and "the fleet pack is installed but off: halo pack enable fleet --grant-all" in err and "install fleet" not in err)
        rc, _out, err = _main(["recall", "--fleet", "test"], h.repo)
        ctx.check(f"halo recall --fleet with the pack off: that line, exit 2, got {rc} {err!r}", rc == 2 and "installed but off" in err)


@test
def test_every_door_names_a_module_the_pack_has(ctx: Ctx):
    """3.4.0.1 defect 4: `halo recall --fleet` asked the door for fleet/recall_fleet.py, which stayed core: the door
    answered None and the verb said "install the pack" with the pack on."""
    import re
    pack = REPO / "halo_harness" / "templates" / "packs" / "fleet"
    named = set()
    for p in sorted((REPO / "halo_harness").rglob("*.py")):
        if "templates" not in p.parts:
            named |= set(re.findall(r'fleet_door\.(?:module|call)\(\s*"([^"]+)"', p.read_text(encoding="utf-8")))
    missing = sorted(rel for rel in named if not (pack / rel).is_file())
    ctx.check(f"the core's doors name {len(named)} pack modules, every one in the pack, missing {missing}",
              len(named) >= 8 and not missing)


@test
def test_the_core_imports_nothing_of_the_pack(ctx: Ctx):
    pkg = REPO / "halo_harness"
    bad = []
    for p in sorted(pkg.rglob("*.py")):
        rel = p.relative_to(REPO).as_posix()
        if rel.startswith("halo_harness/templates/") or "__pycache__" in p.parts:
            continue
        for node in ast.walk(ast.parse(p.read_text(encoding="utf-8"), filename=rel)):
            names = [a.name for a in node.names] if isinstance(node, ast.Import) else (
                [node.module or ""] if isinstance(node, ast.ImportFrom) and not node.level else [])
            bad += [f"{rel}:{node.lineno}: {n}" for n in names if n.startswith(("halo_harness.fleet", "halo_packs"))]
    ctx.check("no core module imports halo_harness.fleet or halo_packs.*:\n  " + "\n  ".join(bad), not bad)
    ctx.check("halo_harness/fleet/ is gone", not (pkg / "fleet").exists())


@test
def test_a_halo_that_had_a_fleet_gets_the_pack_once_and_keeps_its_files(ctx: Ctx):
    from halo_harness.packs import fleet_migrate as FM
    from halo_harness.packs.discover import find
    with PacksHome() as h:
        ctx.check("a home with no fleet: nothing done", FM.run(h.state) == "" and not (h.state / "packs" / FM.MARKER).exists())
        (h.state / "fleet.json").write_text(json.dumps({"version": 1, "hubs": [{"url": "https://192.0.2.7:7430",
                                                                                "name": "hub", "state": "joined"}]}),
                                            encoding="utf-8")
        line = FM.run(h.state)
        ctx.check(f"a joined hub: the shipped pack installed (copied) and on, one line, got {line!r}",
                  line == FM.LINE and (h.state / "packs" / "fleet" / "pack.yaml").is_file())
        pack = find("fleet", cwd=h.repo, state_dir=h.state)
        from halo_harness.packs import state as S
        rec = S.entry("fleet", h.state) or {}
        ctx.check(f"enabled with cli:fleet and cli:mission, got {rec}", pack is not None and rec.get("enabled")
                  and {"cli:fleet", "cli:mission"} <= set(rec.get("granted") or []))
        ctx.check("fleet.json is left as it was", "192.0.2.7" in (h.state / "fleet.json").read_text(encoding="utf-8"))
        ctx.check("the marker, and a second run does nothing", (h.state / "packs" / FM.MARKER).is_file() and FM.run(h.state) == "")


@test
def test_halo_pack_test_passes_the_shipped_pack(ctx: Ctx):
    from halo_harness.packs.cli import cmd_pack
    out, err = io.StringIO(), io.StringIO()
    with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
        rc = cmd_pack(["test", str(REPO / "halo_harness" / "templates" / "packs" / "fleet")])
    ctx.check(f"halo pack test fleet passes, got {rc} {out.getvalue()[-400:]!r}", rc == 0 and "0 failed" in out.getvalue())


if __name__ == "__main__":
    ctx = Ctx()
    results, passed, failed, skipped = run_all(TESTS, ctx)
    sys.exit(print_results(results, passed, failed, skipped, label="fleet pack tests"))
