"""tests.test_update_from_3501_docs -- 3.6.0.0 fix package update-install, pass 2: the way from 3.5.0.1 is written
down where a person looks.

At v3.5.0.1, `halo update` in a shell runs the reinstall inside the running halo (`update_cli.apply_update`), the
path that once left a Windows tool environment without `halo_harness`; nothing in 3.6.0.0 can change that code. Its
`/update` in a session hands the install to a script that runs after halo has exited. And 3.5.0.1's process scan does
not see a LAN host started by `halo host install`, on any platform. So the README, docs/INSTALL.md and
docs/MOVING-from-3.5.md each say: on Windows use `/update`, or close Halo, stop the Studio and run the repair line;
everywhere, stop the LAN host first."""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from tests.helpers.runner import Ctx, new_registry, print_results, run_all

REPO = Path(__file__).resolve().parent.parent
DOCS = ("README.md", "docs/INSTALL.md", "docs/MOVING-from-3.5.md")
REPAIR = ("uv tool install --reinstall --constraints "
          "https://raw.githubusercontent.com/roloVibes/Halo-Harness/v3.6.0.0/requirements.lock "
          "\"git+https://github.com/roloVibes/Halo-Harness@v3.6.0.0\"")

test, TESTS = new_registry()


def _block(rel: str) -> str:
    text = (REPO / rel).read_text(encoding="utf-8")
    at = text.find("From 3.5.0.1")
    return text[at:at + 2500] if at >= 0 else ""


@test
def test_each_doc_has_the_from_3501_block(ctx: Ctx):
    for rel in DOCS:
        ctx.check(f"{rel} has a 'From 3.5.0.1' block", bool(_block(rel)))


@test
def test_the_block_says_what_a_windows_user_runs(ctx: Ctx):
    for rel in DOCS:
        b = _block(rel)
        ctx.check(f"{rel}: names /update in a session", "`/update`" in b)
        ctx.check(f"{rel}: warns against `halo update` in a shell on Windows", "`halo update`" in b and "Windows" in b)
        ctx.check(f"{rel}: stops the Studio first", "halo studio --stop" in b)
        ctx.check(f"{rel}: gives the repair line pinned to the release and its lock", REPAIR in b)


@test
def test_the_block_says_to_stop_the_lan_host_on_every_platform(ctx: Ctx):
    for rel in DOCS:
        b = _block(rel)
        ctx.check(f"{rel}: `halo host stop` before the update", "halo host stop" in b and "halo host install" in b)


if __name__ == "__main__":
    ctx = Ctx()
    results, passed, failed, skipped = run_all(TESTS, ctx)
    sys.exit(print_results(results, passed, failed, skipped))
