"""tests.test_crew_own_copy -- your own copy of a starter to edit (Halo 3.6.0.0 R5d, `own_copy`).

`crew/store.own_copy(kind, name, as_name=)` writes the file as Halo reads it under `my-<name>` (or the name given) in
~/.halo/crew/<kind>s/ and never over a file of yours; `halo agents | workflows | maps copy <name> [--as <new>]` say so
in one line; `edit` on a starter names the copy verb. A scratch home, no model call.

Run: python -m tests.test_crew_own_copy
"""

from __future__ import annotations

import contextlib
import io
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from tests.helpers.config_seed import ConfigHome  # noqa: E402
from tests.helpers.runner import Ctx, new_registry, print_results, run_all  # noqa: E402

test, TESTS = new_registry()


def _cli(fn, argv, cwd: Path) -> "tuple[int, str, str]":
    out, err = io.StringIO(), io.StringIO()
    old = os.getcwd()
    os.chdir(cwd)
    try:
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
            rc = fn(argv)
    finally:
        os.chdir(old)
    return rc, out.getvalue(), err.getvalue()


@test
def test_a_starters_copy_is_yours_and_reads_the_same(ctx: Ctx):
    from halo_harness.crew import store
    with ConfigHome() as h:
        for kind, name in (("agent", "coder"), ("workflow", "code"), ("map", "starter")):
            path, new = store.own_copy(kind, name, cwd=h.repo, state_dir=h.state)
            ctx.check(f"{kind} {name}: my-{name} in your folder, got {new} {path}",
                      new == f"my-{name}" and path == h.state / "crew" / f"{kind}s" / f"my-{name}.yaml" and path.is_file())
            mine, starter = store.load(kind, new, cwd=h.repo, state_dir=h.state), store.load(kind, name, cwd=h.repo, state_dir=h.state)
            ctx.check(f"{kind}: yours, the same fields as the starter but its name",
                      mine["_scope"] == "yours" and {**store.clean(starter), "name": new} == store.clean(mine))
        try:
            store.own_copy("agent", "coder", cwd=h.repo, state_dir=h.state)
            again = ""
        except ValueError as e:
            again = str(e)
        ctx.check(f"never over a file of yours, got {again!r}", "already" in again and "--as" in again)
        path, new = store.own_copy("agent", "coder", as_name="fixer", cwd=h.repo, state_dir=h.state)
        ctx.check("--as names it", new == "fixer" and store.load("agent", "fixer", cwd=h.repo, state_dir=h.state) is not None)
        for bad in ("nope", ):
            try:
                store.own_copy("map", bad, cwd=h.repo, state_dir=h.state)
                said = ""
            except ValueError as e:
                said = str(e)
            ctx.check(f"a name with nothing behind it is one line, got {said!r}", said == "no map named 'nope' to copy (halo maps list)")


@test
def test_the_three_clis_copy_and_edit_names_the_verb(ctx: Ctx):
    from halo_harness.agents_cli import cmd_agents
    from halo_harness.maps_cli import cmd_maps
    from halo_harness.workflows_cli import cmd_workflows
    with ConfigHome() as h:
        for fn, kind, name in ((cmd_agents, "agent", "reviewer"), (cmd_workflows, "workflow", "review"), (cmd_maps, "map", "ship-it")):
            rc, out, err = _cli(fn, ["copy", name, "--as", f"own-{name}"], h.repo)
            ctx.check(f"halo {kind}s copy: exit 0 and one line, got {rc} {out!r} {err!r}", rc == 0 and not err
                      and out.startswith("wrote ") and str(h.state) in out and f"(a copy of {name}); halo {kind}s edit own-{name} opens it" in out)
            rc, out, err = _cli(fn, ["copy", name, "--as", f"own-{name}"], h.repo)
            ctx.check(f"halo {kind}s copy twice: exit 1, the line, got {rc} {err!r}", rc == 1 and "already" in err)
        from halo_harness import crew_cli_parts as P
        seen = {}
        P_open = None
        try:
            import halo_harness.studio_edit_cli as E
            P_open, E.open_in_studio = E.open_in_studio, lambda kind, name, **kw: seen.setdefault("opened", (kind, name)) and 0
            rc, out, _err = _cli(lambda argv: P.edit("map", "starter", h.repo), [], h.repo)
        finally:
            if P_open is not None:
                E.open_in_studio = P_open
        ctx.check(f"edit on a starter names the copy verb, got {out!r}",
                  "starter is a starter (read-only): halo maps copy starter makes yours (my-starter)" in out)


if __name__ == "__main__":
    ctx = Ctx()
    results, passed, failed, skipped = run_all(TESTS, ctx)
    sys.exit(print_results(results, passed, failed, skipped))
