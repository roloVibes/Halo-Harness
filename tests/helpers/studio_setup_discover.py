"""tests.helpers.studio_setup_discover -- the Find / Add / Measure step of the
Setup driver (tests/helpers/studio_setup.py, Halo 3.3.0.0 R5), real clicks in
headless Chrome over the driver's scratch home. Two `MockUpstream`s on
127.0.0.1:0 with different model lists, `ollama.discover.ports` naming their
ports (the default port is never asked), `BRIDGE_TEST_NO_BACKGROUND_NET=1`
(the network sweep answers its note); the Models refresh asks only the
loopback hosts (`models_refresh.jobs_for` narrowed; R2's documentation-address
host is never asked); the calibration is stubbed (`run_calibration`, and the
GPU-memory estimate), so no model loads:

1. Find Ollama servers lists both mocks with their models; Scan this network
   answers the test note and no rows;
2. a tick on each, Add the ticked: both in the hosts table and config.json
   after R2's host (still the default), the rows say configured;
3. the Models panel (Roles) lists `Ollama (<name>)` for each new host after
   the refresh Add runs;
4. back in Setup, Measure the found models fills the log: one line per model
   and the summary.
"""
from __future__ import annotations

import json
import time
from types import SimpleNamespace

from tests.helpers.studio_packs_steps import CUR, alt, q, qa

OTHER = {"models": [{"name": "llama3.2:3b", "model": "llama3.2:3b", "size": 2000, "digest": "sha256:feed1",
                     "details": {"family": "llama"}}]}
ROWS = qa("[data-testid=setup-found-row]")


def click(c, expr: str, done: str, wait: float = 8) -> str:
    """Click by pointer and wait for `done`; the element's own click when the pointer missed."""
    c.wait(f"!!({expr}) && !({expr}).disabled", 15)
    c.js(f"({expr}).scrollIntoView({{block: 'center'}}); 1")
    time.sleep(0.2)
    c.click_on(expr)
    try:
        c.wait(done, wait)
        return "pointer"
    except TimeoutError:
        c.js(f"({expr})?.click(); 1")
        c.wait(done, 20)
        return "element"


class _Rig:
    def __enter__(self):
        from tests.helpers.mock_ollama import MockUpstream
        from halo_harness.providers import ollama_calibrate as OC, ollama_hw as HW
        from halo_harness.providers.ollama import resolve_ollama_hosts
        from halo_harness.studio import models_refresh as MR
        from halo_harness.theme import set_config_value
        self.a, self.b = MockUpstream().start(), MockUpstream(tags_response=OTHER).start()
        set_config_value("ollama.discover", {"ports": [self.a.port, self.b.port]})
        self.calls: list = []

        def calibrate(host, model, **kw):
            self.calls.append((host.name, model))
            return SimpleNamespace(outcome="fits", max_full_gpu_ctx=32768, steps=1, tight_ctx=None, tight_vram=None, gpu_total=None)

        def loopback_jobs(state_dir, env, local=True):  # the Models refresh: only the mocks, never a provider or R2's host
            return [(f"Ollama ({h.name})", "ollama", MR._ollama(h)) for h in resolve_ollama_hosts(env)
                    if h.url.startswith("http://127.0.0.1:")]

        self.saved = (OC.run_calibration, HW.estimate_fit_for_host, MR.jobs_for)
        OC.run_calibration, HW.estimate_fit_for_host, MR.jobs_for = calibrate, (lambda *a, **k: None), loopback_jobs
        return self

    def __exit__(self, *exc):
        from halo_harness.providers import ollama_calibrate as OC, ollama_hw as HW
        from halo_harness.studio import models_refresh as MR
        OC.run_calibration, HW.estimate_fit_for_host, MR.jobs_for = self.saved
        self.a.stop()
        self.b.stop()


def discover(c, url, ctx) -> dict:
    with _Rig() as rig:
        return _steps(c, ctx, rig)


