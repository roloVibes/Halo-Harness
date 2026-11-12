"""tests.test_engines_peer_key -- the host's engine offer hands a peer only the engine's own key (Halo 3.4.1.2, the
2026-11-12 review's SERVERS-8, the last review's REMOTE-9; engines/peer.py `offer`):

an engine entry of config.json whose `api_key_env` names another variable (OPENROUTER_API_KEY here, holding a fake
value) offers peers no value of it; the engine's own HALO_SECRET_<ENGINE>_API_KEY is what is offered.
Nothing is sent anywhere; the values are fakes made here.
"""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from tests.helpers.engine_home import EngineHome  # noqa: E402
from tests.helpers.runner import Ctx, new_registry, print_results, run_all  # noqa: E402

test, TESTS = new_registry()


@test
def test_servers_8_an_offer_never_carries_the_variable_an_entry_names(ctx: Ctx):
    from halo_harness.engines import peer
    from halo_harness.engines.adapter import key_env
    from halo_harness.engines.descriptors import TABLE
    engine = sorted(TABLE)[0]
    other = "OPENROUTER_API_KEY"
    fake_other, fake_own = "or-" + "fa" * 12, "own-" + "ke" * 12
    with EngineHome():
        home = Path(os.environ["BRIDGE_TEST_HOME"]) / ".halo"
        home.mkdir(parents=True, exist_ok=True)
        rows = [{"name": engine, "engine": engine, "url": "http://127.0.0.1:1919/v1", "model": "m", "lan": True,
                 "api_key_env": other}]
        (home / "config.json").write_text(json.dumps({"huggingface": {"local_servers": rows}}), encoding="utf-8")
        saved = {k: os.environ.get(k) for k in (other, key_env(engine))}
        try:
            os.environ[other] = fake_other
            os.environ.pop(key_env(engine), None)
            got = peer.offer(home).get(engine) or {}
            ctx.check(f"the offer is made, without the named variable's value, got {got.get('api_key')!r}",
                      got.get("lan") is True and got.get("api_key") != fake_other)
            os.environ[key_env(engine)] = fake_own
            got = peer.offer(home).get(engine) or {}
            ctx.check("the engine's own HALO_SECRET_<ENGINE>_API_KEY is what is offered", got.get("api_key") == fake_own)
        finally:
            for k, v in saved.items():
                os.environ.pop(k, None) if v is None else os.environ.__setitem__(k, v)


if __name__ == "__main__":
    ctx = Ctx()
    results, passed, failed, skipped = run_all(TESTS, ctx)
    sys.exit(print_results(results, passed, failed, skipped))
