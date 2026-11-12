"""tests.test_pack_first_run -- the guided first run as the shipped first-run pack (Halo 3.4.0.0 B, F4 of the Focus
plan): `halo pack install first-run` installs it, `--grant-all` enables it (cli:start, studio-script, studio-routes);
then `halo start --explain` is the pack's verb (contributes.cli), `/start` its slash command (contributes.slash),
Setup's Check page has its row through its Setup block (`pack:first-run:run`), Studio's registry its First run panel
and routes; with the pack off, `halo start` and `/start` are one line each and none of it shows anywhere. The engine's
own behaviour: tests/test_pack_first_run_cli.py and test_pack_first_run_errors.py (moved from test_start_cli*).
Run: python -m tests.test_pack_first_run
"""

from __future__ import annotations

import contextlib
import io
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from tests.helpers.packs_home import PacksHome  # noqa: E402
from tests.helpers.runner import Ctx, new_registry, print_results, run_all  # noqa: E402

test, TESTS = new_registry()
REPO = Path(__file__).resolve().parent.parent


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


def _slash(name: str, cwd: Path) -> str:
    from types import SimpleNamespace
    from halo_harness.commands.registry import Registry
    from halo_harness.packs import registry
    registry.invalidate()
    reg = Registry.discover(cwd)
    cmd = reg.resolve(name)
    return cmd.run("", SimpleNamespace(session=None, cwd=cwd)) if cmd is not None else ""


@test
def test_off_the_verb_the_slash_the_check_and_the_panel_say_nothing_but_one_line(ctx: Ctx):
    from halo_harness.checks.pack import rows
    from halo_harness.packs.studio_registry import registry
    with PacksHome() as h:
        rc, out, err = _main(["start", "--explain"], h.repo)
        ctx.check(f"halo start: one line naming the pack, exit 2, got {rc} {err!r}",
                  rc == 2 and not out and "halo pack install first-run" in err and len(err.strip().splitlines()) == 1)
        line = _slash("start", h.repo)
        ctx.check(f"/start: the same line, got {line!r}", line.startswith("/start: the guided first run is a pack now"))
        ctx.check("no Setup check row", not [r for r in rows(h.repo, h.state) if r["key"].startswith("pack:first-run")])
        reg = registry(cwd=h.repo, state_dir=h.state)
        ctx.check("nothing of it in Studio", not [p for p in reg["packs"] if p["id"] == "first-run"])


@test
def test_on_the_verb_the_slash_the_check_row_and_the_panel_work(ctx: Ctx):
    from halo_harness.checks.pack import rows
    from halo_harness.packs.studio_registry import registry
    from tests.helpers.custom_lineup import custom_lineup
    with PacksHome() as h:
        code, out, err = h.cli("install", "first-run")
        ctx.check(f"halo pack install first-run installs the shipped folder, got {code} {err[-300:]!r}", code == 0)
        code, out, err = h.cli("enable", "first-run", "--grant-all")
        ctx.check(f"enable --grant-all grants cli:start, studio-script, studio-routes, got {out!r}",
                  code == 0 and "cli:start" in out and "studio-routes" in out)
        os.environ["HALO_START_FAKE"] = "1"
        try:
            with custom_lineup():
                rc, out, err = _main(["start", "--explain"], h.repo)
        finally:
            os.environ.pop("HALO_START_FAKE", None)
        ctx.check(f"halo start --explain: the card, exit 0, got {rc} {out[:300]!r} {err[-300:]!r}",
                  rc == 0 and "halo start" in out and "Estimated cost" in out)
        line = _slash("start", h.repo)
        ctx.check(f"/start: the card and how to run it, got {line[-200:]!r}", "Run it: `halo start`" in line)
        keys = [r["key"] for r in rows(h.repo, h.state)]
        ctx.check(f"Setup's Check page has the pack's row, got {keys}", "pack:first-run:run" in keys)
        reg = registry(cwd=h.repo, state_dir=h.state)
        entry = next((p for p in reg["packs"] if p["id"] == "first-run"), {})
        panel = next((p for p in entry.get("panels") or [] if p.get("id") == "first-run--run"), {})
        ctx.check(f"its First run panel joins Agents, got {panel.get('section')} {panel.get('title')}",
                  panel.get("section") == "agents" and panel.get("title") == "First run")
        ctx.check(f"its routes are granted, got {entry.get('routes')}",
                  entry.get("routes") == {"prefix": "start", "api": "api/packs/first-run/start", "granted": True})
        h.cli("disable", "first-run")
        rc, _out, err = _main(["start"], h.repo)
        ctx.check(f"disabled: one line, installed but off (3.4.0.1), got {rc} {err!r}", rc == 2 and "halo pack enable first-run --grant-all" in err and "pack install" not in err)


@test
def test_halo_pack_test_passes_the_shipped_pack(ctx: Ctx):
    from halo_harness.packs.cli import cmd_pack
    out, err = io.StringIO(), io.StringIO()
    os.environ["HALO_START_FAKE"] = "1"
    try:
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
            rc = cmd_pack(["test", str(REPO / "halo_harness" / "templates" / "packs" / "first-run")])
    finally:
        os.environ.pop("HALO_START_FAKE", None)
    ctx.check(f"halo pack test first-run passes, got {rc} {out.getvalue()[-400:]!r}", rc == 0 and "0 failed" in out.getvalue())


if __name__ == "__main__":
    ctx = Ctx()
    results, passed, failed, skipped = run_all(TESTS, ctx)
    sys.exit(print_results(results, passed, failed, skipped, label="first-run pack tests"))
