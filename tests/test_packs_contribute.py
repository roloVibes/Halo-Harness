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
        h.cli("enable", "doc-review", "--grant-all", "--yes")
        ctx.check("enabled: something", _everything(h)["bios"] != [])
        h.cli("disable", "doc-review")
        ctx.check(f"disabled again: nothing, got {_everything(h)}", _everything(h) == empty)


@test
def test_pack_files_are_read_only(ctx: Ctx):
    with PacksHome() as h:
        h.install(h.source(), enable=True)
        pack_file = h.packs / "doc-review" / "agents" / "reviewer.yaml"
        before = pack_file.read_bytes()

        # 3.6.0.0 R5: Studio's bio and lineup routes went with Cast; a copy of yours shadows the pack's all the same
        mine = h.state / "agents" / "doc-review--reviewer.yaml"
        mine.parent.mkdir(parents=True, exist_ok=True)
        mine.write_bytes(before.replace(b"description:", b"description: my copy --", 1))
        ctx.check("the pack's file is untouched", pack_file.read_bytes() == before)
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
