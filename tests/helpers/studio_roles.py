"""tests.helpers.studio_roles -- the Roles click checks of tests/test_studio_ui.py
(Halo 3.0.7.0 round R2: Roles is a React section), driven through real
clicks, drags and keys in headless Chrome over the DevTools protocol
(tests/helpers/cdp.py), over a scratch home with a seeded catalog, a lineup
with two declared tiers and a card on a bio whose model the catalog lacks
(tools/capture_roles.py). Run as a subprocess with a scrubbed environment:

    python -m tests.helpers.studio_roles roles

The last stdout line is a JSON object of what it saw (exit 2: no Chrome).
No model is called: `POST models/test` answers through a stubbed
`model_probe.probe_model` (this process serves Studio in a thread)."""
from __future__ import annotations

import json
import shutil
import sys
import time
from contextlib import contextmanager
from pathlib import Path

import yaml

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO))
sys.path.insert(0, str(REPO / "tools"))

from tests.helpers.chrome_driver import Driver  # noqa: E402

Q = "document.querySelectorAll"
PROBE = {"ok": True, "latency_ms": 42, "error": "", "cost_line": "stub", "reply": "ok"}


def tid(name: str) -> str:
    return f"{Q}('[data-testid=\"{name}\"]')"


def card(agent: str) -> str:
    return f"[...{tid('roles-card')}].find((n) => n.dataset.agent === '{agent}')"


def tier(name: str) -> str:
    return f"document.querySelector('[data-testid=\"roles-tier\"][data-tier=\"{name}\"]')"


def tiers_on_disk(state: Path) -> dict:
    path = state / "teams" / "studio-tiers.yaml"
    for attempt in range(20):  # Windows: the canvas's save replaces the file while this reads it (PermissionError)
        try:
            text = path.read_text(encoding="utf-8")
            break
        except PermissionError:
            if attempt == 19:
                raise
            time.sleep(0.05)
    raw = yaml.safe_load(text) or {}
    return {t["name"]: list(t.get("members") or []) for t in raw.get("tiers") or []}


def ctrl(c, key: str, shift: bool = False) -> None:
    code, vk = f"Key{key.upper()}", ord(key.upper())
    mods = 2 | (8 if shift else 0)
    for kind in ("keyDown", "keyUp"):
        c.call("Input.dispatchKeyEvent", type=kind, key=key.upper() if shift else key, code=code, windowsVirtualKeyCode=vk, modifiers=mods)


