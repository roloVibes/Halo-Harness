"""tests.test_crew_old_files -- Halo 3.6.0.0 R5: every session runs on a map, and the old files get one line, once
(halo_harness/crew/old_files.py, live/crew_attention.py `crew_old`, doctor's `old_files` row, headless `--team`).

1. nothing old: no line, no Attention row, no doctor row;
2. old lineups / bios / squares under ~/.halo and this project's .halo: one line naming them and how many files,
   said once in the terminal, an Attention row until it is set aside (then gone for good), doctor's row while the
   folders hold files -- and every file byte for byte as it was (nothing deleted, converted or rewritten);
3. 3.6.0.0 R5 fix: Halo's own unchanged copies of its shipped lineups and bios are not named; a changed one is, and a
   configured `team:` is named with what to do;
4. the old `--team <name>` says it is gone in one line and the session runs on the map in use (the starter);
5. 3.6.0.0 R5c (the judge's S5): old_stock.txt holds every version Halo ever shipped -- today's files and three older
   copies (tests/fixtures/old_copies, from git history) are Halo's own: no line.
Run: python -m tests.test_crew_old_files
"""
from __future__ import annotations

import io
import sys
from contextlib import redirect_stderr
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from tests.helpers import catalog_facts_seed as S  # noqa: E402
from tests.helpers.runner import Ctx, new_registry, print_results, run_all  # noqa: E402

test, TESTS = new_registry()


def _rows(state: Path) -> list:
    from halo_harness.live.crew_attention import rows
    return [r for r in rows(state, {"id": "h", "name": "this harness", "local": True}, {}, 1.0) if r["kind"] == "crew_old"]


def _doctor(root: Path) -> list:
    from halo_harness.doctor import _check_entries
    return [line for rid, line in _check_entries(cwd=root) if rid == "old_files"]


@test
def test_nothing_old_says_nothing(ctx: Ctx):
    from halo_harness.crew import old_files
    with S.home("crew-old-none-") as (root, state):
        ctx.check("no line", old_files.line(root, state) == "" and old_files.once(root, state) == "")
        ctx.check("no Attention row", _rows(state) == [])
        ctx.check("no doctor row", _doctor(root) == [])


@test
def test_old_files_one_line_once_and_never_touched(ctx: Ctx):
    from halo_harness.crew import old_files
    from halo_harness.live.crew_attention import open_target, set_aside
    with S.home("crew-old-some-") as (root, state):
        files = {state / "teams" / "mine.yaml": b"name: mine\nroles: {}\n", state / "agents" / "coder.yaml": b"name: coder\r\n",
                 root / "repo" / ".halo" / "workflows" / "fix.yaml": b"name: fix\n"}
        for p, data in files.items():
            p.parent.mkdir(parents=True, exist_ok=True)
            p.write_bytes(data)
        repo = root / "repo"
        text = old_files.line(repo, state)
        ctx.check(f"one line naming the folders and the count, got {text!r}",
                  "~/.halo/teams" in text and "~/.halo/agents" in text and "this project's .halo/workflows" in text
                  and "(3 files of yours)" in text and "~/.halo/crew/" in text and "~/.halo/workflows" not in text)
        out = io.StringIO()
        old_files.terminal_once(repo, state, out=out)
        old_files.terminal_once(repo, state, out=out)
        ctx.check(f"the terminal says it once, got {out.getvalue()!r}", out.getvalue().count("Halo no longer uses") == 1)
        got = _rows(state)
        ctx.check(f"an Attention row with the line, got {got}", len(got) == 1 and "Halo no longer uses" in got[0]["detail"]
                  and set(got[0]["keys"]) == {"a", "o"})
        ctx.check("its o opens the Map", open_target(got[0]) == {"section": "agents", "view": "map"})
        set_aside(state, got[0])
        ctx.check("set aside: gone for good", _rows(state) == [])
        ctx.check(f"doctor repeats it while the folders hold files, got {_doctor(repo)}",
                  len(_doctor(repo)) == 1 and "Halo no longer uses" in _doctor(repo)[0])
        ctx.check("every old file is byte for byte as it was", all(p.read_bytes() == data for p, data in files.items()))


