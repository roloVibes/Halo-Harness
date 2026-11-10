"""tests.helpers.studio_fleet_caps -- the capabilities and "Who can..." of Halo 3.0.6.0 round R6 in headless Chrome over
the DevTools protocol, over tests/helpers/studio_fleet_rig.py (this harness `you@studio` with its seeded catalog: an
RTX 4090, design and film apps; the member `kali@lab`, whose catalog the hub asks it for once: gridcraft). 3.3.16.0 R2
"the Fleet fold": the Capabilities panel went with the Fleet section -- a machine's spec card is its summary's Specs
page on Agents -> Live (fleet scope), under the "Who can..." box and over the recall box. Run through
tests/helpers/studio_fleet.py:

    python -m tests.helpers.studio_fleet caps

* each machine node on Live carries its chips;
* this harness's Specs page: its card; "gridcraft" typed in Who can... ranks the member first with what matched;
  clicking it picks the member (its box lights, its summary's Specs page with its card focused);
* the member's gridcraft server opens to its two tools;
* People's "specs" link on this harness's summary focuses its own card;
* 3.1.8.0 R4: the recall box under the card finds a finding seeded on this harness (the fake embedder,
  tests/helpers/knowledge_rig.py), with its chip, its id, who and when.
"""
from __future__ import annotations

CARD = "document.querySelector('[data-testid=\"fleet-caps-card\"][data-id=\"{}\"]')"
PAGE = "document.querySelector('[data-testid=\"machine-page\"]')"


def specs_of(c, hid: str) -> None:
    """The machine's summary on Live, then its Specs page (the Edit row)."""
    from tests.helpers.studio_agents_fleet import press
    press(c, f"document.querySelector('[data-testid=\"live-machine\"][data-harness=\"{hid}\"]')",
          f"document.querySelector('[data-testid=\"machine-summary\"]')?.dataset.harness === '{hid}'", 15)
    press(c, "document.querySelector('[data-testid=\"machine-edit-specs\"]')", f"!!{PAGE} && !!{CARD.format(hid)}", 20)


def caps(c, rig) -> dict:
    from tests.helpers.studio_fleet_member import MEMBER
    from tests.helpers.studio_fleet_panels import open_strip, seen
    out: dict = {}
    local = rig.hub.state.identity["id"]
    c.go(rig.url("fleet"))
    out["box_chips"] = c.wait("document.querySelectorAll('[data-testid=\"fleet-box-chip\"]').length >= 6 && Object.fromEntries([...document.querySelectorAll('[data-testid=\"live-machine\"]')]"
                              ".map((b) => [b.querySelector('.rlm-name').textContent, [...b.querySelectorAll('[data-testid=\"fleet-box-chip\"]')].map((t) => t.textContent)]))", 30)
    open_strip(c, "roles-inspector")
    specs_of(c, local)
    out["about"] = c.js(f"{PAGE}.dataset.block")
    cards = [c.js(f"{CARD.format(local)}.querySelector('.fcap-head b').textContent")]
    out["local_servers"] = c.js(f"[...{CARD.format(local)}.querySelectorAll('[data-testid=\"fleet-caps-server\"]')].map((s) => s.dataset.name)")
    who = "document.querySelector('[data-testid=\"fleet-who-input\"]')"
    c.click_on(who)
    c.type_text("gridcraft")
    out["who"] = c.wait("document.querySelectorAll('[data-testid=\"fleet-who-result\"]').length && [...document.querySelectorAll('[data-testid=\"fleet-who-result\"]')]"
                        ".map((r) => r.querySelector('.fwho-name').textContent)", 15)
    out["who_why"] = c.js("document.querySelector('[data-testid=\"fleet-who-result\"] .fwho-why')?.textContent || ''")
    c.click_on("document.querySelector('[data-testid=\"fleet-who-result\"]')")
    member = CARD.format(MEMBER)
    out["picked_box"] = c.wait("document.querySelector(`[data-testid=\"live-machine\"][data-harness=\"${document.querySelector('[data-testid=\"fleet-box\"][data-who]')?.dataset.key.slice(2)}\"] .rlm-name`)?.textContent", 10)
    out["selected"] = c.wait(f"!!{member} && document.querySelector('[data-testid=\"live-inspector\"]')?.dataset.pick === 'machine' && '{MEMBER}'", 10)
    out["picked_card"] = c.wait(f"{member}?.dataset.focus === 'true' && 'focused'", 10)
    cards.append(c.js(f"{member}.querySelector('.fcap-head b').textContent"))
    out["cards"] = cards
    out["member_servers"] = c.js(f"[...{member}.querySelectorAll('[data-testid=\"fleet-caps-server\"]')].map((s) => s.dataset.name)")
    summary = f"{member}.querySelector('[data-testid=\"fleet-caps-server\"] summary')"
    seen(c, summary)
    c.click_on(summary)
    out["member_tools"] = c.wait(f"[...{member}.querySelectorAll('[data-testid=\"fleet-caps-tool\"] b')].map((b) => b.textContent).join(',')", 10)
    out.update(recall(c, rig))
    out["caps_asks"] = len([d for d in rig.member_cmds if d.get("cmd") == "capabilities"])
    c.click_on("document.querySelector('[data-testid=\"machine-page-back\"]')")
    from tests.helpers.studio_agents_fleet import press
    press(c, f"document.querySelector('[data-testid=\"live-machine\"][data-harness=\"{local}\"]')",
          f"document.querySelector('[data-testid=\"machine-summary\"]')?.dataset.harness === '{local}'", 15)
    specs = f"document.querySelector('[data-testid=\"fleet-person\"][data-id=\"{local}\"] [data-testid=\"fleet-person-specs\"]')"
    c.wait(f"!!{specs}", 10)
    seen(c, specs)
    c.click_on(specs)
    out["specs_focus"] = c.wait(f"{CARD.format(local)}?.dataset.focus === 'true' && 'focused'", 10)
    return out


def recall(c, rig) -> dict:
    """3.1.8.0 R4: a finding written here, then "basket total" in the recall box, on the fake embedder."""
    from halo_harness.knowledge.store import write
    from tests.helpers.knowledge_rig import embedder
    from tests.helpers.studio_fleet_panels import seen
    f = write("finding", "basket total rounds half up with decimal", evidence=["tests: `pytest -q` exit 0, 5 passed"],
              by="gate", state_dir=rig.state)
    box = "document.querySelector('[data-testid=\"fleet-recall-input\"]')"
    with embedder():
        seen(c, box)
        c.click_on(box)
        c.type_text("basket total")
        hits = c.wait("document.querySelectorAll('[data-testid=\"fleet-recall-hit\"]').length && "
                      "[...document.querySelectorAll('[data-testid=\"fleet-recall-hit\"]')].map((h) => [h.dataset.kind, "
                      "h.querySelector('.frec-title').textContent, h.querySelector('[data-testid=\"fleet-recall-meta\"]')?.textContent || ''])", 20)
    return {"recall_id": f["id"], "recall_when": f["when"][:10], "recall_hits": hits}
