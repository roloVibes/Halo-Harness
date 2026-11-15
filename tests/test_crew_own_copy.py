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
            ctx.check(f"{kind}: yours, the same fields as the starter but its name and where it came from",
                      mine["_scope"] == "yours" and {**store.clean(starter), "name": new, "from": f"starter {name}"} == store.clean(mine))
            ctx.check(f"{kind}: the copy reads clean, got {store.PROBLEMS[kind](store.clean(mine), name=new)}",
                      not store.PROBLEMS[kind](store.clean(mine), name=new))
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


@test
def test_a_packs_map_copy_says_where_it_came_from_and_when_its_agents_are_gone(ctx: Ctx):
    """The judge's item 8a: a copy of a pack's map records `from: pack <pack>--<name>`; after `halo pack disable` the
    copy names agents no file answers, and `halo maps list` and `halo doctor` say so in one line."""
    from halo_harness import doctor
    from halo_harness.crew import store
    from halo_harness.maps_cli import cmd_maps
    from halo_harness.packs.grants import disable
    from tests.helpers.packs_home import PacksHome
    from tests.test_packs_crew import _more_pack
    with PacksHome() as h:
        h.install(_more_pack(h), enable=True)
        path, new = store.own_copy("map", "more-pack--base", cwd=h.repo, state_dir=h.state)
        mine = store.load("map", new, cwd=h.repo, state_dir=h.state)
        ctx.check(f"my-base, from the pack's map, got {new} {mine.get('from')!r}",
                  new == "my-base" and mine["from"] == "pack more-pack--base" and store.from_note(mine) == "pack more-pack--base")
        ctx.check("while the pack runs, nothing is missing", store.dangling_line(mine, cwd=h.repo, state_dir=h.state) == ""
                  and not doctor._dangling_maps(h.repo))
        ok, _lines = disable("more-pack")
        ctx.check("the pack is disabled", ok)
        line = store.dangling_line(store.load("map", new, cwd=h.repo, state_dir=h.state), cwd=h.repo, state_dir=h.state)
        ctx.check(f"one line naming the gone agent and the pack, got {line!r}",
                  line == "map my-base names agent more-pack--fetcher, which no longer exists (a copy of more-pack--base: "
                          "is that pack still enabled? halo pack list): its boxes for them do nothing")
        rc, out, _err = _cli(cmd_maps, ["list"], h.repo)
        ctx.check(f"halo maps list says it under the map, got {out!r}", rc == 0 and f"    {line}" in out)
        ctx.check(f"halo doctor says it, got {doctor._dangling_maps(h.repo)}", doctor._dangling_maps(h.repo) == [("my-base", line)])


@test
def test_a_copy_a_nearer_project_file_would_shadow_is_refused(ctx: Ctx):
    """The judge's item 8b: in a trusted project with `.halo/crew/agents/my-coder.yaml`, `copy coder` would write a file
    the project's shadows (edit would open the project's); it says so and names --as, and writes nothing."""
    from halo_harness.agents_cli import cmd_agents
    from halo_harness.crew import store
    from tests.helpers.trust_dir import trust
    with ConfigHome() as h:
        trust(h.repo)
        proj = h.repo / ".halo" / "crew" / "agents" / "my-coder.yaml"
        proj.parent.mkdir(parents=True)
        proj.write_text("format: agent/1\nname: my-coder\ndoes: the project's\nmodel: auto\nuses: [read]\ncareful: ask-changes\n",
                        encoding="utf-8")
        rc, out, err = _cli(cmd_agents, ["copy", "coder"], h.repo)
        ctx.check(f"refused in one line naming --as, got {rc} {out!r} {err!r}",
                  rc == 1 and not out and "this project has an agent named my-coder" in err and "--as" in err
                  and not (h.state / "crew" / "agents" / "my-coder.yaml").exists())
        rc, out, _err = _cli(cmd_agents, ["copy", "coder", "--as", "own-coder"], h.repo)
        ctx.check(f"--as writes it, got {rc} {out!r}", rc == 0 and store.find("agent", "own-coder", cwd=h.repo)[1] == "yours")


@test
def test_the_model_pickers_agents_source_lists_the_starters(ctx: Ctx):
    """The judge's item 1: `/model`'s Agents source (Ctrl+A) read `rows("agents")`, a KeyError a bare `except` turned
    into "no agents". A fresh home lists every starter agent; a programming error is not swallowed."""
    from halo_harness.crew import store
    from halo_harness.tui.dialogs import model_picker as M
    with ConfigHome() as h:
        got = M._agent_picker_rows(cwd=h.repo, state_dir=h.state)
        starters = sorted(p.stem for p in (store.SHIPPED / "agents").glob("*.yaml"))
        ctx.check(f"every starter agent, got {[r['name'] for r in got]}",
                  len(starters) >= 5 and sorted(r["name"] for r in got) == starters)
        ctx.check("each row has its fields", all(set(r) == {"name", "description", "preferred_model", "tools_summary"}
                                                 and r["description"] for r in got))
        real = store.rows
        try:
            store.rows = lambda *a, **k: (_ for _ in ()).throw(KeyError("agents"))
            try:
                M._agent_picker_rows(cwd=h.repo, state_dir=h.state)
                raised = False
            except KeyError:
                raised = True
        finally:
            store.rows = real
        ctx.check("a programming error (KeyError) is not hidden as no agents", raised)


@test
def test_picking_an_agent_row_uses_its_model_for_the_session(ctx: Ctx):
    """The judge's item 9: the Agents source dismisses `{"agent", "model"}`; `_apply_model` sets that model (a bio's
    old behaviour), and an agent with no model of its own leaves the session's model alone and says so."""
    from types import SimpleNamespace
    from halo_harness.tui.slash import _apply_model
    with ConfigHome() as h:
        sets, notes = [], []
        app = SimpleNamespace(cwd=h.repo, notify=lambda msg, **kw: notes.append(msg),
                              controller=SimpleNamespace(set_model=lambda ref: sets.append(ref) or None, session=None,
                                                         state_dir=h.state))
        _apply_model(app, {"agent": "coder", "model": "or:v/eyes"})
        ctx.check(f"the agent's model is set as a string, got {sets} {notes}",
                  sets == ["or:v/eyes"] and notes and notes[-1].startswith("Model set to or:v/eyes"))
        _apply_model(app, {"agent": "planner", "model": ""})
        ctx.check(f"no model of its own: nothing set, one line, got {sets} {notes[-1]!r}",
                  sets == ["or:v/eyes"] and notes[-1].startswith("planner has no model of its own"))
        _apply_model(app, "or:v/other")
        ctx.check("a plain ref still works", sets == ["or:v/eyes", "or:v/other"])


if __name__ == "__main__":
    ctx = Ctx()
    results, passed, failed, skipped = run_all(TESTS, ctx)
    sys.exit(print_results(results, passed, failed, skipped))
