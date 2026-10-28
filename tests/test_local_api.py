"""tests.test_local_api -- Halo 3.3.5.0 R1: the Local section's routes (studio/local_api.py, local_hosts_view.py,
local_models_view.py, local_traffic.py, local_catalog.py) on the seeded state dir of tests/helpers/local_seed.py
(the Ollama panel's fixture plus `box`, a fake Ollama on 127.0.0.1:0). In-process through studio/api.dispatch, a
fresh home, background reads off: no real server, no model call.

1. GET local/hosts: every host as a card -- configured, the local server, a fleet member's host -- with its kind,
   what is loaded and its VRAM share, who calls it, the steward's finding, the fit plan's chosen option, the controls;
2. POST local/host/box/load | unload against the fake: a /api/generate with the profile's window and keep-alive,
   then keep_alive 0; a host another machine serves is refused with the reason, and so is one whose fleet member
   has fleet.allow_control: none; with `all` the command goes to the member's session (host = the member's name);
3. POST local/host/add writes the ollama.hosts entry through Setup's writer;
4. GET local/traffic: the fixture ledger's rows, the per-host buckets with the bytes; a ledger line written while a
   listener is on becomes a `traffic` frame; POST local/traffic (another process's tap) publishes them;
5. GET local/models: the cards, the meters and the intent scores (embed: the embedding model only; code: the coder
   first); GET local/resources and POST local/resources/watch;
6. the catalog cache keyed by /api/tags' signature; the 404 / 405 / 409 / 422 answers.
Run: python -m tests.test_local_api
"""
from __future__ import annotations

import json
import sys
from pathlib import Path
from types import SimpleNamespace

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from tests.helpers.provider_env_defaults import ensure_default_provider_credentials  # noqa: E402
ensure_default_provider_credentials()

from tests.helpers import local_seed as L  # noqa: E402
from tests.helpers.local_api_rig import FakeHub, Local  # noqa: E402
from tests.helpers.runner import Ctx, new_registry, print_results, run_all  # noqa: E402

test, TESTS = new_registry()


@test
def test_the_hosts_page(ctx: Ctx):
    with Local() as h:
        status, body = h.api("GET", "local/hosts")
        names = [(c["name"], c["source"]) for c in body["hosts"]]
        ctx.check(f"200, every host: the three configured, the local server, got {status} {names}", status == 200
                  and names[:4] == [("pc", "configured"), ("samus", "configured"), ("box", "configured"), ("llama-box", "local server")])
        pc, box = h.card("pc"), h.card("box")
        ctx.check(f"pc: Ollama, another machine's, the 27B loaded at 90% VRAM, got {pc['kind']} {pc['served_by']} {pc['loaded']}",
                  pc["kind"] == "Ollama" and pc["served_by"] == "another machine" and pc["loaded"][0]["vram_pct"] == 90)
        ctx.check(f"pc: who calls it and the steward's finding, got {pc['users']} {pc['finding']!r}",
                  pc["users"] == [{"from": None, "calls": 12}] and "cut" in (pc["finding"] or ""))
        ctx.check(f"pc: the fit plan's chosen option has changes, got {pc['plan']}",
                  pc["plan"] and pc["plan"]["fits_now"] is False and pc["plan"]["chosen"]["changes"])
        ctx.check(f"pc: no control from here, and why, got {pc['controls']}",
                  pc["controls"]["ok"] is False and "served by another machine" in pc["controls"]["why"])
        ctx.check(f"box: served here, its models from the catalog, Load from here, got {box['controls']} {box['models']}",
                  box["served_here"] and box["controls"] == {"ok": True, "via": "this machine", "why": ""}
                  and box["models"] == list(L.BOX_MODELS) and box["version"] == "0.40.6")
        from halo_harness.ollama_steward.resources_share import take_remote
        take_remote(h.state, L.MEMBER, L.member_samples())
        mac = h.card("local@" + L.MEMBER)
        ctx.check(f"a fleet member's host from its samples, got {mac['source']} {mac['served_by']} {mac['loaded']}",
                  mac["source"] == "member" and mac["served_by"] == L.MEMBER and mac["loaded"][0]["model"] == "qwen3.5:9b")


