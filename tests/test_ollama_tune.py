"""tests.test_ollama_tune -- Halo 3.2.3.0 R3: a tuned twin. `twin_name`'s
rule, `plan_twin` from the recorded safe window and from `--window`,
`create_twin` through the mock's derived-model `/api/create` (streamed
status lines) and the `/api/show` confirmation, the marker `is_twin` reads,
and `halo ollama tune` (the plan line, progress, the ref, `--remove` of a
twin and of an original, `--json`, the exit codes). One `MockUpstream` on
127.0.0.1:0; a fresh BRIDGE_TEST_HOME; never a real server.
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

from tests.helpers.mock_ollama import MockUpstream
from tests.helpers.runner import Ctx, new_registry, print_results, run_all

test, TESTS = new_registry()

_ENV_NAMES = ("BRIDGE_TEST_HOME", "BRIDGE_STATE_DIR", "BRIDGE_TEST_NO_BACKGROUND_NET", "OLLAMA_HOST",
              "OLLAMA_API_KEY", "HALO_OFFLINE")


class _Env:
    def __enter__(self):
        from halo_harness.providers.ollama import reset_catalog_cache
        self._saved = {k: os.environ.get(k) for k in _ENV_NAMES}
        d = Path(tempfile.mkdtemp(prefix="ol-tune-"))
        os.environ["BRIDGE_TEST_HOME"] = str(d)
        os.environ["BRIDGE_STATE_DIR"] = str(d / ".halo")
        os.environ["BRIDGE_TEST_NO_BACKGROUND_NET"] = "1"
        for k in ("OLLAMA_HOST", "OLLAMA_API_KEY", "HALO_OFFLINE"):
            os.environ.pop(k, None)
        reset_catalog_cache()
        self.state_dir = d / ".halo"
        self.mock = MockUpstream().start()
        self.mock.show_responses["qwen3:30b"]["model_info"]["qwen3.block_count"] = 48
        from halo_harness.theme import set_config_value
        set_config_value("ollama.hosts", [{"name": "pc", "url": self.mock.base_url, "default": True}])
        from halo_harness.providers.ollama import resolve_ollama_host
        self.host = resolve_ollama_host("pc")
        return self

    def calibrated(self, model: str = "qwen3:30b", cap: int = 32768) -> "_Env":
        from halo_harness.providers.ollama_calibrate import record_calibration
        record_calibration(self.state_dir, host_url=self.mock.base_url, model=model, digest=None,
                           max_full_gpu_ctx=cap, ollama_version=None)
        return self

    def __exit__(self, *exc):
        self.mock.stop()
        for k, v in self._saved.items():
            if v is None:
                os.environ.pop(k, None)
            else:
                os.environ[k] = v


def _run(argv: list) -> "tuple[int, str, str]":
    from halo_harness.ollama_cli import cmd_ollama
    out, err = io.StringIO(), io.StringIO()
    with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
        rc = cmd_ollama(["tune"] + argv)
    return rc, out.getvalue(), err.getvalue()


@test
def test_twin_name_keeps_the_tag(ctx: Ctx):
    from halo_harness.providers.ollama_tune import origin_from_twin_name, twin_name
    cases = {"qwen3.8:27b": "qwen3.8-halo:27b", "qwen3": "qwen3-halo:latest", "user/coder:7b": "user/coder-halo:7b",
             "registry.ollama.ai/library/gemma3:12b": "gemma3-halo:12b", "qwen3.8-halo:27b": "qwen3.8-halo:27b",
             "hf.co/org/Repo-GGUF:Q4_K_M": "hf.co/org/Repo-GGUF-halo:Q4_K_M"}
    for model, want in cases.items():
        ctx.check(f"twin_name({model!r}) == {want!r}, got {twin_name(model)!r}", twin_name(model) == want)
    ctx.check("the rule read back", origin_from_twin_name("qwen3.8-halo:27b") == "qwen3.8:27b"
              and origin_from_twin_name("qwen3.8:27b") is None and origin_from_twin_name("-halo:1b") is None)


@test
def test_plan_from_the_recorded_safe_window(ctx: Ctx):
    from halo_harness.providers.ollama_tune import TuneError, plan_twin
    with _Env() as env:
        try:
            plan_twin(env.host, "qwen3:30b", state_dir=env.state_dir)
            ctx.check("no recorded window raises", False)
        except TuneError as e:
            ctx.check(f"no window: one line naming calibrate, got {e.message}",
                      e.kind == "no_window" and "halo ollama calibrate qwen3:30b --host pc" in e.message)
        env.calibrated()
        plan = plan_twin(env.host, "qwen3:30b", state_dir=env.state_dir)
        ctx.check(f"the Modelfile, got {plan.modelfile!r}",
                  plan.modelfile == "FROM qwen3:30b\nPARAMETER num_ctx 32768\nPARAMETER num_gpu 49\n")
        ctx.check(f"the twin and the ref, got {plan.twin} {plan.ref}",
                  plan.twin == "qwen3-halo:30b" and plan.ref == "ol:qwen3-halo:30b@pc" and plan.measured)
        ctx.check(f"the plan line, got {plan.line}", "num_ctx 32,768 (the safe window calibrated on 'pc')" in plan.line
                  and "num_gpu 49 (every layer on the GPU)" in plan.line and "no extra disk" in plan.line)
        layers = plan_twin(env.host, "gpt-oss:20b", 8192, state_dir=env.state_dir).layers
        ctx.check(f"no block_count: 999 layers, got {layers}", layers == 999)


@test
def test_plan_from_window_and_the_trained_ceiling(ctx: Ctx):
    from halo_harness.providers.ollama_tune import TuneError, plan_twin
    with _Env() as env:
        env.calibrated()
        plan = plan_twin(env.host, "qwen3:30b", 16384, state_dir=env.state_dir)
        ctx.check(f"--window wins, not the measured one, got {plan.window} {plan.measured}",
                  plan.window == 16384 and not plan.measured and "(--window)" in plan.line)
        plan = plan_twin(env.host, "qwen3:30b", 65536, state_dir=env.state_dir)
        ctx.check(f"held at the trained 40,960, got {plan.window} {plan.line}",
                  plan.window == 40960 and "held at its trained 40,960" in plan.line)
        for model, kind in (("nope:1b", "missing"),):
            try:
                plan_twin(env.host, model, 8192, state_dir=env.state_dir)
                ctx.check(f"{model} raises", False)
            except TuneError as e:
                ctx.check(f"{model}: kind {kind}, got {e.kind} {e.message}", e.kind == kind)
        dead = MockUpstream().start()
        from halo_harness.providers.ollama import OllamaHost
        gone = OllamaHost(name="gone", url=dead.base_url)
        dead.stop()
        try:
            plan_twin(gone, "qwen3:30b", 8192, state_dir=env.state_dir)
            ctx.check("an unreachable host raises", False)
        except TuneError as e:
            ctx.check(f"unreachable, got {e.kind} {e.message}", e.kind == "unreachable" and "no answer" in e.message)


@test
def test_create_twin_streams_status_and_confirms_with_show(ctx: Ctx):
    from halo_harness.providers.ollama import fetch_show
    from halo_harness.providers.ollama_calibrate import lookup_learned_cap
    from halo_harness.providers.ollama_tune import create_twin, is_twin, plan_twin, twin_origin
    with _Env() as env:
        env.calibrated()
        lines: list = []
        result = create_twin(env.host, plan_twin(env.host, "qwen3:30b", state_dir=env.state_dir),
                             on_progress=lines.append, state_dir=env.state_dir)
        ctx.check(f"made, got {result}", result.ok and result.ref == "ol:qwen3-halo:30b@pc")
        ctx.check(f"each streamed status forwarded, got {lines}", lines[-1] == "success" and len(lines) == 4)
        body = env.mock.created[-1]
        ctx.check(f"the create body, got {body}", body.get("model") == "qwen3-halo:30b" and body.get("from") == "qwen3:30b"
                  and body.get("parameters") == {"num_ctx": 32768, "num_gpu": 49} and "files" not in body)
        show = fetch_show(env.host, "qwen3-halo:30b")
        ctx.check(f"the twin's /api/show names its origin, got {twin_origin(show, name='qwen3-halo:30b')}",
                  twin_origin(show, name="qwen3-halo:30b") == "qwen3:30b")
        ctx.check("an original is not a twin", not is_twin(fetch_show(env.host, "qwen3:30b")))
        ctx.check("the name must follow the rule", not is_twin(show, name="other:30b"))
        cap = lookup_learned_cap(env.state_dir, host_url=env.mock.base_url, model="qwen3-halo:30b")
        ctx.check(f"the twin inherits the measured window (no second calibration), got {cap}", cap == 32768)


@test
def test_a_server_without_parent_model_uses_halos_record(ctx: Ctx):
    from halo_harness.providers.ollama import fetch_show
    from halo_harness.providers.ollama_tune import create_twin, is_twin, plan_twin
    with _Env() as env:
        env.mock.create_records_parent = False
        env.calibrated()
        ctx.check("made", create_twin(env.host, plan_twin(env.host, "qwen3:30b", state_dir=env.state_dir),
                                      state_dir=env.state_dir).ok)
        show = fetch_show(env.host, "qwen3-halo:30b")
        ctx.check("no parent_model and no record: not a twin", not is_twin(show, name="qwen3-halo:30b"))
        rc, out, err = _run(["qwen3-halo:30b", "--host", "pc"])
        ctx.check(f"tuning a twin again: one line (Halo's record), got {rc} {err}",
                  rc == 1 and "is a tuned twin already (of qwen3:30b)" in err)


@test
def test_cli_plan_progress_ref_and_json(ctx: Ctx):
    with _Env() as env:
        env.calibrated()
        rc, out, err = _run(["qwen3:30b", "--host", "pc"])
        lines = out.strip().splitlines()
        ctx.check(f"exit 0, got {rc} {err}", rc == 0)
        ctx.check(f"the plan line first, got {lines}", lines[0].startswith("plan: qwen3-halo:30b on 'pc': FROM qwen3:30b"))
        ctx.check(f"progress lines, got {lines}", "  writing manifest" in lines and "  success" in lines)
        ctx.check(f"ends with the ref, got {lines[-1]}", lines[-1] == "ol:qwen3-halo:30b@pc")
        rc, out, err = _run(["qwen3:30b", "--json", "--window", "8192"])
        data = json.loads(out)
        ctx.check(f"--json: ok, the plan and progress, got {data}",
                  rc == 0 and data["ok"] and data["plan"]["window"] == 8192 and data["plan"]["num_gpu"] == 49
                  and data["ref"] == "ol:qwen3-halo:30b@pc" and "success" in data["progress"] and "plan:" in err)


@test
def test_cli_remove_a_twin_never_an_original(ctx: Ctx):
    with _Env() as env:
        env.calibrated()
        _run(["qwen3:30b"])
        rc, out, err = _run(["qwen3:30b", "--remove"])
        ctx.check(f"an original is left alone, in one line, got {rc} {err}", rc == 1 and err.strip() ==
                  "not a twin: qwen3:30b is an original; halo ollama tune makes twins and removes only them "
                  "(its twin here is qwen3-halo:30b)")
        rc, _out, err = _run(["gpt-oss:20b", "--remove"])
        ctx.check(f"no twin: the bare line, got {err}", rc == 1 and err.strip().endswith("removes only them"))
        ctx.check(f"nothing deleted, got {env.mock.deleted}", env.mock.deleted == [])
        rc, out, err = _run(["qwen3-halo:30b", "--remove", "--host", "pc"])
        ctx.check(f"the twin is deleted, got {rc} {out} {err}", rc == 0 and env.mock.deleted == ["qwen3-halo:30b"]
                  and "removed qwen3-halo:30b from 'pc' (qwen3:30b and its weights stay)" in out)
        from halo_harness.providers.ollama_tune_store import lookup_twin_record
        ctx.check("the record is gone", lookup_twin_record(env.state_dir, host_url=env.mock.base_url,
                                                           twin="qwen3-halo:30b") is None)
        rc, _out, err = _run(["qwen3-halo:30b", "--remove"])
        ctx.check(f"a twin that is gone: exit 1, got {rc} {err}", rc == 1 and "is not on 'pc'" in err)


@test
def test_cli_exit_codes(ctx: Ctx):
    with _Env() as env:
        ctx.check("exit 2: --window 0", _run(["qwen3:30b", "--window", "0"])[0] == 2)
        ctx.check("exit 2: --remove with --window", _run(["x-halo:1b", "--remove", "--window", "8"])[0] == 2)
        ctx.check("exit 2: no model", _run([])[0] == 2)
        rc, _o, err = _run(["qwen3:30b", "--host", "elsewhere"])
        ctx.check(f"exit 1: no such host, got {rc} {err}", rc == 1 and "no configured host named 'elsewhere'" in err)
        rc, _o, err = _run(["qwen3:30b"])
        ctx.check(f"exit 1: no recorded window, got {rc} {err}", rc == 1 and "no safe window recorded" in err)
        env.mock.create_responses["qwen3-halo:30b"] = [{"status": "pulling"}, {"error": "disk full"}]
        rc, _o, err = _run(["qwen3:30b", "--window", "8192"])
        ctx.check(f"exit 1: Ollama answered with an error, got {rc} {err}", rc == 1 and "did not make qwen3-halo:30b: disk full" in err)


if __name__ == "__main__":
    ctx = Ctx()
    results, passed, failed, skipped = run_all(TESTS, ctx)
    sys.exit(print_results(results, passed, failed, skipped))
