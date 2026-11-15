"""tests.test_ollama_cut_shapes -- Halo 3.6.0.0 R8, second fix pass (brief v360-R8-fix-judge): the shapes a real
Ollama server cuts a prompt into, and the window choices around them.

Measured on Ollama 0.40.16 by the coordinator (the facts these tests rely on): one over-long message comes back with
`prompt_eval_count` = `num_ctx // 2 + 2` (1,026 / 2,050 / 4,098 at 2,048 / 4,096 / 8,192); a chat of many messages
loses whole messages from the front and lands a little under `num_ctx` (2,020 at 2,048, 4,012 at 4,096); both answer
`done_reason: "stop"`; an honest prompt whose reply runs out answers `"length"`. Loopback fakes only
(tests/helpers/mock_ollama_loads.LoadCountingOllama, plain http.server stubs); never a real Ollama, never a real model.

Pinned:
- F1: every cut shape (the judge's probe table: edge, half, front-drop) ends with the prompt sent whole at a window
  that holds it (or one line that it cannot fit under the host's cap), and no ratio is learned from a cut count; the
  four signs (half the window, into the reply's room, a count that shrank, under 70 %) and an honest call that is
  none of them;
- F2: a loaded window wholly on the card right now is held, and a recorded spill at or under it is cleared;
- F3: the measure guard's restore with an unreadable `/api/ps` afterwards puts back only the measured model and says
  the others were not checked;
- F4: a helper call on the session's own model never makes the main call grow, and a helper never grows past its need;
- F5: two sub-agents starting together on one loaded model cause at most one reload, in either order;
- F6: the read before a call waits 3 s at most, and the call says in one line that it was given up on.
Run: python -m tests.test_ollama_cut_shapes
"""
from __future__ import annotations

import json
import sys
import tempfile
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from types import SimpleNamespace

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from tests.helpers.provider_env_defaults import ensure_default_provider_credentials  # noqa: E402
ensure_default_provider_credentials()

from tests.helpers.runner import Ctx, new_registry, print_results, run_all  # noqa: E402
from tests.helpers.mock_ollama_loads import GB  # noqa: E402
from tests import test_ollama_loads as L  # noqa: E402
from tests import test_ollama_window_fixes as F  # noqa: E402

MODEL, CAP = L.MODEL, L.CAP
test, TESTS = new_registry()


# ---- F1: the judge's probe table, end to end -----------------------------------------------------------------------

ROWS = (("edge", 4.0, "edge"), ("half", 4.0, "half"), ("half", 2.2, "half"), ("drop", 2.2, ("drop", 1500)))


@test
def test_every_cut_shape_ends_with_the_prompt_sent_whole_or_one_line(ctx: Ctx):
    est0, real0 = F._baseline()
    for name, ratio, shape in ROWS:
        fake = L._fake()
        fake.count_ratio = ratio / (real0 / est0)
        fake.cut_shape = shape
        try:
            fh = L._home(fake)
            result = L._run(fh, fake, "Reply with exactly one word: ready", "--verbose")
            F._ok(ctx, result, f"{name} {ratio}")
            sent = F._opts(fake)
            cut_windows = [c["num_ctx"] for c in fake.cuts]
            whole = bool(sent) and len(fake.cuts) < len(sent) and sent[-1].get("num_ctx") not in cut_windows[-1:]
            line = [ln for ln in result.stdout.splitlines() if "re-sent" in ln or "cannot fit" in ln
                    or "compacted" in ln]
            ctx.check(f"{name} {ratio}: the prompt was cut ({cut_windows}) and then sent whole, got {sent}", whole)
            ctx.check(f"{name} {ratio}: one plain line says so, got {line}", len(line) == 1)
            stored = (F._fit(fh).get("token_ratio") or {})
            ratios = [v.get("ratio") for v in stored.values() if isinstance(v, dict)]
            ctx.check(f"{name} {ratio}: no ratio learned from the cut count (about 1.0), got {ratios}",
                      all(r is None or r > 1.5 for r in ratios))
        finally:
            fake.stop()


