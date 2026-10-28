"""tests.test_model_card_tui -- Halo 3.3.5.0 R0b in the terminal (Textual
pilots over a fake controller; no server, no model call):

1. the /model picker's local rows carry the card's chips and the fit word
   (`fits` / `tight` / `spill` / `no`) from the cached catalog and the cached
   hardware card; a cloud row carries none;
2. bare `/effort` on a thinking local model lists THIS model's options
   (on / off / default), the pick writes `models.think` and the status bar
   follows at once; on a model whose effort does nothing it says so;
3. `/model` with no argument (the headless command) prints the current
   model's card;
4. the main-model line with an offer mounts the one-key card; y accepts.
Run: python -m tests.test_model_card_tui
"""
from __future__ import annotations

TIER = "full"  # TUI pilots (Textual run_test): the full tier

import asyncio
import sys
import tempfile
import time
from pathlib import Path
from types import SimpleNamespace

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from tests.helpers.provider_env_defaults import ensure_default_provider_credentials  # noqa: E402
ensure_default_provider_credentials()

from tests.helpers.model_card_fixtures import ROWS, host_card, write_probes  # noqa: E402
from tests.helpers.runner import Ctx, new_registry, print_results, run_all  # noqa: E402
from tests.helpers.steward_seed import Home  # noqa: E402

test, TESTS = new_registry()


def _seed(names):
    from halo_harness.providers import ollama as O
    from halo_harness.studio import ollama_hosts_view as V
    host = O.resolve_ollama_host("pc")
    with O._CATALOG_LOCK:
        O._CATALOG_CACHE[host.url] = (time.monotonic(), {"models": [dict(ROWS[n]) for n in names]})
    with V._LOCK:
        V._CACHE[("card", host.url)] = (time.monotonic(), host_card())
    return host


def _unseed():
    from halo_harness.providers.ollama import reset_catalog_cache
    from halo_harness.studio import ollama_hosts_view as V
    reset_catalog_cache()
    V.reset_cache()


def _controller(session=None):
    from halo_harness.testing.fake_controller import FakeController

    class _C(FakeController):
        def run_slash(self, name, args=""):
            if name == "effort":
                from halo_harness.commands.builtins import _cmd_effort
                return _cmd_effort(args, SimpleNamespace(session=self.session, effort=None))
            return super().run_slash(name, args)
    c = _C()
    c.session = session
    c.state_dir = Path(tempfile.mkdtemp(prefix="m1-tui-"))
    return c


def _app(controller):
    from halo_harness.tui.app import BridgeApp
    return BridgeApp(controller, cwd=tempfile.mkdtemp(prefix="m1-tui-cwd-"))


def _ollama_session(model: str):
    return SimpleNamespace(model_ref=SimpleNamespace(provider="ollama", model=model, host="pc", local=False, mlx=False,
                                                     raw=f"ol:{model}@pc", dialect="ollama"),
                           effort="high", effort_requested="high", effort_source="settings", provider_profile=None,
                           settings=None, _ollama_supports_thinking=None, state_dir=None)


@test
def test_the_picker_rows_carry_the_card_and_the_fit_word(ctx: Ctx):
    from halo_harness.tui.dialogs.model_picker import ModelPicker
    with Home(hosts=({"name": "pc", "url": "http://192.0.2.10:11434", "default": True},)) as h:
        write_probes(h.state)
        _seed(["qwen3-coder:30b", "qwen3.5:9b"])
        models = [{"ref": "ol:qwen3-coder:30b", "provider": "ollama", "group": "Ollama (pc)"},
                  {"ref": "ol:qwen3.5:9b", "provider": "ollama", "group": "Ollama (pc)"},
                  {"ref": "or:mock/cloud", "provider": "openrouter"}]
        out = {}

        async def body():
            app = _app(_controller())
            async with app.run_test(size=(160, 40)) as pilot:
                picker = ModelPicker(models, current="")
                picker.state_dir = h.state
                app.push_screen(picker)
                await pilot.pause(0.2)
                for m in models:
                    out[m["ref"]] = str(picker._row_text(m))
        try:
            asyncio.run(body())
        finally:
            _unseed()
    ctx.check(f"the coder row: no tools, coder, its window, the fit word, got {out.get('ol:qwen3-coder:30b')!r}",
              "no tools · coder" in out.get("ol:qwen3-coder:30b", "") and out["ol:qwen3-coder:30b"].rstrip().endswith(
                  ("fits", "tight", "spill", "no")))
    ctx.check(f"the 9B row fits, got {out.get('ol:qwen3.5:9b')!r}", "tools · instruct" in out.get("ol:qwen3.5:9b", "")
              and "fits" in out["ol:qwen3.5:9b"])
    ctx.check(f"a cloud row carries no card words, got {out.get('or:mock/cloud')!r}",
              "tools" not in out.get("or:mock/cloud", "") and "fits" not in out.get("or:mock/cloud", ""))


