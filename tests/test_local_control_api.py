"""tests.test_local_control_api -- Halo 3.3.5.0 R3: studio/local_control_api.py's routes on R1's seeded state
(tests/helpers/local_api_rig.Local: hosts pc and samus on 192.0.2.x placeholders, `box` the fake Ollama on
127.0.0.1:0) through studio/api.dispatch:

1. POST local/host/box/pull: a job; GET local/pulls follows it to the end; the Models page has the row and the
   Library row says installed on box; a second ask joins; the cancel route; each answer's `cli` line;
2. POST local/host/box/delete: 422 with the uses card when a role uses it, 409 while a live session is on it, force
   deletes it (the fake's /api/tags loses it), a 404 for a model the host lacks;
3. GET show (the facts), POST copy and rename, GET loaded after a Load;
4. POST twin: the dry plan (the twin's name, the window, what it costs), then the twin made through /api/create and
   recorded in the tune store;
5. a host another machine serves: 409 (no member), 403 when its member has fleet.allow_control: none, and with
   `all` the pull / delete go to the member's session as ollama_pull / ollama_delete with its own host name.
Run: python -m tests.test_local_control_api
"""
from __future__ import annotations

import json
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from tests.helpers import local_seed as L  # noqa: E402
from tests.helpers.control_env import QWEN_SHOW  # noqa: E402
from tests.helpers.local_api_rig import FakeHub, Local  # noqa: E402
from tests.helpers.runner import Ctx, new_registry, print_results, run_all  # noqa: E402

test, TESTS = new_registry()


class Box(Local):
    def __enter__(self):
        super().__enter__()
        from halo_harness.studio import local_pull_job as J, local_uses
        J.reset()
        local_uses.READERS["live"] = lambda: list(self.live)
        self.live: list = []
        self.mock.pullable["gemma3:4b"] = json.loads(json.dumps(QWEN_SHOW))
        return self

    def __exit__(self, *exc):
        from halo_harness.studio import local_pull_job as J, local_uses
        J.reset()
        local_uses.READERS.clear()
        return super().__exit__(*exc)

    def wait(self, job: str, s: float = 10.0) -> dict:
        end = time.monotonic() + s
        while time.monotonic() < end:
            got = next((j for j in self.api("GET", "local/pulls")[1]["jobs"] if j["job"] == job), {})
            if got.get("done"):
                return got
            time.sleep(0.05)
        return {}

    def tags(self) -> list:
        return [t["model"] for t in self.mock.tags_response["models"]]


@test
def test_pull_a_job_to_installed_and_its_row(ctx: Ctx):
    with Box() as h:
        status, v = h.api("POST", "local/host/box/pull", {"name": "gemma3:4b"})
        ctx.check(f"a job, its cli line, got {status} {v}", status == 200 and v["job"] and not v["joined"]
                  and v["cli"] == "halo models pull gemma3:4b --host box")
        end = h.wait(v["job"])
        ctx.check(f"the job ends ok at 100 %, got {end}", end.get("ok") and end.get("percent") == 100.0)
        rows = next(x for x in h.api("GET", "local/models")[1]["hosts"] if x["name"] == "box")["models"]
        ctx.check(f"the Models page has the row, got {[r['model'] for r in rows]}", "gemma3:4b" in [r["model"] for r in rows])
        lib = h.api("GET", "local/library", query={"q": "gemma3", "source": "ollama", "host": "box"})[1]["rows"]
        row = next((r for r in lib if r["name"] == "gemma3:4b"), None)
        ctx.check(f"the Library row says installed on box, got {row and (row['installed'], row['pull_target'])}",
                  row is not None and row["installed"] == ["box"] and row["pull_target"] == "gemma3:4b")
        other = next((r for r in lib if r["name"] != "gemma3:4b"), None)
        ctx.check(f"another row is not installed, got {other and other['installed']}", other is None or other["installed"] == [])
        ctx.check(f"422 without a name, got {h.api('POST', 'local/host/box/pull', {})[0]}", h.api("POST", "local/host/box/pull", {})[0] == 422)


@test
def test_a_second_ask_joins_and_cancel_stops_it(ctx: Ctx):
    with Box() as h:
        h.mock.pull_delay_s = 0.3
        _s, v = h.api("POST", "local/host/box/pull", {"name": "gemma3:4b"})
        _s, again = h.api("POST", "local/host/box/pull", {"name": "gemma3:4b"})
        ctx.check(f"joined, got {again}", again["joined"] and again["job"] == v["job"])
        status, c = h.api("POST", f"local/pull/{v['job']}/cancel")
        ctx.check(f"cancelling, got {status} {c}", status == 200 and c["cancelling"])
        end = h.wait(v["job"])
        ctx.check(f"cancelled, nothing added, got {end}", end.get("cancelled") and "gemma3:4b" not in h.tags()
                  and "keeps the layers" in end.get("say", ""))
        ctx.check("an unknown job: 404", h.api("POST", "local/pull/pull-nope/cancel")[0] == 404)
        ctx.check("GET only for the jobs list", h.api("POST", "local/pulls")[0] == 405)