@test
def test_load_and_unload(ctx: Ctx):
    with Local() as h:
        from halo_harness.ollama_steward.profiles import set_field
        set_field("box|qwen3.5:9b", "num_ctx", 16384, by="user")
        status, body = h.api("POST", "local/host/box/load", {"model": "qwen3.5:9b", "keep_alive": "30m"})
        gen = h.mock.generated[-1] if h.mock.generated else {}
        ctx.check(f"Load: 200, a generate with the profile's window and the keep-alive, got {status} {body.get('say')!r} {gen}",
                  status == 200 and gen.get("options") == {"num_ctx": 16384} and gen.get("keep_alive") == "30m"
                  and "16,384 (the steward profile)" in body["say"])
        ctx.check(f"the card shows it loaded, got {h.card('box')['loaded']}", [m["model"] for m in h.card("box")["loaded"]] == ["qwen3.5:9b"])
        status, body = h.api("POST", "local/host/box/unload", {"model": "qwen3.5:9b"})
        ctx.check(f"Unload: keep_alive 0, gone from /api/ps, got {status} {h.mock.generated[-1]}",
                  status == 200 and h.mock.generated[-1]["keep_alive"] == 0 and h.card("box")["loaded"] == [])
        status, body = h.api("POST", "local/host/box/load", {"model": "not-here:1b"})
        ctx.check(f"a model the server does not have: its answer, got {status} {body.get('error')!r}", status == 502 and "404" in body["error"])
        status, body = h.api("POST", "local/host/pc/load", {"model": "qwen3.8:27b"})
        ctx.check(f"another machine's host: 409 with the reason, got {status} {body}", status == 409 and "another machine" in body["error"])
        ctx.check("nothing reached the fake for it", all(g["model"] != "qwen3.8:27b" for g in h.mock.generated))


@test
def test_a_remote_hosts_control_goes_through_its_member(ctx: Ctx):
    from halo_harness.ollama_steward.resources_share import take_remote
    for level, want in (("none", 409), ("all", 200)):
        hub = FakeHub(level, None)
        with Local(server=hub) as h:
            hub.fleet_hub.home = h.state
            cfg = h.config()
            cfg["ollama"]["hosts"].append({"name": "mac", "url": "http://192.0.2.30:11434"})
            (h.state / "config.json").write_text(json.dumps(cfg), encoding="utf-8")
            take_remote(h.state, L.MEMBER, L.member_samples())
            card = h.card("mac")
            status, body = h.api("POST", "local/host/mac/load", {"model": "qwen3.5:9b"})
            if level == "none":
                ctx.check(f"allow_control none: disabled with the reason, got {card['controls']} {status} {body}",
                          card["controls"]["ok"] is False and "fleet.allow_control: none" in card["controls"]["why"]
                          and status == 409 and "allow_control: none" in body["error"] and not hub.sent)
            else:
                ctx.check(f"allow_control all: the command to the member's session, its own host name, got {status} {hub.sent}",
                          status == want and hub.sent == [("hid-mac", "s-mac", "ollama_load", {"host": "local", "model": "qwen3.5:9b"})])


@test
def test_add_a_found_server(ctx: Ctx):
    from tests.helpers.mock_ollama import MockUpstream
    with Local() as h, MockUpstream() as found:
        status, body = h.api("POST", "local/host/add", {"url": found.base_url, "name": "found"})
        hosts = h.config()["ollama"]["hosts"]
        ctx.check(f"Add to hosts: the entry written through Setup's writer, got {status} {body.get('lines')} {[x['name'] for x in hosts]}",
                  status == 200 and any(x.get("name") == "found" and x.get("url") == found.base_url for x in hosts))
        status, body = h.api("POST", "local/host/add", {"name": "x"})
        ctx.check(f"no url: 422, got {status}", status == 422)


@test
def test_the_traffic_routes_and_the_frames(ctx: Ctx):
    from halo_harness.ollama_steward import ledger_tap
    from halo_harness.ollama_steward.ledger import append_lines
    from halo_harness.studio.local_traffic import tap
    from tests.helpers.steward_seed import line
    with Local() as h:
        status, body = h.api("GET", "local/traffic", query={"since": "15m"})
        calls = {k: sum(b["calls"] for b in v) for k, v in body["spark"].items()}
        ctx.check(f"200: the fixture's rows of the last 15 minutes, per host, got {status} {len(body['rows'])} {calls}",
                  status == 200 and calls == {"pc": 7, "llama-box": 3, "box": 3} and len(body["rows"]) == 13)
        box = [r for r in body["rows"] if r["host"] == "box"]
        ctx.check(f"a row: model, kind, tokens in and out, the window and its source, the bytes, got {box[0]}",
                  box[0]["model"] == "qwen3.5:9b" and box[0]["kind"] == "turn" and box[0]["prompt_in"] == 2000
                  and box[0]["reply_out"] == 120 and box[0]["window"] == 32768 and box[0]["bytes_in"] == 8192 and box[0]["ok"])
        ctx.check("the sparkline buckets carry the bytes", sum(b["bytes_in"] for b in body["spark"]["box"]) == 3 * 8192)
        ctx.check(f"the trimmed and the cut rows are marked, got {sum(r['trimmed'] for r in body['rows'])} {sum(r['cut'] for r in body['rows'])}",
                  sum(r["trimmed"] for r in body["rows"]) == 1 and sum(r["cut"] for r in body["rows"]) == 2)
        frames: list = []
        stop = ledger_tap.listen(h.state, tap(frames.append))
        try:
            append_lines(h.state, [line(host={"name": "box", "url": h.mock.base_url}, model="qwen3-coder:30b", ago=1,
                                        bytes_in=100, bytes_out=50)])
        finally:
            stop()
        rows = [r for f in frames for r in f["data"]["rows"]]
        ctx.check(f"a line written while Studio listens is a `traffic` frame, got {[f['event'] for f in frames]} {rows[:1]}",
                  [f["event"] for f in frames] == ["traffic"] and rows[0]["model"] == "qwen3-coder:30b" and rows[0]["host"] == "box")
        status, body = h.api("GET", "local/traffic", query={"since": "15m"})
        ctx.check("its id is the one the catch-up gives the same line", rows[0]["id"] in {r["id"] for r in body["rows"]})
        status, body = h.api("POST", "local/traffic", {"lines": [{"at": "2026-10-28T00:00:00Z", "model": "m"}]})
        ctx.check(f"another process's tap with no Studio server here: nothing to publish to, got {status} {body}", status == 200 and body["published"] == 0)
        status, _ = h.api("GET", "local/traffic", query={"since": "soon"})
        ctx.check("a since that is no span: 422", status == 422)