# ---- F1: the four signs, on the measured numbers ---------------------------------------------------------------------

@test
def test_the_four_signs_of_a_cut_and_an_honest_call_that_shows_none(ctx: Ctx):
    from halo_harness.agent.ollama_window_truth import cut_kind
    for window, count in ((2048, 1026), (4096, 2050), (8192, 4098), (16384, 8194)):
        got = cut_kind(count=count, num_ctx=window, num_predict=window // 4, ceiling=65536, prompt=9000, raw=9000)
        ctx.check(f"one message cut to half of {window} ({count}): 'half', got {got}", got == "half")
    for window, count in ((2048, 2020), (4096, 4012)):
        got = cut_kind(count=count, num_ctx=window, num_predict=window // 4, ceiling=65536, prompt=1500, raw=1500)
        ctx.check(f"61 messages front-dropped to {count} of {window}: 'room', got {got}", got == "room")
    got = cut_kind(count=9000, num_ctx=32768, num_predict=8192, ceiling=65536, prompt=12000, raw=12000,
                   prev=(11000, 11500))
    ctx.check(f"a count that shrank while the conversation grew: 'shrink', got {got}", got == "shrink")
    got = cut_kind(count=3000, num_ctx=32768, num_predict=8192, ceiling=65536, prompt=12000, raw=12000)
    ctx.check(f"under 70 % of the estimate: 'low', got {got}", got == "low")
    honest = (dict(count=9393, num_ctx=16384, num_predict=4096, prompt=9393, raw=9393),
              dict(count=2355, num_ctx=4096, num_predict=16, prompt=2300, raw=2300),  # the reply ran out: "length"
              dict(count=7725, num_ctx=16384, num_predict=4096, prompt=7950, raw=7950),
              dict(count=9000, num_ctx=32768, num_predict=8192, prompt=8000, raw=8000, prev=(11000, 12000)))
    for kw in honest:
        got = cut_kind(ceiling=65536, **kw)
        ctx.check(f"an honest call is none of them: {kw} -> {got}", got is None)
    got = cut_kind(count=60000, num_ctx=65536, num_predict=16384, ceiling=65536, prompt=58000, raw=58000)
    ctx.check(f"at the largest window a full reply room is not a cut (compaction's to fix), got {got}", got is None)


@test
def test_a_call_that_loaded_the_model_learns_no_ratio_from_a_cut_count(ctx: Ctx):
    import halo_harness.providers.ollama as O
    from halo_harness.agent import ollama_window_truth as W
    host = SimpleNamespace(url="http://gpu-box:11434", name="gpu-box", api_key=None, max_ctx=None, keep_alive=None)
    real_host = W._host_for_url
    W._host_for_url = lambda session, url: host
    try:
        state = Path(tempfile.mkdtemp())
        ref = SimpleNamespace(model=MODEL)
        st = {"factor": {}, "trim_turn": None, "last": None,
              "sent": {(host.url, MODEL): {"estimate": 8974, "reserve": 1024, "raw_prompt": 7950}}}
        session = SimpleNamespace(state_dir=state, model_ref=ref, _ollama_window_state=st,
                                  _ollama_loading={"model": MODEL, "host": "gpu-box", "t0": time.monotonic()})
        req = SimpleNamespace(prebuilt_ollama_body={"model": MODEL, "options": {"num_ctx": 16384, "num_predict": 4096}},
                              creds=SimpleNamespace(base_url=host.url))
        W.after_call(session, req, {"timing_ns": {"prompt_eval_count": 8194, "eval_count": 2}}, "turn")
        ctx.check(f"no ratio from the half-window count of a fresh load, got {W._section(state, 'token_ratio', W._key(host.url, MODEL))}",
                  not W._section(state, "token_ratio", W._key(host.url, MODEL)))
        verdict = W.take_cut(session, req)
        ctx.check(f"and the call is marked cut for the resend, got {verdict}", bool(verdict) and verdict["kind"] == "half")
    finally:
        W._host_for_url = real_host
    del O


# ---- F2: a live reading beats a stale record -----------------------------------------------------------------------

@test
def test_a_loaded_window_wholly_on_the_card_now_is_held_and_its_old_spill_cleared(ctx: Ctx):
    state = {"shared": True}

    def vram(num_ctx):
        size = GB + num_ctx * 64 * 1024
        return size, (size // 2 if state["shared"] and num_ctx >= 32768 else size)
    fake = L._fake()
    fake.vram[MODEL] = vram
    try:
        fh = L._home(fake)
        truth_path = Path(fh["home"]) / ".halo" / "ollama-fit.json"
        truth_path.parent.mkdir(parents=True, exist_ok=True)
        truth_path.write_text(json.dumps({"window_truth": {f"{fake.base_url}|{MODEL}": {
            "spills": 32768, "fits": 16384, "num_ctx": 16384, "num_gpu": None}}}), encoding="utf-8")
        state["shared"] = False
        fake.preload(MODEL, 32768)  # another client loaded it at 32,768, wholly on the card now
        outs = [L._run(fh, fake, "Reply with exactly one word: ready", "--verbose") for _ in range(2)]
        for i, r in enumerate(outs):
            F._ok(ctx, r, f"run {i}")
        ctx.check(f"no reload of a window wholly on the card, got {fake.loads}", not fake.loads)
        said = [ln for r in outs for ln in r.stdout.splitlines() if "CPU" in ln]
        ctx.check(f"no line that it runs on the CPU, got {said}", not said)
        t = (F._fit(fh).get("window_truth") or {}).get(f"{fake.base_url}|{MODEL}") or {}
        ctx.check(f"the old spill at 32,768 is cleared, got {t}", not t.get("spills"))
    finally:
        fake.stop()


# ---- F3: the measure guard's restore with an unreadable server ----------------------------------------------------

@test
def test_the_measure_restore_puts_back_only_the_measured_model_when_ps_is_unreadable(ctx: Ctx):
    import halo_harness.providers.ollama_load as LD
    import halo_harness.providers.ollama_measure_guard as G
    host = SimpleNamespace(url="http://gpu-box:11434", name="gpu-box")
    reads = iter([{MODEL: 16384, "big:27b": 8192, "other:7b": 4096}, None])
    loads = []
    real = (G._resident, LD.load, LD.unload)
    G._resident = lambda h: next(reads)
    LD.load = lambda h, m, **kw: loads.append((m, kw.get("num_ctx"))) or {"ok": True, "say": "loaded"}
    LD.unload = lambda h, m: loads.append((m, 0)) or {"ok": True, "say": "unloaded"}
    try:
        with G.measuring(host, MODEL, Path(tempfile.mkdtemp())) as g:
            ctx.check("the guard holds the server", g.ok)
        ctx.check(f"only the measured model is put back, got {loads}", loads == [(MODEL, 16384)])
        ctx.check(f"and the line says the others were not checked, got {g.left!r}",
                  "not checked" in g.left and "big:27b" in g.left and "other:7b" in g.left)
    finally:
        G._resident, LD.load, LD.unload = real


# ---- F4 / F5: start_window on stub sessions ----------------------------------------------------------------------

def _host(port: int) -> SimpleNamespace:
    return SimpleNamespace(url=f"http://127.0.0.1:{port}", name="gpu-box", max_ctx=CAP, api_key=None, keep_alive=None)


def _session(ref) -> SimpleNamespace:
    return SimpleNamespace(state_dir=Path(tempfile.mkdtemp()), model_ref=ref, provider_profile=None)


def _ask(session, ref, host, tokens: int) -> int:
    from halo_harness.agent.ollama_window_truth import start_window
    request = ("You answer.", [{"role": "user", "content": "x" * int(tokens * 3.5)}], [])
    return start_window(session, host=host, ref=ref, decision=SimpleNamespace(profile=None), cap=CAP,
                        cap_source="host max_ctx", request=request, requested=None)[0]


def _resident(host, window: int) -> None:
    from halo_harness.providers.ollama_hw import _record_last_known_offload
    _record_last_known_offload(host.url, MODEL, {"model": MODEL, "name": MODEL, "context_length": window,
                                                 "size": 2 * GB, "size_vram": 2 * GB})


@test
def test_a_helper_call_never_makes_the_main_call_or_itself_grow_to_the_cap(ctx: Ctx):
    host = _host(40001)
    ref = SimpleNamespace(model=MODEL)
    s = _session(ref)
    s._ollama_helper_call = True  # a title / hook call on the session's own model, before the main call
    w_helper = _ask(s, ref, host, 1500)
    s._ollama_helper_call = False
    _resident(host, w_helper)
    w_main = _ask(s, ref, host, 7000)  # the helper's window does not hold it: the main call loads
    ctx.check(f"the helper asked small ({w_helper}), and the main call asks its need, not the cap {CAP}, got {w_main}",
              w_helper <= 16384 and w_main < CAP)
    small = SimpleNamespace(model=MODEL)  # a small-model ref (not the session's own) on the same server
    h2 = _host(40002)
    s2 = _session(SimpleNamespace(model="main:27b"))
    first = _ask(s2, small, h2, 2000)
    _resident(h2, first)
    again = _ask(s2, small, h2, 9000)
    ctx.check(f"a helper that grows asks its need ({first} -> {again}), never the cap {CAP}", again < CAP)


@test
def test_two_sub_agents_starting_together_reload_the_model_at_most_once_in_either_order(ctx: Ctx):
    for port, order in ((40011, "AB"), (40012, "BA")):
        host = _host(port)
        _resident(host, 16384)
        ra, rb = SimpleNamespace(model=MODEL), SimpleNamespace(model=MODEL)
        a, b = _session(ra), _session(rb)
        needs = {"A": (a, ra, 20000), "B": (b, rb, 5000)}
        resident, reloads, seen = 16384, 0, []
        for _round in range(2):  # both start together (one /api/ps reading), then each makes its next call
            asks = [(who, _ask(*needs[who][:2], host, needs[who][2])) for who in order]
            for who, w in asks:  # the server runs them one after the other
                seen.append((who, w))
                if w != resident:
                    reloads, resident = reloads + 1, w
            _resident(host, resident)
        ctx.check(f"{order}: at most one reload, got {reloads} from {seen}", reloads <= 1)


# ---- F6: the read before a call is bounded ------------------------------------------------------------------------

class _SlowPs(BaseHTTPRequestHandler):
    def log_message(self, *a):
        pass

    def do_GET(self):  # noqa: N802
        time.sleep(6)
        try:
            self.send_response(200)
            self.end_headers()
            self.wfile.write(b'{"models": []}')
        except OSError:
            pass


@test
def test_the_read_before_a_call_waits_three_seconds_and_says_it_gave_up(ctx: Ctx):
    from halo_harness.providers.ollama import OllamaHost, fetch_ps
    from halo_harness.providers.ollama_hw import ps_gave_up
    srv = ThreadingHTTPServer(("127.0.0.1", 0), _SlowPs)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    try:
        url = f"http://127.0.0.1:{srv.server_address[1]}"
        t0 = time.monotonic()
        got = fetch_ps(OllamaHost(name="gpu-box", url=url))
        took = time.monotonic() - t0
        ctx.check(f"a server that stopped answering costs about 3 s, took {took:.1f} s", got is None and took < 4.0)
        ctx.check("the read is noted as given up on", ps_gave_up(url))
        ref = SimpleNamespace(model=MODEL)
        s = _session(ref)
        _ask(s, ref, SimpleNamespace(url=url, name="gpu-box", max_ctx=CAP), 2000)
        markers = (getattr(s, "_ollama_window_state", None) or {}).get("markers") or []
        ctx.check(f"and the call says so in one line, got {markers}",
                  any("did not answer /api/ps within 3 s" in m for m in markers))
    finally:
        srv.shutdown()


if __name__ == "__main__":
    ctx = Ctx()
    results, passed, failed, skipped = run_all(TESTS, ctx)
    sys.exit(print_results(results, passed, failed, skipped))
