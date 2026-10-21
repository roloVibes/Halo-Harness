"""tests.test_packs_contribute -- what an enabled pack adds (Halo 3.2.0.0 R1,
halo_harness/packs/contribute.py): its bio and lineup under `<id>--<name>`
with `_pack` and `_name`, read in place, the lineup's own bios qualified;
its skill, command, plugin agent and MCP server with their names; the MCP
server only once `mcp:lint` is granted, the hooks only once `hooks` is;
`halo agents` / `halo teams` list them; Studio answers 409 to a write or a
delete of a pack's bio or lineup; a session built here carries the pack's root; and a
disabled pack adds nothing at all.
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from tests.helpers.packs_home import PacksHome  # noqa: E402
from tests.helpers.runner import Ctx, new_registry, print_results, run_all  # noqa: E402

test, TESTS = new_registry()


def _roots(h):
    from halo_harness.packs.contribute import pack_plugin_roots
    return pack_plugin_roots(cwd=h.repo)


def _everything(h) -> dict:
    """Every name a session would see from the pack."""
    from halo_harness import agents_yaml as A
    from halo_harness import teams_yaml as T
    from halo_harness.commands.registry import Registry
    from halo_harness.config.agents_md import discover_agents
    from halo_harness.config.plugins import discover_plugin_mcp_servers
    from halo_harness.packs.contribute import hook_roots
    from halo_harness.hooks import load_plugin_hooks
    roots = _roots(h)
    reg = Registry.discover(h.repo, h.home, plugin_roots=roots)
    names = {c.name for c in reg.all()}
    return {"bios": [n for n in A.list_agent_bios(cwd=h.repo) if n.startswith("doc-review--")],
            "lineups": [n for n in T.list_team_templates(cwd=h.repo) if n.startswith("doc-review--")],
            "roots": roots, "commands": sorted(n for n in names if n.startswith("doc-review:")),
            "agents": [n for n in discover_agents(h.repo, plugin_roots=roots or None) if n == "doc-helper"],
            "mcp": sorted(discover_plugin_mcp_servers(env={}, extra_roots=roots)[0]),
            "hooks": [e for r in hook_roots(roots) for e in load_plugin_hooks(r)]}


@test
def test_an_enabled_packs_bio_and_lineup_are_listed_under_its_name(ctx: Ctx):
    from halo_harness import agents_yaml as A
    from halo_harness import teams_yaml as T
    with PacksHome() as h:
        h.install(h.source(), enable=True)
        found = A.find_agent_bio_path("doc-review--writer", cwd=h.repo)
        ctx.check(f"read in place from the pack's folder, got {found}",
                  found and found[1] == "pack:doc-review" and found[0] == h.packs / "doc-review" / "agents" / "writer.yaml")
        bio = A.resolve_agent_bio("doc-review--writer", cwd=h.repo)
        ctx.check(f"_pack and _name attached, extends qualified, got {bio.get('_pack')} {bio.get('extends')}",
                  bio["_pack"] == "doc-review" and bio["_name"] == "writer" and bio["extends"] == "doc-review--reviewer"
                  and bio["tools"]["allow"] == ["Read", "Edit", "Write"] and bio["models"]["effort"] == "medium")
        lineup = T.resolve_team_template("doc-review--review", cwd=h.repo)
        ctx.check(f"the lineup names the pack's own bios, got {lineup['agents']}",
                  [e["agent"] for e in lineup["agents"]] == ["doc-review--writer", "doc-review--reviewer"])
        ctx.check(f"it validates, got {T.validate_team_template(lineup, name='doc-review--review', cwd=h.repo)}",
                  T.validate_team_template(lineup, name="doc-review--review", cwd=h.repo) == [])
        ctx.check("a bare name does not reach a pack file", A.find_agent_bio_path("writer", cwd=h.repo) is None)
        ctx.check("the qualified name meets the name rule", A.is_valid_agent_name("doc-review--writer"))
        ctx.check("not counted as yours", "doc-review--writer" not in A.list_agent_bios(cwd=h.repo, include_templates=False))
        from halo_harness.teams_cli_views import agent_group_lines, lineup_rows
        lines = agent_group_lines(cwd=h.repo)
        ctx.check(f"halo agents groups them under the pack, got {lines[:3]}", "Pack doc-review agents:" in lines
                  and any(ln.startswith("  doc-review--reviewer (reviewer)") for ln in lines))
        rows = {r["name"]: r["scope"] for r in lineup_rows(cwd=h.repo)}
        ctx.check(f"halo teams lists the lineup as the pack's, got {rows.get('doc-review--review')}",
                  rows.get("doc-review--review") == "pack doc-review")


@test
def test_skills_commands_agents_and_grants(ctx: Ctx):
    with PacksHome() as h:
        h.install(h.source(), enable=True)
        got = _everything(h)
        ctx.check(f"the skill and the command are namespaced, got {got['commands']}",
                  got["commands"] == ["doc-review:check-links", "doc-review:review"])
        ctx.check("the plugin agent loads", got["agents"] == ["doc-helper"])
        ctx.check(f"no MCP server and no hooks before the grants, got {got['mcp']} {got['hooks']}",
                  got["mcp"] == [] and got["hooks"] == [])
        from halo_harness.packs.discover import find
        from halo_harness.packs.grants import enable
        enable(find("doc-review", cwd=h.repo), grant=["mcp:lint", "hooks"])
        got = _everything(h)
        ctx.check(f"granted: the server as plugin_doc-review_lint and the hook, got {got['mcp']} {got['hooks']}",
                  got["mcp"] == ["plugin_doc-review_lint"] and got["hooks"] == ["PostToolUse"])


@test
def test_a_disabled_pack_contributes_nothing(ctx: Ctx):
    with PacksHome() as h:
        h.install(h.source())
        empty = {"bios": [], "lineups": [], "roots": [], "commands": [], "agents": [], "mcp": [], "hooks": []}
        ctx.check(f"installed, never enabled: nothing, got {_everything(h)}", _everything(h) == empty)
        h.cli("enable", "doc-review", "--grant-all")
        ctx.check("enabled: something", _everything(h)["bios"] != [])
        h.cli("disable", "doc-review")
        ctx.check(f"disabled again: nothing, got {_everything(h)}", _everything(h) == empty)
        from halo_harness.where.yaml_files import bio_folder_rows
        ctx.check("config where shows no pack folder for it", all(r["scope"] != "pack" for r in bio_folder_rows(h.repo, h.state)))


@test
def test_pack_files_are_read_only(ctx: Ctx):
    from halo_harness.studio import api
    with PacksHome() as h:
        h.install(h.source(), enable=True)
        pack_file = h.packs / "doc-review" / "agents" / "reviewer.yaml"
        before = pack_file.read_bytes()

        def call(fn, name, body=None, query=None):
            req = api.Request(method="PUT", path="/", query=query or {}, body=body or {}, cwd=h.repo, state_dir=h.state,
                              params={"name": name})
            return fn(req)
        status, data = call(api.put_bio, "doc-review--reviewer", {"raw": {"description": "changed"}})
        ctx.check(f"PUT a pack bio: 409, got {status} {data}", status == 409 and "pack doc-review bio" in data["error"])
        status, _data = call(api.delete_bio, "doc-review--reviewer")
        ctx.check("DELETE a pack bio: 409", status == 409)
        status, _data = call(api.put_lineup, "doc-review--review", {"raw": {"agents": []}})
        ctx.check("PUT a pack lineup: 409", status == 409)
        ctx.check("the pack's file is untouched", pack_file.read_bytes() == before)
        status, data = call(api.put_bio, "doc-review--reviewer", {"raw": {"description": "my copy"}}, {"duplicate": "1"})
        mine = h.state / "agents" / "doc-review--reviewer.yaml"
        ctx.check(f"duplicate saves your own copy, which wins, got {status}", status == 200 and mine.is_file()
                  and pack_file.read_bytes() == before)
        from halo_harness.packs.doctor import problems
        ctx.check("doctor names your copy shadowing the pack's", any("doc-review--reviewer" in p["text"] and "yours is used" in p["text"]
                                                                   for p in problems(cwd=h.repo)))
        from halo_harness.packs.names import read_only_source
        ctx.check("read_only_source: template and pack:*", read_only_source("template") and read_only_source("pack:x")
                  and not read_only_source("user") and not read_only_source("project"))


@test
def test_a_session_built_here_carries_the_packs_root(ctx: Ctx):
    with PacksHome() as h:
        h.install(h.source(), enable=True)
        from halo_harness import headless
        build = headless.build_session(cwd=h.repo, model_ref_raw="or:deepseek/deepseek-v4.1-flash", bare=False,
                                       print_mode=True)
        try:
            root = str(h.packs / "doc-review")
            ctx.check(f"Session.plugin_roots has the pack's root, got {build.session.plugin_roots}",
                      root in [str(r) for r in build.session.plugin_roots])
            ctx.check("the pack's command is a slash command", build.command_registry.resolve("doc-review:review") is not None)
        finally:
            for closer in ("close_runtimes",):
                getattr(build.session, closer, lambda: None)()
            if build.mcp_manager is not None:
                build.mcp_manager.close_all()


if __name__ == "__main__":
    ctx = Ctx()
    results, passed, failed, skipped = run_all(TESTS, ctx)
    sys.exit(print_results(results, passed, failed, skipped))
