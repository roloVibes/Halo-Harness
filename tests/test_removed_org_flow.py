"""tests.test_removed_org_flow -- Halo 3.1.4.0 round R3: Org and Flow are gone.

1. the invariants: no module under halo_harness imports `halo_harness.flows`,
   `halo_harness.orgs`, `halo_harness.paperclip` or `coach_flow_rules`; no
   builtin `/org`; no CLI dispatch `flow` / `postiz` / `org` / `paperclip`; no
   Studio mode `org` / `flow`; no feed kind `flow_*`; no team stage kind `flow`;
2. what a user with old files sees: a leftover `orgs` / `paperclip` section in
   config.json loads and `halo doctor --config` names each in one line; a
   leftover `org:` section in a lineup loads with one warning line, never a
   block; a team stage of kind `flow` fails validation with one line naming
   3.1.4.0 and the stage;
3. the shipped team template validates clean, and the Roles graph of a lineup
   without `org:` hangs every non-main card off main.
No model is called. Run: python -m tests.test_removed_org_flow
"""
from __future__ import annotations

import ast
import contextlib
import io
import re
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO))

from tests.helpers.provider_env_defaults import ensure_scoped_state_dir_once  # noqa: E402

ensure_scoped_state_dir_once()

from tests.helpers.config_seed import ConfigHome  # noqa: E402
from tests.helpers.runner import Ctx, new_registry, print_results, run_all  # noqa: E402

test, TESTS = new_registry()
PKG = REPO / "halo_harness"
GONE = ("halo_harness.flows", "halo_harness.orgs", "halo_harness.org_cli", "halo_harness.paperclip",
        "halo_harness.orchestra.coach_flow_rules", "halo_harness.work.adapters.step", "halo_harness.design.store_posts")
CONFIG_LINES = ["orgs: removed in 3.1.4.0, the section is ignored", "paperclip: removed in 3.1.4.0, the section is ignored"]
LINEUP_LINE = "org: removed in 3.1.4.0, ignored"
STAGE_LINE = "stage `post`: kind `flow` was removed in 3.1.4.0; make it an agent or orchestra stage, or delete it"


def _imports(path: Path) -> "list[str]":
    out = []
    for node in ast.walk(ast.parse(path.read_text(encoding="utf-8"))):
        if isinstance(node, ast.Import):
            out += [a.name for a in node.names]
        elif isinstance(node, ast.ImportFrom) and node.module:
            out += [node.module] + [f"{node.module}.{a.name}" for a in node.names]
    return out


@test
def test_no_module_imports_a_removed_package(ctx: Ctx):
    bad = []
    for path in sorted(PKG.rglob("*.py")):
        for name in _imports(path):
            if any(name == g or name.startswith(g + ".") for g in GONE) or name.endswith("coach_flow_rules"):
                bad.append(f"{path.relative_to(REPO).as_posix()}: {name}")
    ctx.check(f"no import of a removed module, got {bad}", not bad)
    left = [p for p in ("flows", "paperclip", "orgs.py", "org_cli.py", "templates/flows", "templates/orgs",
                        "studio/paperclip_api.py", "studio/flow_api.py", "tui/dialogs/org_editor.py") if (PKG / p).exists()]
    ctx.check(f"the removed files are gone, left: {left}", not left)


@test
def test_no_org_command_no_flow_or_org_dispatch_and_no_section(ctx: Ctx):
    from halo_harness.commands.builtins import _BUILTIN_SPECS
    from halo_harness.completion_cli import SUBCOMMANDS
    from halo_harness.studio.launch import _query
    from halo_harness.studio.server import STUDIO_MODES
    ctx.check("no builtin /org", "org" not in _BUILTIN_SPECS)
    cli = (PKG / "cli.py").read_text(encoding="utf-8")
    hits = re.findall(r'argv\[0\] == "(flow|postiz|org|paperclip|paperclip-run)"', cli)
    ctx.check(f"no cli dispatch of a removed command, got {hits}", not hits)
    ctx.check("no completion word for one", not {"org", "paperclip", "flow", "postiz"} & set(SUBCOMMANDS))
    ctx.check(f"no Studio mode org or flow, got {STUDIO_MODES}", not {"org", "flow"} & set(STUDIO_MODES)
              and _query("org", None) == "" and _query("flow", None) == "")
    ui = PKG / "studio" / "ui" / "src"
    routes = (ui / "routes" / "index.tsx").read_text(encoding="utf-8")
    ctx.check("no Org or Flow section in the shell", 'id: "org"' not in routes and 'id: "flow"' not in routes
              and not (ui / "routes" / "org").exists() and not (ui / "routes" / "flow").exists())


@test
def test_no_flow_feed_kind_stage_kind_unit_kind_or_attention_kind(ctx: Ctx):
    from halo_harness import events
    from halo_harness.fleet import attention, mission_stage_run, push
    from halo_harness.orchestra import coach
    from halo_harness.studio.feed_kinds import DEFAULT_KINDS
    from halo_harness.team import spec as S
    from halo_harness.work import states, store
    kinds = [k for k in DEFAULT_KINDS if k.startswith("flow_")]
    ctx.check(f"no flow_* feed kind, got {kinds}", not kinds and not [k for k in events.EVENT_KINDS if k.startswith("flow_")])
    ts = (PKG / "studio" / "ui" / "src" / "lib" / "events.ts").read_text(encoding="utf-8")
    ctx.check("the UI asks for no flow_* frame", '"flow_' not in ts)
    ctx.check("no team stage kind flow", "flow" not in S.STAGE_KINDS and S.REMOVED_STAGE_KINDS == {"flow": "3.1.4.0"})
    ctx.check("no mission part kind flow", mission_stage_run.KINDS == ("orchestra",))
    ctx.check("no work unit kind step", "step" not in states.KINDS and "flow" not in store.RUN_KINDS)
    ctx.check("no coach run kind flow", "flow" not in coach.RUN_KINDS)
    ctx.check("no flow_gate attention or push row", "flow_gate" not in attention.KEYS and "flow_gate" not in push.PUSH_KINDS)