def _steps(c, ctx, rig) -> dict:
    a, b = rig.a.base_url, rig.b.base_url
    more = q("[data-testid=setup-ollama-more]")  # 3.3.1.0 R1: the finders are a disclosure under the hosts, closed at first
    if not c.js(f"{more}.open"):
        click(c, f"{more}.querySelector('summary')", f"{more}.open")
    out = {"finders_off": c.js(f"[{q('[data-testid=setup-ollama-find]')}.disabled, {q('[data-testid=setup-ollama-scan]')}.disabled]"),
           "ports_line": c.js(f"{q('[data-testid=setup-ollama-ports]')}?.textContent || ''")}
    out["find_by"] = click(c, q("[data-testid=setup-ollama-find]"), f"{ROWS}.length === 2", 15)
    out["found"] = c.js(f"{ROWS}.map((r) => [r.dataset.url, r.dataset.name, r.querySelector('[data-testid=setup-found-models]').textContent, "
                        f"!!r.querySelector('[data-testid=setup-found-tick]')])")
    out["scan_by"] = click(c, q("[data-testid=setup-ollama-scan]"),
                           f"{q('[data-testid=setup-ollama-scan-line]')}?.dataset.state === 'done'", 10)
    out["scan_line"] = c.js(f"{q('[data-testid=setup-ollama-scan-line]')}.textContent")
    out["rows_after_scan"] = c.js(f"{ROWS}.length")
    out["tick_by"] = []
    for u in (a, b):
        box = q(f"[data-testid=setup-found-tick][data-url='{u}']")
        out["tick_by"].append(click(c, box, f"{box}.checked", 4))
    out["add_label"] = c.js(f"{q('[data-testid=setup-ollama-add]')}.textContent")
    hosts_rows = qa("[data-testid=setup-row][data-card=ollama]")
    out["add_by"] = click(c, q("[data-testid=setup-ollama-add]"), f"{hosts_rows}.length === 3", 15)
    out["hosts_rows"] = c.js(f"{hosts_rows}.map((r) => [...r.querySelectorAll('td')].slice(0, 3).map((t) => t.textContent))")
    out["configured_after"] = c.wait(f"{qa('[data-testid=setup-found-configured]')}.length === 2 && 2", 10)
    out["add_lines"] = c.js(f"{q('[data-testid=setup-card-lines][data-card=ollama-found]')}?.textContent || ''")
    cfg = json.loads((ctx["state"] / "config.json").read_text(encoding="utf-8"))
    out["hosts_config"] = [[h.get("name"), h.get("url"), h.get("default")] for h in (cfg.get("ollama") or {}).get("hosts", [])]
    names = [h[0] for h in out["hosts_config"][1:]]
    out["added_names"] = names
    alt(c, 3)  # the Models panel in Roles: the refresh Add ran lists each new host
    c.wait(f"{CUR}.startsWith('Roles')", 15)
    lines = qa("[data-testid=roles-models-body] [data-testid=model-outcome][data-provider=ollama]")
    out["models_panel"] = c.wait(f"{lines}.length >= 2 && {lines}.map((l) => l.textContent)", 30)
    alt(c, 8)
    c.wait(f"{CUR}.startsWith('Setup') && !!{q('[data-testid=setup-measure]')}", 20)
    out["measure_models"] = c.js(f"{qa('[data-testid=setup-measure-model]')}.map((m) => [m.dataset.ref, m.querySelector('input').checked])")
    log = qa("[data-testid=setup-measure-line]")
    out["measure_by"] = click(c, q("[data-testid=setup-ollama-measure]"),
                              f"!!{q('[data-testid=setup-measure-summary]')} && {log}.length === 3", 30)
    out["measure_lines"] = c.js(f"{log}.map((l) => l.textContent)")
    out["measure_summary"] = c.js(f"{q('[data-testid=setup-measure-summary]')}.textContent")
    out["measure_calls"] = sorted([list(x) for x in rig.calls])
    out["fit_recorded"] = (ctx["state"] / "ollama-fit.json").is_file()
    return out


STEPS = (discover,)