@test
def test_effort_on_a_thinking_local_model(ctx: Ctx):
    from halo_harness.providers.effort_on import think_choice_for
    from halo_harness.tui.widgets.cards import EffortCard
    with Home(hosts=({"name": "pc", "url": "http://192.0.2.10:11434", "default": True},)):
        _seed(["qwen3.8:27b", "qwen3-coder:30b"])
        session = _ollama_session("qwen3.8:27b")
        got = {}

        async def body():
            app = _app(_controller(session))
            async with app.run_test(size=(140, 40)) as pilot:
                from halo_harness.tui.slash import _handle_effort
                await _handle_effort(app, "")
                await pilot.pause(0.1)
                card = app.pending_card
                got["levels"] = list(getattr(card, "levels", []))
                got["index"] = getattr(card, "index", None)
                card.action_move_left()
                card.action_apply()
                await pilot.pause(0.1)
                got["bar"] = app.status_bar.effort
                session.model_ref = SimpleNamespace(provider="ollama", model="qwen3-coder:30b", host="pc", local=False,
                                                    mlx=False, raw="ol:qwen3-coder:30b@pc", dialect="ollama")
                await _handle_effort(app, "")
                await pilot.pause(0.1)
                none = app.pending_card
                got["none_levels"] = list(getattr(none, "levels", ["?"]))
                got["none_text"] = str(none.render()) if none is not None else ""
        try:
            asyncio.run(body())
            choice = think_choice_for("ol:qwen3.8:27b@pc")
        finally:
            _unseed()
    ctx.check(f"this model's options, the current one 'default', got {got}",
              got.get("levels") == ["on", "off", "default"] and got.get("index") == 2 and isinstance(got["levels"][0], str))
    ctx.check(f"the pick writes models.think, got {choice!r}", choice == "off")
    ctx.check(f"the status bar follows at once, got {got.get('bar')!r}", got.get("bar") == "think off")
    ctx.check(f"a model whose effort does nothing: no options, it says so, got {got.get('none_levels')} "
              f"{got.get('none_text')!r}", got.get("none_levels") == [] and "no adjustable effort" in got.get("none_text", ""))


@test
def test_model_with_no_argument_prints_the_card(ctx: Ctx):
    from halo_harness.commands.builtins import _cmd_model
    with Home(hosts=({"name": "pc", "url": "http://192.0.2.10:11434", "default": True},)) as h:
        write_probes(h.state)
        _seed(["qwen3-coder:30b"])
        try:
            s = _ollama_session("qwen3-coder:30b")
            s.state_dir = h.state
            s.model_profile = SimpleNamespace(context_tokens=65536, vision=False)
            text = _cmd_model("", SimpleNamespace(session=s, model_ref=None, effort=None))
        finally:
            _unseed()
    ctx.check(f"the current model, then its card, got {text!r}", text.startswith("Current model: ol:qwen3-coder:30b@pc")
              and "a coding model" in text and "how Halo calls it:" in text and "orchestrator: no" in text)


@test
def test_the_offer_card_is_mounted_and_y_accepts(ctx: Ctx):
    from halo_harness.tui import lane_offer_flow
    seen = {}

    async def body():
        app = _app(_controller())
        async with app.run_test(size=(140, 40)) as pilot:
            real = lane_offer_flow.accept_worker
            lane_offer_flow.accept_worker = lambda a, offer: seen.setdefault("accepted", offer)
            try:
                await lane_offer_flow.show(app, {"text": "x is a coding model ...", "line": "x is a coding model ...",
                                                 "offer": {"lineup": "local-coder", "coder": "ol:x", "orchestrator": "ol:y"}})
                await pilot.pause(0.1)
                seen["card"] = type(app.pending_card).__name__
                app.pending_card.action_accept()
                await pilot.pause(0.3)
            finally:
                lane_offer_flow.accept_worker = real
    asyncio.run(body())
    ctx.check(f"the one-key card is pending, got {seen.get('card')}", seen.get("card") == "LaneOfferCard")
    ctx.check(f"y accepts: the worker gets the offer, got {seen.get('accepted')}",
              (seen.get("accepted") or {}).get("lineup") == "local-coder")


if __name__ == "__main__":
    results, passed, failed, skipped = run_all(TESTS, Ctx())
    sys.exit(print_results(results, passed, failed, skipped))
