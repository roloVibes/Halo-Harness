"""tests.test_subscription_defaults -- Halo 3.0.2.0: the cc:/cx:
subscription routes are off in EVERY part of Halo until accepted -- the
shipped templates, the catalog rows, Studio's model list, the resolved
shipped bios -- so no screen (Roles mode, the wizard, a picker) shows a
subscription model as a default pick before `halo subscriptions accept`.

Run: python -m tests.test_subscription_defaults
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

REPO_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_DIR))

from tests.helpers.provider_env_defaults import ensure_default_provider_credentials, ensure_scoped_state_dir_once

ensure_default_provider_credentials()
ensure_scoped_state_dir_once()

from tests.helpers.runner import Ctx, new_registry, print_results, run_all  # noqa: E402

test, TESTS = new_registry()
_SUB = re.compile(r"(?<![\w/.-])c[cx]:[\w.-]+")


def _refs(text: str) -> list:
    return [m for m in _SUB.findall(text) if not m.startswith(("cc:/", "cx:/"))]


@test
def test_no_shipped_template_names_a_subscription_route(ctx: Ctx):
    tdir = REPO_DIR / "halo_harness" / "templates"
    bad = {}
    for p in sorted(tdir.rglob("*.yaml")):
        body = "\n".join(line.split("#", 1)[0] for line in p.read_text(encoding="utf-8").splitlines())
        found = _refs(body)
        if found:
            bad[p.name] = found
    ctx.check(f"no shipped bio or lineup names cc:/cx:, got {bad}", not bad)
    ctx.check("the shipped templates were scanned", len(list(tdir.rglob("*.yaml"))) >= 10)


@test
def test_catalog_and_resolved_bios_carry_no_subscription_route_while_off(ctx: Ctx):
    from halo_harness.subscription_consent import is_accepted, revoke
    revoke()  # the combined CI run shares one home with suites that accept the routes
    ctx.check("the gate is off", is_accepted() is False)
    from halo_harness.providers.model_enumeration import build_model_rows
    from halo_harness.providers.config import default_state_dir
    rows = build_model_rows(default_state_dir())
    refs = [r.get("ref") for r in (rows if isinstance(rows, list) else rows.get("rows", []))]
    ctx.check(f"the catalog lists no cc:/cx: row, got {[r for r in refs if str(r).startswith(('cc:', 'cx:'))]}",
              not any(str(r).startswith(("cc:", "cx:")) for r in refs))
    from halo_harness.agents_yaml import list_agent_bios, resolve_agent_bio
    seen = {}
    for bio in list_agent_bios():
        name = bio.get("name") if isinstance(bio, dict) else getattr(bio, "name", str(bio))
        try:
            resolved = resolve_agent_bio(name)
        except Exception as e:  # a bio that needs a project is not this test's concern
            seen[name] = f"skipped: {type(e).__name__}"
            continue
        models = (resolved.get("models") if isinstance(resolved, dict) else None) or {}
        picks = [str(models.get(k)) for k in ("preference", "fallback", "escalation") if models.get(k)]
        hit = [p for p in picks if p.startswith(("cc:", "cx:"))]
        if hit:
            seen[name] = hit
    ctx.check(f"no resolved shipped bio prefers a subscription route, got {seen}", not any(isinstance(v, list) for v in seen.values()))


@test
def test_studio_model_list_and_lineup_graph_carry_none(ctx: Ctx):
    from tests.test_studio_org import _Studio
    with _Studio() as s:
        status, body = s.call("GET", "/api/models")
        rows = body if isinstance(body, list) else (body.get("rows") or body.get("models") or [])
        refs = [str(r.get("ref") if isinstance(r, dict) else r) for r in rows]
        ctx.check(f"GET /api/models is 200 with rows, got {status} {len(refs)}", status == 200 and refs)
        ctx.check(f"and none is a subscription route, got {[r for r in refs if r.startswith(('cc:', 'cx:'))]}",
                  not any(r.startswith(("cc:", "cx:")) for r in refs))
        status, graph = s.call("GET", "/api/lineup/halo-dev-cycle")
        text = str(graph)
        ctx.check(f"the halo-dev-cycle graph names no subscription route, got {status} {_refs(text)[:5]}",
                  status == 200 and not _refs(text))


@test
def test_subscription_refs_map_to_api_equivalents_everywhere(ctx: Ctx):
    from halo_harness.subscription_scrub import equivalent_ref, scrub_model_block, scrub_text
    ctx.check("cc:claude-opus-5-5 -> or:anthropic/claude-opus-5.5", equivalent_ref("cc:claude-opus-5-5") == "or:anthropic/claude-opus-5.5")
    ctx.check("cc:claude-sonnet-5 keeps a single version", equivalent_ref("cc:claude-sonnet-5") == "or:anthropic/claude-sonnet-5")
    ctx.check("a dated id drops the date", equivalent_ref("cc:claude-haiku-4-5-20251001") == "or:anthropic/claude-haiku-4.5")
    ctx.check("a bare family alias goes to the family's current row", equivalent_ref("cc:opus") == "or:anthropic/claude-opus-5.5")
    ctx.check("cx: goes to openai/", equivalent_ref("cx:gpt-5") == "or:openai/gpt-5")
    ctx.check("an API ref is untouched", equivalent_ref("or:deepseek/deepseek-chat") == "or:deepseek/deepseek-chat" and equivalent_ref("default") == "default")
    models = {"preference": "cc:claude-sonnet-5", "fallback": "ol:qwen3", "escalation": "cx:gpt-5"}
    notes = scrub_model_block(models, where="x.models")
    ctx.check(f"a model block is rewritten in place with notes, got {models} {notes}",
              models == {"preference": "or:anthropic/claude-sonnet-5", "fallback": "ol:qwen3", "escalation": "or:openai/gpt-5"} and len(notes) == 2)
    text, changes = scrub_text("models:\n  preference: cc:claude-fable-5-1\n  fallback: or:x/y\nescalation: {to: cx:gpt-5}\n")
    ctx.check(f"a YAML text is scrubbed token by token, got {changes}", "cc:" not in text and "cx:" not in text and len(changes) == 2 and "or:x/y" in text)


@test
def test_copies_on_disk_are_scrubbed_and_a_handwritten_bio_never_resolves_to_a_subscription(ctx: Ctx):
    import tempfile
    from pathlib import Path as _P
    from halo_harness.providers.config import default_state_dir
    from halo_harness.subscription_consent import record_acceptance, revoke
    from halo_harness.subscription_scrub import scrub_files
    from halo_harness.agents_yaml import resolve_agent_bio, save_agent_bio, user_agents_dir
    state = _P(default_state_dir())
    proj = _P(tempfile.mkdtemp(prefix="halo-scrub-"))
    (proj / ".halo" / "teams").mkdir(parents=True)
    (proj / ".halo" / "teams" / "old.yaml").write_text("name: old\nroles:\n  main: general\nescalation:\n  to: cc:claude-opus-5-5\n", encoding="utf-8")
    done = scrub_files(state_dir=state, cwd=proj)
    ctx.check(f"a project lineup copy loses its cc: ref, got {done}", any(p.name == "old.yaml" for p, _c in done)
              and "cc:" not in (proj / ".halo" / "teams" / "old.yaml").read_text(encoding="utf-8"))
    ctx.check("a second scrub changes nothing", scrub_files(state_dir=state, cwd=proj) == [])
    user_agents_dir(state_dir=state).mkdir(parents=True, exist_ok=True)
    save_agent_bio("sub-bio", {"name": "sub-bio", "description": "names a subscription", "kind": "subagent",
                               "models": {"preference": "cc:claude-sonnet-5", "fallback": "cx:gpt-5"}}, state_dir=state)
    record_acceptance()
    try:
        bio = resolve_agent_bio("sub-bio", state_dir=state)
        ctx.check(f"even with the routes accepted the bio resolves to API models, got {bio.get('models')}",
                  bio["models"]["preference"] == "or:anthropic/claude-sonnet-5" and bio["models"]["fallback"] == "or:openai/gpt-5")
    finally:
        revoke()
    from halo_harness.teams_yaml import resolve_role_table
    table, notes = resolve_role_table({"name": "t", "agents": [{"agent": "sub-bio", "role": "main"}]}, state_dir=state)
    ctx.check(f"the role table never carries a subscription route, got {table} {notes}",
              table.get("main") == "or:anthropic/claude-sonnet-5" and not any(str(v).startswith(("cc:", "cx:")) for v in table.values()))


if __name__ == "__main__":
    ctx = Ctx()
    results, passed, failed, skipped = run_all(TESTS, ctx)
    print_results(results, passed, failed, skipped)
    sys.exit(1 if failed else 0)
