"""tests.test_local_view_cache -- the shared local-models view (providers/local_view_cache.py, 3.6.0.0 R14).

3.6.0.0 fix pass:
1. A background rebuild that started BEFORE forget() must not write its pre-change answer back, and the read right
   after forget() must not wait for that old build and return its answer (a model pulled or deleted while the
   revalidation ran stayed hidden or pickable for the next 20 s).
2. A stale answer is served at once only while it is young (under 2 x FRESH_S); an older one (the first read after
   an hour idle) is built again before it is shown.
3. The Local section's load / unload and a delete / copy / rename forwarded to another machine drop the view.
No network: build_local_view and the host calls are stubbed.

Run: python -m tests.test_local_view_cache
"""
from __future__ import annotations

import sys
import tempfile
import threading
import time
from pathlib import Path
from types import SimpleNamespace

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from tests.helpers.runner import Ctx, new_registry, print_results, run_all  # noqa: E402

test, TESTS = new_registry()


class _Stub:
    """build_local_view stand-in: answers the hosts as they are when the build STARTS; the next build blocks on
    `gate` when `block_next` is set (a slow revalidation)."""

    def __init__(self):
        self.hosts = ["old-model"]
        self.block_next = False
        self.gate = threading.Event()
        self.started = threading.Event()
        self.calls = 0

    def __call__(self, env=None, state_dir=None):
        self.calls += 1
        snap = list(self.hosts)
        if self.block_next:
            self.block_next = False
            self.started.set()
            self.gate.wait(5)
        return snap


def _with_stub(fn):
    from halo_harness.providers import local_models, local_view_cache as C
    saved_build, saved_fresh = local_models.build_local_view, C.FRESH_S
    stub = _Stub()
    local_models.build_local_view = stub
    C.forget()
    try:
        return fn(C, stub)
    finally:
        stub.gate.set()
        local_models.build_local_view = saved_build
        C.FRESH_S = saved_fresh
        C.forget()


@test
def test_forget_wins_over_a_rebuild_already_in_flight(ctx: Ctx):
    def body(C, stub):
        state = tempfile.mkdtemp(prefix="lvc-")
        C.FRESH_S = 0.2
        ctx.check("the first read builds", C.view({}, state) == ["old-model"])
        time.sleep(0.3)
        stub.block_next = True
        ctx.check("a stale read answers the last view at once", C.view({}, state) == ["old-model"])
        ctx.check("and starts the background rebuild", stub.started.wait(3))
        stub.hosts = ["new-model"]  # a pull finished while the rebuild was reading the hosts
        C.forget()
        t0 = time.monotonic()
        got = C.view({}, state)
        waited = time.monotonic() - t0
        ctx.check(f"the read after forget() has the new hosts, got {got}", got == ["new-model"])
        ctx.check(f"and did not wait on the old build, waited {waited:.2f}s", waited < 1.0)
        stub.gate.set()
        for th in [t for t in threading.enumerate() if t.name == "halo-local-view"]:
            th.join(5)
        C.FRESH_S = 20.0
        got = C.view({}, state)
        ctx.check(f"the old build did not write its answer back, got {got}", got == ["new-model"])
    _with_stub(body)


@test
def test_an_old_stale_view_is_built_again_before_it_is_shown(ctx: Ctx):
    def body(C, stub):
        state = tempfile.mkdtemp(prefix="lvc-")
        C.FRESH_S = 0.1
        ctx.check("the first read builds", C.view({}, state) == ["old-model"])
        stub.hosts = ["new-model"]
        time.sleep(0.1 * 2 + 0.25)  # older than 2 x FRESH_S
        got = C.view({}, state)
        ctx.check(f"a view older than 2 x FRESH_S is not served, got {got}", got == ["new-model"])
    _with_stub(body)


@test
def test_a_young_stale_view_is_still_served_at_once(ctx: Ctx):
    def body(C, stub):
        state = tempfile.mkdtemp(prefix="lvc-")
        C.FRESH_S = 0.5
        C.view({}, state)
        stub.hosts = ["new-model"]
        time.sleep(0.6)  # stale, but under 2 x FRESH_S
        ctx.check("a young stale view is the answer at once (the rebuild runs behind it)",
                  C.view({}, state) == ["old-model"])
        for th in [t for t in threading.enumerate() if t.name == "halo-local-view"]:
            th.join(5)
        ctx.check("the next read has the rebuild", C.view({}, state) == ["new-model"])
    _with_stub(body)


@test
def test_load_unload_and_forwarded_changes_drop_the_view(ctx: Ctx):
    from halo_harness.providers import local_view_cache as C
    from halo_harness.providers import ollama, ollama_load
    from halo_harness.studio import local_api, local_control_api, local_hosts_view, ollama_hosts_view
    forgot = []
    saved = (C.forget, local_api._remote, local_hosts_view.hosts, ollama.resolve_ollama_host, ollama_load.load,
             ollama_load.unload, ollama_hosts_view.reset_cache)
    via = {"v": "host"}
    C.forget = lambda: forgot.append(1)
    local_api._remote = lambda req, card, act, fields: (200, {"ok": True})
    local_hosts_view.hosts = lambda state_dir: {"hosts": [{"name": "gpu-box", "controls": {"ok": True, "via": via["v"]}}]}
    ollama.resolve_ollama_host = lambda name: SimpleNamespace(url="http://gpu-box:11434", name=name)
    ollama_load.load = lambda host, model, **kw: {"ok": True}
    ollama_load.unload = lambda host, model: {"ok": True}
    ollama_hosts_view.reset_cache = lambda: None
    try:
        req = SimpleNamespace(body={"model": "m:1", "num_ctx": 4096}, state_dir=tempfile.mkdtemp(prefix="lvc-"),
                              cwd=".", query={})
        for v in ("host", "Ollama's API"):
            via["v"] = v
            for act in ("load", "unload"):
                forgot.clear()
                code, _out = local_api.post_host_act(req, "gpu-box", act)
                ctx.check(f"{act} through {v!r} answers 200 and drops the view, got {code} {len(forgot)}",
                          code == 200 and forgot)
        req.body = {"src": "m:1", "dst": "m:2"}
        for rename in (False, True):
            forgot.clear()
            code, _out = local_control_api.post_copy(req, "gpu-box", None, {"via": "host"}, False, rename)
            ctx.check(f"a forwarded {'rename' if rename else 'copy'} drops the view, got {code} {len(forgot)}",
                      code == 200 and forgot)
    finally:
        (C.forget, local_api._remote, local_hosts_view.hosts, ollama.resolve_ollama_host, ollama_load.load,
         ollama_load.unload, ollama_hosts_view.reset_cache) = saved


if __name__ == "__main__":
    ctx = Ctx()
    results, passed, failed, skipped = run_all(TESTS, ctx)
    sys.exit(print_results(results, passed, failed, skipped))
