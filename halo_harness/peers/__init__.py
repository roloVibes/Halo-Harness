"""halo_harness.peers -- one machine reaching another (Halo 3.4.0.0 C: out of halo_harness/fleet/ when the fleet left
the core for the shipped `fleet` pack).

Who this harness is (identity.py), the joiner's files (store.py: fleet.json, the pair keys), the signed wire
(protocol.py), TLS and its pin (tls.py), pairing codes and the key exchange (pairing.py, pair_kex.py, hub_join.py),
the relay client (relay.py, relay_stream.py), halo hosts (hub_hosts.py, hub_host_cmd.py), Ollama on the network
(ollama_share*.py, control_models.py, control_pulls.py, control_probes.py), this harness's own sessions
(local_view.py, agent_tokens.py), this machine's hardware (capabilities_host.py), the capability cache (catalog.py)
and three helpers (net.py). `halo host serve`, the pool, Local -> Hosts and the steward use them with the pack off;
the fleet pack (hub, members, missions) builds on them.
"""
