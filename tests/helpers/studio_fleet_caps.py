"""tests.helpers.studio_fleet_caps -- the Studio Fleet Capabilities panel of
Halo 3.0.6.0 round R6 in headless Chrome over the DevTools protocol, over
tests/helpers/studio_fleet_rig.py (this harness `you@studio` with its seeded
catalog: an RTX 4090, design and film apps; the member `kali@lab`, whose
catalog the hub asks it for once: gridcraft). Run through
tests/helpers/studio_fleet.py:

    python -m tests.helpers.studio_fleet caps

* the about line is there; the map's harness boxes carry their chips;
* "gridcraft" typed in Who can... (the panel's compact face) ranks the member
  first with what matched; clicking it picks the member (its map box lights,
  its session's main agent is selected);
* Expand shows both spec cards, the member's focused; its gridcraft server
  opens to its two tools;
* People's "specs" link on this harness focuses its own card;
* 3.1.8.0 R4: the recall box under Who can... (the full face) finds a finding
  seeded on this harness (the fake embedder, tests/helpers/knowledge_rig.py),
  with its chip, its id, who and when.
"""
from __future__ import annotations

CARD = "document.querySelector('[data-testid=\"fleet-caps-card\"][data-id=\"{}\"]')"


def caps(c, rig) -> dict:
    from tests.helpers.studio_fleet_member import MEMBER
    from tests.helpers.studio_fleet_panels import open_strip, seen
    out: dict = {}
    c.go(rig.url("fleet"))
    out["about"] = c.wait("document.querySelector('[data-testid=\"fleet-capabilities\"] .panel-about')?.textContent", 30)
    open_strip(c, "fleet-capabilities")  # 3.1.4.0 R1: a strip on the right edge by default
    out["box_chips"] = c.wait("document.querySelectorAll('[data-testid=\"fleet-box-chip\"]').length >= 6 && Object.fromEntries([...document.querySelectorAll('[data-testid=\"fleet-box\"]')]"
                              ".map((b) => [b.querySelector('.fm-box-label').textContent, [...b.querySelectorAll('[data-testid=\"fleet-box-chip\"] text')].map((t) => t.textContent)]))", 30)
    who = "document.querySelector('[data-testid=\"fleet-capabilities\"] [data-testid=\"fleet-who-input\"]')"
    c.click_on(who)  # on the panel's compact face
    c.type_text("gridcraft")
    out["who"] = c.wait("document.querySelectorAll('[data-testid=\"fleet-who-result\"]').length && [...document.querySelectorAll('[data-testid=\"fleet-who-result\"]')]"
                        ".map((r) => r.querySelector('.fwho-name').textContent)", 15)
    out["who_why"] = c.js("document.querySelector('[data-testid=\"fleet-who-result\"] .fwho-why')?.textContent || ''")
    c.click_on("document.querySelector('[data-testid=\"fleet-who-result\"]')")
    out["picked_box"] = c.wait("document.querySelector('[data-testid=\"fleet-box\"][data-who]')?.querySelector('.fm-box-label')?.textContent", 10)
    out["selected"] = c.wait("document.querySelector('[data-testid=\"fleet-node\"][data-selected]')?.dataset.key", 10)
    c.click_on("document.querySelector('[data-testid=\"fleet-capabilities\"] [data-testid=\"panel-compact\"]')")  # Expand: the spec cards
    out["cards"] = c.wait("document.querySelectorAll('[data-testid=\"fleet-caps-card\"]').length === 2 && "
                          "[...document.querySelectorAll('[data-testid=\"fleet-caps-card\"] .fcap-head b')].map((b) => b.textContent)", 20)
    member = CARD.format(MEMBER)
    out["picked_card"] = c.wait(f"{member}?.dataset.focus === 'true' && 'focused'", 10)
    out["member_servers"] = c.js(f"[...{member}.querySelectorAll('[data-testid=\"fleet-caps-server\"]')].map((s) => s.dataset.name)")
    summary = f"{member}.querySelector('[data-testid=\"fleet-caps-server\"] summary')"
    seen(c, summary)
    c.click_on(summary)
    out["member_tools"] = c.wait(f"[...{member}.querySelectorAll('[data-testid=\"fleet-caps-tool\"] b')].map((b) => b.textContent).join(',')", 10)
    out.update(recall(c, rig))
    local = rig.hub.state.identity["id"]
    out["local_servers"] = c.js(f"[...{CARD.format(local)}.querySelectorAll('[data-testid=\"fleet-caps-server\"]')].map((s) => s.dataset.name)")
    out["caps_asks"] = len([d for d in rig.member_cmds if d.get("cmd") == "capabilities"])
    c.click_on("document.querySelector('[data-testid=\"fleet-people\"] [data-testid=\"panel-compact\"]')")
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
