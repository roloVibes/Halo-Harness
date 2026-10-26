"""tests.test_ollama_discover_cli -- Halo 3.2.3.0 R2: `halo ollama discover
[--lan] [--add [NAME,NAME]] [--calibrate] [--json] [--timeout S]`, in
process: the one line per server, `--json`, `--add NAME`, `--calibrate`
measuring every model of the hosts just added through the mock (a
scripted `/api/ps` that answers with the window each load asked for), and
the exit codes. Two `MockUpstream`s on 127.0.0.1:0; `ollama.discover.ports`
names them, so no real server is ever asked.
"""
from __future__ import annotations

import contextlib
import io
import json
import os
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from tests.helpers.mock_ollama import SCENARIOS, MockUpstream
from tests.helpers.runner import Ctx, new_registry, print_results, run_all

test, TESTS = new_registry()

_GB = 1024 ** 3
_ENV_NAMES = ("BRIDGE_TEST_HOME", "BRIDGE_STATE_DIR", "BRIDGE_TEST_NO_BACKGROUND_NET", "OLLAMA_HOST",
              "OLLAMA_API_KEY", "HALO_OFFLINE")
OTHER_TAGS = {"models": [{"name": "gpt-oss:20b", "model": "gpt-oss:20b", "size": 13 * _GB,
                          "digest": "sha256:feed2", "details": {"family": "gptoss"}}]}


class _FitScenario:
    """`/api/chat` for one model: `/api/ps` then lists the model loaded at
    the window the request asked for, fully in GPU memory up to `fit`."""

    def __init__(self, mock: MockUpstream, model: str, fit: int):
        self.mock, self.model, self.fit, self.asked = mock, model, fit, []

    def __call__(self, handler, body) -> None:
        n = int(((body or {}).get("options") or {}).get("num_ctx") or 0)
        self.asked.append(n)
        size = 13 * _GB
        self.mock.ps_response = {"models": [{"model": self.model, "name": self.model, "size": size,
                                             "size_vram": size if n <= self.fit else size // 2,
                                             "context_length": n}]}
        SCENARIOS["done-reason-stop"](handler, body)


class _Env:
    def __enter__(self):
        from halo_harness.providers.ollama_discover import reset_discover_cache
        self._saved = {k: os.environ.get(k) for k in _ENV_NAMES}
        d = Path(tempfile.mkdtemp(prefix="ol-discover-cli-"))
        os.environ["BRIDGE_TEST_HOME"] = str(d)
        os.environ["BRIDGE_STATE_DIR"] = str(d / ".halo")
        os.environ["BRIDGE_TEST_NO_BACKGROUND_NET"] = "1"
        for k in ("OLLAMA_HOST", "OLLAMA_API_KEY", "HALO_OFFLINE"):
            os.environ.pop(k, None)
        reset_discover_cache()
        from halo_harness.providers import ollama_hw  # R3: calibration reads the card's size; no GPU tool here
        self._gpu, ollama_hw.get_local_gpu_memories = ollama_hw.get_local_gpu_memories, lambda **kw: []
        self.state_dir = d / ".halo"
        self.a = MockUpstream().start()
        self.b = MockUpstream(tags_response=OTHER_TAGS).start()
        from halo_harness.theme import set_config_value
        set_config_value("ollama.discover", {"ports": [self.a.port, self.b.port]})
        set_config_value("ollama.hosts", [{"name": "pc", "url": self.a.base_url, "default": True}])
        return self

    def __exit__(self, *exc):
        from halo_harness.providers import ollama_hw
        ollama_hw.get_local_gpu_memories = self._gpu
        self.a.stop()
        self.b.stop()
        for k, v in self._saved.items():
            if v is None:
                os.environ.pop(k, None)
            else:
                os.environ[k] = v


def _run(argv: list) -> "tuple[int, str, str]":
    from halo_harness.ollama_cli import cmd_ollama
    out, err = io.StringIO(), io.StringIO()
    with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
        rc = cmd_ollama(["discover"] + argv)
    return rc, out.getvalue(), err.getvalue()


def _hosts() -> list:
    from halo_harness.theme import get_config_value
    return get_config_value("ollama.hosts", default=None) or []


@test
def test_one_line_per_server_configured_and_new(ctx: Ctx):
    with _Env() as env:
        rc, out, _err = _run([])
        lines = [ln for ln in out.splitlines() if ln.strip()]
        ctx.check(f"exit 0 when something is found, got {rc}", rc == 0)
        pc = [ln for ln in lines if ln.startswith("pc ")]
        new = [ln for ln in lines if f"127.0.0.1:{env.b.port}" in ln]
        ctx.check(f"the configured line, got {lines}",
                  len(pc) == 1 and env.a.base_url in pc[0] and "0.1.0-mock" in pc[0]
                  and "2 models: qwen3:30b, gpt-oss:20b" in pc[0] and pc[0].endswith("configured"))
        ctx.check(f"the new line, got {lines}",
                  len(new) == 1 and "1 model: gpt-oss:20b" in new[0] and new[0].endswith("new"))
        ctx.check(f"without --add nothing is written, got {_hosts()}", len(_hosts()) == 1)
        rc, out, _err = _run(["--lan"])
        ctx.check(f"--lan in tests: the local rows plus one note, got {rc} {out}",
                  rc == 0 and out.count("note: the network scan is off in tests") == 1 and "pc " in out)


