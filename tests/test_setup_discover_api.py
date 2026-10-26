"""tests.test_setup_discover_api -- Find, Scan, Add and Measure in Setup's
Ollama card (Halo 3.3.0.0 R5, studio/setup_discover_api.py + setup_discover_jobs.py).

Hermetic: a scratch home with its own env file (tests/helpers/setup_home.py),
`BRIDGE_TEST_NO_BACKGROUND_NET=1`, two `MockUpstream`s on 127.0.0.1:0 with
different model lists and `ollama.discover.ports` naming their ports (the
default port is never asked); the network sweep never runs (in tests the scan
answers its note, and the 409 check stubs the sweep to block); the
calibration runs against a mock whose `/api/ps` is scripted, the GPU-memory
estimate stubbed. No model call.
Run: python -m tests.test_setup_discover_api
"""
from __future__ import annotations

import sys
import threading
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from tests.helpers.mock_ollama import SCENARIOS  # noqa: E402
from tests.helpers.runner import Ctx, new_registry, print_results, run_all  # noqa: E402
from tests.helpers.setup_discover_home import DiscoverHome as _Home, set_hosts as _set_hosts, wait_done  # noqa: E402

test, TESTS = new_registry()
_GB = 1024 ** 3


@test
def test_find_lists_both_mocks_with_their_models_and_marks_the_configured_one(ctx: Ctx):
    with _Home() as h:
        _set_hosts([{"name": "pc", "url": h.a.base_url, "default": True}])
        code, got = h.call("POST", "setup/ollama/find")
        by_url = {r["url"]: r for r in got.get("rows") or []}
        ctx.check(f"200 and both mocks, got {code} {sorted(by_url)}", code == 200 and set(by_url) == {h.a.base_url, h.b.base_url})
        a, b = by_url.get(h.a.base_url, {}), by_url.get(h.b.base_url, {})
        ctx.check(f"a: configured as pc with its two models, got {a}",
                  a.get("configured") is True and a.get("name") == "pc" and a.get("models") == ["qwen3:30b", "gpt-oss:20b"])
        ctx.check(f"b: new, named after its door and port, its own model, got {b}",
                  b.get("configured") is False and b.get("name") == f"local-{h.b.port}" and b.get("models") == ["llama3.2:3b"])
        ctx.check(f"the version and the row shape, got {b}", b.get("version") == "0.1.0-mock"
                  and sorted(b) == ["configured", "models", "name", "url", "version", "where"])
        ctx.check(f"the ports Find asked, got {got.get('ports')}", got.get("ports") == [h.a.port, h.b.port])
        _code, state = h.call("GET", "setup/state")
        block = state.get("ollama_discover") or {}
        ctx.check(f"the state carries the ports and the idle jobs, got {block}", block.get("ports") == [h.a.port, h.b.port]
                  and block.get("scan", {}).get("state") == "idle" and block.get("measure", {}).get("state") == "idle")
        ctx.check("GET is not a find", h.call("GET", "setup/ollama/find")[0] == 405)


@test
def test_scan_in_tests_answers_the_note_and_no_rows(ctx: Ctx):
    from halo_harness.providers.ollama_discover import TEST_LAN_NOTE
    with _Home() as h:
        code, got = h.call("POST", "setup/ollama/scan")
        ctx.check(f"202 with the job, got {code} {got}", code == 202 and got.get("job", {}).get("kind") == "scan")
        ctx.check("the job ends", wait_done("scan"))
        _c, last = h.call("GET", "setup/ollama/scan")
        ctx.check(f"done, no rows, the one note, got {last}", last.get("state") == "done" and last.get("rows") == []
                  and last.get("note") == TEST_LAN_NOTE and last.get("notes") == [TEST_LAN_NOTE] and last.get("running") is False)
        frame = h.frames[-1] if h.frames else {}
        ctx.check(f"the end frame on the feed: event setup, session setup:scan:<job>, got {frame}",
                  frame.get("event") == "setup" and frame.get("session_id") == f"setup:scan:{last.get('job')}"
                  and frame.get("data", {}).get("state") == "done")