@test
def test_delete_the_uses_card_422_409_and_force(ctx: Ctx):
    with Box() as h:
        cfg = h.config()
        cfg["roles"] = {"reviewer": "ol:qwen3-coder:30b@box"}
        (h.state / "config.json").write_text(json.dumps(cfg), encoding="utf-8")
        status, body = h.api("POST", "local/host/box/delete", {"name": "qwen3-coder:30b"})
        ctx.check(f"422 with the uses card, got {status} {body.get('error')}", status == 422 and body["uses"]["roles"] == ["reviewer"]
                  and "`reviewer` role" in body["error"] and body["cli"] == "halo models rm qwen3-coder:30b --force --host box")
        h.live.append({"session_id": "s1", "title": "on the coder", "model": "ol:qwen3-coder:30b@box"})
        status, body = h.api("POST", "local/host/box/delete", {"name": "qwen3-coder:30b", "force": True})
        ctx.check(f"409 while a live session is on it, even with force, got {status} {body.get('error')}",
                  status == 409 and body["uses"]["live"] == 1 and "qwen3-coder:30b" in h.tags())
        h.live.clear()
        status, body = h.api("POST", "local/host/box/delete", {"name": "qwen3-coder:30b", "force": True})
        ctx.check(f"force: deleted anyway, got {status} {body.get('say')}", status == 200 and "qwen3-coder:30b" not in h.tags()
                  and body["cli"] == "halo models rm qwen3-coder:30b --force --host box")
        status, body = h.api("POST", "local/host/box/delete", {"name": "qwen3-coder:30b", "force": True})
        ctx.check(f"a model the host lacks: 404, got {status} {body}", status == 404 and "HTTP 404" in body["error"])
        status, body = h.api("POST", "local/host/box/delete", {"name": "nomic-embed-text"})
        ctx.check(f"nothing uses the embedder: deleted at once, got {status}", status == 200 and "nomic-embed-text" not in h.tags())


@test
def test_show_copy_rename_and_loaded(ctx: Ctx):
    with Box() as h:
        status, s = h.api("GET", "local/host/box/show", query={"model": "qwen3.5:9b"})
        ctx.check(f"the facts, got {status} {s.get('facts')}", status == 200 and s["facts"]["params"] == "9.0B" and s["cli"] ==
                  "halo models show qwen3.5:9b --host box" and "capabilities" in s["show"])
        ctx.check("show takes ?model=", h.api("GET", "local/host/box/show")[0] == 422)
        status, c = h.api("POST", "local/host/box/copy", {"src": "qwen3.5:9b", "dst": "qwen3.5-mine:9b"})
        ctx.check(f"copied, got {status} {c.get('say')}", status == 200 and "qwen3.5-mine:9b" in h.tags()
                  and c["cli"] == "halo models copy qwen3.5:9b qwen3.5-mine:9b --host box")
        status, r = h.api("POST", "local/host/box/rename", {"src": "qwen3.5-mine:9b", "dst": "qwen3.5-other:9b"})
        ctx.check(f"renamed, got {status} {r.get('say')}", status == 200 and "qwen3.5-other:9b" in h.tags()
                  and "qwen3.5-mine:9b" not in h.tags())
        h.api("POST", "local/host/box/load", {"model": "qwen3.5:9b"})
        status, ld = h.api("GET", "local/host/box/loaded")
        ctx.check(f"loaded lists it, got {status} {ld}", status == 200 and [m["model"] for m in ld["models"]] == ["qwen3.5:9b"]
                  and ld["cli"] == "halo models loaded --host box")
        ctx.check("GET only for show", h.api("POST", "local/host/box/show")[0] == 405)


@test
def test_the_twin_planned_then_made_and_recorded(ctx: Ctx):
    from halo_harness.providers.ollama_tune_store import lookup_twin_record
    with Box() as h:
        status, plan = h.api("POST", "local/host/box/twin", {"name": "qwen3.5:9b", "window": 32768, "dry": True})
        ctx.check(f"the plan: the twin's name, the window, the cost, got {status} {plan}", status == 200 and plan["dry"]
                  and plan["twin"] == "qwen3.5-halo:9b" and plan["window"] == 32768 and "no new blobs" in plan["cost"]
                  and plan["cli"] == "halo models twin qwen3.5:9b --window 32768 --host box" and not h.mock.created)
        status, made = h.api("POST", "local/host/box/twin", {"name": "qwen3.5:9b", "window": 32768})
        ctx.check(f"made, got {status} {made.get('say')}", status == 200 and made["ok"] and "qwen3.5-halo:9b" in h.tags()
                  and h.mock.created[-1]["from"] == "qwen3.5:9b")
        rec = lookup_twin_record(h.state, host_url=h.mock.base_url, twin="qwen3.5-halo:9b")
        ctx.check(f"recorded in the tune store, got {rec}", rec and rec["origin"] == "qwen3.5:9b" and rec["window"] == 32768)
        status, again = h.api("POST", "local/host/box/twin", {"name": "qwen3.5-halo:9b", "window": 8192})
        ctx.check(f"a twin of a twin: 422 with the reason, got {status} {again}", status == 422 and "twin already" in again["error"])


