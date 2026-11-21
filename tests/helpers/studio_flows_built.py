"""tests.helpers.studio_flows_built -- two steps of tests/helpers/studio_flows.py's driver for Agents -> 2 · Workflows
(Halo 3.6.0.2 R47), read by tests/test_studio_flows.py:

    head     R47's head line over the main panel, with no workflow open and with one open (a starter's copy); its link
             "Map" lands on 3 · Map; the 2 key brings the tab back
    built    a workflow main has just built (a `builder_done` frame) is open in the form on the next visit: a mounted
             tab left for 1 · Agents and come back to with 2; the same with an unsaved edit in the form (the form keeps
             the edit and the list marks the built one); a NEW one built while he is away, the list's read held back as he
             comes back: open once the read lands (P4 batch 12); a fresh page on Session where Workflows was never opened
    follows  3.6.0.9 V (the owner's point 34): the workflow open in the form follows its file: a plain write, a Builder
             card's write (left and come back), the form's own Save (no read, no line), an unsaved edit (kept, the
             stale line, Reload), the file removed (the form stays, Save writes it again), and a map naming a workflow
             moves the list's "on the map" tag
No model is called."""
from __future__ import annotations

import os
import time

from tests.helpers.studio_agents import key
from tests.helpers.studio_flows import P, VIEW, click, q, t, type_in

HEAD = t("flow-head")
FORM = t("flow-form")
STORED = "localStorage.getItem('halo.studio.flow-open')"


def head(c, rig) -> dict:
    out = {"head_empty": c.wait(f"!!{t('flow-empty')} && !!{HEAD} && {HEAD}.textContent", 20)}
    c.js(f"{q('[data-testid=flow-starter][data-name=plan]')}.click(); 1")
    out["head_open"] = c.wait(f"{t('flow-name')}?.value === 'my-plan' && !!{HEAD} && {HEAD}.textContent", 20)
    click(c, "flow-head-map")
    out["head_map"] = c.wait(f"{VIEW} === 'map' && {VIEW}", 20)
    c.js("document.activeElement?.blur(); 1")
    key(c, "2")
    c.wait(f"{VIEW} === 'workflows'", 20)
    return out


def _frame(c, rig, wrote: list) -> str:
    """`builder_done` as P2b sends it, published until the page has heard it (the remembered name is stored)."""
    from halo_harness.peers.identity import harness
    name = [w["name"] for w in wrote if w["kind"] == "workflow"][-1]
    for _ in range(20):
        now = time.time()
        rig.server.events.publish({"session_id": "s-flows", "harness": harness()["id"], "event": "builder_done", "agent_id": "main",
                                   "turn": 1, "data": {"id": "card-w", "outcome": "applied", "wrote": wrote, "undo": "u", "t": now}, "ts": now})
        deadline = time.time() + 1.5
        while time.time() < deadline:
            if c.js(f"{STORED} === '{name}'"):
                return name
            time.sleep(0.1)
    return ""


def _leave(c) -> None:
    c.js("document.querySelector('[data-testid=agents-view-crew]').click(); 1")
    c.wait(f"{VIEW} === 'crew'", 20)


def _back(c) -> None:
    c.js("document.activeElement?.blur(); 1")
    key(c, "2")
    c.wait(f"{VIEW} === 'workflows'", 20)


def _open(c, name: str) -> None:
    c.wait(f"!!{q(f'[data-testid=flow-item][data-name={name}]')}", 20)
    c.js(f"{q(f'[data-testid=flow-item][data-name={name}]')}.click(); 1")
    c.wait(f"{FORM}?.dataset.name === '{name}'", 20)


