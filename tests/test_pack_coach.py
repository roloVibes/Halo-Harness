"""tests.test_pack_coach -- the coach as the shipped coach pack (Halo 3.4.0.0 B2, F4 of the Focus plan).

Off (the default): `halo coach`, `halo improve`, `halo orchestra coach`, `halo fleet mission coach` and `/coach`,
`/improve` are one line each naming the pack; no Settings row, no doctor row, no Studio panel; the old keys `coach.*`
and `improve.*` are ignored with one line (config set and doctor --config); the guided first run's step 6 says the
coach is a pack. On (`--grant-all`): the verbs and the slash commands run the pack's code, its seven Settings rows and
its doctor row show, Studio's registry has its Coach panel in Agents and its routes answer a run's card;
`halo pack test` passes on its folder. What the coach does: the moved tests (test_coach_*.py, test_improve_*.py,
test_orchestra_coach*.py) against the pack's modules. Run: python -m tests.test_pack_coach
"""

from __future__ import annotations

import contextlib
import io
import json
import os
import sys
from pathlib import Path
from types import SimpleNamespace

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from tests.helpers import coach_pack as CP  # noqa: E402
from tests.helpers.packs_home import PacksHome  # noqa: E402
from tests.helpers.runner import Ctx, new_registry, print_results, run_all  # noqa: E402

test, TESTS = new_registry()
LINE = "is a pack now: halo pack install coach, then halo pack enable coach --grant-all"


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


def _slash(name: str, args: str, cwd: Path) -> str:
    from halo_harness.commands.registry import Registry
    from halo_harness.packs import registry
    registry.invalidate()
    cmd = Registry.discover(cwd).resolve(name)
    return cmd.run(args, SimpleNamespace(session=None, cwd=cwd)) if cmd is not None else ""


def _studio(cwd) -> dict:
    from halo_harness.packs.studio_registry import registry
    return next((p for p in registry(cwd=cwd)["packs"] if p["id"] == "coach"), {})


@test
def test_off_every_verb_is_one_line_and_nothing_shows(ctx: Ctx):
    from halo_harness.doctor import _check_entries
    from halo_harness.settings_catalog import rows
    with PacksHome() as h:
        from tests.helpers import fleet_pack as FP  # 3.4.0.0 C: `halo fleet` is the fleet pack's; on, it hands over
        for argv in (["coach"], ["improve", "--json"], ["orchestra", "coach"], ["fleet", "mission", "coach", "m-1"]):
            FP.on() if argv[0] == "fleet" else None
            try:
                rc, out, err = _main(argv, h.repo)
            finally:
                FP.off()
            ctx.check(f"halo {' '.join(argv)}: exit 2 and the one line, got {rc} {err!r}", rc == 2 and not out
                      and LINE in err and len(err.strip().splitlines()) == 1)
        for name in ("coach", "improve"):
            said = _slash(name, "", h.repo)
            ctx.check(f"/{name}: the line, got {said!r}", said.startswith(f"/{name}: ") and LINE in said)
        ctx.check("no Settings row", not [r for r in rows() if r.key.startswith("packs.settings.coach.")])
        ctx.check("no doctor row", not [c for c, _ in _check_entries(h.repo) if c.startswith("pack:coach")])
        ctx.check("nothing in Studio's registry", _studio(h.repo) == {})


@test
def test_off_the_old_keys_are_ignored_with_one_line(ctx: Ctx):
    from halo_harness.config_cli import cmd_config
    from halo_harness.doctor_config import config_findings
    with PacksHome() as h:
        err = io.StringIO()
        with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(err):
            rc = cmd_config(["set", "improve.model", "or:x/y"])
        ctx.check(f"config set improve.model: exit 2 naming the pack's key, got {rc} {err.getvalue()!r}", rc == 2
                  and "moved to the coach pack in 3.4.0.0: halo config set packs.settings.coach.improve.model" in err.getvalue())
        (h.state / "config.json").write_text(json.dumps({"improve": {"model": "or:x/y"}, "coach": {"probe": {"k": 2}}}),
                                             encoding="utf-8")
        found = [f for f in config_findings(cwd=h.repo, state_dir=h.state) if f.get("check") == "packed-section"]
        ctx.check(f"doctor --config: one warn line per section, got {[f['text'] for f in found]}",
                  sorted(f["key"] for f in found) == ["coach", "improve"] and all(f["severity"] == "warns" for f in found)
                  and all("this section is ignored" in f["text"] for f in found))


