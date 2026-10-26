"""tests.test_ollama_tune_wizard -- Halo 3.2.3.0 R3: the wizard's calibrate
offer ends with "make tuned twins of the models that fit? (Enter / n)". A
pilot of `CalibrateOffer` with `measure_hosts` and `make_twins` stubbed:
Enter runs the measuring, the question appears when a model fits, Enter
makes the twins (one line each), n skips them; no question when nothing
fits. No server is asked at all.
"""
from __future__ import annotations

TIER = "full"  # a TUI pilot (Textual run_test): the full tier

import asyncio
import os
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from tests.helpers.runner import Ctx, new_registry, print_results, run_all

test, TESTS = new_registry()

QUESTION = "make tuned twins of the models that fit? (Enter / n)"
_ENV_NAMES = ("BRIDGE_TEST_HOME", "BRIDGE_STATE_DIR", "BRIDGE_TEST_NO_BACKGROUND_NET")


class _Stubs:
    def __init__(self, outcome: str = "fits"):
        self.outcome, self.made = outcome, []

    def __enter__(self):
        from halo_harness.providers import ollama_discover_measure, ollama_tune_offer
        self._saved = {k: os.environ.get(k) for k in _ENV_NAMES}
        d = Path(tempfile.mkdtemp(prefix="ol-tune-wizard-"))
        os.environ.update({"BRIDGE_TEST_HOME": str(d), "BRIDGE_STATE_DIR": str(d / ".halo"),
                           "BRIDGE_TEST_NO_BACKGROUND_NET": "1"})
        self._measure, self._make = ollama_discover_measure.measure_hosts, ollama_tune_offer.make_twins

        def _measure(names, *, models_by_host=None, timeout=None, state_dir=None, on_line=None):
            on_line("qwen3:30b on lab: 32k fits, 65k does not (1 s)")
            return [{"host": "lab", "model": "qwen3:30b", "outcome": self.outcome,
                     "max_full_gpu_ctx": 32768 if self.outcome == "fits" else None}]

        def _make(measurements, *, state_dir=None, on_line=None, create=None):
            self.made.append([m["model"] for m in measurements])
            on_line("qwen3:30b on lab: tuned twin qwen3-halo:30b made (32k window, all layers on the GPU) "
                    "[ol:qwen3-halo:30b@lab]")
            return []

        ollama_discover_measure.measure_hosts, ollama_tune_offer.make_twins = _measure, _make
        return self

    def __exit__(self, *exc):
        from halo_harness.providers import ollama_discover_measure, ollama_tune_offer
        ollama_discover_measure.measure_hosts, ollama_tune_offer.make_twins = self._measure, self._make
        for k, v in self._saved.items():
            if v is None:
                os.environ.pop(k, None)
            else:
                os.environ[k] = v


async def _until(pilot, predicate, seconds: float = 4.0) -> bool:
    for _ in range(int(seconds / 0.1)):
        if predicate():
            return True
        await pilot.pause(0.1)
    return predicate()


def _pilot(ctx: Ctx, stubs: _Stubs, answer: str) -> None:
    from textual.app import App
    from halo_harness.tui.dialogs.ollama_calibrate_offer import CalibrateOffer

    async def body():
        app = App()
        async with app.run_test(size=(120, 30)) as pilot:
            offer = CalibrateOffer({"lab": ["qwen3:30b"]})
            app.push_screen(offer)
            await pilot.pause(0.2)
            await pilot.press("enter")
            ctx.check("the measuring ends", await _until(pilot, lambda: offer.finished))
            await pilot.pause(0.2)
            if stubs.outcome != "fits":
                ctx.check(f"nothing fits: no question, got {offer.lines}", QUESTION not in offer.lines)
                return
            ctx.check(f"the question follows the measurements, got {offer.lines}",
                      offer.lines[-1] == QUESTION and offer.twin_offer)
            await pilot.press(answer)
            if answer == "enter":
                ctx.check("Enter makes the twins of the models that fit",
                          await _until(pilot, lambda: offer.twins_done) and stubs.made == [["qwen3:30b"]])
                ctx.check(f"one line per twin, got {offer.lines}",
                          any("tuned twin qwen3-halo:30b made" in ln for ln in offer.lines))
            else:
                await pilot.pause(0.2)
                ctx.check(f"n skips them, got {offer.lines} {stubs.made}",
                          stubs.made == [] and not offer.twin_offer
                          and offer.lines[-1].startswith("no twins made"))

    asyncio.run(body())


@test
def test_enter_makes_the_twins(ctx: Ctx):
    with _Stubs() as stubs:
        _pilot(ctx, stubs, "enter")


@test
def test_n_skips_the_twins(ctx: Ctx):
    with _Stubs() as stubs:
        _pilot(ctx, stubs, "n")


@test
def test_no_question_when_nothing_fits(ctx: Ctx):
    with _Stubs(outcome="does_not_fit") as stubs:
        _pilot(ctx, stubs, "enter")


if __name__ == "__main__":
    ctx = Ctx()
    results, passed, failed, skipped = run_all(TESTS, ctx)
    sys.exit(print_results(results, passed, failed, skipped))