def built(c, rig) -> dict:
    from halo_harness.studio.server import url_for
    from tests.helpers.studio_agents_live import alt
    out: dict = {}
    wf = rig.api("GET", "crew/workflow/my-review")[1].get("workflow") or {}
    rig.api("POST", "crew/workflow/other", {"workflow": {**wf, "name": "other"}})
    _open(c, "other")
    _leave(c)
    out["heard"] = _frame(c, rig, [{"kind": "workflow", "name": "my-review", "added": True}])
    _back(c)
    out["mounted"] = c.wait(f"{FORM}?.dataset.name === 'my-review' && 'my-review'", 30)
    # an unsaved edit in the form when he comes back: the form is his; the list marks the built one
    _open(c, "other")
    type_in(c, "flow-for", "edited here")
    _leave(c)
    _frame(c, rig, [{"kind": "workflow", "name": "my-review", "added": False}])
    remembered = c.js(STORED)
    _back(c)
    # P7: waited on the event, not a time. P8: the event is his return being HANDLED (flowBuilt.takeBuilt gives up the
    # remembered name: the stored one is cleared; a workflow the list already holds needs no read, so a wait on a read
    # never comes), not the mark alone, which the frame had already set before he came back
    try:
        out["dirty_read"] = remembered == "my-review" and bool(c.wait(f"{STORED} === null && 'taken'", 20))
    except TimeoutError:
        out["dirty_read"] = f"his return was not handled in 20 s (stored {c.js(STORED)!r})"
    c.wait(f"!!{q('[data-testid=flow-item][data-name=my-review]')}?.dataset.built", 20)
    out["dirty"] = c.js(f"[{FORM}?.dataset.name, {t('flow-for')}?.value, "
                        f"{q('[data-testid=flow-item][data-name=my-review]')}?.dataset.built || '']")
    click(c, "flow-discard")
    # P4 batch 12: a NEW workflow built while he is away; he comes back before the list was read again (its read held
    # back at the server): it is kept, and open in the form once the read lands
    import threading
    from halo_harness.studio import api as A
    gate, asked, orig = threading.Event(), threading.Event(), A.dispatch

    def held(req):
        if req.method == "GET" and str(req.path) == "crew/workflows":
            asked.set()
            gate.wait(30)
        return orig(req)
    A.dispatch = held
    try:
        rig.api("POST", "crew/workflow/brand-new", {"workflow": {**wf, "name": "brand-new"}})
        _leave(c)
        out["new_heard"] = _frame(c, rig, [{"kind": "workflow", "name": "brand-new", "added": True}])
        _back(c)
        out["read_asked"] = asked.wait(20)  # P7: his arrival asked for the list (the read is held now): an event, not a time
        out["new_listed_before"] = c.js(f"!!{q('[data-testid=flow-item][data-name=brand-new]')}")
        gate.set()
        try:
            out["new_after_read"] = c.wait(f"{FORM}?.dataset.name === 'brand-new' && 'brand-new'", 20)
        except TimeoutError:
            out["new_after_read"] = f"not opened: the form shows {c.js(f'{FORM}?.dataset.name || null')!r}"
    finally:
        gate.set()
        A.dispatch = orig
    # a fresh page on Session: Workflows never opened in it
    c.go("about:blank")
    c.wait("location.href === 'about:blank'", 10)
    c.go(url_for(rig.server, "session").replace("#t=", "&tour=off#t="))
    c.wait("!!document.querySelector('[data-testid=\"section-tab\"][aria-selected=\"true\"]')", 40)
    out["fresh_heard"] = _frame(c, rig, [{"kind": "workflow", "name": "other", "added": True}, {"kind": "map", "name": "review-flow", "added": True}])
    out["fresh_section"] = c.js("document.querySelector('[data-testid=\"section-tab\"][aria-selected=\"true\"]')?.textContent || ''")
    alt(c, 2)
    c.wait(f"!!{VIEW}", 20)
    _back(c)
    out["fresh"] = c.wait(f"{FORM}?.dataset.name === 'other' && 'other'", 30)
    out["fresh_part"] = c.js(f"!!document.querySelector('{P}[data-testid=flow-form]')")
    return out


STEPS = "[...document.querySelectorAll('[data-part=\"workflows\"] [data-testid=flow-step]')].map((s) => s.dataset.name)"


def _until(c, expr: str, want, timeout: float = 12):
    """`want` once `expr` (JSON-compared) equals it within `timeout`, else what it was then: a STATE, never a time."""
    import json
    try:
        c.wait(f"JSON.stringify({expr}) === {json.dumps(json.dumps(want))}", timeout)
        return want
    except TimeoutError:
        return c.js(expr)


