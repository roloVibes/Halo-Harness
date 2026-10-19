"""tests.test_config_where -- `halo config where [--json]` and `/config where`
(Halo 3.1.1.0 R2): over a seeded home and repo, one row per file of every
kind with what it sets; the precedence column follows the resolvers (a
clash moves when the file the resolver prefers goes away); `--json` is the
same rows; an env file, a `.env` and a secret-bearing config.json show the
variable and key NAMES only, never a value.
"""

from __future__ import annotations

import contextlib
import io
import json
import sys
from pathlib import Path
from types import SimpleNamespace

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from tests.helpers.config_seed import CONFIG_SECRET, DOT_ENV_VALUE, FAKE_KEY, ConfigHome, by, seed  # noqa: E402
from tests.helpers.runner import Ctx, new_registry, print_results, run_all  # noqa: E402

test, TESTS = new_registry()


def _rows(h):
    from halo_harness.config_where import where_rows
    return where_rows(h.repo)


def _capture(fn, argv) -> "tuple[int, str]":
    buf = io.StringIO()
    with contextlib.redirect_stdout(buf):
        code = fn(argv)
    return code, buf.getvalue()


@test
def test_every_row_over_a_seeded_home_and_repo(ctx: Ctx):
    with ConfigHome() as h:
        rows = _rows(seed(h))
        cfg = by(rows, "config", "~/.halo/config.json")
        ctx.check(f"config.json: the top-level keys, got {cfg['sets']}", cfg["sets"] == ["model", "ollama", "team", "theme"])
        repo_cfg = by(rows, "config", "./.halo/config.json")
        ctx.check("a repo .halo/config.json is listed and marked not read", repo_cfg["exists"] and not repo_cfg["read"])
        ctx.check("routes.json sets default", by(rows, "config", "~/.halo/routes.json")["sets"] == ["default"])
        env = by(rows, "env", "~/.config/halo/env")
        ctx.check(f"the env file lists its names, got {env['sets']}", env["sets"] == ["DATABRICKS_HOST", "OPENROUTER_API_KEY"])
        dot = by(rows, "env", "./.env")
        ctx.check("the repo .env is listed with its names and marked not read",
                  dot["sets"] == ["REPO_ONLY_TOKEN"] and not dot["read"] and dot["scope"] == "repo")
        for f in ("~/.claude/settings.json", "./.claude/settings.json", "./.claude/settings.local.json"):
            ctx.check(f"settings layer {f} is a row", by(rows, "settings", f)["exists"])
        ctx.check("the repo .mcp.json lists its server", by(rows, "mcp", "./.mcp.json")["sets"] == ["fs"])
        ctx.check("~/.claude.json lists the user servers", by(rows, "mcp", "~/.claude.json")["sets"] == ["fs", "web"])
        active = [r for r in rows if r["kind"] == "lineup"]
        ctx.check(f"the active lineup, then the lineup it extends, got {[r['file'] for r in active]}",
                  [r["file"] for r in active] == ["~/.halo/teams/mine.yaml", "./.halo/teams/standard.yaml"])
        ctx.check("the active lineup's row names its sections", set(active[0]["sets"]) == {"delegation", "roles"})
        folders = [r for r in rows if r["kind"] == "lineups"]
        ctx.check(f"three lineup folders, repo first, got {[(r['file'], r['scope']) for r in folders]}",
                  [r["scope"] for r in folders] == ["repo", "home", "shipped"] and folders[2]["file"] == "<halo>/templates/teams")
        bios = by(rows, "bios", "~/.halo/agents")
        ctx.check(f"the home bio folder counts its bios, got {bios['sets']} / {bios['note']}",
                  bios["sets"] == ["coder"] and bios["note"].startswith("1 file"))
        ctx.check("the team file of the repo", by(rows, "team", "./.halo/team.yaml")["sets"] == ["repo-team"])
        ctx.check("the team file kept outside the repo is listed", by(rows, "team", "~/.halo/teams/repo.team.yaml")["exists"])
        ctx.check("the Databricks preset rows are listed (missing here)",
                  not by(rows, "team-preset", "./.halo/team.json")["exists"])
        ctx.check("no flows group (3.1.4.0), though the home still has a flow file", not [r for r in rows if r["kind"] == "flows"])
        ctx.check("every row has the documented keys", all(set(r) >= {"kind", "file", "path", "scope", "exists", "read",
                                                                    "sets", "rank", "wins", "loses", "note", "files"} for r in rows))


