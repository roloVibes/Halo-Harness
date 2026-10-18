"""tests.test_doctor_config -- `halo doctor --config` (Halo 3.1.1.0 R2): each
finding from one seeded file (an unknown key with its closest known key, a
wrong type, a lineup naming a bio that is not there, a team or flow naming a
lineup that is not there, config.json's `team:` naming a missing lineup, a
repo config.json nothing reads, two files giving one key different values
and which wins, an env-file name the environment overrides); a clean home
(the shipped lineups copied in) reports nothing; the CLI's text, JSON and
exit codes; Studio's `GET /api/doctor/config` with and without `?lineup=`.
"""

from __future__ import annotations

import contextlib
import io
import json
import os
import sys
import threading
import urllib.request
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from tests.helpers.config_seed import ConfigHome, seed  # noqa: E402
from tests.helpers.runner import Ctx, new_registry, print_results, run_all  # noqa: E402

test, TESTS = new_registry()


def _findings(h):
    from halo_harness.doctor_config import config_findings
    return config_findings(h.repo)


def _one(findings, check, file, key=None):
    hits = [f for f in findings if f["check"] == check and f["file"] == file and (key is None or f["key"] == key)]
    return hits[0] if len(hits) == 1 else None


@test
def test_a_clean_home_reports_nothing(ctx: Ctx):
    from halo_harness.teams_yaml import ensure_builtin_team_templates
    with ConfigHome() as h:
        ctx.check(f"an empty home and repo: no findings, got {_findings(h)}", _findings(h) == [])
        ensure_builtin_team_templates(state_dir=h.state)
        h.config({"team": "standard", "theme": "doom", "intro": False})
        ctx.check(f"the shipped lineups copied in and a valid config.json: none, got {_findings(h)}", _findings(h) == [])


@test
def test_the_shipped_files_pass_their_schemas(ctx: Ctx):
    """The schema set is built from the loaders' own key lists; every file
    Halo ships must pass it (doctor --config skips shipped rows on this basis)."""
    import yaml
    from halo_harness.schemas import check_file_shape
    root = Path(__file__).resolve().parent.parent / "halo_harness" / "templates"
    for kind, pattern in (("lineup", "teams/*.yaml"), ("bio", "agents/*.yaml"), ("flow", "flows/*.flow.yaml"),
                          ("team", "team/*.yaml")):
        files = sorted(root.glob(pattern))
        ctx.check(f"some shipped {kind} files", files)
        for path in files:
            found = check_file_shape(kind, yaml.safe_load(path.read_text(encoding="utf-8")))
            ctx.check(f"{path.name} passes the {kind} schema, got {found}", found == [])


@test
def test_every_config_key_the_code_reads_is_in_the_schema(ctx: Ctx):
    """A key some module reads or writes with `get_config_value` /
    `set_config_value` (or `config_value`) must never be reported unknown."""
    import re
    from halo_harness.schemas.config_json import known_keys
    pkg = Path(__file__).resolve().parent.parent / "halo_harness"
    used = set()
    for path in pkg.rglob("*.py"):
        text = path.read_text(encoding="utf-8", errors="replace")
        used |= set(re.findall(r"(?:get_config_value|set_config_value|config_value)\(\s*f?[\"']([A-Za-z0-9_]+)", text))
        used |= set(re.findall(r"load_config\(\)\.get\([\"']([A-Za-z0-9_]+)", text))
    missing = sorted(used - set(known_keys()))
    ctx.check(f"found the keys the code reads ({len(used)})", len(used) > 20)
    ctx.check(f"every one is in schemas/config_json.py; missing: {missing}", not missing)


