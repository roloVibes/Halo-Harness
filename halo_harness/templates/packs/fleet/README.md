# Fleet

Several halos joined to one hub, as a pack (Halo 3.4.0.0; part of Halo's core from 3.0.5.0 until then).

```sh
halo pack install fleet
halo pack enable fleet --grant-all     # cli:fleet, cli:mission
halo studio --fleet                    # the hub inside Studio (or: halo fleet serve)
halo fleet pair                        # a six-word code for another machine
halo fleet join <host:port> --code "..."   # on the other machine (it needs the pack on too)
halo mission new "<goal>"              # one goal split across every halo (= halo fleet mission new)
```

With the pack on:

- `halo fleet ...` and `halo mission ...`, `/fleet` and `/mission` (docs/COMMANDS-fleet.md);
- in Studio, the Fleet fold in Agents -> Live (every machine, its sessions and agents), the Fleet Tree panel, the hub,
  pairing, health, the digest, capabilities and who, missions, recall across the fleet (docs/STUDIO-fleet.md);
- a joined halo relays its sessions to the hub, and the hub's commands reach them as each owner allows
  (`fleet.allow_control`).

With it off, `halo fleet`, `halo mission`, `/fleet`, `/mission` and `halo studio --fleet` say in one line that the
fleet is a pack now and how to turn it on; Studio shows no Fleet door; Settings shows no hub or mission key; nothing
relays and no hub runs. What stays in the core either way: `halo host serve`, the pool, Local -> Hosts and Ollama on
the network (another machine's models), Session and Agents -> Live for this machine's own sessions, the attention
queue, the caps, recording and replay.

A halo that had fleet state before 3.4.0.0 (a joined hub in `~/.halo/fleet.json`, a hub's `~/.halo/fleet/hub/`,
missions) gets this pack enabled on its first run after the update, with one line that says so; nothing is deleted.

Its Python reaches the core through `halo_harness.ext.core` (peers/: identity, the signed wire, pairing, TLS, the
relay client; live/: attention, caps, the journal; the session's control socket). The docs: docs/FLEET.md,
docs/MISSIONS.md, docs/COMMANDS-fleet.md, docs/STUDIO-fleet.md in Halo's repo.
