"""tests.test_workflow_inputs -- no value someone outside the repo's writers can choose is pasted into a CI shell script
(Halo 3.4.1.2, the 2026-11-12 review's PACKS-9; .github/workflows/*.yml):

a `run:` script never holds `${{ inputs.* }}`, `${{ github.event.* }}` or `${{ github.head_ref }}`: such a value
reaches the step through `env:` and the script reads the variable (`"$SHA"`), so a dispatch input or a pull request's
title is data, never script.
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from tests.helpers.runner import Ctx, new_registry, print_results, run_all  # noqa: E402

test, TESTS = new_registry()
WORKFLOWS = Path(__file__).resolve().parent.parent / ".github" / "workflows"
CHOSEN = re.compile(r"\$\{\{[^}]*\b(inputs\.|github\.event\.|github\.head_ref)")


def run_lines(text: str) -> "list[tuple[int, str]]":
    """(line number, text) of every line of every `run:` script (inline or a block)."""
    out, block = [], None
    for n, line in enumerate(text.splitlines(), 1):
        indent = len(line) - len(line.lstrip())
        if block is not None:
            if line.strip() and indent <= block:
                block = None
            else:
                out.append((n, line))
                continue
        m = re.match(r"^(\s*)(-\s+)?run:\s*(.*)$", line)
        if m:
            rest = m.group(3)
            if rest.startswith(("|", ">")):
                block = len(m.group(1)) + (len(m.group(2)) if m.group(2) else 0)
            else:
                out.append((n, line))
    return out


@test
def test_packs_9_no_chosen_value_is_pasted_into_a_run_script(ctx: Ctx):
    files = sorted(WORKFLOWS.glob("*.yml")) + sorted(WORKFLOWS.glob("*.yaml"))
    ctx.check(f"the workflows are read, got {[f.name for f in files]}", bool(files))
    bad = [f"{f.name}:{n}: {line.strip()[:120]}" for f in files for n, line in run_lines(f.read_text(encoding="utf-8"))
           if CHOSEN.search(line)]
    ctx.check("these run: lines paste a chosen value (pass it through env: instead):\n  " + "\n  ".join(bad), not bad)
    sample = 'jobs:\n  x:\n    steps:\n      - run: |\n          echo "${{ inputs.sha }}"\n      - name: y\n        run: echo ok\n'
    ctx.check("the scan sees a block script", any(CHOSEN.search(line) for _n, line in run_lines(sample)))


if __name__ == "__main__":
    ctx = Ctx()
    results, passed, failed, skipped = run_all(TESTS, ctx)
    sys.exit(print_results(results, passed, failed, skipped))