@test
def test_another_machines_host(ctx: Ctx):
    from halo_harness.ollama_steward.resources_share import take_remote
    with Box() as h:
        status, body = h.api("POST", "local/host/pc/pull", {"name": "gemma3:4b"})
        ctx.check(f"pc (no member serves it here): 409 with the reason, got {status} {body}", status == 409 and "another machine" in body["error"])
    for level in ("none", "all"):
        hub = FakeHub(level, None)
        with Box() as h:
            h.server = hub
            hub.fleet_hub.home = h.state
            cfg = h.config()
            cfg["ollama"]["hosts"].append({"name": "mac", "url": "http://192.0.2.30:11434"})
            (h.state / "config.json").write_text(json.dumps(cfg), encoding="utf-8")
            take_remote(h.state, L.MEMBER, L.member_samples())
            sp, pull = h.api("POST", "local/host/mac/pull", {"name": "gemma3:4b"})
            sd, dele = h.api("POST", "local/host/mac/delete", {"name": "gemma3:4b"})
            if level == "none":
                ctx.check(f"allow_control none: 403 with the reason, nothing sent, got {sp} {pull} {sd}",
                          sp == 403 and sd == 403 and "allow_control: none" in pull["error"] and not hub.sent)
            else:
                ctx.check(f"allow_control all: ollama_pull / ollama_delete to the member, got {sp} {sd} {hub.sent}",
                          sp == 200 and pull["remote"] and sd == 200 and [s[2] for s in hub.sent] == ["ollama_pull", "ollama_delete"]
                          and hub.sent[0][3] == {"host": "local", "model": "gemma3:4b"}
                          and hub.sent[1][3] == {"host": "local", "model": "gemma3:4b", "force": False})


@test
def test_the_members_side_runs_them_on_its_own_host(ctx: Ctx):
    from halo_harness.fleet import control_models as M
    from halo_harness.fleet.control_pulls import read_pulls
    with Box() as h:
        got = M.run({"cmd": "ollama_pull", "host": "box", "model": "gemma3:4b"})
        ctx.check(f"the member's own job, answered at once, got {got}", got["ok"] and got["job"])
        end = h.wait(got["job"])
        ctx.check(f"it pulls on the member's host and its push carries it, got {end.get('ok')} {read_pulls(h.state)[:1]}",
                  end.get("ok") and "gemma3:4b" in h.tags() and read_pulls(h.state)[0]["name"] == "gemma3:4b")
        cfg = h.config()
        cfg["roles"] = {"small": "ol:gemma3:4b@box"}
        (h.state / "config.json").write_text(json.dumps(cfg), encoding="utf-8")
        try:
            M.run({"cmd": "ollama_delete", "host": "box", "model": "gemma3:4b"})
            refused = ""
        except ValueError as e:
            refused = str(e)
        ctx.check(f"its own uses card first, got {refused!r}", "`small` role" in refused and "force" in refused)
        gone = M.run({"cmd": "ollama_delete", "host": "box", "model": "gemma3:4b", "force": True})
        ctx.check(f"with force it goes, got {gone}", gone["ok"] and "gemma3:4b" not in h.tags())
        cp = M.run({"cmd": "ollama_copy", "host": "box", "src": "qwen3.5:9b", "dst": "q-mine:9b", "rename": True})
        ctx.check(f"a rename, got {cp}", cp["ok"] and "q-mine:9b" in h.tags() and "qwen3.5:9b" not in h.tags())
        tw = M.run({"cmd": "ollama_twin", "host": "box", "model": "q-mine:9b", "window": 8192})
        ctx.check(f"a twin, got {tw}", tw["ok"] and tw["twin"] == "q-mine-halo:9b")
        ctx.check("the owner's card names it", M.describe("ollama_copy", {"src": "a", "dst": "b", "rename": True, "host": "box"},
                                                          "rolo", "hub") == "rolo on hub wants to rename a to b on box")
        try:
            M.run({"cmd": "ollama_pull", "host": "pc", "model": "x"})
            ctx.check("pc is not served here", False)
        except ValueError as e:
            ctx.check(f"a host this machine does not serve is refused, got {e}", "not served by this machine" in str(e))


if __name__ == "__main__":
    ctx = Ctx()
    results, passed, failed, skipped = run_all(TESTS, ctx)
    sys.exit(print_results(results, passed, failed, skipped))