@test
def test_off_the_guided_first_run_step_six_says_the_line(ctx: Ctx):
    from tests.helpers import first_run_pack as FR
    with PacksHome():
        lines = FR.module("first_run/coach_step.py").card(SimpleNamespace(run_dir=Path("."), repo=None))
        ctx.check(f"step 6: the coach is a pack, got {lines}", lines[-1].startswith("The coach (what to change next time) is a pack"))


@test
def test_on_the_verbs_the_rows_the_panel_and_the_routes(ctx: Ctx):
    from halo_harness.doctor import _check_entries
    from halo_harness.settings_catalog import rows
    from tests.helpers import coach_seed as S
    with PacksHome() as h:
        S.seed_home(h.state)
        S.orchestra_run(h.repo, [S.lane(1, bio="coach-deny", denied=[{"tool_name": "WebFetch", "reason": "denied by rule"}])])
        CP.enable(h.state, cwd=h.repo)
        rc, out, err = _main(["coach", "--json", "--repo", str(h.repo)], h.repo)
        ctx.check(f"halo coach --json: the card, got {rc} {err!r}", rc == 0 and json.loads(out)["suggestions"][0]["id"] == "tools-1-WebFetch")
        rc, out, _ = _main(["orchestra", "coach", "--repo", str(h.repo)], h.repo)
        ctx.check(f"halo orchestra coach hands over, got {rc}", rc == 0 and f"coach: orchestra run {S.RUN}: 1 suggestion" in out)
        rc, out, _ = _main(["improve", "--bare"], h.repo)
        ctx.check(f"halo improve --bare, got {rc} {out!r}", rc == 0 and "--bare disables /improve entirely" in out)
        said = _slash("coach", S.RUN, h.repo)  # the facade's cwd is the repo
        ctx.check(f"/coach: the card, got {said[:120]!r}", said.startswith(f"coach: orchestra run {S.RUN}: 1 suggestion"))
        keys = sorted(r.key for r in rows() if r.key.startswith("packs.settings.coach."))
        ctx.check(f"seven Settings rows, got {keys}", len(keys) == 7 and "packs.settings.coach.improve.model" in keys)
        doc = [line for c, line in _check_entries(h.repo) if c.startswith("pack:coach")]
        ctx.check(f"one doctor row, got {doc}", len(doc) == 1 and doc[0].startswith("[OK] From packs, coach: the coach is on"))
        reg = _studio(h.repo)
        panels = [p for p in reg.get("panels") or [] if p.get("section") == "agents"]
        ctx.check(f"the Coach panel in Agents and the routes, got {[p.get('id') for p in panels]} {reg.get('routes')}",
                  [p.get("title") for p in panels] == ["Coach"] and (reg.get("routes") or {}).get("prefix") == "coach")
        routes = CP.module("server/routes.py")
        ctx_ = SimpleNamespace(pack_id="coach", cwd=h.repo, state_dir=h.state, bridge=None)
        code, body = routes.handle(ctx_, "GET", "runs", {}, {})
        ctx.check(f"GET runs lists the run, got {code} {body}", code == 200 and [r["run_id"] for r in body["runs"]] == [S.RUN])
        code, body = routes.handle(ctx_, "GET", f"orchestra/{S.RUN}/coach", {}, {})
        ctx.check(f"GET orchestra/<run>/coach: the card, got {code}", code == 200 and len(body["suggestions"]) == 1)
        from tests.helpers import first_run_pack as FR
        run = SimpleNamespace(run_dir=h.repo / ".halo" / "orchestra" / S.RUN, repo=h.repo, coach={})
        lines = FR.module("first_run/coach_step.py").card(run)
        ctx.check(f"the guided first run's step 6 shows the pack's card (halo coach as a child), got {lines}",
                  lines[1].startswith("coach: 1 suggestion(s)") and "[tools-1-WebFetch]" in lines[2]
                  and len(run.coach.get("suggestions") or []) == 1)


@test
def test_halo_pack_test_passes_on_both_shipped_packs(ctx: Ctx):
    from halo_harness.packs.cli_test import cmd
    with PacksHome():
        for name in ("coach", "first-run"):
            out = io.StringIO()
            with contextlib.redirect_stdout(out), contextlib.redirect_stderr(out):
                rc = cmd([str(CP.PACK.parent / name)])
            ctx.check(f"halo pack test {name}: 0, got {rc} {out.getvalue()[-300:]!r}", rc == 0)


if __name__ == "__main__":
    ctx = Ctx()
    results, passed, failed, skipped = run_all(TESTS, ctx)
    sys.exit(print_results(results, passed, failed, skipped, label="coach pack tests"))
