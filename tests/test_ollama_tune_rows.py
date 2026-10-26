"""tests.test_ollama_tune_rows -- Halo 3.2.3.0 R3: where a tuned twin shows
and the offers that make one. The catalog's `twin_of`; `halo ollama` (the
panel) and `halo local` list the twin under its original with "tuned twin
of <model> (32k window, all layers on the GPU)"; the pickers (the local
rows `/model` and Studio read, and the picker's own sort pass) put the twin
first, the original after it; `halo ollama discover --calibrate` with
`--twins` (made without asking), `--no-twins` (no question), and the
question answered through a stubbed `_ask` with a stubbed create. Mocks on
127.0.0.1:0 only, a fresh BRIDGE_TEST_HOME, no GPU tool.
"""
from __future__ import annotations

import contextlib
import io
import os
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from tests.helpers.mock_ollama import SCENARIOS, MockUpstream
from tests.helpers.runner import Ctx, new_registry, print_results, run_all

test, TESTS = new_registry()

_GB = 1024 ** 3
_NO_GPU = lambda argv, timeout: None  # never a real OS tool here
_ENV_NAMES = ("BRIDGE_TEST_HOME", "BRIDGE_STATE_DIR", "BRIDGE_TEST_NO_BACKGROUND_NET", "OLLAMA_HOST",
              "OLLAMA_API_KEY", "HALO_OFFLINE", "HF_HUB_CACHE", "HF_HOME", "HF_LOCAL_PROBE_PORTS")
NOTE = "tuned twin of qwen3:30b (32k window, all layers on the GPU)"


class _Env:
    def __init__(self, *, twin: bool = True, second: bool = False):
        self.twin, self.second = twin, second

    def __enter__(self):
        from halo_harness.providers import ollama_hw
        from halo_harness.providers.ollama import reset_catalog_cache, resolve_ollama_host
        from halo_harness.providers.ollama_discover import reset_discover_cache
        from halo_harness.theme import set_config_value
        self._saved = {k: os.environ.get(k) for k in _ENV_NAMES}
        d = Path(tempfile.mkdtemp(prefix="ol-tune-rows-"))
        os.environ.update({"BRIDGE_TEST_HOME": str(d), "BRIDGE_STATE_DIR": str(d / ".halo"),
                           "BRIDGE_TEST_NO_BACKGROUND_NET": "1", "HF_HUB_CACHE": str(d / "no-hf-cache")})
        for k in ("OLLAMA_HOST", "OLLAMA_API_KEY", "HALO_OFFLINE", "HF_HOME", "HF_LOCAL_PROBE_PORTS"):
            os.environ.pop(k, None)
        self._gpu = ollama_hw.get_local_gpu_memories
        ollama_hw.get_local_gpu_memories = lambda **kw: []
        reset_catalog_cache()
        reset_discover_cache()
        self.state_dir = d / ".halo"
        self.mock = MockUpstream().start()
        self.b = MockUpstream(tags_response={"models": [{"name": "gpt-oss:20b", "model": "gpt-oss:20b",
                                                         "size": 13 * _GB, "digest": "sha256:feed2"}]}).start() \
            if self.second else None
        set_config_value("ollama.hosts", [{"name": "pc", "url": self.mock.base_url, "default": True}])
        set_config_value("ollama.discover", {"ports": [self.mock.port] + ([self.b.port] if self.b else [])})
        self.host = resolve_ollama_host("pc")
        if self.twin:
            from halo_harness.providers.ollama_calibrate import record_calibration
            from halo_harness.providers.ollama_tune import create_twin, plan_twin
            record_calibration(self.state_dir, host_url=self.mock.base_url, model="qwen3:30b", digest=None,
                               max_full_gpu_ctx=32768, ollama_version=None)
            assert create_twin(self.host, plan_twin(self.host, "qwen3:30b", state_dir=self.state_dir),
                               state_dir=self.state_dir).ok
        return self

    def __exit__(self, *exc):
        from halo_harness.providers import ollama_hw
        ollama_hw.get_local_gpu_memories = self._gpu
        self.mock.stop()
        if self.b:
            self.b.stop()
        for k, v in self._saved.items():
            if v is None:
                os.environ.pop(k, None)
            else:
                os.environ[k] = v