def roles(c, url: str, state: Path) -> dict:
    from capture_roles import seed_catalog, seed_tiers
    out: dict = {}
    seed_catalog(state)
    seed_tiers(state, dead=True)
    lineup = state / "teams" / "studio-tiers.yaml"  # 3.1.1.0 R2: a key nothing reads, for the Config group
    lineup.write_text(lineup.read_text(encoding="utf-8") + "notes: the Config group lists this key\n", encoding="utf-8")
    c.go(url)
    out["cards"] = c.wait(f"{tid('roles-card')}.length >= 8 && {tid('roles-card')}.length", 30)
    out["tiers"] = c.js(f"[...{tid('roles-tier')}].map((t) => t.dataset.tier)")
    time.sleep(1.0)  # the first draw fits the canvas
    # every card sits inside the box of the tier the graph puts it in
    out["cards_in_tiers"] = c.js(f"""(async () => {{
      const g = (await (await fetch('/api/lineup/studio-tiers', {{headers: {{Authorization: 'Bearer ' + sessionStorage.getItem('halo-studio-token')}}}})).json()).graph;
      return g.tiers.every((t) => t.node_ids.every((id) => {{
        const r = document.querySelector(`[data-testid="roles-card"][data-id="${{id}}"]`).getBoundingClientRect();
        const b = document.querySelector(`[data-testid="roles-tier"][data-tier="${{t.name}}"]`).getBoundingClientRect();
        return r.left >= b.left - 1 && r.right <= b.right + 1 && r.top >= b.top - 1 && r.bottom <= b.bottom + 1; }})); }})()""")
    out["problem"] = c.wait(f"[...{tid('roles-problem')}].map((p) => p.textContent).find((t) => t.includes('or:vendor/gone'))", 15)
    out["config_problem"] = c.wait(f"[...{tid('roles-problem-config')}].map((p) => p.textContent).find((t) => t.includes(\"'notes'\"))", 15)
    # a card dragged into another tier box: the lineup saves with it there, and it moves into that box
    x, y, w, h = c.rect(card("implementer"))
    bx, by, bw, bh = c.rect(tier("rest"))
    c.drag(x + w / 2, y + h / 2, bx + 5, by + bh / 2)
    end = time.time() + 10
    while time.time() < end and "worker" in tiers_on_disk(state).get("leads", []):
        time.sleep(0.1)
    out["tiers_after_drag"] = tiers_on_disk(state)
    out["moved_box"] = c.wait(f"""(() => {{ const r = {card('implementer')}.getBoundingClientRect(), b = {tier('rest')}.getBoundingClientRect();
      return r.left >= b.left - 1 && r.right <= b.right + 1 && r.top >= b.top - 1 && r.bottom <= b.bottom + 1 && 'rest'; }})()""", 10)
    # the main card cannot leave tier 0: the drop snaps back with the rule, nothing is saved
    before = tiers_on_disk(state)
    x, y, w, h = c.rect(card("orchestrator"))
    bx, by, bw, bh = c.rect(tier("leads"))
    c.drag(x + w / 2, y + h / 2, bx + 5, by + bh / 2)
    out["main_toast"] = c.wait("[...document.querySelectorAll('.toast')].map((t) => t.textContent).find((t) => t.includes('tier 0'))", 10)
    time.sleep(0.6)
    out["main_unchanged"] = tiers_on_disk(state) == before
    out["main_in_top"] = c.js(f"(() => {{ const r = {card('orchestrator')}.getBoundingClientRect(), b = {tier('top')}.getBoundingClientRect(); return r.left >= b.left - 1 && r.right <= b.right + 1; }})()")
    # an edit, then Ctrl+Z puts it back
    sx, sy, sw, sh = c.rect("document.querySelector('.rc-scroll')")
    c.click(sx + sw - 12, sy + sh - 12)  # the canvas's empty corner: no card selected, the Inspector shows the lineup's fields
    c.click_on(f"{tid('roles-tab-assignment')}[0]")
    field = "document.querySelector('[data-testid=\"roles-description\"]')"
    out["description_before"] = c.wait(f"{field}?.value", 10)
    c.click_on(field)
    c.js(f"{field}.select(); 1")
    c.type_text("A description typed in the test")
    c.click(sx + sw - 12, sy + sh - 12)  # the field loses the focus: the edit commits
    out["dirty"] = c.wait(f"!!{tid('roles-dirty')}[0] && {field}.value", 10)
    ctrl(c, "z")
    out["description_after_undo"] = c.wait(f"{field}.value === {json.dumps(out['description_before'])} && {field}.value", 10)
    # the dead bio's model, tested: the stubbed probe's answer shows inline
    dead = "document.querySelector('[data-testid=\"roles-bio\"][data-name=\"dead-bio\"]')"
    c.js(f"{dead}.scrollIntoView({{block: 'center'}}); 1")  # 3.1.9.0 R2: seven auto-* bios list above it
    time.sleep(0.3)
    c.click_on(dead)
    c.wait("!!document.querySelector('[data-testid=\"bio-form\"][data-bio=\"dead-bio\"]')", 15)
    more = "document.querySelector('[data-testid=\"bio-form\"] [data-testid=\"model-select-more\"]')"  # 3.1.4.0 R4: the table is folded
    c.js(f"{more}.scrollIntoView({{block: 'center'}}); 1")
    time.sleep(0.3)
    c.click_on(more)
    out["model_rows"] = c.wait(f"{tid('model-row')}.length", 10)
    btn = "document.querySelector('[data-testid=\"bio-form\"] [data-testid=\"model-test\"]')"
    c.js(f"{btn}.scrollIntoView({{block: 'center'}}); 1")
    time.sleep(0.3)
    c.click_on(btn)
    out["probe"] = c.wait("document.querySelector('[data-testid=\"bio-form\"] [data-testid=\"model-test-result\"]')?.textContent", 10)
    out["dialogs"] = c.js("document.querySelectorAll('[role=dialog]').length")
    return out


class RolesDriver(Driver):
    """`roles`: the Roles section over capture_studio's seeded home, the model probe stubbed."""

    no_chrome = {"skip": "no Chrome found"}

    @contextmanager
    def session(self, c):
        from capture_studio import seeded_home, serve
        import halo_harness.model_probe as probe
        probe.probe_model = lambda ref, **_kw: {**PROBE, "ref": ref}
        state = seeded_home()
        srv, url = serve(state, True)
        from tests.helpers.studio_full import full
        url = full(url)  # 3.3.2.0 R3: every panel open, the arrangement this driver works in
        try:
            yield ((roles, (c, url.replace("mode=orchestra", "mode=roles").replace("feed=off", "feed=off&tour=off"), state)),)
        finally:
            srv.shutdown()
            srv.server_close()
            shutil.rmtree(state.parent, ignore_errors=True)


def main(argv: list) -> int:
    return RolesDriver(argv).main()


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
