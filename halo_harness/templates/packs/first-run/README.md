# First run

The guided first run, as a pack (Halo 3.4.0.0; part of Halo's core from 3.1.1.0 until then): one real Orchestra run
that rehearses your lineup on your models -- a sample repo with five empty functions and their tests, the lead's plan,
the run, the report and (with the coach pack on) the coach's card -- with a card first that says what it does, the models it calls, what it
should cost, how long it takes and what it writes.

```sh
halo pack install first-run
halo pack enable first-run --grant-all     # cli:start, doctor, studio-script, studio-routes
halo start --explain                       # the card only
halo start                                 # the seven steps, Enter between each (--yes: straight through)
```

With the pack on:

- `halo start` and `/start` (its CLI verb and slash command; `/start` shows the card and how to run it);
- a row on Setup's Check page, "The guided first run" (the pack's Setup block `run`), ticked like any check;
- a **First run** panel in Studio's Agents section: the card, Run, the seven steps live, Stop. It is where "Start
  here" and Agents -> Runs' "Test this lineup" went (and Runs itself in 3.4.0.0 D: a goal run is on Live);
- one row in `halo doctor` (3.4.0.0 B2): ready to rehearse your lineup, or what is missing first (a provider, then a
  lineup of your own).

Step 6 shows the coach's card only while the coach pack is enabled (it runs `halo coach <run> --json`); with it off,
step 6 says in one line that the coach is a pack.

With it off, `halo start` and `/start` say in one line that it is a pack now and how to get it; Setup's Check page
has no row for it; nothing of it runs.

The run rehearses the active lineup (`team` in config.json), read as it is; on the Auto lineup (or none) it says why it
would say little there and offers `halo gym --quick` instead. The sample run's knowledge records stay tagged `sample`,
so a search from another project never returns them. `HALO_START_FAKE=1` runs the whole path on fake model calls.

What it needs: `cli:start` (the verb and the slash command run the pack's Python), `doctor` (its row), `studio-script` (the panel) and
`studio-routes` (the panel's routes, `/api/packs/first-run/start/...`). Its Python reaches the Orchestra engine through
`halo_harness.ext.core` (extension API 1.3, draft).
