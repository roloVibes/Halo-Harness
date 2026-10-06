# Contributing

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

`tests/test_invariants.py` collects the house's standing rules (no
safety/refusal wording, the network choke point, no file under
`halo_harness/` writing to the real home under test, every slash command
and CLI flag documented, the privacy scan, no test module exporting
`BRIDGE_STATE_DIR` for its whole run) as regression-guarded tests, one
`@test` per rule.

## CI

`.github/workflows/suites.yml` runs all three suites on every push to
`master` and every pull request, on both Linux and Windows, Python 3.12.
A job summary shows pass/fail for each suite at a glance without opening
a log; the full logs upload as a build artifact only when something
fails. This is now the normal way the suites get run -- the orchestrator's
manual three-platform run (the Windows build host, the Kali VM, WSL)
stays for what CI cannot do: real local models, real MCP servers, real
hardware, real terminal rendering. A suite failing in CI is the exception
that should now trigger that manual run, not the other way around.

## Releasing

`python scripts/release.py <version>` bumps
`halo_harness/__init__.py::__version__`, dates the CHANGELOG's own
`## [<version>] - unreleased` section, commits, tags, pushes, and
refreshes the local install (plus any `--remote user@host` given on the
command line). Run it with `--dry-run` first to see every step printed
with nothing executed. `tests/test_release_script.py` drives it against a
scratch git repo, never this one.