@test
def test_the_models_and_resources_routes(ctx: Ctx):
    from halo_harness.studio.local_models_view import rank
    with Local() as h:
        status, body = h.api("GET", "local/models")
        box = next(x for x in body["hosts"] if x["name"] == "box")
        ctx.check(f"box's models with their cards and meters, got {[(m['model'], m['fit']['level']) for m in box['models']]}",
                  status == 200 and [m["model"] for m in box["models"]] == list(L.BOX_MODELS) and box["models"][0]["card"]["chips"])
        ctx.check(f"embed: the embedding model only, got {[m['model'] for m in rank(box['models'], 'embed')]}",
                  [m["model"] for m in rank(box["models"], "embed")] == ["nomic-embed-text"])
        ctx.check(f"code: the coder first, no embedding model, got {[m['model'] for m in rank(box['models'], 'code')]}",
                  [m["model"] for m in rank(box["models"], "code")] == ["qwen3-coder:30b", "qwen3.5:9b"])
        ctx.check("the intents and their why lines", [i["id"] for i in body["intents"]] == ["code", "chat", "long", "images", "embed"]
                  and all(i["why"] for i in body["intents"]))
        coder = next(m for m in box["models"] if m["model"] == "qwen3-coder:30b")
        ctx.check(f"the coder cannot orchestrate (the lane offer's row), got {coder['card']['fit_for']}", coder["card"]["fit_for"]["orchestrator"] is False)
        from halo_harness.ollama_steward import resources
        resources.SAMPLER_SEAMS["hosts"] = lambda: []  # the sampler runs, and samples no host
        status, body = h.api("POST", "local/resources/watch", {"on": True})
        ctx.check(f"the tab's lease turns the sampler on, got {status} {body}", status == 200 and body["on"] and "tab" in body["owners"])
        status, body = h.api("POST", "local/resources/watch", {"on": False})
        ctx.check(f"and off, got {body}", body["on"] is False)
        from halo_harness.ollama_steward.resources import STORE
        STORE.add({"host": "box", "t": __import__("time").time(), "gpu": 12})
        status, body = h.api("GET", "local/resources", query={"host": "box"})
        ctx.check(f"GET local/resources: the samples kept, got {status} {body['samples']}", status == 200 and body["samples"][-1]["gpu"] == 12)
        resources.SAMPLER_SEAMS.clear()


@test
def test_the_catalog_cache_and_the_errors(ctx: Ctx):
    from halo_harness.studio import local_catalog as C
    host = SimpleNamespace(url="http://192.0.2.50:11434", dialect=None)
    built: list = []
    tags = {"models": [{"model": "a", "digest": "1", "modified_at": "t1"}]}
    C.reset()
    C.TAGS_TTL_S = 0.0
    try:
        for _ in range(3):
            C.catalog_for(host, tags=lambda _h: tags, build=lambda h: built.append(1) or {"models": [{"model": "a"}]})
        ctx.check(f"the same /api/tags: the catalog built once, got {len(built)}", len(built) == 1)
        tags["models"].append({"model": "b", "digest": "2", "modified_at": "t2"})
        C.catalog_for(host, tags=lambda _h: tags, build=lambda h: built.append(1) or {"models": []})
        ctx.check(f"a model pulled: built again, got {len(built)}", len(built) == 2)
        C.catalog_for(host, tags=lambda _h: None, build=lambda h: built.append(1) or {"models": []})
        ctx.check("the server not answering keeps the catalog in hand", len(built) == 2)
    finally:
        C.TAGS_TTL_S = 15.0
        C.reset()
    with Local() as h:
        ctx.check("an unknown host: 404", h.api("POST", "local/host/nope/load", {"model": "m"})[0] == 404)
        ctx.check("load without a model: 422", h.api("POST", "local/host/box/load", {})[0] == 422)
        ctx.check("GET on load: 405", h.api("GET", "local/host/box/load")[0] == 405)
        ctx.check("POST on hosts: 405", h.api("POST", "local/hosts")[0] == 405)
        ctx.check("an unknown route: 404", h.api("GET", "local/nothing")[0] == 404)


if __name__ == "__main__":
    ctx = Ctx()
    results, passed, failed, skipped = run_all(TESTS, ctx)
    sys.exit(print_results(results, passed, failed, skipped))
