"""tests.helpers.studio_model_takes -- what a model takes, wherever a model is picked in Studio (Halo 3.3.15.0 R2),
real clicks in headless Chrome through the driver base, for tests/test_studio_model_takes.py:

    python -m tests.helpers.studio_model_takes

A fresh home with the shipped lineups and a fake OpenRouter catalog (models.json, no request) of two models: one
that reads images and PDFs and states tools and reasoning, one text-only. The default model (config `model`) is the
first, the role table's `main` the second. Session's Start view: the new-session select shows the default's
`model-takes` chips (their title the honest line), and picking the text-only model turns them to `text`.
Orchestra's goal form: the model select shows the lead's (text-only) chips, and picking the first turns them to its
words; its "more..." opens Roles' picker table, where every row is one line (<= 28 px), no tag is taller than 20 px,
the TAKES column holds the tags only and the focused row's honest line is the detail line under the list (owner
feedback 2026-11-09). The last stdout line is the JSON of what it saw (exit 2: no Chrome)."""
from __future__ import annotations

import json
import shutil
import sys
from contextlib import contextmanager
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO))
sys.path.insert(0, str(REPO / "tools"))

from tests.helpers.chrome_driver import Driver  # noqa: E402
from tests.helpers.studio_roles_model import pick  # noqa: E402

EYES, PLAIN = "or:fakeco/eyes-1", "or:fakeco/plain-2"
EYES_TAKES = "text,vision,pdf,tools,think"
NS = "document.querySelector('[data-testid=\"session-new\"]')"
OM = "document.querySelector('[data-testid=\"orchestra-model\"]')"


def seed_catalog(state: Path) -> None:
    from halo_harness.theme import set_config_value
    rows = {
        "fakeco/eyes-1": {"context_length": 1_000_000, "input_modalities": ["text", "image", "file"], "output_modalities": ["text"],
                          "supported_parameters": ["tools", "reasoning"], "pricing": {"prompt": "0.000003", "completion": "0.000015"}},
        "fakeco/plain-2": {"context_length": 128_000, "input_modalities": ["text"], "output_modalities": ["text"],
                           "pricing": {"prompt": "0.0000001", "completion": "0.0000004"}},
    }
    (state / "models.json").write_text(json.dumps(rows), encoding="utf-8")
    set_config_value("providers.openrouter.enabled", True)


def chips(scope: str) -> str:
    """`[takes, title]` of the first model-takes group under `scope` (JS)."""
    g = f"{scope}?.querySelector('[data-testid=\"model-takes\"]')"
    return f"({g} ? [{g}.dataset.takes, {g}.title, [...{g}.querySelectorAll('[data-take]')].map((n) => n.dataset.take).join(' ')] : null)"


def picker_table(c) -> dict:
    """Orchestra's "more..." opens Roles' picker table: one line per row, square tags, the detail line."""
    out: dict = {}
    c.js(f"{OM}.querySelector('[data-testid=\"model-select-more\"]').click(); 1")
    rows = "[...document.querySelectorAll('[data-testid=\"model-select-dialog\"] [data-testid=\"model-row\"]')]"
    try:
        out["rows"] = c.wait(f"{rows}.length === 2 && {rows}.length", 15)
    except TimeoutError:
        raise TimeoutError("picker table: " + json.dumps(c.js("[!!document.querySelector('[data-testid=\"model-select-dialog\"]'), "
                                                              "document.querySelectorAll('[data-testid=\"model-row\"]').length, "
                                                              "[...document.querySelectorAll('[data-testid=\"model-row\"]')].map((r) => r.dataset.ref)]")))
    out["row_heights"] = c.js(f"{rows}.map((r) => Math.round(r.getBoundingClientRect().height))")
    out["tag_heights"] = c.js(f"{rows}.flatMap((r) => [...r.querySelectorAll('.mtakes-tag')].map((t) => Math.round(t.getBoundingClientRect().height)))")
    out["row_tags"] = c.js(f"{rows}.map((r) => [r.dataset.ref, [...r.querySelectorAll('[data-take]')].map((t) => t.dataset.take).join(' ')])")
    out["head"] = c.js("document.querySelector('[data-testid=\"model-select-dialog\"] .rm-head')?.textContent")
    out["no_line_in_rows"] = c.js(f"{rows}.every((r) => !r.querySelector('[data-testid=\"model-best-line\"]'))")
    c.call("Emulation.setFocusEmulationEnabled", enabled=True)  # a headless page without window focus fires no focus events
    c.js(f"{rows}.find((r) => r.dataset.ref === {json.dumps(PLAIN)}).focus(); 1")
    detail = "document.querySelector('[data-testid=\"model-select-dialog\"] [data-testid=\"model-detail\"]')"
    try:
        out["detail"] = c.wait(f"{detail}?.dataset.ref === {json.dumps(PLAIN)} && {detail}.querySelector('[data-testid=\"model-best-line\"]').textContent", 10)
    except TimeoutError:
        raise TimeoutError("detail: " + json.dumps(c.js(f"[{detail}?.outerHTML?.slice(0, 400), document.activeElement?.outerHTML?.slice(0, 200)]")))
    return out


def run(c, url: str) -> dict:
    out: dict = {}
    c.go(url.replace("mode=orchestra", "mode=session").replace("feed=off", "feed=off&tour=off"))
    out["session_default"] = c.wait(f"(() => {{ const v = {chips(NS)}; return v && v[0] === {json.dumps(EYES_TAKES)} && v; }})()", 40)
    c.wait(f"!!{NS}.querySelector('option[value=\"{PLAIN}\"]')", 15)
    out["session_option_title"] = c.js(f"{NS}.querySelector('option[value=\"{EYES}\"]').title")
    pick(c, f"{NS}.querySelector('[data-testid=\"session-new-model\"]')", PLAIN)
    out["session_picked"] = c.wait(f"(() => {{ const v = {chips(NS)}; return v && v[0] === 'text' && v; }})()", 15)
    c.go("about:blank")
    c.go(url)
    out["orch_lead"] = c.wait(f"(() => {{ const v = {chips(OM)}; return v && v[0] === 'text' && v; }})()", 40)
    c.wait(f"!!{OM}.querySelector('option[value=\"{EYES}\"]')", 15)
    pick(c, f"{OM}.querySelector('select')", EYES)
    out["orch_picked"] = c.wait(f"(() => {{ const v = {chips(OM)}; return v && v[0] === {json.dumps(EYES_TAKES)} && v; }})()", 15)
    out["orch_value"] = c.js(f"{OM}.dataset.value")
    out["orch_select_title"] = c.js(f"{OM}.querySelector('select').title")
    out.update(picker_table(c))
    return out


class TakesDriver(Driver):
    no_chrome = {"skip": "no Chrome found"}

    @contextmanager
    def session(self, c):
        from capture_studio import seeded_home, serve
        from halo_harness.theme import set_config_value
        state = seeded_home()
        seed_catalog(state)
        set_config_value("roles.main", PLAIN)
        set_config_value("model", EYES)
        srv, url = serve(state, True)
        from tests.helpers.studio_full import full
        try:
            yield ((run, (c, full(url))),)
        finally:
            srv.shutdown()
            srv.server_close()
            shutil.rmtree(state.parent, ignore_errors=True)


if __name__ == "__main__":
    sys.exit(TakesDriver(sys.argv[1:]).main())
