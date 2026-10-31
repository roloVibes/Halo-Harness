"""tests.test_library_presets -- Halo 3.3.6.0 R2 "presets and the inverse flow" (models_library/presets.py,
presets_save.py, role_gaps.py, studio/local_verify_job.py, studio/local_search_api.py) over the library snapshot
and a fake Ollama on 127.0.0.1:0 whose pulls are scripted (tests/helpers/mock_ollama_pull.py) and whose model
answers the battery like a full agent (tests/helpers/mock_ollama_battery.py). No real server, no model call:

1. each preset's bundle (needs at their floors, fit, supply, its role), all nine in order;
2. Save as role template writes `local-<preset>` through the teams path, and the role entry of a lineup named;
3. the sentence parser ("a local coder that can use tools" -> Coder + tools verified-or-declared, and the extras);
4. the inverse flow: a lineup role -> its preset -> the ranked rows, a probed model first; a lineup gap names it
   (`halo teams show`, Roles -> Problems' `find`);
5. Download and verify: one job, `pull` then `probe` frames, the profile written, the role offered; the offer
   accepted writes the lineup (POST local/library/assign).
Run: python -m tests.test_library_presets
"""
from __future__ import annotations

import contextlib
import io
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from tests.helpers.runner import Ctx, new_registry, print_results, run_all  # noqa: E402
from tests.helpers.search_rig import SearchHome, box_card  # noqa: E402

test, TESTS = new_registry()


def _models(table: dict) -> dict:
    from halo_harness.roles import role_value_parts
    return {k: role_value_parts(v)[0] for k, v in table.items()}


def _api(h, method, path, body=None, query=None):
    from halo_harness.studio.api import Request, dispatch
    return dispatch(Request(method=method, path=path, query=query or {}, body=body or {}, cwd=h.root, state_dir=h.state,
                            server=None))


@test
def test_each_presets_bundle(ctx: Ctx):
    from halo_harness.models_library.presets import ORDER, all_bundles, bundle
    titles = [b["title"] for b in all_bundles()]
    ctx.check(f"nine presets in the brief's order, got {titles}", titles == ["Coder", "Reasoner / planner", "Bulk worker", "Compactor",
              "Verifier", "Security / pentest", "Multimodal", "Embeddings", "Offline-only"] and len(ORDER) == 9)
    c, v, o = bundle("coder"), bundle("verifier"), bundle("offline")
    ctx.check(f"Coder: coder expected + tools declared, fits, runs here, role coder, got {c}",
              c["needs"] == {"coder": "expected", "tools": "declared"} and c["fit"] == {"fits_at": True} and c["role"] == "coder")
    ctx.check(f"Verifier: verifier any (needs a probe) + tools, role reviewer, got {v['needs']}",
              v["needs"] == {"verifier": "any", "tools": "declared"} and v["role"] == "reviewer")
    ctx.check(f"Offline-only: runs here, loads on this Ollama, not gated, got {o['supply']}",
              o["supply"] == {"runs_here": True, "ollama_supports": True, "gated": False})
    e = bundle("coder", needs={"tools": "verified"}, fit={"params_max": 14})
    ctx.check(f"a bundle is editable: an override replaces its keys, got {e['needs']} {e['fit']}",
              e["needs"]["tools"] == "verified" and e["fit"] == {"fits_at": True, "params_max": 14} and bundle("coder")["needs"]["tools"] == "declared")
    with SearchHome(card=box_card()) as h:
        s, body = _api(h, "GET", "local/library/presets")
    ctx.check(f"GET local/library/presets: the nine expanded, got {s} {[p['id'] for p in body.get('presets', [])]}",
              s == 200 and [p["id"] for p in body["presets"]] == list(ORDER))