@test
def test_catalog_rows_carry_twin_of(ctx: Ctx):
    from halo_harness.providers.ollama import get_catalog
    with _Env() as env:
        rows = {r["model"]: r for r in get_catalog(env.host, force=True)["models"]}
        ctx.check(f"the twin's row, got {rows.get('qwen3-halo:30b')}",
                  rows["qwen3-halo:30b"].get("twin_of") == "qwen3:30b" and rows["qwen3-halo:30b"]["twin_window"] == 32768)
        ctx.check("an original's row has none", "twin_of" not in rows["qwen3:30b"])


@test
def test_the_panel_lists_the_twin_under_its_original(ctx: Ctx):
    from halo_harness.providers.ollama_panel import analyze_host, format_host_analysis
    with _Env() as env:
        text = format_host_analysis(analyze_host(env.host, hw_runner=_NO_GPU, force=True, state_dir=env.state_dir))
        lines = text.splitlines()
        orig = next(i for i, ln in enumerate(lines) if ln.startswith("    qwen3:30b:"))
        ctx.check(f"the twin right under its original, got {lines[orig:orig + 6]}",
                  any(ln.startswith("    qwen3-halo:30b:") for ln in lines[orig + 1:orig + 4]))
        twin = next(i for i, ln in enumerate(lines) if ln.startswith("    qwen3-halo:30b:"))
        ctx.check(f"with the note, got {lines[twin + 1]}", lines[twin + 1].strip() == NOTE)
        ctx.check("the twin is calibrated from the start", "calibrated" in lines[twin])


@test
def test_halo_local_lists_the_twin_under_its_original(ctx: Ctx):
    from halo_harness.providers.local_models import build_local_view, format_local_view
    with _Env() as env:
        rows = [r for r in build_local_view(state_dir=env.state_dir, hw_runner=_NO_GPU) if r.group == "Ollama (pc)"]
        ctx.check(f"the rows (picker order) put the twin first, got {[r.name for r in rows]}",
                  [r.name for r in rows][:2] == ["qwen3-halo:30b", "qwen3:30b"] and rows[0].twin_of == "qwen3:30b")
        text = format_local_view(rows).splitlines()
        orig = next(i for i, ln in enumerate(text) if ln.startswith("  qwen3:30b"))
        ctx.check(f"the listing: the twin under it, indented, with the note, got {text}",
                  text[orig + 1].startswith("    qwen3-halo:30b") and NOTE in text[orig + 1]
                  and "[ol:qwen3-halo:30b]" in text[orig + 1])


@test
def test_the_pickers_put_the_twin_first(ctx: Ctx):
    from halo_harness.providers.model_enumeration import build_model_rows
    from halo_harness.providers.ollama_tune_rows import picker_twins_first
    with _Env() as env:
        rows = [r for r in build_model_rows(env.state_dir, env=dict(os.environ)) if r.get("group") == "Ollama (pc)"]
        refs = [r["ref"] for r in rows]
        ctx.check(f"twin first, original after, got {refs}", refs[:2] == ["ol:qwen3-halo:30b", "ol:qwen3:30b"])
        ctx.check(f"the twin's row says so, got {rows[0]}", rows[0]["twin_of"] == "qwen3:30b" and NOTE in rows[0]["detail"])
    scattered = [{"ref": "ol:a:1b@x"}, {"ref": "ol:qwen3:30b@x"}, {"ref": "ol:b:1b@x"},
                 {"ref": "ol:qwen3-halo:30b@x", "twin_of": "qwen3:30b"}, {"ref": "ol:lone-halo:2b@x", "twin_of": "lone:2b"}]
    got = [m["ref"] for m in picker_twins_first(scattered)]
    ctx.check(f"after any sort the twin lands right before its original, got {got}",
              got == ["ol:a:1b@x", "ol:qwen3-halo:30b@x", "ol:qwen3:30b@x", "ol:b:1b@x", "ol:lone-halo:2b@x"])


