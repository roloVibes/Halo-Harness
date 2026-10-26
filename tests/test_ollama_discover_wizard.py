"""tests.test_ollama_discover_wizard -- Halo 3.2.3.0 R2: the wizard's Ollama
tab finds the servers. A pilot of `init_tabs.InitTabsApp` (the tab
`init_wizard.ProvidersStep` shares through `tui/dialogs/ollama_found.py`):
**Find Ollama servers** lists both mock servers (the configured one ticked
and dimmed), a tick + Save adds the new one through `add_hosts`, and the
calibrate offer then runs with `measure_hosts` stubbed (Enter runs it, Esc
closes it and leaves the app running). Hermetic: the mocks sit on
127.0.0.1:0 and `ollama.discover.ports` names them.
"""
from __future__ import annotations

TIER = "full"  # a TUI pilot (Textual run_test): the full tier

import asyncio
import json
import os
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from tests.helpers.mock_ollama import MockUpstream
from tests.helpers.runner import Ctx, new_registry, print_results, run_all

test, TESTS = new_registry()

_SCRUB = ("OLLAMA_HOST", "OLLAMA_API_KEY", "HALO_OFFLINE", "HF_TOKEN", "OPENROUTER_API_KEY", "DATABRICKS_HOST",
          "DATABRICKS_TOKEN", "ANTHROPIC_API_KEY", "TYPESAFE_API_KEY", "OPENAI_API_KEY", "EXPLABS_API_KEY")
_ENV_NAMES = ("BRIDGE_TEST_HOME", "BRIDGE_STATE_DIR", "BRIDGE_ENV_FILE", "BRIDGE_TEST_NO_BACKGROUND_NET",
              "BRIDGE_TEST_CC_AUTH_STATUS") + _SCRUB
OTHER_TAGS = {"models": [{"name": "llama3.2:3b", "model": "llama3.2:3b", "size": 2000, "digest": "sha256:feed1"}]}


class _Env:
    def __enter__(self):
        from halo_harness.providers.ollama_discover import reset_discover_cache
        self._saved = {k: os.environ.get(k) for k in _ENV_NAMES}
        d = Path(tempfile.mkdtemp(prefix="ol-discover-wizard-"))
        os.environ["BRIDGE_TEST_HOME"] = str(d)
        os.environ["BRIDGE_STATE_DIR"] = str(d / ".halo")
        os.environ["BRIDGE_ENV_FILE"] = str(d / "env-file")
        os.environ["BRIDGE_TEST_NO_BACKGROUND_NET"] = "1"
        os.environ["BRIDGE_TEST_CC_AUTH_STATUS"] = json.dumps({"loggedIn": False})
        for k in _SCRUB:
            os.environ.pop(k, None)
        reset_discover_cache()
        self.a = MockUpstream().start()
        self.b = MockUpstream(tags_response=OTHER_TAGS).start()
        from halo_harness.theme import set_config_value
        set_config_value("ollama.discover", {"ports": [self.a.port, self.b.port]})
        set_config_value("ollama.hosts", [{"name": "pc", "url": self.a.base_url, "default": True}])
        return self

    def __exit__(self, *exc):
        self.a.stop()
        self.b.stop()
        for k, v in self._saved.items():
            if v is None:
                os.environ.pop(k, None)
            else:
                os.environ[k] = v


async def _until(pilot, predicate, seconds: float = 8.0) -> bool:
    for _ in range(int(seconds / 0.1)):
        if predicate():
            return True
        await pilot.pause(0.1)
    return predicate()


