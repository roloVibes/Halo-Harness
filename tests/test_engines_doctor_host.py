"""tests.test_engines_doctor_host -- Halo 3.3.13.0 R1 deliverable 3 (doctor, host, placement, bench):

1. `halo doctor --local`'s line per engine found here (halo_harness/engines/doctor.py): none for a user with none of
   them; one OK line per configured engine with its --version; the old `huggingface.<id>_bin` word said with the new
   one; a program that does not answer: a WARN with the owner's install line;
2. the host (host/routes_view.catalog's `engines`, engines/peer.py): over tests/helpers/host_act_rig.PeerRig the host's
   machine runs an engine server (a Server row, no process) whose entry Halo wrote for `--lan`; the join lists it, the
   catalog offers it with its key under `engines`, a peer resolves `hf:local/<model>@<the host's name>` to it at the
   host's address; a loopback-only server is not offered; every address a 192.0.2.x placeholder or 127.0.0.1;
3. placement: the host's engine server is a candidate (engines/peer.EngineHost, the host flag `engine`): the model it
   serves is warm, another model the engine names is a restart with its loading tax, any other model is out;
4. `halo local bench --host freetoken --yes --quick` through the OpenAI-compatible route of the fake: the cost line
   first, a speed card of runtime freetoken, kept under the model's own id too, which the fit then says as measured.
Run: python -m tests.test_engines_doctor_host
"""
from __future__ import annotations

import contextlib
import io
import json
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from tests.helpers.engine_home import FAKE, EngineHome  # noqa: E402
from tests.helpers.runner import Ctx, new_registry, print_results, run_all  # noqa: E402

test, TESTS = new_registry()
MODEL, KEY_ENV = "qwen3.6-35b-a3b", "HALO_SECRET_FREETOKEN_API_KEY"


def _local(*argv) -> "tuple[int, str]":
    from halo_harness.local_cli import cmd_local
    out = io.StringIO()
    with contextlib.redirect_stdout(out), contextlib.redirect_stderr(out):
        code = cmd_local(list(argv))
    return code, out.getvalue()


@test
def test_the_doctor_line_per_engine_found(ctx: Ctx):
    from halo_harness.engines import adapter
    from halo_harness.engines.doctor import steps
    with EngineHome() as h:
        rows = steps(h.state)
        ctx.check(f"one OK line per configured engine, got {rows}", [r["step"] for r in rows] == [
            "engine freetoken", "engine strata", "engine tensorfold"] and not any(r.get("tag") for r in rows)
                  and "FreeToken: ft --version 0.0.0+gfake (huggingface.engine_bins.freetoken)" in rows[0]["reason"]
                  and "unverified until a live run" in rows[0]["reason"])
        adapter.SEAMS["which"] = lambda name: None
        h.set_hf(engine_bins={})
        ctx.check("none found: no line", steps(h.state) == [])
        h.set_hf(strata_bin=[sys.executable, str(FAKE), "strata"])
        rows = steps(h.state)
        ctx.check(f"the old word, said with the new one, got {rows}", len(rows) == 1 and rows[0]["tag"] == "WARN"
                  and "huggingface.strata_bin is the old word: it is read as huggingface.engine_bins.strata" in rows[0]["reason"])
        h.set_hf(strata_bin=None, engine_bins={"tensorfold": [sys.executable, "-c", "pass"]})
        rows = steps(h.state)
        ctx.check(f"a silent program: the install line, got {rows}", len(rows) == 1 and rows[0]["tag"] == "WARN"
                  and "did not answer --version: the release archive" in rows[0]["reason"])


class Rig:
    def __init__(self, lan: bool = True) -> None:
        self.lan = lan

    def __enter__(self):
        from halo_harness.engines import peer
        from halo_harness.ollama_steward.servers_hf import Server
        from tests.helpers.host_act_rig import PeerRig
        self._key = os.environ.get(KEY_ENV)
        os.environ[KEY_ENV] = "fixture-engine-key"
        self.srv = Server(name="freetoken", url="http://127.0.0.1:19190", runtime="freetoken", model=MODEL)
        self.peer = PeerRig(servers=[self.srv]).__enter__()
        cfg = Path(self.peer.home) / "config.json"
        data = json.loads(cfg.read_text(encoding="utf-8"))
        data.setdefault("huggingface", {})["local_servers"] = [
            {"name": "freetoken", "url": "http://127.0.0.1:19190/v1", "runtime": "freetoken", "model": MODEL,
             "engine": "freetoken", "lan": self.lan, "api_key_env": KEY_ENV}]
        cfg.write_text(json.dumps(data), encoding="utf-8")
        peer.reset()
        return self

    def __exit__(self, *exc):
        from halo_harness.engines import peer
        peer.reset()
        try:
            self.peer.__exit__(*exc)
        finally:
            if self._key is None:
                os.environ.pop(KEY_ENV, None)
            else:
                os.environ[KEY_ENV] = self._key


