"""tests.test_library_presets -- Halo 3.3.6.0 R2 "presets and the inverse flow" (models_library/presets.py,
presets_save.py, role_gaps.py, studio/local_verify_job.py, studio/local_search_api.py) over the library snapshot
and a fake Ollama on 127.0.0.1:0 whose pulls are scripted (tests/helpers/mock_ollama_pull.py) and whose model
answers the battery like a full agent (tests/helpers/mock_ollama_battery.py). No real server, no model call:

1. each preset's bundle (needs at their floors, fit, supply, its role), all nine in order;
2. Save as role template writes the agent `local-<preset>` on the model (3.6.0.0 R5c, where it wrote a lineup), a new
   session hands it work on that model; with no model, a lineup named, or no role it refuses in one line; a fresh
   home gets no `teams` folder and no old-files line;
3. the sentence parser ("a local coder that can use tools" -> Coder + tools verified-or-declared, and the extras);
4. the inverse flow: a lineup role -> its preset -> the ranked rows, a probed model first; a lineup gap names it
   (`halo teams show`, Roles -> Problems' `find`);
5. Download and verify: one job, `pull` then `probe` frames, the profile written, the role offered; the offer
   accepted writes roles.<role> and nothing else (POST local/library/assign); a new session's coder card runs on an
   assigned coder model.
Run: python -m tests.test_library_presets
"""
from __future__ import annotations

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
    ctx.check(f"ten presets in the brief's order (3.3.8.0 R1: Pool last), got {titles}", titles == ["Coder", "Reasoner / planner", "Bulk worker", "Compactor",
              "Verifier", "Security / pentest", "Multimodal", "Embeddings", "Offline-only", "Pool"] and len(ORDER) == 10)
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
    ctx.check(f"GET local/library/presets: the ten expanded, got {s} {[p['id'] for p in body.get('presets', [])]}",
              s == 200 and [p["id"] for p in body["presets"]] == list(ORDER))


def _new_session(h):
    from halo_harness import headless  # a new plain session, as `halo -p` builds one
    return headless.build_session(cwd=h.root, model_ref_raw="ol:bt-coder:30b@box", print_mode=True, cli_flags={}).session


def _fresh(h) -> "tuple[str, bool]":
    from halo_harness.crew import old_files
    return old_files.line(state_dir=h.state), (h.state / "teams").exists()


@test
def test_save_as_role_template_writes_an_agent(ctx: Ctx):
    """3.6.0.0 R5c (the judge's M1): an agent file in today's format, not a lineup no session reads."""
    from halo_harness.crew import store
    from tests.test_crew_compile import _child
    with SearchHome(card=box_card()) as h:
        s, ans = _api(h, "POST", "local/library/template", {"preset": "verifier", "model": "ol:bt-coder:30b@box"})
        body = store.load("agent", "local-verifier", state_dir=h.state) or {}
        line, teams = _fresh(h)
        fresh = _new_session(h)
        child = _child(fresh, fresh.agent_runtime.agents["local-verifier"], None, "check the diff")
        fresh.close_runtimes()
        bare = _api(h, "POST", "local/library/template", {"preset": "verifier"})
        named = _api(h, "POST", "local/library/template", {"preset": "coder", "lineup": "local-verifier", "model": "ol:qwen3-coder:30b@box"})
        embed = _api(h, "POST", "local/library/template", {"preset": "embeddings", "model": "ol:nomic-embed-text@box"})
        bad = _api(h, "POST", "local/library/template", {"preset": "poetry"})
        line2, teams2 = _fresh(h)
    ctx.check(f"written: one line naming the agent and the model, got {s} {ans}",
              s == 200 and ans["ok"] and ans["agent"] == "local-verifier" and ans["say"].startswith("agent local-verifier written")
              and "halo teams" not in ans["say"])
    ctx.check(f"the agent file: agent/1 on the model, read only, got {body}", body.get("format") == "agent/1"
              and body.get("model") == "ol:bt-coder:30b@box" and body.get("uses") == ["read"])
    ctx.check(f"a new session hands it work on that model, got {child}", child["model"] == "ol:bt-coder:30b@box")
    ctx.check(f"a fresh home: no teams folder, no old-files line, got {teams} {line!r}", not teams and line == "")
    ctx.check(f"no model: refused in one line, got {bare}", bare[0] == 422 and len(bare[1]["lines"]) == 1
              and bare[1]["say"].startswith("pick a model first"))
    ctx.check(f"a lineup named: refused in one line, got {named}", named[0] == 422 and "reads no lineup" in named[1]["say"])
    ctx.check(f"no role (Embeddings): refused in one line, got {embed}", embed[0] == 422 and "fills no role" in embed[1]["say"])
    ctx.check(f"an unknown preset names the nine, got {bad}", bad[0] == 422 and "coder" in bad[1]["say"])
    ctx.check(f"and still no teams folder, no old-files line, got {teams2} {line2!r}", not teams2 and line2 == "")


@test
def test_assign_writes_the_role_and_a_new_session_runs_on_it(ctx: Ctx):
    """3.6.0.0 R5c (the judge's M1): roles.<role> and nothing else -- no lineup, no `halo teams apply`, roles kept on."""
    from halo_harness.theme import get_config_value
    from tests.test_crew_compile import _child
    with SearchHome(card=box_card()) as h:
        before = dict(get_config_value("roles", default={}) or {})
        s, ans = _api(h, "POST", "local/library/assign", {"role": "coder", "ref": "ol:qwen3-coder:30b@box"})
        after = dict(get_config_value("roles", default={}) or {})
        line, teams = _fresh(h)
        fresh = _new_session(h)
        child = _child(fresh, fresh.agent_runtime.agents["coder"], "coder", "implement the retry in client.py")
        fresh.close_runtimes()
    ctx.check(f"one line, roles.coder, no lineup words, got {s} {ans}", s == 200 and ans["ok"]
              and ans["say"].startswith("roles.coder = ol:qwen3-coder:30b@box") and "lineup" not in ans["say"]
              and "teams" not in ans["say"])
    ctx.check(f"roles.coder written and nothing else, got {before} -> {after}",
              {k: v for k, v in after.items() if before.get(k) != v} == {"coder": "ol:qwen3-coder:30b@box"})
    ctx.check(f"a fresh home: no teams folder, no old-files line, got {teams} {line!r}", not teams and line == "")
    ctx.check(f"a new session's coder runs on it, got {child}", child["model"] == "ol:qwen3-coder:30b@box")


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
            from halo_harness.roles import configured_role_table
            table = _models(configured_role_table())
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
    ctx.check(f"accepted: roles.verify on it, got {s} {ans} {table}",
              s == 200 and ans["ok"] and table.get("verify") == "ol:bt-coder:30b@box")
    ctx.check(f"the route starts the same job, and lists it, got {s2} {routed.get('stage')} {s3}", s2 == 200 and routed.get("job") and s3 == 200)


if __name__ == "__main__":
    ctx = Ctx()
    results, passed, failed, skipped = run_all(TESTS, ctx)
    sys.exit(print_results(results, passed, failed, skipped))
