"""tests.test_studio_cards -- Halo 3.3.6.0 R4, the measured card, the dialect record and the shelf on Local ->
Models in headless Chrome through tests/helpers/studio_cards.py (skipped without one), over R1's seeded home (`box` a
fake Ollama on 127.0.0.1:0); no provider request, no model call:

1. a row's speed chip from its measured calls; an idle model's shelf hint;
2. the unfolded card's Measured block and "How Halo talks to this model", each field with its `from`; an edit where
   it stands is marked yours and stored at ollama.profiles["box|<model>"]["dialect"]; "back" undoes it;
3. Retire from the actions menu: the delete on the fake, then the model on the folded Shelf with Re-pull.
Run: python -m tests.test_studio_cards
"""
from __future__ import annotations

TIER = "full"  # headless Chrome: the full tier

import json
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from tests.helpers.runner import Ctx, SkipTest, new_registry, print_results, run_all  # noqa: E402

test, TESTS = new_registry()
REPO = Path(__file__).resolve().parent.parent
_RUN: dict = {}


def _got(ctx: Ctx) -> dict:
    from tests.helpers.chrome_driver import driver_env, find_chrome
    if not find_chrome():
        raise SkipTest("no Chrome found (the card checks need headless Chrome)")
    if "r" not in _RUN:
        r = subprocess.run([sys.executable, "-m", "tests.helpers.studio_cards"], capture_output=True, encoding="utf-8",
                           errors="replace", timeout=480, env=driver_env(REPO), cwd=str(REPO), stdin=subprocess.DEVNULL)
        try:
            info = json.loads(r.stdout.strip().splitlines()[-1])
        except (ValueError, IndexError):
            info = {}
        _RUN["r"] = (r, info)
    r, info = _RUN["r"]
    if info.get("skip"):
        raise SkipTest(info["skip"])
    ctx.check(f"the driver ran, got {r.returncode} {info.get('failed')!r} {r.stderr[-800:]!r}", r.returncode == 0 and "failed" not in info)
    return info


@test
def test_the_speed_chip_and_the_shelf_hint(ctx: Ctx):
    got = _got(ctx)
    ctx.check(f"the measured speed chip, got {got.get('speed')!r}", str(got.get("speed")).endswith("tok/s"))
    ctx.check(f"an idle model's hint, got {got.get('hints')}", any(str(h).startswith(("never used", "not used in"))
                                                                  for h in got.get("hints") or []))


@test
def test_the_measured_block_and_the_dialect_edit(ctx: Ctx):
    got = _got(ctx)
    ctx.check(f"the Measured and dialect blocks, got {got.get('blocks')}", {"measured", "dialect"} <= set(got.get("blocks") or []))
    ctx.check(f"a measured line with its source, got {got.get('measured')}", any("tok/s (the ledger" in x for x in got.get("measured") or []))
    fields = dict(got.get("fields") or [])
    ctx.check(f"every field with its from, got {fields}", len(fields) == 8 and all(fields.values()))
    ctx.check(f"the edit is yours and said, got {got.get('edited')!r}", "--set reply_reserve=4096" in str(got.get("edited")))
    stored = got.get("stored") or {}
    ctx.check(f"stored in the profile, got {stored}", stored.get("reply_reserve") == 4096
              and (stored.get("from") or {}).get("reply_reserve") == "user")
    ctx.check(f"back undoes it, got {got.get('after_back')}", got.get("after_back") in ("battery", "default"))


@test
def test_retire_and_the_shelf(ctx: Ctx):
    got = _got(ctx)
    ctx.check(f"Retire's card, got {got.get('retire_label')!r}", str(got.get("retire_label")).startswith("Retire"))
    ctx.check(f"the delete on the fake, got {got.get('deleted')} {got.get('retired_said')!r}", got.get("deleted") == ["nomic-embed-text"]
              and "retired nomic-embed-text from box" in str(got.get("retired_said")))
    ctx.check(f"the model on the Shelf with Re-pull, got {got.get('shelf')}", got.get("shelf") == ["box", True])


if __name__ == "__main__":
    ctx = Ctx()
    results, passed, failed, skipped = run_all(TESTS, ctx)
    sys.exit(print_results(results, passed, failed, skipped))