def _client():
    from halo_harness.fleet import identity, store
    from halo_harness.ollama_steward.host_client import HostClient
    e = store.hosts()[-1]
    return HostClient(e, store.key_for(e), identity.harness()["id"])


@test
def test_the_hosts_engines_offer_reaches_a_peer(ctx: Ctx):
    from halo_harness.providers.huggingface import resolve_huggingface_local_server
    with Rig() as r:
        rows = r.peer.entry.get("servers") or []
        row = next((x for x in rows if x.get("runtime") == "freetoken"), {})
        ctx.check(f"the join lists it with its model, got {rows}", row.get("kind") == "server" and row.get("model") == MODEL)
        got = _client().catalog(4096).get("engines") or {}
        ctx.check(f"the catalog's engines offer it with its key, got {got}", got.get("freetoken", {}).get("api_key") ==
                  "fixture-engine-key" and got["freetoken"]["url"] == "http://127.0.0.1:19190/v1")
        name = r.peer.entry["name"]
        s = resolve_huggingface_local_server(name)
        ctx.check(f"hf:local/{MODEL}@{name} resolves through the host, got {s}", s is not None and s.runtime == "freetoken"
                  and s.url == "http://127.0.0.1:19190/v1" and s.api_key == "fixture-engine-key")
        ctx.check("a name no entry and no host has stays unresolved", resolve_huggingface_local_server("nobody") is None)
    with Rig(lan=False):
        ctx.check("a loopback-only server is not offered", (_client().catalog(4096).get("engines") or {}) == {})


@test
def test_placement_sees_the_engine_server(ctx: Ctx):
    from halo_harness.engines.peer import EngineHost, hosts
    from halo_harness.local_sched import place
    from halo_harness.local_sched.place_advice import candidates, tax
    with Rig() as r:
        name = r.peer.entry["name"]
        h = next((x for x in hosts() if x.name == name), None)
        ctx.check(f"the host's engine server is a candidate, got {hosts()}", h is not None and h.engine == "freetoken"
                  and not h.local and any(isinstance(x, EngineHost) for x in candidates()))
        warm = place.answer(h, {"lane": "worker", "model": f"hf:local/{MODEL}@{name}"})
        ctx.check(f"the model it serves: warm, got {warm}", warm["warm"] and warm["fits"] is True
                  and warm["via"] == "freetoken" and tax(warm) == "warm: no load")
        other = place.answer(h, {"lane": "worker", "model": "gpt-oss-120b"})
        ctx.check(f"another model it names: the restart and its tax, got {tax(other)!r}", other["fits"] is None
                  and tax(other).startswith("a restart onto gpt-oss-120b, ~40 s reading it from disk")
                  and "kernel compile" in tax(other) and tax(other).endswith(f"evicts {MODEL}"))
        out = place.answer(h, {"lane": "worker", "model": "qwen3.8:27b"})
        ctx.check(f"any other model is out, got {out['verdict']!r}", out["fits"] is False
                  and "FreeToken serves the models its docs name" in out["verdict"])


@test
def test_the_bench_through_the_openai_route(ctx: Ctx):
    from halo_harness.engines.bench import speed_word
    with EngineHome() as h:
        code, _out = _local("serve", "--runtime", "freetoken", "--model", str(h.checkpoint()))
        code, out = _local("bench", "--host", "freetoken", "--yes", "--quick")
        lines = out.strip().splitlines()
        ctx.check(f"the cost line first, then the card, got {code} {out!r}", code == 0 and lines[0].startswith(
            "local: ~") and "no tokens leave this machine" in lines[0] and "speed card:" in out)
        from halo_harness.providers.local_bench_runs import all_cards
        cards = [c for c in all_cards(h.state) if c.get("runtime") == "freetoken"]
        ctx.check(f"cards of runtime freetoken, under the served name and the model's id, got "
                  f"{[c.get('digest') for c in cards]}", {c["digest"] for c in cards} == {
                      "freetoken|Qwen3.6-35B-A3B-NVFP4", "freetoken|nvidia/Qwen3.6-35B-A3B-NVFP4"})
        word = speed_word(h.state, "freetoken", "nvidia/Qwen3.6-35B-A3B-NVFP4", "freetoken")
        ctx.check(f"the fit's speed word is measured, got {word!r}", word and word.endswith("tok/s measured"))


if __name__ == "__main__":
    ctx = Ctx()
    results, passed, failed, skipped = run_all(TESTS, ctx)
    sys.exit(print_results(results, passed, failed, skipped))