@test
def test_json_prints_the_rows(ctx: Ctx):
    with _Env() as env:
        rc, out, _err = _run(["--json"])
        data = json.loads(out)
        ctx.check(f"exit 0, got {rc}", rc == 0)
        urls = {s["url"]: s for s in data["servers"]}
        ctx.check(f"both servers, got {list(urls)}", set(urls) == {env.a.base_url, env.b.base_url})
        ctx.check(f"the fields, got {data['servers'][0]}",
                  all(set(s) == {"url", "name", "version", "models", "configured", "where"} for s in data["servers"]))
        ctx.check("configured flags", urls[env.a.base_url]["configured"] and not urls[env.b.base_url]["configured"])
        ctx.check(f"measurements empty without --calibrate, got {data}", data["measurements"] == [] and data["added"] == [])


@test
def test_add_named_writes_only_that_host(ctx: Ctx):
    with _Env() as env:
        name = f"local-{env.b.port}"
        rc, out, _err = _run(["--add", name])
        hosts = _hosts()
        ctx.check(f"exit 0, got {rc}", rc == 0)
        ctx.check(f"the named host added, pc untouched, got {hosts}",
                  [h["name"] for h in hosts] == ["pc", name] and hosts[0] == {"name": "pc", "url": env.a.base_url,
                                                                            "default": True}
                  and hosts[1]["url"] == env.b.base_url)
        ctx.check(f"one added line, got {out}", f"added Ollama host '{name}'" in out and f"ol:<model>@{name}" in out)
        rc, out, _err = _run(["--add"])
        ctx.check(f"a second --add has nothing new, got {out}", "nothing new to add" in out and len(_hosts()) == 2)


@test
def test_calibrate_measures_every_model_of_the_added_host(ctx: Ctx):
    from halo_harness.providers.ollama_calibrate import lookup_learned_cap
    with _Env() as env:
        scenario = _FitScenario(env.b, "gpt-oss:20b", fit=32768)
        env.b.scenarios["gpt-oss:20b"] = scenario
        rc, out, err = _run(["--add", "--calibrate", "--timeout", "5", "--no-twins"])  # R3: no twins question
        name = f"local-{env.b.port}"
        ctx.check(f"exit 0, got {rc} {err}", rc == 0)
        ctx.check(f"the mock was loaded at each window asked, got {scenario.asked}", 32768 in scenario.asked)
        line = [ln for ln in out.splitlines() if ln.startswith(f"gpt-oss:20b on {name}:")]
        ctx.check(f"one progress line for the model, got {out}", len(line) == 1)
        ctx.check(f"the line names the measured window, got {line}", line and "32k fits" in line[0])
        cap = lookup_learned_cap(env.state_dir, host_url=env.b.base_url, model="gpt-oss:20b")
        ctx.check(f"recorded through record_calibration, got {cap}", cap == 32768)
        ctx.check("the configured host 'pc' was not measured (not named)",
                  not any(ln.startswith("qwen3:30b on pc") for ln in out.splitlines()))


@test
def test_calibrate_json_carries_the_measurements(ctx: Ctx):
    with _Env() as env:
        env.b.scenarios["gpt-oss:20b"] = _FitScenario(env.b, "gpt-oss:20b", fit=32768)
        rc, out, err = _run(["--add", "--calibrate", "--json"])
        data = json.loads(out)
        ctx.check(f"exit 0, got {rc}", rc == 0)
        m = data["measurements"]
        ctx.check(f"one measurement, got {m}", len(m) == 1 and m[0]["model"] == "gpt-oss:20b"
                  and m[0]["max_full_gpu_ctx"] == 32768 and m[0]["outcome"] == "fits")
        ctx.check(f"progress lines go to stderr with --json, got {err}", "gpt-oss:20b on " in err)


@test
def test_exit_codes_nothing_found_and_usage(ctx: Ctx):
    from halo_harness.theme import set_config_value
    with _Env():
        set_config_value("ollama.discover", {})
        rc, out, _err = _run([])
        ctx.check(f"exit 1 when nothing is found, got {rc} {out}", rc == 1 and "No Ollama server found" in out)
        rc, _out, _err = _run(["--timeout", "-1"])
        ctx.check(f"exit 2 on a bad --timeout, got {rc}", rc == 2)
        rc, _out, _err = _run(["--bogus"])
        ctx.check(f"exit 2 on an unknown flag, got {rc}", rc == 2)


if __name__ == "__main__":
    ctx = Ctx()
    results, passed, failed, skipped = run_all(TESTS, ctx)
    sys.exit(print_results(results, passed, failed, skipped))