@test
def test_config_json_unknown_key_wrong_type_and_missing_lineup(ctx: Ctx):
    with ConfigHome() as h:
        h.config({"modle": "or:a/b", "intro": "yes", "team": "nowhere"})
        found = _findings(h)
        unknown = _one(found, "unknown-key", "~/.halo/config.json", "modle")
        ctx.check(f"modle: unknown, closest model, got {unknown}", unknown and "'model'" in unknown["text"]
                  and unknown["severity"] == "warns" and unknown["fix"] == "rename it to model")
        wrong = _one(found, "wrong-type", "~/.halo/config.json", "intro")
        ctx.check(f"intro: a wrong type that blocks, got {wrong}", wrong and wrong["severity"] == "blocks")
        team = _one(found, "missing-lineup", "~/.halo/config.json", "team")
        ctx.check(f"team: names a lineup that is not there, got {team}", team and team["lineups"] == ["nowhere"])
        h.write(".halo/config.json", "{not json", base=h.repo)
        h.write(".halo/config.json", "{not json")
        ctx.check("a config.json that does not parse blocks", _one(_findings(h), "unreadable", "~/.halo/config.json"))


@test
def test_a_repo_config_json_is_reported_as_not_read(ctx: Ctx):
    with ConfigHome() as h:
        h.write(".halo/config.json", json.dumps({"theme": "mario"}), base=h.repo)
        hit = _one(_findings(h), "unread-file", "./.halo/config.json")
        ctx.check(f"the repo config.json is a warning naming the home one, got {hit}",
                  hit and hit["severity"] == "warns" and "~/.halo/config.json" in hit["text"])


@test
def test_lineup_and_bio_files(ctx: Ctx):
    with ConfigHome() as h:
        h.write(".halo/teams/mine.yaml", "roles: {main: ghost-bio}\ndelegaton: {mode: manual}\nbudget: 3\n")
        h.write(".halo/agents/odd.yaml", "kind: wizard\nmodels: fast\n")
        found = _findings(h)
        bio = _one(found, "missing-bio", "~/.halo/teams/mine.yaml")
        ctx.check(f"a lineup naming a bio that is not there, got {bio}", bio and "ghost-bio" in bio["text"]
                  and bio["lineups"] == ["mine"] and bio["severity"] == "blocks")
        typo = _one(found, "unknown-key", "~/.halo/teams/mine.yaml", "delegaton")
        ctx.check(f"a lineup's unknown key with its closest, got {typo}", typo and "'delegation'" in typo["text"])
        ctx.check("a lineup section of the wrong type", _one(found, "wrong-type", "~/.halo/teams/mine.yaml", "budget"))
        bad = [f for f in found if f["file"] == "~/.halo/agents/odd.yaml"]
        ctx.check(f"the bio validator's lines for a bad bio, got {[f['text'] for f in bad]}",
                  any("kind" in f["text"] for f in bad) and any('"models" must be a mapping' in f["text"] for f in bad))


@test
def test_team_and_flow_naming_a_lineup_that_is_not_there(ctx: Ctx):
    with ConfigHome() as h:
        h.write("BRIEF.md", "# b\n", base=h.repo)
        h.write(".halo/team.yaml", "name: t\nbrief: BRIEF.md\nmembers: [{name: a, lineup: nope, role: main}]\n"
                "workflow: {stages: [{id: s, kind: agent, members: [a]}]}\nextra: 1\n", base=h.repo)
        h.write(".halo/flows/p.flow.yaml", "name: p\nsteps: [{id: plan, kind: roles, uses: 'lineup:gone', roles: [x]}]\n")
        found = _findings(h)
        team = _one(found, "missing-lineup", "./.halo/team.yaml")
        ctx.check(f"a team member's lineup that is not there, got {team}", team and team["lineups"] == ["nope"])
        ctx.check("the team file's unknown key", _one(found, "unknown-key", "./.halo/team.yaml", "extra"))
        flow = _one(found, "missing-lineup", "~/.halo/flows/p.flow.yaml")
        ctx.check(f"a flow naming a lineup that does not resolve, got {flow}", flow and flow["lineups"] == ["gone"])


