"""tests.test_block_templates -- blocks you can start from, and who is inside a square (Halo 3.3.16.3 "Blocks",
workflows/blocks.py, blocks_tier.py, members.py, blocks_cli.py, studio/blocks_api.py): the four shipped templates load
and validate, every agent on `auto` (nothing names a provider); a square template writes a square of YOURS and wires it
(remove undoes it); a tier template merges below the last tier (aliases kept apart, routing words not overwritten; a
shipped lineup copied to yours); an agent joins / leaves a square of yours in place, a shipped square is copied to yours
first and the board swaps to the copy with its rule; the last agent cannot leave; `halo blocks list | add | show` and
`halo teams show`'s block lines. No model.
Run: python -m tests.test_block_templates
"""

from __future__ import annotations

import contextlib
import io
import re
import sys
from pathlib import Path
from types import SimpleNamespace as NS

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from tests.helpers.packs_home import PacksHome  # noqa: E402
from tests.helpers.runner import Ctx, new_registry, print_results, run_all  # noqa: E402

test, TESTS = new_registry()
PROVIDERS = re.compile(r"\b(or|oa|an|ol|gm|ds|cp):|openrouter|anthropic|openai|ollama|claude-|gpt-|gemini|deepseek|kimi|glm", re.I)


def run(fn, *argv) -> "tuple[int, str]":
    buf = io.StringIO()
    with contextlib.redirect_stdout(buf), contextlib.redirect_stderr(buf):
        code = fn(list(argv))
    return code, buf.getvalue()


@test
def test_the_templates_load_validate_and_name_no_provider(ctx: Ctx):
    from halo_harness.workflows import blocks as B
    with PacksHome() as h:
        ctx.check(f"four templates, got {B.names()}", B.names() == ["local-workers", "media", "review-panel", "thinking"])
        for name in B.names():
            t, why = B.load(name)
            ctx.check(f"{name} loads ({why})", t is not None)
            ctx.check(f"{name} validates, got {B.problems(t, cwd=h.repo)}", B.problems(t, cwd=h.repo) == [])
            body = "\n".join(l for l in Path(t["_path"]).read_text(encoding="utf-8").splitlines() if not l.startswith("#"))
            ctx.check(f"{name} names no provider", not PROVIDERS.search(body))
            ctx.check(f"{name}: every agent on auto", all(a["model"] == "auto" for a in B.summary(t)["agents"]))
        s = B.summary(B.load("thinking")[0])
        ctx.check(f"thinking: three reasoning agents, got {s['agents']}", len(s["agents"]) == 3 and s["kind"] == "square")
        bad = dict(B.load("thinking")[0])
        bad["square"] = dict(bad["square"], lineup={"lead": {"bio": "auto-planner", "model": "or:vendor/x"}})
        ctx.check(f"a pinned model is a problem, got {B.problems(bad, cwd=h.repo)}", any("names a model" in p for p in B.problems(bad, cwd=h.repo)))


@test
def test_a_square_template_writes_yours_and_wires_it(ctx: Ctx):
    from halo_harness.workflows import blocks as B
    from halo_harness.workflows import registry
    with PacksHome() as h:
        ok, line, info = B.add("thinking", None, None, cwd=h.repo)
        mine = h.state / "workflows" / "thinking.yaml"
        ctx.check(f"written into yours and enabled, got {line!r}", ok and mine.is_file() and "thinking" in registry.enabled_refs(cwd=h.repo))
        ok2, line2, _ = B.add("thinking", None, None, cwd=h.repo)
        ctx.check(f"a second add says pick another name, got {line2!r}", not ok2 and "--as" in line2)
        ok3, line3 = B.remove("thinking", None, cwd=h.repo)
        ctx.check(f"remove undoes it, got {line3!r}", ok3 and not mine.exists() and "thinking" not in registry.enabled_refs(cwd=h.repo))
        ok4, _l, info4 = B.add("media", None, None, cwd=h.repo)
        ctx.check(f"media adds as media-team, the shipped media untouched, got {info4}", ok4 and info4["ref"] == "media-team")


@test
def test_a_tier_template_merges_below_the_last_tier(ctx: Ctx):
    from halo_harness.agents_yaml import _read_yaml_file
    from halo_harness.teams_yaml import validate_team_template
    from halo_harness.workflows import blocks as B
    from halo_harness.workflows.blocks_tier import merge
    with PacksHome() as h:
        ok, line, info = B.add("local-workers", None, "auto", cwd=h.repo)
        raw = _read_yaml_file(h.state / "teams" / "auto.yaml") or {}
        ctx.check(f"a shipped lineup becomes your copy, got {line!r}", ok and "your copy now" in line)
        ctx.check(f"the tier is last with its purpose, got {raw['tiers'][-1]}",
                  raw["tiers"][-1]["name"] == "local" and raw["tiers"][-1]["members"] == ["local-coder", "local-writer", "local-ops"]
                  and raw["tiers"][-1]["purpose"].startswith("local workers"))
        ctx.check(f"it validates, got {validate_team_template(raw, cwd=h.repo)}", validate_team_template(raw, cwd=h.repo) == [])
        again, name = merge(raw, B.load("local-workers")[0])
        ctx.check(f"twice: the aliases and the tier kept apart, got {name} {again['tiers'][-1]['members']}",
                  name == "local-2" and again["tiers"][-1]["members"] == ["local-coder-2", "local-writer-2", "local-ops-2"])
        ctx.check("routing words already there are not overwritten", again["routing"]["bulk"] == "local-coder")
        none, why = merge({"agents": [{"agent": "default-model", "role": "main"}]}, B.load("local-workers")[0])
        ctx.check(f"a lineup with no tiers says add one first, got {why!r}", none is None and "add one first" in why)


