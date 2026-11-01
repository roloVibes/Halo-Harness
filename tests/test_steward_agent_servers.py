"""tests.test_steward_agent_servers -- Halo 3.3.8.0 R2: the steward's fix loop for a local server (llama-server, LM
Studio, mlx_lm.server): agent_proposals checks and lands a `<server>|<model>` change under the server's window per
slot and the next hf:local call reads it (providers/hf_profile.py); the steward job's tick reads every local server's
log and its pass names the server. Fixture logs (tests/helpers/servers_seed.py); no server runs, no model is called.
Run: python -m tests.test_steward_agent_servers
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from tests.helpers.provider_env_defaults import ensure_default_provider_credentials  # noqa: E402
ensure_default_provider_credentials()

from tests.helpers.runner import Ctx, new_registry, print_results, run_all  # noqa: E402

test, TESTS = new_registry()


@test
def test_a_proposal_for_a_local_server_lands_in_its_profile_and_the_call_reads_it(ctx: Ctx):
    """3.3.8.0 R2: agent_proposals checks and lands a `<server>|<model>` change under the server's window per slot;
    the next hf:local call reads it (providers/hf_profile.py): the window, the reply's room, the tool budget."""
    from types import SimpleNamespace
    from halo_harness.ollama_steward.agent_proposals import land
    from halo_harness.ollama_steward.profiles import all_profiles
    from halo_harness.ollama_steward.rules import gather
    from halo_harness.ollama_steward.server_log_hf import scan
    from halo_harness.providers import hf_profile
    from tests.helpers.servers_seed import Home as ServersHome, hf_line
    with ServersHome(lms=False, mlx=False, pid=None) as h:
        scan(h.state, h.server("llama-8080"), from_start=True, root=h.root)
        h.calls(*[hf_line(prompt_eval_count=7800) for _ in range(5)])
        c = gather(h.state, cards={}, catalogs={})
        said: list = []
        got = land(h.state, [{"key": "llama-8080|qwen3-8b", "field": "num_ctx", "to": 16384, "why": "more"},
                             {"key": "llama-8080|qwen3-8b", "field": "num_ctx", "to": 8192, "why": "the server's"},
                             {"key": "llama-8080|qwen3-8b", "field": "tools_max", "to": 8, "why": "fewer tools"}],
                   c, mode_name="auto", say=said.append)
        kinds = [(o["kind"], o.get("reason", "")[:60]) for o in got]
        ctx.check(f"above the server's window: dropped; at it: applied, got {kinds}", got[0]["kind"] == "dropped"
                  and "the measured cap (8192)" in got[0]["reason"] and got[1]["kind"] == "apply")
        prof = all_profiles().get("llama-8080|qwen3-8b") or {}
        ctx.check(f"the server's profile, got {prof}", prof.get("num_ctx") == 8192 and prof.get("by") == "steward")
        ref = SimpleNamespace(provider="huggingface", local=True, mlx=False, host=None, model="qwen3-8b")
        ctx.check("the call's window is the profile's", hf_profile.window(ref, 16384) == 8192
                  and hf_profile.window(ref, 4096) == 4096 and hf_profile.window(ref, None) == 8192)
        from halo_harness.ollama_steward.profiles import set_field
        set_field("llama-8080|qwen3-8b", "num_predict", 2048)
        sess = SimpleNamespace(model_ref=ref, state_dir=h.state)
        ctx.check("the reply's room from num_predict", hf_profile.reply_budget(sess, 512) == 2048
                  and hf_profile.reply_budget(sess, 4096) == 4096)
        ctx.check("a named ref reads its own server only", hf_profile.profile_for_ref(
            SimpleNamespace(provider="huggingface", local=True, host="other", model="qwen3-8b")) == {})


@test
def test_the_job_watches_the_local_servers_beside_the_hosts(ctx: Ctx):
    """3.3.8.0 R2: each tick reads every local server's log (server_log_hf.tail_servers); a warning wakes the pass,
    and the pass's findings name the server."""
    from halo_harness.ollama_steward.job import StewardJob
    from tests.helpers.servers_seed import Home as ServersHome, hf_line
    with ServersHome(lms=False, mlx=False, pid=None) as h:
        h.calls(*[hf_line(prompt_eval_count=7800, ago=60) for _ in range(5)])
        job = StewardJob(h.state, readers={"card_reader": None, "catalog_reader": None, "cards": {}, "catalogs": {}},
                         watch=lambda *a, **k: None, model=(None, "no model in this test"))
        job.tick()
        ctx.check(f"the server's warnings woke the pass, got notify={job.notify}", job.last_run is not None)
        from halo_harness.ollama_steward import notes
        said = [n.get("say") or "" for n in notes.read(h.state, stage="finding")]
        ctx.check(f"a finding names the server, got {said[:3]}", any("llama-8080" in x and "window-small" in x for x in said))


if __name__ == "__main__":
    ctx = Ctx()
    results, passed, failed, skipped = run_all(TESTS, ctx)
    sys.exit(print_results(results, passed, failed, skipped))