@test
def test_a_key_two_files_set_differently_names_the_winner(ctx: Ctx):
    with ConfigHome() as h:
        seed(h)
        os.environ["OPENROUTER_API_KEY"] = "sk-or-v1-abcdef1234567890"
        found = [f for f in _findings(h) if f["check"] == "conflict"]
        texts = {f["file"] + "|" + f["key"]: f["text"] for f in found}
        ctx.check(f"settings model: settings.local.json wins, got {texts}",
                  "./.claude/settings.local.json wins" in texts.get("./.claude/settings.json|model", ""))
        ctx.check("config.json model vs routes.json default: routes.json wins",
                  "~/.halo/routes.json wins" in texts.get("~/.halo/config.json|model", ""))
        ctx.check("config.json theme vs settings.json theme: settings.json wins",
                  "~/.claude/settings.json wins" in texts.get("~/.halo/config.json|theme", ""))
        ctx.check("MCP server fs in two files: .mcp.json wins", "./.mcp.json wins" in texts.get("~/.claude.json|fs", ""))
        ctx.check("lineup standard in the repo and the home folder with different contents",
                  not any(k.startswith("<halo>") for k in texts))
        ctx.check("the env file's key the process environment overrides",
                  "process environment wins" in texts.get("~/.config/halo/env|OPENROUTER_API_KEY", ""))
        h.write(".halo/teams/standard.yaml", "description: mine\nroles: {main: coder}\n")
        texts = {f["file"] + "|" + f["key"]: f["text"] for f in _findings(h) if f["check"] == "conflict"}
        ctx.check(f"the same lineup in the home and repo folders: the repo's wins, got {list(texts)}",
                  "./.halo/teams/standard.yaml wins" in texts.get("~/.halo/teams|standard", ""))
        ctx.check("every conflict is a warning", all(f["severity"] == "warns" for f in found))


@test
def test_cmd_doctor_config_text_json_and_exit_codes(ctx: Ctx):
    from halo_harness.doctor import cmd_doctor
    with ConfigHome() as h:
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            code = cmd_doctor(["--config", "--cwd", str(h.repo)])
        ctx.check(f"clean: exit 0 and a RESULT line, got {code} / {buf.getvalue()[-120:]}",
                  code == 0 and "RESULT: 0 finding(s)" in buf.getvalue())
        h.config({"modle": 1})
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            code = cmd_doctor(["--config", "--cwd", str(h.repo)])
        ctx.check("one finding: exit 1, the line names the file, the key and the fix",
                  code == 1 and "[WARN] ~/.halo/config.json: unknown key 'modle'" in buf.getvalue()
                  and "-> fix: rename it to model" in buf.getvalue())
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            code = cmd_doctor(["--config", "--json", "--cwd", str(h.repo)])
        data = json.loads(buf.getvalue())
        ctx.check("--json is the findings and the file count",
                  code == 1 and data["findings"][0]["key"] == "modle" and data["files_checked"] >= 1)


@test
def test_studio_route_answers_the_same_rows(ctx: Ctx):
    from halo_harness.doctor_config import config_findings
    from halo_harness.studio.server import start_server
    with ConfigHome() as h:
        h.write(".halo/teams/mine.yaml", "extends: base\nroles: {main: coder}\n")
        h.write(".halo/teams/base.yaml", "roles: {main: ghost-bio}\n")
        h.write(".halo/teams/other.yaml", "roles: {main: ghost2}\n")
        h.config({"modle": 1, "team": "mine"})
        srv = start_server(port=0, cwd=h.repo, state_dir=h.state)
        threading.Thread(target=srv.serve_forever, daemon=True).start()
        try:
            def get(path):
                req = urllib.request.Request(f"http://127.0.0.1:{srv.server_address[1]}/api/{path}")
                req.add_header("Authorization", "Bearer " + srv.token)
                with urllib.request.urlopen(req, timeout=20) as r:
                    return r.status, json.loads(r.read())
            status, body = get("doctor/config")
            ctx.check("GET doctor/config answers 200 with every finding",
                      status == 200 and body["findings"] == config_findings(h.repo, state_dir=h.state)
                      and body["lineup"] is None)
            status, body = get("doctor/config?lineup=mine")
            files = sorted({f["file"] for f in body["findings"]})
            ctx.check(f"?lineup=mine: the lineup and the one it extends, not other's or config's key, got {files}",
                      status == 200 and files == ["~/.halo/teams/base.yaml"] and body["lineup"] == "mine")
        finally:
            srv.shutdown()
            srv.server_close()


if __name__ == "__main__":
    ctx = Ctx()
    results, passed, failed, skipped = run_all(TESTS, ctx)
    sys.exit(print_results(results, passed, failed, skipped))