@test
def test_save_as_role_template_writes_the_lineup(ctx: Ctx):
    from halo_harness.teams_yaml import resolve_role_table, resolve_team_template
    with SearchHome(card=box_card()) as h:
        s, ans = _api(h, "POST", "local/library/template", {"preset": "verifier", "model": "ol:bt-coder:30b@box"})
        from halo_harness.teams_yaml import load_team_template_raw
        t = resolve_team_template("local-verifier", state_dir=h.state) or {}
        table = _models(resolve_role_table(t, state_dir=h.state)[0] if t else {})
        raw = load_team_template_raw("local-verifier", state_dir=h.state) or {}
        s2, ans2 = _api(h, "POST", "local/library/template", {"preset": "coder", "lineup": "local-verifier", "model": "ol:qwen3-coder:30b@box"})
        t2 = resolve_team_template("local-verifier", state_dir=h.state) or {}
        raw2 = load_team_template_raw("local-verifier", state_dir=h.state) or {}
        bad = _api(h, "POST", "local/library/template", {"preset": "poetry"})
    ctx.check(f"written, not active, with the command that applies it, got {s} {ans}",
              s == 200 and ans["ok"] and ans["lineup"] == "local-verifier" and "halo teams apply local-verifier" in ans["say"])
    ctx.check(f"the lineup: main and verify on the model, the bundle as `search`, got {table} {raw.get('search')}",
              table.get("verify") == "ol:bt-coder:30b@box" and (raw.get("search") or {}).get("verify", {}).get("id") == "verifier")
    ctx.check(f"into a lineup named: its coder entry added with the model and the bundle, got {s2} {ans2.get('say')}",
              s2 == 200 and _models(resolve_role_table(t2, state_dir=h.state)[0]).get("coder") == "ol:qwen3-coder:30b@box"
              and "coder" in (raw2.get("search") or {}))
    ctx.check(f"an unknown preset names the nine, got {bad}", bad[0] == 422 and "coder" in bad[1]["say"])


@test
def test_the_sentence_parser(ctx: Ctx):
    from halo_harness.models_library.presets import parse_sentence, preset_for_role
    a = parse_sentence("a local coder that can use tools")
    b = parse_sentence("find me a local coder that fits my card and can use tools")
    c = parse_sentence("an uncensored model that can see images, under 12 GB, apache licence")
    ctx.check(f"a coder that uses tools: Coder + tools verified-or-declared, got {a}",
              a["preset"] == "coder" and a["needs"] == {"tools": "declared"} and "tools verified or declared" in a["understood"])
    ctx.check(f"fits my card: fits at the window, got {b['fit']}", b["preset"] == "coder" and b["fit"] == {"fits_at": True})
    ctx.check(f"the extras: vision, abliterated, a disk ceiling, a permissive licence, got {c}",
              c["preset"] == "multimodal" and c["needs"].get("abliterated") and c["fit"].get("disk_max_gb") == 12.0
              and c["supply"] == {"licence": "permissive"})
    got = {r: preset_for_role(r) for r in ("verify", "coder", "planner", "compaction", "small", "eyes", "embed", "lunch")}
    ctx.check(f"a lineup role -> its preset, got {got}", got == {"verify": "verifier", "coder": "coder", "planner": "reasoner",
              "compaction": "compactor", "small": "bulk", "eyes": "multimodal", "embed": "embeddings", "lunch": ""})


@test
def test_the_inverse_flow_and_the_lineup_gap(ctx: Ctx):
    from halo_harness.models_library.presets import for_role
    with SearchHome(card=box_card()) as h:
        h.profile("qwen3:14b", size_gb=9.3)
        h.profile("qwen3:8b", tools="no", agentic_ready=False)
        got = for_role("verify", state_dir=h.state, host="box")
        said = for_role("a local coder that can use tools", state_dir=h.state, host="box")
        from halo_harness.models_library.presets_save import save
        save("verifier", state_dir=h.state, model="ol:qwen3:8b@box")  # verify on a model with no tool calling
        out = io.StringIO()
        from halo_harness.teams_cli import cmd_teams
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(io.StringIO()):
            rc = cmd_teams(["show", "local-verifier"])
        from halo_harness.teams_yaml import load_team_template_raw
        from halo_harness.studio.roles_findings import findings_for
        found = findings_for(load_team_template_raw("local-verifier", state_dir=h.state), problems=[], graph={}, state_dir=h.state)
    rows = got["rows"]
    ctx.check(f"verify -> the Verifier preset, the probed model first, got {got['search']['preset']} {[r['name'] for r in rows[:3]]}",
              got["search"]["preset"] == "verifier" and rows and rows[0]["name"] == "qwen3:14b" and rows[0]["gate_tier"] == 3
              and rows[0]["verdicts"]["role_ready"]["ok"] is True)
    ctx.check(f"the rest need a probe (download and verify), got {rows[1]['facts']['verifier']['why'] if len(rows) > 1 else None}",
              len(rows) > 1 and all(r["gate_tier"] == 0 for r in rows[1:]))
    ctx.check(f"a sentence -> Coder with tools, got {said['search']['understood']}",
              said["search"]["preset"] == "coder" and said["rows"] and all(r["facts"]["tools"]["value"] for r in said["rows"]))
    text = out.getvalue()
    ctx.check(f"halo teams show names the gap and the command, got {text[-400:]!r}",
              rc == 0 and "(gap) `verify` on ol:qwen3:8b@box: no tool calling" in text and "halo models browse --for-role verify" in text)
    gap = next((f for f in found if f["id"] == "gap:verify"), None)
    ctx.check(f"Roles -> Problems: the gap carries find {{role, preset}}, got {gap}",
              gap and gap["find"] == {"role": "verify", "preset": "verifier"} and "find a model for this role" in gap["fix"])


