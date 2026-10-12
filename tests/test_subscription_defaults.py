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
    from halo_harness.subscription_consent import is_accepted
    ctx.check("the gate is off in a fresh home", is_accepted() is False)
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


if __name__ == "__main__":
    ctx = Ctx()
    results, passed, failed, skipped = run_all(TESTS, ctx)
    print_results(results, passed, failed, skipped)
    sys.exit(1 if failed else 0)