@test
def test_a_second_scan_is_409_while_one_runs_and_stop_ends_it(ctx: Ctx):
    from halo_harness.providers.ollama_discover import DiscoverResult
    from halo_harness.studio import setup_discover_jobs as J
    release = threading.Event()

    def blocking(env, on_progress):
        on_progress("scanning 192.0.2.0/24 ...")
        release.wait(10)
        return DiscoverResult([], [])

    real, J.lan_rows = J.lan_rows, blocking
    try:
        with _Home() as h:
            code, _got = h.call("POST", "setup/ollama/scan")
            time.sleep(1.3)
            again, busy = h.call("POST", "setup/ollama/scan")
            ctx.check(f"202 then 409 while it runs, got {code} {again} {busy.get('error')!r}",
                      code == 202 and again == 409 and busy.get("job", {}).get("running") is True)
            running = [f["data"] for f in h.frames if f["data"].get("state") == "running"]
            ctx.check(f"a running frame every second with the subnet, got {len(running)} {running[-1:]}",
                      len(running) >= 2 and running[-1].get("note") == "scanning 192.0.2.0/24" and running[-1].get("rows") == [])
            ctx.check(f"elapsed counts up, got {[f.get('elapsed') for f in running]}", running[-1]["elapsed"] >= 1.0)
            ctx.check("Stop says it is stopping", h.call("POST", "setup/ollama/scan/stop") == (200, {"stopping": True}))
            time.sleep(1.2)
            _c, last = h.call("GET", "setup/ollama/scan")
            ctx.check(f"the page sees stopped at once, got {last.get('state')}", last.get("state") == "stopped")
            ctx.check("a new scan waits for the sweep to end (409)", h.call("POST", "setup/ollama/scan")[0] == 409)
            release.set()
            ctx.check("the sweep then ends", wait_done("scan"))
    finally:
        release.set()
        J.lan_rows = real


@test
def test_add_writes_the_hosts_never_repoints_the_first_stays_default(ctx: Ctx):
    with _Home() as h:
        lab = {"name": "lab", "url": "http://192.0.2.50:11434", "default": True, "max_ctx": 8192}
        _set_hosts([lab])
        _c, found = h.call("POST", "setup/ollama/find")
        names = {r["url"]: r["name"] for r in found["rows"]}
        ctx.check(f"nothing found yet: 422, got {h.call('POST', 'setup/ollama/add', {'names': ['nope']})[0]}",
                  h.call("POST", "setup/ollama/add", {"names": ["nope"]})[0] == 422)
        code, got = h.call("POST", "setup/ollama/add", {"names": [names[h.a.base_url]]})
        hosts = h.hosts()
        ctx.check(f"200, one line, the fresh state, got {code} {got.get('lines')}", code == 200
                  and got["lines"][0].startswith(f"added Ollama host '{names[h.a.base_url]}'") and "providers" in got)
        ctx.check(f"lab kept as it was and first (the default), a added after, got {hosts}",
                  hosts[0] == lab and hosts[1] == {"name": names[h.a.base_url], "url": h.a.base_url} and len(hosts) == 2)
        ctx.check(f"added names it, the rows mark it configured, got {got.get('added')}",
                  got.get("added") == [names[h.a.base_url]]
                  and {r["url"]: r["configured"] for r in got["rows"]} == {h.a.base_url: True, h.b.base_url: False})
        ctx.check(f"the hosts table in the state has it, got {got['ollama']['hosts']}",
                  [x["name"] for x in got["ollama"]["hosts"]] == ["lab", names[h.a.base_url]])
        code, again = h.call("POST", "setup/ollama/add", {"urls": [h.a.base_url]})
        ctx.check(f"again by url: nothing new, nothing written, got {again.get('lines')}",
                  code == 200 and again["lines"][0].startswith("nothing new to add") and len(h.hosts()) == 2 and again["added"] == [])
        code, mixed = h.call("POST", "setup/ollama/add", {"urls": [h.b.base_url, "http://192.0.2.99:11434"]})
        ctx.check(f"b added, the unknown url named, got {mixed.get('lines')}", code == 200 and len(h.hosts()) == 3
                  and any("192.0.2.99" in ln and "not found by Find or Scan" in ln for ln in mixed["lines"]))
        ctx.check("only lab is the default", [x.get("default") for x in h.hosts()] == [True, None, None])
        ctx.check("no names, no urls: 422", h.call("POST", "setup/ollama/add", {})[0] == 422)


@test
def test_add_on_a_fresh_home_makes_the_first_one_the_default(ctx: Ctx):
    with _Home() as h:
        h.call("POST", "setup/ollama/find")
        code, got = h.call("POST", "setup/ollama/add", {"urls": [h.a.base_url, h.b.base_url]})
        hosts = h.hosts()
        ctx.check(f"both written, the first the default, no key field, got {code} {hosts}", code == 200 and len(hosts) == 2
                  and hosts[0].get("default") is True and "default" not in hosts[1]
                  and all(set(x) <= {"name", "url", "default"} for x in hosts))
        ctx.check(f"the first is ol:<model>, the second ol:<model>@<name>, got {got['lines']}",
                  "use ol:<model>" in got["lines"][0] and f"@{hosts[1]['name']}" in got["lines"][1])


class _Fits:
    """`/api/chat` for one model: script `/api/ps` (resident or offloaded) before a one-line reply."""

    def __init__(self, mock, model: str, resident: bool):
        self.mock, self.model, self.resident = mock, model, resident

    def __call__(self, handler, body) -> None:
        size = 20 * _GB
        self.mock.ps_response = {"models": [{"model": self.model, "name": self.model, "size": size,
                                             "size_vram": size if self.resident else 2 * _GB}]}
        SCENARIOS["done-reason-stop"](handler, body)


