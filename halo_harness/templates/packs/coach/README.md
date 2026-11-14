# Coach

The post-run coach, as a pack (Halo 3.4.0.0; part of Halo's core from 3.0.9.0 until then). It reads a finished run's
files -- an Orchestra run -- and suggests what to change next time: a bio's prompt, model or tools, a
lane's `after`, a gate that looped. Each card shows its evidence; Ask has the run's lead explain it in one paragraph,
Apply writes the change after one confirm (the file and its diff first) and Undo puts the file back. A probe runs the
goal again under two candidate overlays and keeps what beat the run; every Apply leaves an entry in the improvement
library, which later cards cite. `/improve` drafts memory and rule candidates from your recent sessions.

```sh
halo pack install coach
halo pack enable coach --grant-all     # cli:coach, cli:improve, doctor, studio-script, studio-routes
halo coach                             # the latest run's card (a folder, an id or a prefix picks another)
halo orchestra coach --apply <id>      # the confirm card, then y/N
halo coach --undo                      # put back the last apply
halo coach library list                # the improvement library
halo improve                           # draft candidates; halo improve --apply FILE#ID writes one
```

With the pack on:

- `halo coach`, `halo improve`, `/coach`, `/improve` (its verbs and slash commands); `halo orchestra coach` hands over to
  `halo coach`;
- a **Coach** panel in Studio's Agents section: pick a run, its cards, Ask, Apply (confirm first), Undo, Probe;
- its rows in Studio's Settings under "From packs" (`packs.settings.coach.<key>`: probe.k, probe.budget_factor,
  library.cite, improve.enabled, improve.model, improve.since_days, improve.max_candidates) and in `halo config
  get/set`;
- one row in `halo doctor` (what the coach keeps, the model /improve drafts with, or the grant its panel waits for);

With it off, `halo coach`, `halo improve`, `/coach` and `/improve` say in one line that the coach is a pack now and how
to get it; there is no Coach panel, no Settings row and no doctor row, and the guided first run's step 6 says the same
line. The keys `coach.*` and `improve.*` Halo read until 3.4.0.0 are ignored (`halo doctor --config` says so once);
set the pack's own keys instead. The coach's files stay where they were (`~/.halo/coach/`).

What changed with the move: the TUI's `/improve` card review and its once-a-session hint left (the pack's `/improve`
prints what `halo improve` prints), and Studio's Coach panel writes a card's change itself after the confirm instead of
staging it in the bio form or the plan canvas. The supervisor, replanning and verified outcomes stay in Halo's core;
the pack reads outcomes through `halo_harness.ext.core` (`outcomes.records`).
