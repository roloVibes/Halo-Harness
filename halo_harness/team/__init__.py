"""halo_harness.team -- a Team (Halo 3.0.8.0): people, blocks and stages.

A team file (`<repo>/.halo/team.yaml`, else `~/.halo/teams/<project>.team.yaml`)
names the brief every agent reads first, the members (an instance of a
lineup alias, here or on a fleet member), the blocks the work lands in
(a file, a folder or a git tree, each with its own claim ledger) and the
workflow's stages (an agent stage, an Orchestra run or a flow), each with
what it reads and writes, what starts it and whether a human answers its
gate before the next one starts.

* `spec`     -- find, load, normalise and validate the team file;
* `blocks`   -- the block ledgers `<block>/.halo-block/{claims,changes,state}`;
* `guard`    -- the PermissionEngine hook that keeps a stage's writes inside
  its blocks and its member's claims;
* `board`    -- the run ledger `<repo>/.halo/team/<run-id>/` (board.json,
  events.jsonl, stages/<id>/);
* `stages`   -- one stage's prompt, its gate and its acceptance;
* `triggers` -- manual, `block_change:<block>` (a settle window) and
  `stage_done:<stage>`;
* `run`      -- the runner and its seams (SPAWN, ORCHESTRA, FLOW, DISPATCH);
* `cli`      -- `halo team ...`.

See docs/TEAM.md.
"""

SCOPE_ENV = "HALO_TEAM_SCOPE"
LEDGER_DIR = ".halo-block"
RUNS_DIR = (".halo", "team")
