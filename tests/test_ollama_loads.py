"""tests.test_ollama_loads -- Halo 3.6.0.0 R8: a model on another machine answers as fast as that machine can.

Every test runs a real `halo -p` (tests/helpers/halo_turn_net.py: a turn's own requests unmasked) against
`tests/helpers/mock_ollama_loads.LoadCountingOllama` -- a fake Ollama on loopback that counts loads, reloads,
unloads and measurement steps the way a real server's resident set would. Never a real Ollama, never a real model.
The host entry is the shape a laptop uses for a desktop: `{"name": "gpu-box", "url": ..., "max_ctx": 65536}`.

Pinned (plans brief v360-R8, section H):
- first use of a model: exactly ONE load, zero measurement (`calibrate`) requests;
- a second call (a new process, the same home): zero loads;
- a model already loaded at a larger window by another client: zero reloads, the turn uses that window;
- a request larger than the loaded window: one reload, to a ladder step, not to the host's cap;
- nothing is unloaded at the end of a session, and no request carries a keep_alive nobody set;
- the estimate after one turn is within 1.5x of the real count, and starts from the measured ratio next time;
- the wait says what it is: a `system`/`status` line "loading <model> on <host>" in stream-json.
Run: python -m tests.test_ollama_loads
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from tests.helpers.provider_env_defaults import ensure_default_provider_credentials  # noqa: E402
ensure_default_provider_credentials()

from tests.helpers.runner import Ctx, new_registry, print_results, run_all  # noqa: E402
from tests.helpers.fake_home import build_fake_home  # noqa: E402
from tests.helpers.mock_ollama_loads import LoadCountingOllama  # noqa: E402

REPO_DIR = Path(__file__).resolve().parent.parent
CAP = 65536
MODEL = "tiny:1b"
test, TESTS = new_registry()


def _fake(**kw) -> LoadCountingOllama:
    return LoadCountingOllama({MODEL: {"size_gb": 1.0, "trained": 262144}}, **kw).start()


def _home(fake, *, max_ctx: int = CAP):
    fh = build_fake_home()
    cfg = Path(fh["home"]) / ".halo" / "config.json"
    cfg.parent.mkdir(parents=True, exist_ok=True)
    data = json.loads(cfg.read_text(encoding="utf-8")) if cfg.exists() else {}
    data.setdefault("ollama", {})["hosts"] = [{"name": "gpu-box", "url": fake.base_url, "max_ctx": max_ctx}]
    cfg.write_text(json.dumps(data), encoding="utf-8")
    return fh


def _env(fh, fake) -> dict:
    env = dict(os.environ)
    env.pop("BRIDGE_STATE_DIR", None)
    for k in [k for k in env if k.startswith("HALO_")]:
        env.pop(k, None)
    env.pop("OLLAMA_API_KEY", None)
    env.update({"BRIDGE_TEST_HOME": str(fh["home"]), "BRIDGE_TEST_NO_BACKGROUND_NET": "1",
                "OLLAMA_HOST": fake.base_url, "PYTHONPATH": str(REPO_DIR)})
    return env


def _run(fh, fake, prompt: str = "Reply with exactly one word: ready", *extra: str, timeout: float = 120):
    args = [sys.executable, "-m", "tests.helpers.halo_turn_net", "-p", prompt, "--model", f"ol:{MODEL}@gpu-box",
            "--cwd", str(fh["proj"]), "--permission-mode", "auto", *extra]
    return subprocess.run(args, env=_env(fh, fake), cwd=str(REPO_DIR), capture_output=True, text=True,
                          timeout=timeout, encoding="utf-8", errors="replace")


def _turn_lines(fh) -> list:
    path = Path(fh["home"]) / ".halo" / "ollama" / "traffic.jsonl"
    if not path.exists():
        return []
    out = []
    for raw in path.read_text(encoding="utf-8").splitlines():
        try:
            line = json.loads(raw)
        except ValueError:
            continue
        if line.get("kind") == "turn":
            out.append(line)
    return out


def _turn_chats(fake) -> list:
    return [r["body"] for r in fake.requests if r["method"] == "POST" and r["path"].rstrip("/") == "/api/chat"
            and (r["body"] or {}).get("stream") is not False]


def _ok(ctx, result, what: str) -> None:
    ctx.check(f"{what}: exit 0, got {result.returncode} {(result.stdout + result.stderr)[-600:]!r}",
              result.returncode == 0)


@test
def test_first_use_is_one_load_and_no_measurement(ctx: Ctx):
    fake = _fake()
    try:
        fh = _home(fake)
        result = _run(fh, fake)
        _ok(ctx, result, "first use")
        ctx.check(f"zero measurement steps, got {len(fake.calibrates)}: {fake.summary()}", not fake.calibrates)
        ctx.check(f"exactly one load, got {len(fake.loads)}: {fake.summary()}", len(fake.loads) == 1)
        sent = _turn_chats(fake)
        window = ((sent[0].get("options") or {}).get("num_ctx")) if sent else None
        ctx.check(f"the turn asks for what it needs, not the cap {CAP}, got {window}",
                  isinstance(window, int) and window < CAP)
    finally:
        fake.stop()


@test
def test_a_second_call_loads_nothing(ctx: Ctx):
    fake = _fake()
    try:
        fh = _home(fake)
        _ok(ctx, _run(fh, fake), "first call")
        before = len(fake.loads)
        result = _run(fh, fake)
        _ok(ctx, result, "second call")
        ctx.check(f"zero loads on the second call, got {len(fake.loads) - before}: {fake.summary()}",
                  len(fake.loads) == before)
        ctx.check(f"zero measurement steps across both calls, got {len(fake.calibrates)}", not fake.calibrates)
    finally:
        fake.stop()


@test
def test_a_model_another_client_loaded_larger_is_used_at_that_window(ctx: Ctx):
    fake = _fake()
    try:
        fh = _home(fake)
        fake.preload(MODEL, 131072)  # another machine loaded it at 131,072 (above this laptop's cap)
        result = _run(fh, fake)
        _ok(ctx, result, "a loaded model")
        ctx.check(f"zero reloads, got {fake.loads}", not fake.loads)
        sent = _turn_chats(fake)
        window = ((sent[0].get("options") or {}).get("num_ctx")) if sent else None
        ctx.check(f"the turn uses the loaded window 131072, got {window}", window == 131072)
        lines = _turn_lines(fh)
        source = lines[0].get("window_source") if lines else None
        ctx.check(f"the ledger says the loaded window chose it, got {source!r}", source == "loaded")
    finally:
        fake.stop()


@test
def test_a_request_larger_than_the_loaded_window_reloads_one_ladder_step(ctx: Ctx):
    fake = _fake()
    try:
        fh = _home(fake)
        fake.preload(MODEL, 4096)  # too small for Halo's own prompt
        result = _run(fh, fake)
        _ok(ctx, result, "a reload")
        ctx.check(f"exactly one reload, got {fake.loads}", len(fake.loads) == 1)
        got = fake.loads[0]["num_ctx"] if fake.loads else None
        ctx.check(f"to a ladder step (8,192 / 16,384 / 32,768), not the cap {CAP}, got {got}",
                  got in (8192, 16384, 32768))
        ctx.check(f"zero measurement steps, got {len(fake.calibrates)}", not fake.calibrates)
    finally:
        fake.stop()


@test
def test_nothing_is_unloaded_at_the_end_of_a_session(ctx: Ctx):
    fake = _fake()
    try:
        fh = _home(fake)
        _ok(ctx, _run(fh, fake), "a session")
        _ok(ctx, _run(fh, fake, "and again"), "a second session")
        ctx.check(f"no unload, got {fake.unloads}", not fake.unloads)
        ctx.check(f"no request carried a keep_alive (none was set), got {fake.keep_alives}", not fake.keep_alives)
        ctx.check(f"the model is still resident, got {fake.resident}", MODEL in fake.resident)
    finally:
        fake.stop()


@test
def test_the_estimate_is_within_1_5x_of_the_real_count(ctx: Ctx):
    fake = _fake()
    try:
        fh = _home(fake)
        _ok(ctx, _run(fh, fake), "one turn")
        lines = _turn_lines(fh)
        line = lines[-1] if lines else {}
        est, real = line.get("estimate_tokens"), line.get("prompt_eval_count")
        ctx.check(f"the ledger has both numbers, got estimate {est} real {real}",
                  isinstance(est, int) and isinstance(real, int) and real > 0)
        if isinstance(est, int) and isinstance(real, int) and real > 0:
            ctx.check(f"estimate {est} within 1.5x of the real {real} (ratio {est / real:.2f})",
                      real / 1.5 <= est <= real * 1.5)
    finally:
        fake.stop()


@test
def test_the_next_estimate_starts_from_the_measured_ratio(ctx: Ctx):
    fake = _fake()
    fake.count_ratio = 1.8  # this model's tokenizer reads 1.8x what chars / 3.5 says (code, CJK, ...)
    try:
        fh = _home(fake)
        _ok(ctx, _run(fh, fake), "the first turn")
        # 3.6.0.0 R8 second fix pass (F1): a first count 1.8x the estimate reaches into the reply's room, so the
        # first process sends the call once more at a larger window (one or two turn lines); the next process's
        # call is the one that starts from the measured ratio
        first = len(_turn_lines(fh))
        _ok(ctx, _run(fh, fake), "the next process")
        lines = _turn_lines(fh)
        ctx.check(f"one turn line for the next process, got {len(lines) - first} after {first}",
                  len(lines) == first + 1 and first in (1, 2))
        if len(lines) == first + 1:
            est, real = lines[-1].get("estimate_tokens"), lines[-1].get("prompt_eval_count")
            ok = isinstance(est, int) and isinstance(real, int) and real > 0 and real / 1.5 <= est <= real * 1.5
            ctx.check(f"the second estimate {est} is within 1.5x of the real {real}", ok)
    finally:
        fake.stop()


@test
def test_the_wait_says_it_is_loading_in_stream_json(ctx: Ctx):
    fake = _fake()
    fake.cold_load_s = 0.4
    try:
        fh = _home(fake)
        result = _run(fh, fake, "hi", "--output-format", "stream-json", "--verbose")
        _ok(ctx, result, "stream-json")
        events = []
        for raw in result.stdout.splitlines():
            try:
                events.append(json.loads(raw))
            except ValueError:
                pass
        status = [e for e in events if e.get("type") == "system" and e.get("subtype") == "status"]
        texts = [str(e.get("text") or "") for e in status]
        ctx.check(f"a 'loading {MODEL} on gpu-box (1.0 GB)' line, got {texts}",
                  any(f"loading {MODEL} on gpu-box" in t and "GB" in t for t in texts))
        ctx.check(f"then how long it took, got {texts}", any("loaded" in t and " s" in t for t in texts))
        first_assistant = next((i for i, e in enumerate(events) if e.get("type") == "assistant"), len(events))
        first_loading = next((i for i, e in enumerate(events) if e in status), len(events))
        ctx.check("the loading line comes before the answer", first_loading < first_assistant)
        # a second call: the model is resident, nothing is said
        result = _run(fh, fake, "hi", "--output-format", "stream-json", "--verbose")
        ctx.check("a warm call says nothing about loading",
                  "loading " + MODEL not in result.stdout)
    finally:
        fake.stop()


@test
def test_a_profiles_window_loaded_by_the_first_request_is_not_reloaded_by_the_second(ctx: Ctx):
    """3.6.0.20 E4: a steward profile sets the window (32,768); the first request of a turn goes without `num_gpu`
    (Halo did not know the window fits the card), and before the second (after a tool step) the window becomes known
    to fit (here a measurement lands in the home; in real use a fresher card reading): the model is resident at the
    window sent, so the second request keeps the runner's options. ONE load (it was two: `num_gpu` then sent)."""
    fake = _fake()
    try:
        fh = _home(fake)
        halo = Path(fh["home"]) / ".halo"
        cfg = halo / "config.json"
        data = json.loads(cfg.read_text(encoding="utf-8"))
        data["ollama"]["profiles"] = {f"gpu-box|{MODEL}": {"num_ctx": 32768}}
        cfg.write_text(json.dumps(data), encoding="utf-8")
        target = Path(fh["proj"]) / "a.txt"
        target.write_text("one line\n", encoding="utf-8")
        fake.replies = [{"role": "assistant", "content": "", "tool_calls": [
            {"function": {"name": "Read", "arguments": {"file_path": str(target)}}}]}]
        seen = fake.observe

        def observe(method, path, body):
            seen(method, path, body)
            if path == "/api/chat" and len(fake.loads) == 1 and not (halo / "ollama-fit.json").exists():
                from halo_harness.providers.ollama_calibrate import record_calibration
                record_calibration(halo, host_url=fake.base_url, model=MODEL, digest=None, max_full_gpu_ctx=32768,
                                   ollama_version=None)
        fake.observe = observe
        result = _run(fh, fake, "Read a.txt, then reply with exactly one word: ready")
        _ok(ctx, result, "a turn with one tool step")
        sent = [(b.get("options") or {}) for b in _turn_chats(fake)]
        ctx.check(f"two requests at the profile's 32,768, got {[o.get('num_ctx') for o in sent]}",
                  len(sent) == 2 and all(o.get("num_ctx") == 32768 for o in sent))
        ctx.check(f"one load, got {fake.loads}", len(fake.loads) == 1)
    finally:
        fake.stop()


