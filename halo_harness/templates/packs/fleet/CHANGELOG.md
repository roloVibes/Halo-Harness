# Changelog

## 1.0.1 (Halo 3.4.0.1)

What a real two-machine run found: a mission part is done only when its hand-back says so and its named outputs are
there (fleet/mission_outcome.py); a part's hand-back pushed to the hub carries no full local path; a member's announce
carries its own `cost_today` (finished sessions too); the hub says when Windows Firewall keeps other machines off its
port; a `halo doctor` row (doctor.py); a plan names an away member that has a need, and notes a part placed where calls
that ask are refused; `halo fleet status` names the hub by its own name; `halo fleet leave` after a kick says so; a
stale capability card says it is refreshing.

## 1.0.0 (Halo 3.4.0.0)

The fleet leaves Halo's core for this pack: the hub (`halo fleet serve`, `halo studio --fleet`), pairing and join,
members, the live table, missions (`halo fleet mission`, now also `halo mission`), the relay of a joined halo, health,
the digest, the capability catalog and "who can do this?", recall and knowledge across the fleet; `/fleet` and
`/mission`; Studio's Fleet doors. What one machine needs to reach another's models (`halo host serve`, the pool,
Local -> Hosts, Ollama on the network) and this machine's own live view (Session, Agents -> Live, attention, replay)
stayed in the core.
