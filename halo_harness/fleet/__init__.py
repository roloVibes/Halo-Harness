"""halo_harness.fleet -- the hub, the pairing, the join and the relay (Halo
3.0.5.0 "Fleet" round R2).

One machine runs a hub (`halo fleet serve`, or `halo studio --fleet` inside
Studio's process); another harness joins it with a six-word pairing code
(`halo fleet pair` on the hub, `halo fleet join <host:port> --code "..."` on
the joiner). Every session of a joined harness is then announced to the hub
and its feed is forwarded as far as that harness shares (`fleet.share`:
status | events | full), and commands from the hub are applied only as its
owner allows (`fleet.allow_control`: none | ask | all). The owner's
permission engine stays in charge of every agent; the hub never gets a tool
permission; the loopback Studio API is unchanged.

    identity.py       who this harness is (R1's fleet-id) and the fleet config keys
    protocol.py       the wire: versioned JSON docs, request signing, share filters
    pair_kex.py       the six-word code and the key agreement behind a join
    tls.py            the hub's self-signed certificate and the pinned client side
    pairing.py        the hub's codes and members (members.json, codes.json)
    store.py          the joiner's ~/.halo/fleet.json and pair keys
    hub.py            the listener (HMAC-signed HTTP + SSE, TLS when possible)
    hub_http.py       its routes; hub_join.py the join handshake
    hub_state.py      the merged view of every member; hub_links.py members and links;
                      hub_commands.py the commands sent down and their outcomes
    relay.py          the joiner's HTTP client; relay_stream.py the command stream reader
    relay_runtime.py  the relay manager remote/runtime.py calls; relay_hub.py one hub's thread
    control.py        commands from a hub, gated by fleet.allow_control
    local_view.py     this harness's own sessions and agent trees
    agent_tokens.py   each agent row's own tokens in and out, from its transcript
    table.py          `halo fleet` and `/fleet` rows; table_live.py the live terminal table
    cli.py            `halo fleet serve | pair`; cli_join.py join | leave | status;
                      cli_members.py members | kick
"""