@test
def test_a_resident_load_that_spills_is_not_kept_by_a_window_of_another_source(ctx: Ctx):
    """3.6.0.20 (its review): E4 keeps the resident runner's options at the window sent whatever the window's source.
    A resident load that runs partly on the CPU is NOT kept: the call sends its own `num_gpu`, so the model is
    reloaded onto the card, as before E4."""
    import tempfile
    from types import SimpleNamespace
    from unittest import mock

    from halo_harness.agent import ollama_window_truth as T
    from halo_harness.providers import ollama_hw
    host = SimpleNamespace(url="http://gpu-box:11434")
    body = {"options": {"num_ctx": 32768, "num_gpu": 48}}
    with tempfile.TemporaryDirectory() as td:
        session = SimpleNamespace(state_dir=Path(td))
        for name, row, want in (("wholly on the card", {"context_length": 32768, "size": 20, "size_vram": 20}, None),
                                ("partly on the CPU", {"context_length": 32768, "size": 20, "size_vram": 15}, 48),
                                ("at another window", {"context_length": 16384, "size": 20, "size_vram": 20}, 48)):
            with mock.patch.object(ollama_hw, "last_ps_entry", lambda url, model, _r=row: (True, _r)):
                got = T.resident_options(session, host, "tiny:1b", body, "steward profile")
            ctx.check(f"{name}: the num_gpu sent is {want}, got {got['options'].get('num_gpu')}",
                      got["options"].get("num_gpu") == want)


if __name__ == "__main__":
    ctx = Ctx()
    results, passed, failed, skipped = run_all(TESTS, ctx)
    sys.exit(print_results(results, passed, failed, skipped))