@test
def test_find_tick_save_adds_and_the_calibrate_offer_runs(ctx: Ctx):
    from textual.widgets import Checkbox, TabbedContent
    from halo_harness.providers import ollama_discover_measure
    from halo_harness.tui.dialogs.init_tabs import InitTabsApp
    from halo_harness.tui.dialogs.ollama_calibrate_offer import CalibrateOffer
    from halo_harness.tui.dialogs.ollama_found import FoundPanel

    calls = []

    def _stub(names, *, models_by_host=None, timeout=None, state_dir=None, on_line=None):
        calls.append((list(names), dict(models_by_host or {})))
        for name in names:
            for model in (models_by_host or {}).get(name) or []:
                on_line(f"{model} on {name}: 32k fits, 65k does not (1 s)")
        return []

    async def body(env):
        app = InitTabsApp(no_live=False)
        async with app.run_test(size=(140, 50)) as pilot:
            app.query_one(TabbedContent).active = "pane-ollama"
            await pilot.pause(0.2)
            app.query_one("#ollama-find").press()
            panel = app.query_one("#ollama-found", FoundPanel)
            ctx.check("Find lists both mocks", await _until(pilot, lambda: len(panel.query(Checkbox)) == 2))
            boxes = list(panel.query(Checkbox))
            labels = [str(b.label) for b in boxes]
            configured = [b for b in boxes if "(configured)" in str(b.label)]
            new = [b for b in boxes if "(new)" in str(b.label)]
            ctx.check(f"one configured row, ticked and dimmed, got {labels}",
                      len(configured) == 1 and configured[0].value and configured[0].disabled
                      and configured[0].has_class("found-configured"))
            ctx.check(f"one new row with its models, unticked, got {labels}",
                      len(new) == 1 and not new[0].value and "llama3.2:3b" in str(new[0].label))
            new[0].value = True
            await pilot.pause(0.2)
            app.query_one("#ollama-save").press()
            ctx.check("the calibrate offer opens after Save",
                      await _until(pilot, lambda: isinstance(app.screen, CalibrateOffer), 4.0))
            from halo_harness.theme import get_config_value
            hosts = get_config_value("ollama.hosts", default=None) or []
            ctx.check(f"Save added the ticked row, pc untouched, got {hosts}",
                      [h["url"] for h in hosts] == [env.a.base_url, env.b.base_url]
                      and hosts[0] == {"name": "pc", "url": env.a.base_url, "default": True})
            offer = app.screen
            ctx.check(f"the offer's wording, got {getattr(offer, 'offer', '')!r}",
                      isinstance(offer, CalibrateOffer) and offer.offer.startswith("Calibrate the found models now")
                      and "Enter runs it, Esc skips" in offer.offer)
            await pilot.press("enter")
            ctx.check("Enter runs the calibration (stubbed) for the added host only",
                      await _until(pilot, lambda: bool(calls) and offer.finished, 4.0)
                      and calls[0][0] == [hosts[1]["name"]] and calls[0][1][hosts[1]["name"]] == ["llama3.2:3b"])
            ctx.check(f"one progress line per model, got {offer.lines}",
                      any(ln.startswith(f"llama3.2:3b on {hosts[1]['name']}: 32k fits") for ln in offer.lines))
            await pilot.press("escape")
            await pilot.pause(0.2)
            ctx.check("Esc closes the offer and leaves the setup running",
                      not isinstance(app.screen, CalibrateOffer) and app.is_running)

    with _Env() as env:
        saved = ollama_discover_measure.measure_hosts
        ollama_discover_measure.measure_hosts = _stub
        try:
            asyncio.run(body(env))
        finally:
            ollama_discover_measure.measure_hosts = saved


@test
def test_the_local_models_step_shows_the_found_rows_read_only(ctx: Ctx):
    from textual.widgets import Checkbox, Static
    from halo_harness.tui.dialogs.init_wizard import InitWizardApp, WizardState
    from halo_harness.tui.dialogs.ollama_found import FoundPanel

    async def body(env):
        state = WizardState(cwd=Path(os.environ["BRIDGE_TEST_HOME"]), step_keys=("local_models",), no_live=True)
        app = InitWizardApp(state)
        async with app.run_test(size=(140, 50)) as pilot:
            await pilot.pause(0.2)
            panel = app.screen.query_one("#wiz-local-found", FoundPanel)
            rows = lambda: [w for w in panel.query(Static) if "Ollama" not in str(w.render()) and "127.0.0.1" in str(w.render())]
            ctx.check("both servers listed without a click", await _until(pilot, lambda: len(rows()) == 2))
            ctx.check("read-only: no ticks, no Find/Scan buttons",
                      not list(panel.query(Checkbox)) and not list(panel.query("#wiz-local-find")))
            texts = [str(w.render()) for w in rows()]
            ctx.check(f"each row names its models and state, got {texts}",
                      any("pc" in t and "(configured)" in t for t in texts)
                      and any("llama3.2:3b" in t and "(new)" in t for t in texts))
            detect = app.screen.query_one("#wiz-local-detect", Static)
            ctx.check("the detection lines below list both too",
                      await _until(pilot, lambda: f"127.0.0.1:{env.b.port}: 1 model, not added" in str(detect.render())))

    with _Env() as env:
        asyncio.run(body(env))


@test
def test_esc_on_the_offer_skips_it_without_measuring(ctx: Ctx):
    from textual.app import App
    from halo_harness.tui.dialogs.ollama_calibrate_offer import CalibrateOffer

    async def body():
        app = App()
        async with app.run_test(size=(100, 30)) as pilot:
            offer = CalibrateOffer({"lab": ["qwen3:30b", "llama3.2:3b"]})
            app.push_screen(offer)
            await pilot.pause(0.2)
            ctx.check(f"about N minutes for two models, got {offer.offer!r}", "about 2 minutes" in offer.offer)
            await pilot.press("escape")
            await pilot.pause(0.2)
            ctx.check("Esc skips: the offer is gone and nothing ran", app.screen is not offer and not offer.running)

    with _Env():
        asyncio.run(body())


if __name__ == "__main__":
    ctx = Ctx()
    results, passed, failed, skipped = run_all(TESTS, ctx)
    sys.exit(print_results(results, passed, failed, skipped))
