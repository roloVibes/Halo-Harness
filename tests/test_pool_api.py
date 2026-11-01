"""tests.test_pool_api -- Halo 3.3.8.0 R1 deliverable 6, the Python half: Studio's Local -> Pool routes
(studio/pool_api.py through studio/local_api.dispatch_local) and the Library's Pool preset (local_pool/library.py
through GET local/library), over a scratch home; the scan's network layer faked, an rpc-server stand-in on
127.0.0.1:0; no model call (the Chrome half is tests/test_studio_pool.py):

1. GET local/pool/members with none, POST local/pool/members add (two stated members) and a refused add (422 with the
   line), remove; the members' head, split and the R2 line;
2. GET local/pool/recommend (and ?batch=1), GET local/pool/verdict (200, 404 for a name not in the catalog, 422 with
   none);
3. POST local/pool/scan: the candidate, the members probed, then GET members carries the scan line and each RTT;
   a GET on the scan route is 405 (a scan is never a page load), an unknown pool route 404;
4. the Library's Pool preset: the three pool catalog rows as hub GGUF rows, each with its badge and preview; Save as
   role template refuses the Pool preset with one line.
Run: python -m tests.test_pool_api
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from tests.helpers.pool_rig import PoolHome, rpc_listener  # noqa: E402
from tests.helpers.runner import Ctx, new_registry, print_results, run_all  # noqa: E402

test, TESTS = new_registry()


def _api(state, method: str, path: str, body=None, query=None):
    from halo_harness.studio.api import Request, dispatch
    return dispatch(Request(method=method, path=path, query=query or {}, body=body or {}, cwd=Path(state),
                            state_dir=state, server=None))


@test
def test_members_add_remove(ctx: Ctx):
    with PoolHome() as h:
        s, got = _api(h.state, "GET", "local/pool/members")
        ctx.check(f"no members: the add line, the R2 line, got {s} {got.get('head')!r}", s == 200 and got["members"] == []
                  and got["head"].startswith("no members yet") and got["not_yet"].startswith("warm and stop arrive in R2"))
        s, got = _api(h.state, "POST", "local/pool/members", {"op": "add", "name": "worker1", "host": "worker1.local",
                                                              "port": "50052", "vram_gb": "40"})
        ctx.check(f"add: 200, the line, the cli, got {s} {got}", s == 200 and got["ok"] and got["cli"] ==
                  "halo pool add worker1 worker1.local:50052 --vram 40")
        _api(h.state, "POST", "local/pool/members", {"op": "add", "name": "worker2", "host": "192.0.2.12", "vram_gb": 20})
        s, got = _api(h.state, "POST", "local/pool/members", {"op": "add", "name": "worker2", "host": "worker9.local"})
        ctx.check(f"a name twice: 422 with the line, got {s} {got.get('problems')}", s == 422
                  and "worker2 is a member twice" in got["problems"][0])
        s, got = _api(h.state, "GET", "local/pool/members")
        ctx.check(f"two members, the split, the head, got {got['head']!r}", s == 200 and len(got["members"]) == 2
                  and got["split"] == [0.6667, 0.3333] and got["head"].startswith("2 members, 2 with VRAM read: 60.0 GB free"))
        s, got = _api(h.state, "POST", "local/pool/members", {"op": "remove", "name": "worker2"})
        ctx.check(f"remove: 200, got {s} {got.get('lines')}", s == 200 and len(got["members"]) == 1)
        s, got = _api(h.state, "POST", "local/pool/members", {"op": "rename"})
        ctx.check(f"an unknown op: 422, got {s}", s == 422)


@test
def test_recommend_and_verdict(ctx: Ctx):
    from halo_harness.local_pool import members as M
    with PoolHome() as h:
        M.add("worker1", "worker1.local", vram_gb=40, state_dir=h.state)
        M.add("worker2", "worker2.local", vram_gb=20, state_dir=h.state)
        s, got = _api(h.state, "GET", "local/pool/recommend")
        ctx.check(f"recommend: Qwen3-Next ranked, Llama left out, the cli, got {s} {[r['model'] for r in got['rows']]}",
                  s == 200 and [r["model"] for r in got["rows"]] == ["qwen3-next-80b-a3b-q4km"] and got["cli"] == "halo pool recommend"
                  and got["hidden"][0]["model"] == "llama-3.3-70b-q4km")
        s, got = _api(h.state, "GET", "local/pool/recommend", query={"batch": "1"})
        ctx.check(f"?batch=1: Llama ranked 2, got {[(r['model'], r['rank']) for r in got['rows']]}", s == 200
                  and got["rows"][1]["model"] == "llama-3.3-70b-q4km" and got["rows"][1]["rank"] == 2)
        s, got = _api(h.state, "GET", "local/pool/verdict", query={"model": "gpt-oss-120b"})
        ctx.check(f"verdict: 200, no, the badge, got {s} {got.get('badge')}", s == 200 and got["state"] == "no"
                  and got["badge"] == "pool: no" and got["cli"] == "halo pool verdict gpt-oss-120b")
        s, got = _api(h.state, "GET", "local/pool/verdict", query={"model": "llama-9000"})
        ctx.check(f"a name not in the catalog: 404, got {s}", s == 404 and "gpt-oss-120b" in got["catalog"])
        s, _got = _api(h.state, "GET", "local/pool/verdict")
        ctx.check(f"no model: 422, got {s}", s == 422)


@test
def test_scan_is_a_post(ctx: Ctx):
    from halo_harness.local_pool import members as M
    from halo_harness.providers import rpc_probe as P
    with PoolHome() as h, rpc_listener() as port:
        M.add("w1", f"127.0.0.1:{port}", vram_gb=24, state_dir=h.state)
        s, _g = _api(h.state, "GET", "local/pool/scan")
        ctx.check(f"GET on the scan: 405 (a scan is never a page load), got {s}", s == 405)
        s, _g = _api(h.state, "GET", "local/pool/nothing")
        ctx.check(f"an unknown pool route: 404, got {s}", s == 404)
        P.SEAMS.update(sweep=lambda networks, ports, deadline: [("127.0.0.1", port)], own=lambda: "192.0.2.5")
        s, got = _api(h.state, "POST", "local/pool/scan", {"port": port})
        ctx.check(f"POST scan: the candidate is w1, the cli, got {s} {got.get('line')!r} {got.get('cli')!r}", s == 200
                  and got["candidates"][0]["member"] == "w1" and got["members"][0]["alive"] and got["cli"] == f"halo pool scan --port {port}")
        s, got = _api(h.state, "GET", "local/pool/members")
        ctx.check(f"the members carry the scan line and the RTT, got {got['scan']} {got['members'][0]['rtt_word']!r}",
                  got["scan"]["line"].startswith("1 rpc-server port answered") and got["members"][0]["rtt_word"].endswith("ms"))


@test
def test_the_librarys_pool_preset(ctx: Ctx):
    from halo_harness.local_pool import members as M
    from tests.helpers.search_rig import SearchHome, box_card
    with SearchHome(card=box_card()) as h:
        M.add("worker1", "worker1.local", vram_gb=40, state_dir=h.state)
        M.add("worker2", "worker2.local", vram_gb=20, state_dir=h.state)
        s, got = _api(h.state, "GET", "local/library", query={"source": "ollama", "preset": "pool", "edited": "1"})
        rows = got.get("rows") or []
        ctx.check(f"the Pool preset: the three pool rows, ranked, got {s} {[r.get('key') for r in rows]}", s == 200
                  and [r["key"] for r in rows] == ["pool/qwen3-next-80b-a3b-q4km", "pool/llama-3.3-70b-q4km", "pool/gpt-oss-120b"]
                  and got["search"]["preset"] == "pool" and got["total"] == 3)
        badges = [r["pool"]["badge"] for r in rows]
        ctx.check(f"each with its badge, got {badges}", badges == ["pool: fits (2 nodes, 32k Q8_0)",
                                                                    "pool: fits (2 nodes, 32k Q8_0)", "pool: no"])
        q = rows[0]
        ctx.check(f"a hub GGUF row with no Pull: Download only, its card and its fit on box (46 GB on a 24 GB card spills), got {q['source']} {q['kind']} "
                  f"{q['pull_target']!r} {q['fit'].get('level')}", q["source"] == "hf" and q["kind"] == "gguf"
                  and q["pull_target"] == "" and q["id"] == "Qwen/Qwen3-Next-80B-A3B-Instruct-GGUF" and q["fit"]["level"] == "spill"
                  and q["card"] and q["pool"]["preview"].startswith("needs 53.6 GB -- 60.0 GB free across 2 nodes"))
        ctx.check("the Pool preset is in the presets list", "pool" in [p["id"] for p in got["presets"]])
        s, got = _api(h.state, "GET", "local/library", query={"source": "ollama", "preset": "coder", "edited": "1"})
        ctx.check("another preset keeps its rows (no pool rows)", s == 200 and not any(r.get("pool") for r in got["rows"]))
        s, got = _api(h.state, "POST", "local/library/template", {"preset": "pool"})
        ctx.check(f"Save as role template refuses Pool with one line, got {s} {got}", s != 200
                  and "fills no lineup role" in str(got))


if __name__ == "__main__":
    ctx = Ctx()
    results, passed, failed, skipped = run_all(TESTS, ctx)
    sys.exit(print_results(results, passed, failed, skipped))