@test
def test_measure_publishes_one_line_per_model_and_a_summary(ctx: Ctx):
    from halo_harness.providers import ollama_hw
    real_fit, ollama_hw.estimate_fit_for_host = ollama_hw.estimate_fit_for_host, (lambda *a, **k: None)
    try:
        with _Home() as h:
            h.a.scenarios["qwen3:30b"] = _Fits(h.a, "qwen3:30b", True)
            h.a.scenarios["gpt-oss:20b"] = _Fits(h.a, "gpt-oss:20b", False)
            _set_hosts([{"name": "pc", "url": h.a.base_url, "default": True}])
            ctx.check("an unknown host is a 422", h.call("POST", "setup/ollama/measure", {"hosts": ["nope"]})[0] == 422)
            ctx.check("a bad timeout is a 422", h.call("POST", "setup/ollama/measure", {"hosts": ["pc"], "timeout": -1})[0] == 422)
            code, got = h.call("POST", "setup/ollama/measure", {"hosts": ["pc"], "timeout": 5})
            ctx.check(f"202 with the job, got {code} {got}", code == 202 and got.get("job", {}).get("kind") == "measure")
            ctx.check("the job ends", wait_done("measure", 60))
            data = [f["data"] for f in h.frames if f["data"].get("kind") == "measure"]
            ends = [d for d in data if d.get("outcome")]
            ctx.check(f"one measured line per model, in the catalog's order, got {[d.get('line') for d in ends]}",
                      [d["model"] for d in ends] == ["qwen3:30b", "gpt-oss:20b"]
                      and all(d["line"].startswith(f"{d['model']} on pc: ") and d["host"] == "pc" for d in ends))
            ctx.check(f"the outcomes, got {[d['outcome'] for d in ends]}", [d["outcome"] for d in ends] == ["fits", "does_not_fit"])
            ctx.check(f"a frame before each model, got {[d['line'] for d in data if not d.get('outcome')][:3]}",
                      sum(1 for d in data if str(d.get("line", "")).startswith("measuring ")) == 2)
            last = data[-1] if data else {}
            ctx.check(f"the summary, got {last.get('summary')!r}", last.get("state") == "done"
                      and str(last.get("summary")).startswith("2 models measured on 1 host in ")
                      and "1 fit, 1 do not fit fully in GPU memory, 0 not recorded" in str(last.get("summary")))
            _c, catch = h.call("GET", "setup/ollama/measure")
            ctx.check(f"GET catches up: the two lines and the summary, got {catch.get('lines')} {catch.get('running')}",
                      catch.get("lines") == [d["line"] for d in ends] and catch.get("summary") == last.get("summary")
                      and catch.get("running") is False)
            fit = h.state_dir / "ollama-fit.json"
            ctx.check(f"what settled is recorded, got {fit.is_file()}", fit.is_file() and "qwen3:30b" in fit.read_text(encoding="utf-8"))
            h.frames.clear()
            h.call("POST", "setup/ollama/measure", {"hosts": ["pc"], "models": ["ol:gpt-oss:20b@pc"], "timeout": 5})
            ctx.check("the second run ends", wait_done("measure", 60))
            only = [f["data"]["model"] for f in h.frames if f["data"].get("outcome")]
            ctx.check(f"models: only the named one, got {only}", only == ["gpt-oss:20b"])
    finally:
        ollama_hw.estimate_fit_for_host = real_fit


@test
def test_measure_is_409_while_one_runs(ctx: Ctx):
    from halo_harness.providers import ollama_discover_measure as M
    release = threading.Event()

    def slow(host, models, **_kw):
        release.wait(10)
        return [{"host": host.name, "model": models[0], "outcome": "fits", "line": f"{models[0]} on {host.name}: stub"}]

    real, M.measure_models = M.measure_models, slow
    try:
        with _Home() as h:
            _set_hosts([{"name": "pc", "url": h.a.base_url, "default": True}])
            first = h.call("POST", "setup/ollama/measure", {"hosts": ["pc"], "models": ["qwen3:30b"]})[0]
            second = h.call("POST", "setup/ollama/measure", {"hosts": ["pc"]})[0]
            ctx.check(f"202 then 409, got {first} {second}", first == 202 and second == 409)
            release.set()
            ctx.check("it ends", wait_done("measure"))
            ctx.check("then a new one starts", h.call("POST", "setup/ollama/measure", {"hosts": ["pc"], "models": ["qwen3:30b"]})[0] == 202)
            ctx.check("and ends", wait_done("measure"))
    finally:
        release.set()
        M.measure_models = real


if __name__ == "__main__":
    ctx = Ctx()
    results, passed, failed, skipped = run_all(TESTS, ctx)
    sys.exit(print_results(results, passed, failed, skipped))