@test
def test_the_precedence_column_follows_the_resolvers(ctx: Ctx):
    with ConfigHome() as h:
        rows = _rows(seed(h))
        loses = lambda r: {e["key"]: e["to"] for e in r["loses"]}  # noqa: E731
        ctx.check("the repo's standard lineup wins over the shipped one",
                  "standard" in by(rows, "lineups", "./.halo/teams")["wins"]
                  and loses(by(rows, "lineups", "<halo>/templates/teams"))["standard"] == "./.halo/teams/standard.yaml")
        ctx.check("my coder bio wins over the shipped coder",
                  loses(by(rows, "bios", "<halo>/templates/agents"))["coder"] == "~/.halo/agents/coder.yaml")
        ctx.check("settings.local.json's model wins over settings.json's",
                  loses(by(rows, "settings", "./.claude/settings.json"))["model"] == "./.claude/settings.local.json"
                  and "model" in by(rows, "settings", "./.claude/settings.local.json")["wins"])
        ctx.check("the repo .mcp.json's fs wins over the user one (the MCP resolver's order)",
                  loses(by(rows, "mcp", "~/.claude.json"))["fs"] == "./.mcp.json")
        ctx.check("the repo team file wins over the one kept outside",
                  loses(by(rows, "team", "~/.halo/teams/repo.team.yaml"))["team file"] == "./.halo/team.yaml")
        cfg = loses(by(rows, "config", "~/.halo/config.json"))
        ctx.check(f"config.json's model loses to routes.json's default, got {cfg}", cfg.get("model") == "routes.json default")
        ctx.check("config.json's theme loses to settings.json's theme", cfg.get("theme") == "settings.json theme")
        ctx.check("the active lineup's own roles win over its parent's",
                  "roles" in by(rows, "lineup", "~/.halo/teams/mine.yaml")["wins"])
        (h.repo / ".halo" / "teams" / "standard.yaml").unlink()
        (h.repo / ".claude" / "settings.local.json").unlink()
        rows = _rows(h)
        ctx.check("with the repo's standard gone, the active lineup extends the shipped one",
                  [r["file"] for r in rows if r["kind"] == "lineup"][1] == "<halo>/templates/teams/standard.yaml")
        ctx.check("and no folder clashes over standard any more",
                  not by(rows, "lineups", "<halo>/templates/teams")["loses"])
        ctx.check("with settings.local.json gone, nothing decides model over settings.json",
                  not by(rows, "settings", "./.claude/settings.json")["loses"])


@test
def test_json_is_the_same_rows(ctx: Ctx):
    from halo_harness.config_cli import cmd_config
    with ConfigHome() as h:
        seed(h)
        code, out = _capture(cmd_config, ["where", "--json", "--cwd", str(h.repo)])
        ctx.check("config where --json exits 0", code == 0)
        data = json.loads(out)
        ctx.check("the payload names the folder and carries the rows",
                  Path(data["cwd"]) == h.repo.resolve() and data["rows"] == _rows(h))
        code, text = _capture(cmd_config, ["where", "--cwd", str(h.repo)])
        ctx.check("the text table has every group heading",
                  code == 0 and all(t in text for t in ("Halo's config", "Env files", "settings.json", "MCP servers",
                                                        "Active lineup", "Lineup folders", "Bio folders", "Team file"))
                  and "Flows" not in text)
        ctx.check("the text table prints the precedence lines", "model: loses to ./.claude/settings.local.json" in text)
        _code, usage = _capture(cmd_config, ["--help"])
        ctx.check("halo config --help names where", "where [--json]" in usage)


@test
def test_nothing_secret_in_the_output(ctx: Ctx):
    from halo_harness.config_where import render
    with ConfigHome() as h:
        rows = _rows(seed(h))
        blob = json.dumps(rows) + render(rows, cwd=h.repo)
        for secret in (FAKE_KEY, DOT_ENV_VALUE, CONFIG_SECRET):
            ctx.check(f"{secret[:12]}... never appears", secret not in blob)
        ctx.check("the names do appear", "OPENROUTER_API_KEY" in blob and "REPO_ONLY_TOKEN" in blob and "ollama" in blob)


@test
def test_an_env_file_name_the_process_environment_overrides_loses_to_it(ctx: Ctx):
    import os
    with ConfigHome() as h:
        seed(h)
        os.environ["OPENROUTER_API_KEY"] = "sk-or-v1-abcdef1234567890"
        rows = _rows(h)
        env = by(rows, "env", "~/.config/halo/env")
        ctx.check(f"OPENROUTER_API_KEY loses to the process environment, got {env['loses']}",
                  any(e["key"] == "OPENROUTER_API_KEY" and e["to"] == "the process environment" for e in env["loses"]))


@test
def test_slash_config_where_prints_the_same_table(ctx: Ctx):
    from halo_harness.commands.builtins import _cmd_config
    from halo_harness.config_where import render
    with ConfigHome() as h:
        rows = _rows(seed(h))
        out = _cmd_config("where", SimpleNamespace(cwd=h.repo))
        ctx.check("/config where prints the table halo config where prints", out == render(rows, cwd=h.repo))
        ctx.check("bare /config keeps its one-line summary",
                  _cmd_config("", SimpleNamespace(theme="doom", permission_mode="auto", model_ref="m")).startswith("model=m"))


if __name__ == "__main__":
    ctx = Ctx()
    results, passed, failed, skipped = run_all(TESTS, ctx)
    sys.exit(print_results(results, passed, failed, skipped))
