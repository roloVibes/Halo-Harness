"""halo_harness.isolation -- opt-in isolation for workers (Halo 3.1.8.0 R5, docs/ISOLATION.md).

Nothing changes by default. A lineup or a bio may declare three opt-ins:

- `isolation: container | user` -- its Orchestra workers run inside a
  per-run container (`container.py`, the image from `Dockerfile`) or as a
  scoped OS user (`scoped_user.py`), the same worktree inside, on a scoped
  state dir (`seed.py`);
- `secrets: {broker: 1password | env}` -- a bio's `environment.secrets`
  refs are read at spawn (`secrets.py`, `brokers/`) into the worker's
  environment only;
- `tools.capabilities` -- an agent sees only the tools of the listed
  capabilities (`capabilities.py`, one table).

`spec.py` reads the declarations, `lane.py` applies them where a worker
starts (orchestra/adapters.py `spawn_worker`), `lines.py` writes the report
lines, `declared.py` lists what your lineups and bios declare,
`doctor_rows.py` the two doctor rows, `cli.py` `halo isolation`,
`tools_view.py` `/tools`. A worker that cannot run as declared stops with
one factual line (`Stop`), like a worker whose harness would not start.
"""

from __future__ import annotations


class Stop(RuntimeError):
    """The one line a lane stops with (no docker here, no `op`, no scoped user on Windows, a ref not read)."""
