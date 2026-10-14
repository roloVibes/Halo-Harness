"""halo_harness.orchestra -- the Orchestra (Halo 3.0.3.0): several agents
editing the same files at the same time without losing a change.

Code decides wherever it can (claims, merge order, tests, the gate); a model
judges only when it must (writing the functions, resolving a merge conflict).
This package is the code-decides foundation:

* `workflow` -- the fixed graph as data (goal -> lead -> split -> workers ->
  merge -> test -> gate -> done, with the gate's loop back to a worker);
* `goal`     -- goal.json (WHAT YOU WANT / DONE WHEN / STOP WHEN) and the
  run folder `<repo>/.halo/orchestra/<run-id>/`;
* `index`    -- the claimable units of a file (functions, classes, headings);
* `claims`   -- the append-only claim log with its fold and its lock;
* `guard`    -- the PermissionEngine hook that checks Write/Edit against claims;
* `events`   -- the timed run log, mirrored into the session feed.

See docs/ORCHESTRA.md.
"""

RUN_ENV = "HALO_ORCHESTRA_RUN"