@test
def test_a_leftover_orgs_or_paperclip_config_section_is_one_doctor_line_each(ctx: Ctx):
    from halo_harness.doctor_config import cmd_doctor_config, config_findings
    from halo_harness.theme import get_config_value
    with ConfigHome() as h:
        h.config({"theme": "doom", "orgs": {"enabled": True, "default": "solo"}, "paperclip": {"enabled": True}})
        ctx.check("config.json still loads", get_config_value("theme") == "doom")
        found = [f for f in config_findings(h.repo) if f["file"] == "~/.halo/config.json"]
        ctx.check(f"one warning per removed section, worded as the brief says, got {[f['text'] for f in found]}",
                  sorted(f["text"] for f in found) == CONFIG_LINES and all(f["severity"] == "warns" for f in found)
                  and {f["check"] for f in found} == {"removed-section"})
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            cmd_doctor_config(cwd=h.repo)
        text = out.getvalue()
        ctx.check(f"halo doctor --config prints each line once, got {text[-400:]!r}",
                  all(text.count(line) == 1 for line in CONFIG_LINES)
                  and len([ln for ln in text.splitlines() if ln.lstrip().startswith(("[WARN]", "[ERROR]"))]) == 2)


@test
def test_a_leftover_lineup_org_section_warns_once_and_never_blocks(ctx: Ctx):
    from halo_harness.doctor_config import config_findings
    from halo_harness.lineup_preflight import blocking, lineup_problems
    from halo_harness.teams_cli import cmd_teams
    from halo_harness.teams_yaml import load_team_template_raw, resolve_team_template, validate_team_template
    with ConfigHome() as h:
        h.write(".halo/teams/old.yaml", "name: old\nagents:\n  - {agent: orchestrator, role: main}\n"
                "org:\n  positions:\n    - {title: Boss, agent: orchestrator, reports_to: nobody}\n")
        raw = load_team_template_raw("old")
        ctx.check(f"the lineup validates clean, got {validate_team_template(raw, name='old')}",
                  validate_team_template(raw, name="old") == [])
        ctx.check("the section is ignored on load", "org" not in (resolve_team_template("old") or {"org": 1}))
        found = lineup_problems("old")
        org = [f for f in found if f["id"] == "removed:org"]
        ctx.check(f"the preflight warns once, got {found}", len(org) == 1 and org[0]["text"] == LINEUP_LINE
                  and org[0]["severity"] == "warns" and not [f for f in blocking(found) if "org" in f["text"]])
        lines = [f for f in config_findings(h.repo) if f["file"] == "~/.halo/teams/old.yaml"]
        ctx.check(f"doctor --config: the one line, no unknown key, got {[(f['check'], f['text']) for f in lines]}",
                  [(f["check"], f["severity"], f["text"]) for f in lines] == [("removed-section", "warns", LINEUP_LINE)])
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            code = cmd_teams(["validate", "old"])
        ctx.check(f"halo teams validate: ok plus the warning, exit 0, got {code} {out.getvalue()!r}",
                  code == 0 and "old: ok" in out.getvalue() and f"old: warning: {LINEUP_LINE}" in out.getvalue())


@test
def test_a_team_stage_of_kind_flow_fails_validation_with_one_line(ctx: Ctx):
    from halo_harness.team import spec as S
    from tests.helpers import team_rig as R
    text = R.TEAM + '    - {id: post, kind: flow, flow: social-post, reads: [copy], trigger: "stage_done:review"}\n'
    root, state = R.repo(text)
    lines = S.validate_team(S.load_team(root, state), cwd=root, state_dir=state, preflight=False)
    ctx.check(f"exactly the one line, got {lines}", lines == [STAGE_LINE])


@test
def test_the_shipped_template_validates_and_roles_hang_off_main(ctx: Ctx):
    from halo_harness.studio.model import graph_for
    from halo_harness.team import spec as S
    from tests.helpers import team_rig as R
    root, state = R.repo(S.template_text())
    team = S.load_team(root, state)
    ctx.check(f"the shipped team template validates clean, got {S.validate_team(team, cwd=root, state_dir=state)}",
              S.validate_team(team, cwd=root, state_dir=state) == [] and [s["kind"] for s in team["workflow"]["stages"]]
              == ["agent", "orchestra"])
    raw = {"name": "plain", "agents": [{"agent": "orchestrator", "role": "main", "as": "boss"},
                                       {"agent": "implementer", "role": "subagent", "as": "worker"},
                                       {"agent": "verifier", "role": "reviewer", "as": "tester"}]}
    g = graph_for(raw, catalog={})
    main = g["nodes"][0]["id"]
    edges = {(e["from"], e["to"]): e["kind"] for e in g["edges"]}
    others = [n["id"] for n in g["nodes"][1:]]
    ctx.check(f"every non-main card hangs off main by delegation, got {edges}",
              all(edges.get((main, n)) == "delegation" for n in others) and "reports" not in edges.values())


if __name__ == "__main__":
    ctx = Ctx()
    results, passed, failed, skipped = run_all(TESTS, ctx)
    sys.exit(print_results(results, passed, failed, skipped, label="removed org and flow tests"))