@test
def test_halos_own_copies_say_nothing_and_a_set_team_is_named(ctx: Ctx):
    """3.6.0.0 R5 fix: the shipped lineups and bios Halo itself copied into ~/.halo (unchanged, line ends aside) are
    not the user's: no line, no doctor row. One the user changed is named; a configured `team:` is named with what to
    do, in one line, even with no old file at all."""
    from halo_harness.crew import old_files
    from halo_harness.theme import set_config_value
    shipped = Path(old_files.__file__).resolve().parent.parent / "templates"
    with S.home("crew-old-stock-") as (root, state):
        for kind in ("teams", "agents"):
            (state / kind).mkdir(parents=True)
            for src in sorted((shipped / kind).glob("*.yaml")):
                (state / kind / src.name).write_bytes(src.read_bytes().replace(b"\n", b"\r\n"))  # as Windows wrote them
        ctx.check(f"Halo's own copies: no line, got {old_files.line(root, state)!r}", old_files.line(root, state) == "")
        ctx.check("3.5's auto lineup, which left the package, is still known as Halo's own (its hash)",
                  any(x.startswith("teams/auto.yaml ") for x in old_files._shipped()))
        ctx.check("no doctor row", _doctor(root) == [])
        auto = state / "teams" / "standard.yaml"  # 3.6.0.0 R5b: auto.yaml left the package (crew/plain); its hash stays
        auto.write_bytes(auto.read_bytes() + b"# mine now\n")
        text = old_files.line(root, state)
        ctx.check(f"a copy the user changed is theirs: named, got {text!r}", "~/.halo/teams (1 file of yours)" in text)
        auto.unlink()
        set_config_value("team", "quality")
        text = old_files.line(root, state)
        ctx.check(f"a configured team: named with what to do, got {text!r}", "team: quality" in text
                  and "halo maps use <name>" in text and "\n" not in text)


@test
def test_every_shipped_version_is_halos_own(ctx: Ctx):
    """3.6.0.0 R5c (the judge's S5): Halo copied its starters once and never overwrote them, so a long-time user holds
    an older version. old_stock.txt is written from git history (scripts/old_stock.py): today's files and three older
    ones (two reviewer bios, one lineup) are in it, and a home holding the old copies gets no line."""
    import hashlib
    from halo_harness.crew import old_files
    shipped = Path(old_files.__file__).resolve().parent.parent / "templates"
    stock = old_files._shipped()
    def sha(p: Path) -> str:
        return hashlib.sha256(p.read_bytes().replace(b"\r\n", b"\n")).hexdigest()
    missing = [f"{k}/{p.name}" for k in ("teams", "agents", "workflows") for p in sorted((shipped / k).glob("*.yaml"))
               if f"{k}/{p.name} {sha(p)}" not in stock]
    ctx.check(f"today's shipped lineups, bios and squares are all in old_stock.txt, missing {missing}", not missing)
    old = Path(__file__).resolve().parent / "fixtures" / "old_copies"
    copies = {"agents/reviewer.yaml": ["reviewer-58bad0f8.yaml", "reviewer-b1dc8997.yaml"],
              "teams/halo-dev-cycle.yaml": ["halo-dev-cycle-58bad0f8.yaml"]}
    for where, files in copies.items():
        for f in files:
            data = (old / f).read_bytes()
            now = (shipped / where).read_bytes() if (shipped / where).is_file() else b""
            ctx.check(f"{f} is an older version than today's {where}", data.replace(b"\r\n", b"\n") != now.replace(b"\r\n", b"\n"))
            with S.home("crew-old-version-") as (root, state):
                (state / where).parent.mkdir(parents=True)
                (state / where).write_bytes(data)
                ctx.check(f"a home holding {f} as {where}: Halo's own copy, no line, got {old_files.line(root, state)!r}",
                          old_files.line(root, state) == "")


@test
def test_the_old_team_flag_is_one_line_and_the_map_in_use(ctx: Ctx):
    from halo_harness import headless
    with S.home("crew-old-team-") as (root, state):
        repo = root / "repo"
        repo.mkdir()
        err = io.StringIO()
        with redirect_stderr(err):
            built = headless.build_session(cwd=repo, model_ref_raw="or:v/eyes", print_mode=True,
                                           cli_flags={"team": "halo-dev-cycle"})
        s = built.session
        try:
            tc = s.team_control
            ctx.check(f"the session runs on Auto, got {getattr(getattr(tc, 'map', None), 'name', None)}",
                      getattr(tc, "is_map", False) and tc.map.name == "auto")
            lines = [ln for ln in err.getvalue().splitlines() if "--team" in ln]
            ctx.check(f"one line: --team is gone, the map in use, got {lines}",
                      len(lines) == 1 and "--team is gone" in lines[0] and "auto" in lines[0] and "starter" not in lines[0] and "--map" in lines[0])
        finally:
            s.close_runtimes()


if __name__ == "__main__":
    ctx = Ctx()
    results, passed, failed, skipped = run_all(TESTS, ctx)
    sys.exit(print_results(results, passed, failed, skipped))