@test
def test_who_is_inside_a_square(ctx: Ctx):
    from halo_harness.agents_yaml import _read_yaml_file
    from halo_harness.workflows import registry
    from halo_harness.workflows.members import change
    from halo_harness.workflows.when_store import set_rule, rules_for
    with PacksHome() as h:
        set_rule("media", {"needs": ["pdf"]}, None, cwd=h.repo)
        ok, line, info = change("media", add="auto-writer", cwd=h.repo)
        ctx.check(f"a shipped square is copied first and says so, got {line!r}",
                  ok and info["ref"] == "my-media" and info["copied_from"] == "media" and "copied to yours as my-media first" in line)
        ctx.check(f"the board swapped to the copy, the rule kept, got {registry.enabled_refs(cwd=h.repo)}",
                  registry.enabled_refs(cwd=h.repo) == ["my-media"] and rules_for(None, cwd=h.repo)["my-media"].needs == ["pdf"])
        data = _read_yaml_file(h.state / "workflows" / "my-media.yaml")
        ctx.check(f"the member on auto, got {data['lineup']}", data["lineup"]["members"] == [{"bio": "auto-writer", "model": "auto"}])
        ok, line, _ = change("my-media", remove="auto-writer", cwd=h.repo)
        ctx.check(f"it leaves, got {line!r}", ok and "auto-writer left my-media" in line)
        ok, line, _ = change("my-media", remove="auto-media", cwd=h.repo)
        ctx.check(f"the last agent cannot leave, got {line!r}", not ok and "last agent cannot leave" in line)
        ok, line, _ = change("my-media", add="nobody-at-all", cwd=h.repo)
        ctx.check(f"an unknown bio says so, got {line!r}", not ok and "no bio" in line)


@test
def test_the_cli_and_the_routes(ctx: Ctx):
    from halo_harness.blocks_cli import cmd_blocks
    from halo_harness.studio.workflows_api import dispatch_workflows
    with PacksHome() as h:
        code, out = run(cmd_blocks, "list", "--repo", str(h.repo))
        ctx.check(f"list: templates then the lineup's blocks, got {out!r}",
                  code == 0 and "thinking       square thinking: three reasoning models" in out and "block media (square): when needs pdf" in out
                  and "block pool (tier 1)" in out)
        code, out = run(cmd_blocks, "show", "review-panel", "--repo", str(h.repo))
        ctx.check(f"show a template, got {out!r}", code == 0 and "review panel of three" in out and "auto-reviewer on auto" in out)
        code, out = run(cmd_blocks, "add", "review-panel", "--as", "panel", "--repo", str(h.repo))
        ctx.check(f"add --as, got {out!r}", code == 0 and "panel added from template review-panel" in out)
        code, out = run(cmd_blocks, "show", "panel", "--repo", str(h.repo))
        ctx.check(f"show a block of the lineup, got {out!r}", code == 0 and "panel (square block)" in out and "when" in out)
        req = lambda path, method, body=None, query=None: NS(path=path, method=method, body=body or {}, query=query or {}, cwd=str(h.repo))  # noqa: E731
        code, got = dispatch_workflows(req("workflows/templates", "GET"))
        ctx.check(f"GET templates, got {[t['name'] for t in got['templates']]}", code == 200 and len(got["templates"]) == 4 and all(not t["problems"] for t in got["templates"]))
        code, got = dispatch_workflows(req("workflows/when", "PUT", {"ref": "panel", "when": {"mode": "always"}}))
        ctx.check(f"PUT when, got {got}", code == 200 and "always first" in got["line"])
        code, got = dispatch_workflows(req("workflows", "GET"))
        row = next(r for r in got["squares"] if r["ref"] == "panel")
        ctx.check(f"the board carries the rule, got {row.get('when_label')!r}", row["when_label"] == "always first" and row["when_mode"] == "always")
        code, got = dispatch_workflows(req("workflows/templates/merge", "POST", {"template": "local-workers", "raw": {"tiers": [{"name": "a", "members": ["main"]}], "agents": [{"agent": "default-model", "role": "main"}]}}))
        ctx.check(f"merge answers the mapping, got {code}", code == 200 and got["raw"]["tiers"][-1]["name"] == "local")


if __name__ == "__main__":
    ctx = Ctx()
    results, passed, failed, skipped = run_all(TESTS, ctx)
    sys.exit(print_results(results, passed, failed, skipped))
