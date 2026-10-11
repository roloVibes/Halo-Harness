"""tests.test_review2_round9b -- pins for the vibes/review.md fix pass, round 9,
the Textual-pilot TUI findings:

  * f68  a typed slash command threw away the pending image attachments
  * f72  recalling a pasted prompt (Up) sent the placeholder text literally
  * f73  deleting an image chip by selecting and typing left the image attached

The rest of the pilots (70, 71, 74, 75) are in tests/test_review2_round9e.py;
the plain-Python halves of round 9 are test_review2_round9.py, 9c and 9d.
"""
from __future__ import annotations

import asyncio
import base64
import os
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from tests.helpers.runner import Ctx, new_registry, print_results, run_all

REPO_DIR = Path(__file__).resolve().parent.parent
test, TESTS = new_registry()

PNG_1X1 = base64.b64decode(
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mNk+A8AAQUBAScY42YAAAAASUVORK5CYII=")
MODELS = [{"ref": "or:vendor/strong-model", "provider": "openrouter", "group": "OpenRouter (or:)",
           "context_tokens": 128000, "price_in_per_m": 1.0, "price_out_per_m": 2.0}]


class _Env:
    def __enter__(self):
        self._saved = {k: os.environ.get(k) for k in ("BRIDGE_TEST_HOME", "BRIDGE_STATE_DIR")}
        d = tempfile.mkdtemp(prefix="r9b-")
        os.environ["BRIDGE_TEST_HOME"] = d
        os.environ["BRIDGE_STATE_DIR"] = str(Path(d) / ".halo")
        self.dir = Path(d)
        return self

    def __exit__(self, *exc):
        for k, v in self._saved.items():
            if v is None:
                os.environ.pop(k, None)
            else:
                os.environ[k] = v
        return False


def _app():
    from halo_harness.testing.fake_controller import FakeController
    from halo_harness.tui.app import BridgeApp
    fake = FakeController()
    return fake, BridgeApp(fake, cwd=str(REPO_DIR))


def _static_text(widget) -> str:
    return str(widget.renderable) if hasattr(widget, "renderable") else str(widget.render())


def _png(env: _Env, name: str = "a.png") -> Path:
    path = env.dir / name
    path.write_bytes(PNG_1X1)
    return path


async def _submit(app, text: str) -> None:
    from halo_harness.tui.widgets.input import PromptInput
    await app.on_prompt_input_submitted(PromptInput.Submitted(text, app.prompt_input.pasted))


# ---- f68 ------------------------------------------------------------------------------

@test
def test_f68_a_typed_slash_command_keeps_the_pending_image_chips(ctx: Ctx):
    async def body():
        with _Env() as env:
            fake, app = _app()
            async with app.run_test(size=(100, 30)) as pilot:
                await pilot.pause(0.2)
                pi = app.prompt_input
                pi.add_image_chip(path=_png(env), width=1, height=1, media_type="image/png")
                label = pi.images[0]["label"]
                pi.text = "/images " + label
                await pilot.pause(0.05)
                await _submit(app, pi.text)
                await pilot.pause(0.1)
                ctx.check(f"the image is still pending, got {pi.images}", len(pi.images) == 1)
                ctx.check(f"its chip is back in the box, got {pi.text!r}", pi.text == label)
                await _submit(app, "describe it " + label)
                await pilot.pause(0.3)
                ctx.check(f"a normal prompt still attaches it, got {fake.submitted_images}",
                          fake.submitted_images and fake.submitted_images[-1])
    asyncio.run(body())


# ---- f73 ------------------------------------------------------------------------------

@test
def test_f73_overtyping_a_chip_drops_its_image_and_keeps_the_others_numbered(ctx: Ctx):
    from textual.widgets.text_area import Selection

    async def body():
        with _Env() as env:
            fake, app = _app()
            async with app.run_test(size=(100, 30)) as pilot:
                await pilot.pause(0.2)
                pi = app.prompt_input
                pi.add_image_chip(path=_png(env, "a.png"), width=1, height=1)
                pi.add_image_chip(path=_png(env, "b.png"), width=1, height=1)
                first, second = pi.images[0]["label"], pi.images[1]["label"]
                await pilot.click("#prompt-input")
                pi.selection = Selection((0, 0), (0, len(first)))
                await pilot.press("x")
                await pilot.pause(0.1)
                ctx.check(f"only the second image is left, got {[i['label'] for i in pi.images]}",
                          [i["label"] for i in pi.images] == [second])
                pi.add_image_chip(path=_png(env, "c.png"), width=1, height=1)
                labels = [i["label"] for i in pi.images]
                ctx.check(f"a new chip never reuses a surviving number, got {labels}", len(set(labels)) == 2)
                pi.text = ""
                await pilot.pause(0.1)
                ctx.check(f"clearing the box clears them all, got {pi.images}", pi.images == [])
    asyncio.run(body())


# ---- f72 ------------------------------------------------------------------------------

@test
def test_f72_recalled_paste_placeholder_expands_on_submit(ctx: Ctx):
    from halo_harness import history as history_mod

    async def body():
        with _Env():
            big = "\n".join(f"line {n}" for n in range(8))
            history_mod.append_history_entry("[Pasted text #1 +8 lines]", str(REPO_DIR), pasted_contents={"1": big})
            fake, app = _app()
            async with app.run_test(size=(100, 30)) as pilot:
                await pilot.pause(0.2)
                await pilot.click("#prompt-input")
                await pilot.press("up")
                await pilot.pause(0.1)
                pi = app.prompt_input
                ctx.check(f"the placeholder is recalled, got {pi.text!r}", pi.text == "[Pasted text #1 +8 lines]")
                ctx.check(f"with its paste contents, got {pi.pasted}", pi.pasted == {1: big})
                await _submit(app, pi.text)
                await pilot.pause(0.3)
                ctx.check(f"the model got the real text, got {fake.submitted}", fake.submitted == [big])
    asyncio.run(body())


if __name__ == "__main__":
    ctx = Ctx()
    results, passed, failed, skipped = run_all(TESTS, ctx)
    sys.exit(print_results(results, passed, failed, skipped))
