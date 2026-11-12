"""tests.test_steward_quiet_start -- Halo 3.4.0.1 "Found live" (defect 13): starting Studio loads and calls no model.

The live check: `halo studio` on the PC started the Ollama steward's job, which called the steward model (a local
model on the PC's Ollama, 36 s) within three minutes and raised an attention row. Now the job that starts with Studio
(or the hub) reads the logs and runs the rules and calls no model, nor probes a new one: the steward explains when
asked, or when the owner turned its watching on (`halo ollama steward --watch`, `ollama.steward.watch: true`).

A fake Ollama counts the calls that would load or run a model (/api/chat, /api/generate, /v1/chat/completions,
/api/embed): zero after the real in-process Studio starts and the job, started the way Studio starts it, has run
its timer's passes with calls flowing and a model with no profile on the host; one note call once watching is on.
Run: python -m tests.test_steward_quiet_start
"""
from __future__ import annotations

import json
import sys
import threading
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from tests.helpers.provider_env_defaults import ensure_default_provider_credentials  # noqa: E402
ensure_default_provider_credentials()

from tests.helpers.runner import Ctx, new_registry, print_results, run_all  # noqa: E402
from tests.helpers.steward_seed import Home, line  # noqa: E402

test, TESTS = new_registry()
LOADS = ("/api/chat", "/api/generate", "/v1/chat/completions", "/api/embed", "/api/embeddings")


def _loads(mock) -> list:
    return [r["path"] for r in mock.requests if r.get("method") == "POST" and str(r.get("path")).split("?")[0] in LOADS]


def _wait(fn, timeout: float = 20.0):
    end = time.monotonic() + timeout
    while time.monotonic() < end:
        got = fn()
        if got:
            return got
        time.sleep(0.05)
    return fn()


@test
def test_studio_and_its_steward_job_call_no_model(ctx: Ctx):
    from halo_harness.ollama_steward import job_state
    from halo_harness.ollama_steward.job import StewardJob
    from halo_harness.studio.server import start_server
    from tests.helpers.mock_ollama import MockUpstream
    mock = MockUpstream().start()
    url = f"http://127.0.0.1:{mock._server.server_address[1]}"
    fake = {"name": "fake", "url": url}
    try:
        with Home(hosts=(fake,), extra={"ollama": {"steward": {"model": "ol:qwen3:30b@fake"}}}) as h:
            h.calls(*[line(host=fake, model="qwen3:30b", prompt_eval_count=31000, ago=120 - i, session=None)
                      for i in range(5)])  # calls flow: the timer's pass is due at once
            proj = h.root / "project"
            proj.mkdir()
            srv = start_server(port=0, cwd=proj, state_dir=h.state)
            threading.Thread(target=srv.serve_forever, daemon=True).start()
            job = StewardJob(h.state, where="studio", watch=False)  # Studio's own start (studio/server.py), its guard aside
            try:
                ok, why = job.start()
                ctx.check(f"the job runs as Studio starts it, got {ok} {why!r}", ok)
                ran = _wait(lambda: job.last_run is not None, 20)
                ctx.check("its timer's first pass ran (calls flow)", bool(ran))
                job.tick(time.time() + 400)  # a second pass, and a probe check past its period
                ctx.check(f"no model call from Studio's start and the job's passes, got {_loads(mock)}", _loads(mock) == [])
                st = job_state.read(h.state)
                ctx.check(f"the model is named, its note not written, got {st.get('model')} {st.get('last_note')}",
                          st.get("model") == "ol:qwen3:30b@fake" and not st.get("last_note"))
                cfg = json.loads((h.state / "config.json").read_text(encoding="utf-8"))
                cfg["ollama"]["steward"]["watch"] = True
                (h.state / "config.json").write_text(json.dumps(cfg), encoding="utf-8")
                job.run_once(time.time() + 800)
                ctx.check(f"watching on: the note is one model call to the fake, got {_loads(mock)}", len(_loads(mock)) >= 1)
            finally:
                job.stop()
                srv.shutdown()
                srv.server_close()
        ctx.check("halo ollama steward --watch (where watch) may call it", job_state.watching("watch") is True)
    finally:
        mock.stop()


if __name__ == "__main__":
    ctx = Ctx()
    results, passed, failed, skipped = run_all(TESTS, ctx)
    sys.exit(print_results(results, passed, failed, skipped, label="steward quiet start tests"))
