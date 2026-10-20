"""tests.test_coach_library_cli -- Halo 3.1.6.0 R3: `halo coach library`
(halo_harness/coach_library_cli.py), caught by `halo coach` before its run
parse, over a seeded run in a scratch home (tests/helpers/coach_seed.py):

1. no entry: one line naming how an entry is born;
2. after `halo coach <run> --apply ID --yes` (which names the entry): `list`
   (id, when, project, lineup, source, title; `--json`), `show` (EXPERIENCE.md
   and the files it keeps), `(undone)` once the apply is undone;
3. `forget`: y/N (no answer deletes nothing), `--yes`; an unknown entry exits 1,
   a word that is not an entry id exits 2; `fetch` with no hub here exits 3.
Run: python -m tests.test_coach_library_cli
"""
from __future__ import annotations

import io
import json
import sys
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from tests.helpers.provider_env_defaults import ensure_scoped_state_dir_once
from tests.helpers.runner import Ctx, new_registry, print_results, run_all
from tests.test_orchestra_coach import Home

ensure_scoped_state_dir_once()
test, TESTS = new_registry()
DENIED = [{"tool_name": "WebFetch", "reason": "denied by rule 'WebFetch'"}]


def cli(argv, stdin: str = ""):
    from halo_harness.coach_cli import cmd_coach
    o, e = io.StringIO(), io.StringIO()
    saved = sys.stdin
    sys.stdin = io.StringIO(stdin)
    try:
        with redirect_stdout(o), redirect_stderr(e):
            rc = cmd_coach(argv)
    finally:
        sys.stdin = saved
    return rc, o.getvalue(), e.getvalue()


def _applied(h):
    from tests.helpers import coach_seed as S
    run = S.orchestra_run(h.root, [S.lane(1, bio="coach-deny", denied=DENIED)])
    rc, out, err = cli([str(run), "--apply", "tools-1-WebFetch", "--yes"])
    return run, rc, out, err


@test
def test_an_empty_library_says_how_an_entry_is_born(ctx: Ctx):
    with Home():
        rc, out, _ = cli(["library"])
        ctx.check(f"one line, exit 0, got {rc} {out!r}", rc == 0 and out.strip().startswith("the library is empty: an entry "
                  "is born when a coach card's Apply writes") and len(out.strip().splitlines()) == 1)
        rc, out, _ = cli(["library", "list", "--json"])
        ctx.check("--json: no entries", rc == 0 and json.loads(out) == {"entries": []})


@test
def test_list_and_show_an_entry_after_an_apply(ctx: Ctx):
    from halo_harness.orchestra import coach_library as L
    from halo_harness.orchestra.coach_record import undo
    with Home() as h:
        run, rc, out, err = _applied(h)
        eid = L.entries(h.state)[0]["id"]
        ctx.check(f"the apply names its entry, got {rc} {out[-200:]!r} {err!r}", rc == 0
                  and f"the library keeps it as {eid} (halo coach library show {eid})" in out)
        rc, out, _ = cli(["library"])
        row = out.strip().splitlines()
        title = L.read(eid, h.state)["title"]
        ctx.check(f"list: one row with id, when, project, lineup, source, title, got {row}", rc == 0 and len(row) == 1
                  and row[0].startswith(f"{eid}  20") and row[0].endswith(f"  {h.root.resolve().name}  -  apply  {title}"))
        rc, out, _ = cli(["library", "list", "--json"])
        ctx.check("list --json carries entry.json", rc == 0 and json.loads(out)["entries"][0]["id"] == eid)
        rc, out, _ = cli(["library", "show", eid])
        ctx.check(f"show: the head, EXPERIENCE.md and the files, got {out[:300]!r}", rc == 0
                  and out.startswith(f"{eid}  20") and "cited for runs like it" in out and "## When it applies" in out
                  and "## Lessons" in out and "files kept in " in out and "  agents/coach-deny.yaml  (home bio coach-deny, kept)" in out)
        rc, out, _ = cli(["library", "show", eid, "--json"])
        got = json.loads(out)
        ctx.check("show --json: entry, experience, files", rc == 0 and got["entry"]["id"] == eid
                  and got["experience"].startswith("# ") and list(got["files"]) == ["agents/coach-deny.yaml"])
        undo(None)
        rc, out, _ = cli(["library"])
        ctx.check(f"an undone entry is marked, got {out!r}", rc == 0 and out.strip().endswith("(undone)"))
        rc, out, _ = cli(["library", "show", eid])
        ctx.check("show says it is never cited", "undone (kept, never cited)" in out)


@test
def test_forget_asks_and_the_errors(ctx: Ctx):
    from halo_harness.orchestra import coach_library as L
    with Home() as h:
        _applied(h)
        eid = L.entries(h.state)[0]["id"]
        rc, out, _ = cli(["library", "forget", eid], stdin="n\n")
        ctx.check(f"no: nothing deleted, got {rc} {out!r}", rc == 1 and "[y/N]" in out and "nothing deleted" in out
                  and L.read(eid, h.state) is not None)
        rc, out, _ = cli(["library", "forget", eid], stdin="y\n")
        ctx.check(f"y deletes the folder, got {rc} {out!r}", rc == 0 and f"forgot {eid}" in out and not L.entry_dir(eid, h.state).exists())
        rc, _, err = cli(["library", "show", eid])
        ctx.check(f"an unknown entry exits 1, got {rc} {err!r}", rc == 1 and "no entry" in err)
        rc, _, err = cli(["library", "forget", "nope"])
        ctx.check(f"not an entry id: exit 2, got {rc} {err!r}", rc == 2 and "not an entry id" in err)
        from halo_harness.orchestra.coach_record import undo
        undo(None)  # the bio as before, so the card applies again
        _applied(h)
        eid = L.entries(h.state)[0]["id"]
        rc, out, _ = cli(["library", "forget", eid, "--yes"])
        ctx.check("--yes skips the y/N", rc == 0 and "[y/N]" not in out and L.read(eid, h.state) is None)
        rc, _, err = cli(["library", "fetch", "kali", "e-20261020-0a1f"])
        ctx.check(f"fetch with no hub here exits 3, got {rc} {err!r}", rc == 3 and "none runs here" in err)
        rc, out, _ = cli(["library", "--help"])
        ctx.check("--help names the four verbs", rc == 0 and all(v in out for v in ("list", "show", "forget", "fetch")))
        from types import SimpleNamespace
        from halo_harness.commands.builtins import _cmd_coach
        from halo_harness.orchestra.coach_record import undo
        undo(None)
        _applied(h)
        eid = L.entries(h.state)[0]["id"]
        facade = SimpleNamespace(session=SimpleNamespace(cwd=h.root), cwd=h.root)
        ctx.check("/coach library lists it (no --repo added)", _cmd_coach("library", facade).startswith(eid))
        said = _cmd_coach(f"library forget {eid}", facade)
        ctx.check(f"/coach library forget without --yes deletes nothing, got {said!r}", "nothing deleted yet" in said
                  and L.read(eid, h.state) is not None)
        ctx.check("/coach library forget --yes deletes it", f"forgot {eid}" in _cmd_coach(f"library forget {eid} --yes", facade)
                  and L.read(eid, h.state) is None)


if __name__ == "__main__":
    ctx = Ctx()
    results, passed, failed, skipped = run_all(TESTS, ctx)
    sys.exit(print_results(results, passed, failed, skipped, label="coach library cli tests"))
