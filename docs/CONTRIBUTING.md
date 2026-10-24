# Contributing

Read this when you send a change to Halo: the house rules and which suite to run.

## Running the suites

Halo Harness has three test suites, run from the repo root with
`PYTHONPATH` set to the repo:

    export PYTHONPATH=.
    python test_bridge.py
    python tests/run_all.py
    python test_tui.py

Every test scopes its own state under `BRIDGE_TEST_HOME`/`BRIDGE_STATE_DIR`
(never the real `~/.halo`), and nothing in any suite opens a real network
connection -- `halo_harness/providers/http.py`'s `open_upstream`/
`urlopen_tls` is the one choke point every real network call goes
through (see `tests/test_offline_mode.py`), and `tests/run_all.py` sets
`BRIDGE_TEST_NO_BACKGROUND_NET=1` for the whole run either way.

### The two tiers of tests/run_all.py

    python tests/run_all.py --fast        # the fast tier: no Chrome, no TUI pilots
    python tests/run_all.py --tier full   # only the full tier: the Chrome and TUI pilot modules
    python tests/run_all.py               # everything (what CI runs)

A module that needs headless Chrome or a Textual pilot (`app.run_test`)
says so near the top of its file, right after its imports start:

    TIER = "full"  # headless Chrome: the full tier

Every other module is in the fast tier. run_all reads the line with a regex
over the first 16 KB of the file, never by importing the module, and
prints which tier ran. Which to run when:

- while you work: the modules you touched (`python -m tests.test_x`), then
  `python tests/run_all.py --fast` before you hand a change back;
- a change to a Chrome driver, a Studio page or a TUI screen: the modules
  it touches plus `--tier full`;
- a change to the suite itself (run_all, the runner, the helpers every
  module uses), a fix pass before a tag, a release round: the whole run.

On the Windows build host (3.1.0.0 R1) the fast tier took about 40 min
(472 modules; ten of those minutes are one governor test that waits on a
socket timeout there), the full tier 5 min (39 modules) and the whole run
45 min (511 modules).

Each module runs with its OWN fresh `BRIDGE_TEST_HOME` (a directory named
after the module under the run's scratch root, removed after the module),
and the module-level caches that key on the state dir are reset between
modules (`tests/helpers/run_all_support.py` lists them). A module never sees
another module's catalog, config or sessions, so a test needs no seeding
"in case another module left something". The real-home guards at the end of
the run are unchanged.

### Chrome drivers

Every headless Chrome driver (`tests/helpers/studio_*.py`, the renders in
`tools/capture_*.py`) stands on one base, `tests/helpers/chrome_driver.py`:
`Driver` scopes the home first thing (`ensure_scoped_state_dir_once`, so a
driver started with `BRIDGE_*` scrubbed never reaches the real `~/.halo`),
`find_chrome()` reads `HALO_CHROME` first, and `run(steps)` runs each step,
records the first one that raises as `failed` and prints the JSON line the
test reads. Exactly one headless Chrome runs at a time: `cdp.Chrome` and
the one-shot `--dump-dom`/`--screenshot` renders hold a file lock under
`<temp>/halo-tests/` (`tests/helpers/chrome_lock.py`), across threads and
processes. A new driver subclasses `Driver` and implements `session(c)`,
which seeds and serves what the steps need and yields the steps;
`python -m tests.helpers.chrome_driver smoke` is the smallest one.
`tests/test_studio_ui.py`'s `_json_of` runs each driver once per argument
list and the tests read that one run.

`tests/test_invariants.py` collects the house's standing rules (no
safety/refusal wording, the network choke point, no file under
`halo_harness/` writing to the real home under test, every slash command
and CLI flag documented, the privacy scan, no test module exporting
`BRIDGE_STATE_DIR` for its whole run) as regression-guarded tests, one
`@test` per rule.

## CI

`.github/workflows/suites.yml` runs all three suites (the whole run of
`tests/run_all.py`, both tiers), Python 3.12:

- **Linux** on every push to `master` and every pull request;
- **Windows** on a version tag (`v*`), nightly at 09:00 UTC, and on
  `workflow_dispatch` with the sha to test
  (`gh workflow run suites.yml -f sha=<sha>`; the run is titled
  "suites windows leg for <sha>");
- the `studio-ui` job (the React build and its drift gate) on every push
  and pull request.

A job summary names the platform, the tier and the sha and shows
pass/fail for each suite at a glance without opening a log; the full logs
upload as a build artifact only when something fails. This is now the normal way the suites get run -- the orchestrator's
manual three-platform run (the Windows build host, the Kali VM, WSL)
stays for what CI cannot do: real local models, real MCP servers, real
hardware, real terminal rendering. A suite failing in CI is the exception
that should now trigger that manual run, not the other way around.

## Releasing

`python scripts/release.py <version>` bumps
`halo_harness/__init__.py::__version__`, sets the shipped reference pack's
`halo: {min: "<major.minor>"}` to the release it ships in, dates the CHANGELOG's own
`## [<version>] - unreleased` section, commits, tags, pushes, and
refreshes the local install (plus any `--remote user@host` given on the
command line). Run it with `--dry-run` first to see every step printed
with nothing executed.

Step 0 (`scripts/release_gate.py`) runs before anything is written (just
after the read-only clean-tree check): the latest Linux suites run for
HEAD's sha must have concluded `success`; then the script dispatches the
Windows suites for that sha, waits for the run (up to 90 minutes) and goes
on only when it concluded `success` too, printing both run ids. With a
green Windows run for the sha already in hand (a dispatch of your own, a
tag or nightly run of that sha), `--skip-windows` accepts it instead of
dispatching another and prints the ids it accepted. The gate needs the
`gh` CLI, logged in. `tests/test_release_ci_gate.py` drives the gate over a
fake `gh`. `tests/test_release_script.py` drives it against a
scratch git repo, never this one.
