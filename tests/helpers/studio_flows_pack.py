"""tests.helpers.studio_flows_pack -- a pack's workflows and agents are the pack's (Halo 3.6.0.6 P, the owner's point 31),
in headless Chrome over tests/helpers/crew_rig.py with the pack that ships with Halo (doc-review) enabled; every press a
real one (the DevTools input domain). tests/test_studio_flows.py reads what it saw:

    flows   Agents -> 2 · Workflows: the groups in order, the group the pack's row sits in, its tag; its form: the
            read-only line, Save off, no Delete; 3.6.0.9 V: the pack's workflow changed, its form shows the new steps;
            Copy: a workflow of his own (my-review-docs) open to edit, Save writes it
    agents  1 · Agents: the pack's agent tagged the same; its form read-only the same way
    map     3 · Map, "Agents and workflows": the pack's workflow and agent tagged the same

    python -m tests.helpers.studio_flows_pack
"""
from __future__ import annotations

import sys
import time
from contextlib import contextmanager
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO))

from tests.helpers.chrome_driver import Driver  # noqa: E402

FLOW, AGENT = "doc-review--review-docs", "doc-review--reviewer"
Q = "document.querySelector"


def t(name: str) -> str:
    return f"{Q}('[data-testid=\"{name}\"]')"


def group_of(sel: str, rows: str) -> str:
    """The `.cw-group` header text the row `sel` sits under, in the list `rows`."""
    return (f"(() => {{ let g = null; for (const e of document.querySelectorAll('{rows} .cw-group, {rows} {sel}')) {{"
            f" if (e.classList.contains('cw-group')) g = e.textContent; else return g; }} return null; }})()")


def flows(c, rig) -> dict:
    row = f"[data-testid=\"flow-item\"][data-name=\"{FLOW}\"]"
    c.go(rig.url("&view=workflows"))
    c.wait(f"!!{Q}('{row}')", 40)
    out = {"groups": c.js("[...document.querySelectorAll('[data-testid=flow-list] .cw-group')].map((g) => g.textContent)"),
           "group": c.js(group_of(row, "[data-testid=flow-list]")),
           "tag": c.js(f"{Q}('{row} [data-tag=pack]')?.innerText"), "scope": c.js(f"{Q}('{row}').dataset.scope")}
    c.click_on(f"{Q}('{row}')")
    c.wait(f"!!{Q}('[data-testid=\"flow-form\"][data-name=\"{FLOW}\"]') && !!{t('flow-savebar')}", 20)
    out["form"] = c.js(f"({{line: {t('flow-readonly')}?.innerText, save: {t('flow-save')}.disabled, delete: !!{t('flow-delete')},"
                       f" copy: !!{t('flow-copy')}}})")
    # 3.6.0.9 V (4): the pack's workflow changes (its file, then the pack's notice, as an update gives it): the read-only
    # form shows the new steps
    from halo_harness.crew import store
    from halo_harness.studio.packs_studio_live import notify
    steps = f"[...document.querySelectorAll('[data-testid=flow-step]')].map((s) => s.dataset.name)"
    where = store.find("workflow", FLOW, cwd=rig.proj, state_dir=rig.state)
    raw = store.read(where[0]) if where else None
    if raw:
        raw["steps"] = [*(raw.get("steps") or []), {**raw["steps"][-1], "name": "pack-new-step"}]
        store.write_text(where[0], store.dump(raw))
        notify("update")
        try:
            c.wait(f"{steps}.includes('pack-new-step')", 15)
        except TimeoutError:
            pass
    out["pack_follows"] = [bool(raw), c.js(steps), c.js(f"!!{t('flow-readonly')}")]
    c.click_on(t("flow-copy"))
    c.wait(f"{t('flow-name')}?.value === 'my-review-docs'", 20)
    out["copy"] = c.js(f"({{name: {t('flow-name')}.value, save: {t('flow-save')}.disabled, line: !!{t('flow-readonly')},"
                       f" note: {t('flow-note')}.innerText}})")
    c.click_on(t("flow-save"))
    c.wait(f"{t('flow-note')}?.innerText.startsWith('Saved my-review-docs')", 30)
    out["copy_file"] = (rig.state / "crew" / "workflows" / "my-review-docs.yaml").is_file()
    out["pack_file"] = (rig.state / "crew" / "workflows" / f"{FLOW}.yaml").exists()
    return out


def agents(c, rig) -> dict:
    row = f"[data-testid=\"crew-item\"][data-name=\"{AGENT}\"]"
    c.go(rig.url("&view=crew"))
    c.wait(f"!!{Q}('{row}')", 40)
    out = {"agent_tag": c.js(f"{Q}('{row} [data-tag=pack]')?.innerText")}
    c.click_on(f"{Q}('{row}')")
    c.wait(f"!!{t('crew-savebar')} && !!{t('crew-copy')}", 20)
    time.sleep(0.3)
    out["agent_form"] = c.js(f"({{line: {t('crew-readonly')}?.innerText, save: {t('crew-save')}.disabled, delete: !!{t('crew-delete')}}})")
    return out


def map_list(c, rig) -> dict:
    c.go(rig.url("&view=map"))
    btn = f"{Q}('[data-part=\"map\"] [data-testid=viewbar-btn][data-panel=map-add]')"
    c.wait(f"!!{btn}", 40)
    if not c.js(f"!!{Q}('[data-part=\"map\"] .stage-drawer[data-panel-in=map-add]')"):
        c.click_on(btn)
    rows = "[data-testid=\"map-add-row\"]"
    c.wait(f"!!{Q}('{rows}[data-ref=\"{FLOW}\"]') && document.querySelectorAll('{rows}[data-ref^=\"doc-review--\"]').length >= 3", 20)
    return {"map_tags": c.js(f"[...document.querySelectorAll('{rows}')].filter((r) => r.dataset.ref.startsWith('doc-review--'))"
                             ".map((r) => [r.dataset.ref, r.querySelector('.mp-scope')?.innerText.trim()])")}


def errors(c) -> dict:
    from tests.helpers.studio_session import page_errors
    return {"page_errors": page_errors(c)}


class FlowsPackDriver(Driver):
    no_chrome = {"skip": "no Chrome found"}
    width, height = 1500, 900

    @contextmanager
    def session(self, c):
        from tests.helpers.crew_rig import CrewRig
        from tests.helpers.studio_session import collect_page_errors
        with CrewRig() as rig:
            rig.with_pack().studio()
            collect_page_errors(c)
            yield ((flows, (c, rig)), (agents, (c, rig)), (map_list, (c, rig)), (errors, (c,)))


if __name__ == "__main__":
    sys.exit(FlowsPackDriver(sys.argv[1:]).main())
