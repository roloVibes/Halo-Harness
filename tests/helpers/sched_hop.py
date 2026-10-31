"""tests.helpers.sched_hop -- Halo 3.3.7.0 R3: the local -> local hop's fixture over tests/helpers/model_switch_rig.Rig
(tests/test_degrade.py, tests/test_escalation.py).

    bigger(rig)   the fake's `big:30b` weighs 20 GB (30B) and `mid:14b` 9 GB (14B), and big:30b has a battery profile
                  that calls tools (host "lan"): the next size up from mid:14b. The card is not read (the test flag):
                  the hop says "fit not read".
"""
from __future__ import annotations

import time


def bigger(rig) -> None:
    from halo_harness.providers.battery_probes import PROBE_SET
    from halo_harness.providers.battery_profile import finish
    from halo_harness.providers.ollama import reset_catalog_cache
    from halo_harness.providers.ollama_capability import save_profile
    from halo_harness.studio import ollama_hosts_view as V
    sizes = {"big:30b": (20_000_000_000, "30B"), "mid:14b": (9_000_000_000, "14B")}
    for m in rig.mock.tags_response["models"]:
        if m["name"] in sizes:
            m["size"], m["details"]["parameter_size"] = sizes[m["name"]]
    reset_catalog_cache()
    V.reset_cache()
    save_profile(rig.state_dir, finish({
        "model": "big:30b", "host": "lan", "digest": "sha256:m00", "ollama_version": "0.40.13", "probe_set": PROBE_SET,
        "probed_at": time.time(), "tools": "yes", "system_role": "honoured", "instruction": "strict", "output": "json",
        "identifiers": "trusted", "reasoning": "none", "window": {"trained": 65536, "used": 32768, "verified": True},
        "speed": {"tok_s": 120.0, "cold_load_s": 21.0}, "agentic_ready": True,
        "evidence": {"instruction": {"content": "OK"}}}))