class _Fit:
    def __init__(self, mock, model: str, fit: int):
        self.mock, self.model, self.fit = mock, model, fit

    def __call__(self, handler, body) -> None:
        n = int(((body or {}).get("options") or {}).get("num_ctx") or 0)
        size = 13 * _GB
        self.mock.ps_response = {"models": [{"model": self.model, "name": self.model, "size": size,
                                             "size_vram": size if n <= self.fit else size // 2, "context_length": n}]}
        SCENARIOS["done-reason-stop"](handler, body)


def _discover(argv: list) -> "tuple[int, str, str]":
    from halo_harness.ollama_cli import cmd_ollama
    out, err = io.StringIO(), io.StringIO()
    with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
        rc = cmd_ollama(["discover", "--add", "--calibrate", "--timeout", "5"] + argv)
    return rc, out.getvalue(), err.getvalue()


@test
def test_discover_twins_makes_them_without_asking(ctx: Ctx):
    from halo_harness import ollama_discover_cli
    with _Env(twin=False, second=True) as env:
        env.b.scenarios["gpt-oss:20b"] = _Fit(env.b, "gpt-oss:20b", 32768)
        asked: list = []
        real_ask, ollama_discover_cli._ask = ollama_discover_cli._ask, lambda q: asked.append(q) or False
        try:
            rc, out, err = _discover(["--twins"])
        finally:
            ollama_discover_cli._ask = real_ask
        name = f"local-{env.b.port}"
        ctx.check(f"exit 0, never asked, got {rc} {asked} {err}", rc == 0 and asked == [])
        line = [ln for ln in out.splitlines() if "tuned twin" in ln]
        ctx.check(f"one line per twin, got {line}", line == [f"gpt-oss:20b on {name}: tuned twin gpt-oss-halo:20b made "
                                                           f"(32k window, all layers on the GPU) [ol:gpt-oss-halo:20b@{name}]"])
        ctx.check(f"made on that host, got {env.b.created}", [c["model"] for c in env.b.created] == ["gpt-oss-halo:20b"])


@test
def test_discover_no_twins_and_the_question(ctx: Ctx):
    from halo_harness import ollama_discover_cli
    from halo_harness.providers import ollama_tune
    from halo_harness.providers.ollama_tune import TwinResult
    with _Env(twin=False, second=True) as env:
        env.b.scenarios["gpt-oss:20b"] = _Fit(env.b, "gpt-oss:20b", 32768)
        asked, made = [], []
        real_ask, real_create = ollama_discover_cli._ask, ollama_tune.create_twin
        ollama_discover_cli._ask = lambda q: asked.append(q) or True
        ollama_tune.create_twin = lambda host, plan, **kw: made.append(plan.twin) or TwinResult(True, "ok", plan.ref,
                                                                                                plan.twin)
        try:
            rc, out, _err = _discover(["--no-twins"])
            ctx.check(f"--no-twins: no question, nothing made, got {rc} {asked} {made}",
                      rc == 0 and asked == [] and made == [] and "tuned twin" not in out)
            from halo_harness.providers.ollama_discover import reset_discover_cache
            from halo_harness.theme import set_config_value
            set_config_value("ollama.hosts", [{"name": "pc", "url": env.mock.base_url, "default": True}])
            reset_discover_cache()
            rc, out, _err = _discover([])
            ctx.check(f"the question asked once, Enter = yes, got {asked}",
                      asked == ["make tuned twins of the models that fit? (Enter / n)"])
            ctx.check(f"the stubbed create ran for the fitting model, got {made} {out}",
                      made == ["gpt-oss-halo:20b"] and "tuned twin gpt-oss-halo:20b made (32k window" in out)
            ctx.check("the stub, not the mock, made it", env.b.created == [])
            rc, _out, _err = _discover(["--twins", "--no-twins"])
            ctx.check(f"exit 2 for both flags, got {rc}", rc == 2)
        finally:
            ollama_discover_cli._ask, ollama_tune.create_twin = real_ask, real_create


if __name__ == "__main__":
    ctx = Ctx()
    results, passed, failed, skipped = run_all(TESTS, ctx)
    sys.exit(print_results(results, passed, failed, skipped))
