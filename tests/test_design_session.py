"""tests.test_design_session -- one design turn (Halo 3.0.1.0 round D2)
over a fake runner: the command line (print mode, stream-json, auto
permissions, the skill file, the tools allowlist naming only present
craft apps, the model, the budget), the skill text (contract, crafts,
system tokens, open comments, existing artboards), event streaming, cost
capture, the snapshot after the turn and the history line; plus the
`halo design` CLI surface and `doctor`.
"""

from __future__ import annotations

import io
import json
import sys
from contextlib import redirect_stdout
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from tests.helpers.provider_env_defaults import ensure_default_provider_credentials, ensure_scoped_state_dir_once

ensure_default_provider_credentials()
ensure_scoped_state_dir_once()

from tests.helpers.runner import Ctx, new_registry, print_results, run_all  # noqa: E402

test, TESTS = new_registry()


def _fake_runner(lines, make_files=None):
    seen = {}

    def runner(cmd, cwd, env, on_line):
        seen["cmd"], seen["cwd"], seen["env"] = cmd, cwd, env
        if "--mcp-config" in cmd:  # read it while it exists (the turn removes it afterwards)
            seen["mcp_cfg"] = json.loads(Path(cmd[cmd.index("--mcp-config") + 1]).read_text(encoding="utf-8"))
        if make_files:
            make_files(Path(cwd))
        for line in lines:
            on_line(json.dumps(line) if isinstance(line, dict) else line)
        return 0
    runner.seen = seen
    return runner


@test
def test_turn_command_skill_events_and_snapshot(ctx: Ctx):
    from halo_harness.design.session import run_turn, skill_text
    from halo_harness.design.store import Project
    p = Project.create("Turny", model="or:v/eyes")
    p.save_system({"tokens": {"colors": {"--accent": "#89b4fa"}}, "components": [{"name": "Button"}]})
    p.add_comment("hero", "bigger title", x=40, y=12)
    text = skill_text(p, registered={"designcraft", "vectorcraft"})
    ctx.check("the skill carries the artboard contract", "artboards/<id>/" in text and "controls.json" in text)
    ctx.check("the skill names only the present craft apps", "mcp__designcraft__" in text and "mcp__vectorcraft__" in text and "mcp__photocraft__" not in text)
    ctx.check("the skill carries the tokens, components and open comments", "--accent=#89b4fa" in text and "Button" in text and "bigger title" in text)

    def make(cwd: Path):
        d = cwd / "artboards" / "hero"
        d.mkdir(parents=True, exist_ok=True)
        (d / "index.html").write_text("<h1>Hello</h1>", encoding="utf-8")
    runner = _fake_runner([{"type": "system", "subtype": "init"},
                           {"type": "assistant", "message": {"content": [{"type": "text", "text": "Making the hero."}]}},
                           "not json at all",
                           {"type": "result", "result": "Done: hero artboard.", "total_cost_usd": 0.0123}], make)
    events = []
    fake_entry = {"type": "stdio", "command": "designcraft-cli", "args": ["mcp"]}
    r = run_turn(p, "A hero section", on_event=events.append, max_budget_usd=2.5, registered={"designcraft"},
                 entries={"designcraft": fake_entry}, runner=runner)
    cmd = runner.seen["cmd"]
    ctx.check("the turn is a print-mode run in the project folder with stream-json and auto permissions",
              "-p" in cmd and "--cwd" in cmd and cmd[cmd.index("--cwd") + 1] == str(p.path) and "stream-json" in cmd and "auto" in cmd)
    ctx.check("the model, the budget and the skill file are passed", cmd[cmd.index("--model") + 1] == "or:v/eyes" and "2.5" in cmd and "--append-system-prompt-file" in cmd)
    tools = cmd[cmd.index("--tools") + 1]
    ctx.check("the allowlist is the core built-in tools", "Read" in tools and "Write" in tools and "mcp__" not in tools)
    ctx.check("the craft apps are the turn's only MCP servers (strict config)", "--strict-mcp-config" in cmd and runner.seen["mcp_cfg"] == {"mcpServers": {"designcraft": fake_entry}})
    ctx.check("events stream in order and a non-JSON line is kept as stdout", [e.get("type") for e in events] == ["system", "assistant", "stdout", "result", "halo_design"])
    ctx.check("the cost and the reply are captured", r["cost"] == 0.0123 and r["text"] == "Done: hero artboard." and r["code"] == 0)
    ctx.check("the changed artboard was discovered and versioned", r["versions"] == [("hero", 1)] and p.artboards()[0]["latest"] == 1)
    ctx.check("the turn is in the history with its cost", p.history()[-1]["cost"] == 0.0123 and p.history()[-1]["prompt"] == "A hero section")
    ctx.check("the skill and mcp files are removed afterwards", not any(Path(c).exists() for c in cmd if "halo-design-skill-" in c or "halo-design-mcp-" in c))
    ctx.check("the child reads UTF-8", runner.seen["env"].get("PYTHONIOENCODING") == "utf-8")


@test
def test_cli_surface_and_doctor(ctx: Ctx):
    from halo_harness.design.cli import cmd_design
    buf = io.StringIO()
    with redirect_stdout(buf):
        rc = cmd_design(["new", "CLI Project", "--model", "or:v/eyes"])
    ctx.check("new creates and names the slug", rc == 0 and "slug cli-project" in buf.getvalue())
    buf = io.StringIO()
    with redirect_stdout(buf):
        cmd_design(["list"])
    ctx.check("list shows it", "cli-project" in buf.getvalue())
    buf = io.StringIO()
    with redirect_stdout(buf):
        cmd_design(["comment", "cli-project", "hero", "move the logo", "--at", "10,20"])
    ctx.check("comment pins", "comment c1" in buf.getvalue())
    buf = io.StringIO()
    with redirect_stdout(buf):
        rc = cmd_design(["show", "cli-project"])
    ctx.check("show prints the project and its open comment", rc == 0 and "1 open comment" in buf.getvalue())
    buf = io.StringIO()
    with redirect_stdout(buf):
        rc = cmd_design(["doctor"])
    ctx.check("doctor lists the seven craft apps", rc == 0 and buf.getvalue().count("craft") >= 7)
    from halo_harness.design.crafts import allowed_tools, guide_lines, which_apps
    ctx.check("which_apps filters by registration", set(which_apps({"PdfCraft", "nope"})) == {"pdfcraft"})
    ctx.check("allowed_tools is the core built-ins only", "mcp__" not in allowed_tools({"filmcraft"}) and allowed_tools().startswith("Read,"))
    ctx.check("with no app the guide says to write HTML and SVG", "No craft app" in guide_lines(set())[0])


if __name__ == "__main__":
    ctx = Ctx()
    results, passed, failed, skipped = run_all(TESTS, ctx)
    sys.exit(print_results(results, passed, failed, skipped, label="design session tests"))