@test
def test_download_and_verify_is_one_job_in_two_stages(ctx: Ctx):
    from tests.helpers import mock_ollama_battery as MB
    from tests.helpers.mock_ollama import MockUpstream
    from halo_harness.studio import local_verify_job as J
    mock = MockUpstream().start()
    try:
        MB.install(mock, ["bt-coder:30b"])
        show = mock.show_responses.pop("bt-coder:30b")
        mock.tags_response = {"models": []}
        mock.pullable = {"bt-coder:30b": show}
        with SearchHome(card=box_card(), url=mock.base_url) as h:
            frames: list = []
            from halo_harness.providers.ollama import resolve_ollama_host
            view = J.start(resolve_ollama_host("box"), "bt-coder:30b", frames.append, state_dir=h.state, role="verify")
            t0 = time.time()
            while time.time() - t0 < 90 and not (J.current()["jobs"][0]["done"]):
                time.sleep(0.2)
            done = J.current()["jobs"][0]
            from halo_harness.providers.ollama_capability import profile_for
            prof = profile_for(h.state, "bt-coder:30b", "box")
            s, ans = _api(h, "POST", "local/library/assign", {"role": "verify", "ref": done["offer"]["ref"] if done.get("offer") else ""})
            from halo_harness.teams_yaml import resolve_role_table, resolve_team_template
            table = _models(resolve_role_table(resolve_team_template(ans.get("lineup") or "-", state_dir=h.state) or {}, state_dir=h.state)[0])
            s2, routed = _api(h, "POST", "local/library/verify", {"host": "box", "name": "bt-coder:30b", "role": "verify"})
            s3, _vs = _api(h, "GET", "local/library/verifies")
    finally:
        mock.stop()
        J.reset()
    kinds = [f["event"] for f in frames]
    stages = [f["data"]["stage"] for f in frames if f["event"] == "verify"]
    ctx.check(f"one job: verify frames around pull then probe frames, got {kinds[:3]}...{sorted(set(kinds))}",
              view["stage"] == "pull" and "pull" in kinds and "probe" in kinds and kinds.index("pull") < kinds.index("probe"))
    ctx.check(f"its stages: pull, probe, offer, got {stages}", stages[0] == "pull" and "probe" in stages and stages[-1] == "offer")
    ctx.check(f"the profile is written to the capability cache, got {prof and prof.get('sits')}", prof is not None and prof.get("tools") == "yes")
    ctx.check(f"the offer: assign `verify` to ol:bt-coder:30b@box?, got {done.get('offer')}",
              done["ok"] and done["offer"]["ok"] and done["offer"]["line"] == "assign `verify` to ol:bt-coder:30b@box?")
    ctx.check(f"accepted: the lineup's verify role on it, got {s} {ans} {table}",
              s == 200 and ans["ok"] and table.get("verify") == "ol:bt-coder:30b@box")
    ctx.check(f"the route starts the same job, and lists it, got {s2} {routed.get('stage')} {s3}", s2 == 200 and routed.get("job") and s3 == 200)


if __name__ == "__main__":
    ctx = Ctx()
    results, passed, failed, skipped = run_all(TESTS, ctx)
    sys.exit(print_results(results, passed, failed, skipped))