def follows(c, rig) -> dict:
    import threading
    from halo_harness.crew import store
    from halo_harness.studio import api as A
    from halo_harness.studio.events import bridge_for
    out: dict = {}
    base = rig.api("GET", "crew/workflow/my-review")[1]["workflow"]
    path = store.path_for("workflow", "my-review", state_dir=rig.state)

    def write(names: list, why: str = "followed") -> list:
        store.write_text(path, store.dump({**base, "for": why, "steps": [{**base["steps"][0], "name": n} for n in names]}))
        return names
    _open(c, "my-review")
    # (f) first, with no workflow write pending: a map that puts `other` on a box; the list's "on the map" tag follows
    tag = f"{q('[data-testid=flow-item][data-name=other] [data-testid=flow-item-map]')}?.dataset.tag || ''"
    # every workflow write made so far has been heard (a new workflow is in the list), so what follows is the
    # map's doing alone: on CI's Linux and macOS runners the tag once followed only because a workflow
    # write was still on its way when the map was written
    settled = store.path_for("workflow", "zz-settled", state_dir=rig.state)
    store.write_text(settled, store.dump({**base, "name": "zz-settled"}))
    out["settled"] = _until(c, f"!!{q('[data-testid=flow-item][data-name=zz-settled]')}", True)
    out["tag_before"] = c.js(tag)
    store.write_text(store.path_for("map", "follow-map", state_dir=rig.state),
                     "format: map/1\nname: follow-map\nboxes:\n- {id: o, workflow: other}\nlines:\n- {from: main, to: o, when: always}\n")
    out["tag_after"] = _until(c, tag, "on")
    os.remove(str(settled))
    out["settled_left"] = _until(c, f"!!{q('[data-testid=flow-item][data-name=zz-settled]')}", False)
    # (1) a plain write, as the Write tool makes: the open form shows the file's steps and words
    out["plain"] = [_until(c, STEPS, write(["a", "b", "c"])), _until(c, f"{t('flow-for')}?.value", "followed", 5)]
    # (2) a Builder card's write of the same name (its file, then its frame): left and come back, the form is the file
    want = write(["a", "b", "c", "d"], "built")
    _leave(c)
    _frame(c, rig, [{"kind": "workflow", "name": "my-review", "added": False}])
    _back(c)
    out["built"] = [_until(c, STEPS, want), _until(c, f"{t('flow-for')}?.value", "built", 5)]
    # (e) the form's own Save comes back from the watcher: nothing read again, no line
    asked, seen, orig = [], threading.Event(), A.dispatch

    def counted(req):
        if req.method == "GET":
            asked.append(str(req.path))
        return orig(req)

    def tap(f: dict) -> None:
        d = f.get("data") or {}
        if f.get("event") == "files_changed" and d.get("kind") == "workflows" and "my-review" in (d.get("names") or []):
            seen.set()
    taps = bridge_for(rig.server).taps
    A.dispatch = counted
    taps.append(tap)
    try:
        type_in(c, "flow-for", "saved here")
        click(c, "flow-save")
        c.wait(f"{t('flow-note')}?.innerText.startsWith('Saved my-review')", 20)
        n0 = len(asked)
        out["own_frame"] = seen.wait(15)
        mark = store.path_for("workflow", "zz-mark", state_dir=rig.state)
        store.write_text(mark, store.dump({**base, "name": "zz-mark"}))  # a later frame: the page has handled the one before
        c.wait(f"!!{q('[data-testid=flow-item][data-name=zz-mark]')}", 20)
        out["own_save"] = {"reads": asked[n0:].count("crew/workflow/my-review"), "line": c.js(f"!!{t('flow-stale')}"),
                           "for": c.js(f"{t('flow-for')}?.value")}
    finally:
        A.dispatch = orig
        taps.remove(tap)
    # (3) an unsaved edit: his text stays, the steps stay, the line says so; its button reads the file
    type_in(c, "flow-for", "typed by hand")
    held = c.js(STEPS)
    disk = write(["a", "b", "c", "d", "e"], "on disk")
    line = "my-review changed on disk while you had edits here. Save writes yours over it."
    out["dirty"] = {"line": _until(c, f"{t('flow-stale-line')}?.textContent || ''", line),
                    "for": c.js(f"{t('flow-for')}?.value"), "kept": c.js(STEPS) == held,
                    "button": c.js(f"{t('flow-stale-reload')}?.textContent || ''")}
    if c.js(f"!!{t('flow-stale-reload')}"):
        click(c, "flow-stale-reload")
    out["reloaded"] = [_until(c, STEPS, disk), c.js(f"{t('flow-for')}?.value"), c.js(f"!!{t('flow-stale')}")]
    # (d) the file removed: his form stays with the line, no Reload; Save writes it again
    path.unlink()
    out["removed"] = {"line": _until(c, f"{t('flow-stale-line')}?.textContent || ''", "my-review was removed on disk. Save writes it again."),
                      "form": c.js(f"{FORM}?.dataset.name"), "steps": c.js(STEPS), "reload": c.js(f"!!{t('flow-stale-reload')}")}
    if c.js(f"!!{t('flow-save')} && !{t('flow-save')}.disabled"):
        click(c, "flow-save")
        c.wait(f"{t('flow-note')}?.innerText.startsWith('Saved my-review')", 20)
    out["written_again"] = [path.is_file(), c.js(f"!!{t('flow-stale')}")]
    return {"follows": out}
