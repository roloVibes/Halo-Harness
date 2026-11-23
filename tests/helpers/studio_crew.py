"""tests.helpers.studio_crew -- Agents -> 1 · Agents and its builder (Halo 3.6.0.0 R1) in headless Chrome, as a first-time
user, over tests/helpers/crew_rig.py (a scratch home, a git repo, the mock upstream for Try it, the builder's scripted
model). tests/test_studio_crew.py reads what it saw:

    first     from Session, Alt+2: Agents opens on 1 · Agents, the list drawer open, no conversation, no dialog;
              the empty form says how to start; the ten starters to copy; the builder's line (model, cost, cap)
    copy      a starter's click: its copy in the form, not saved; Save: in the list, tagged new and not used yet
    edit      Run commands switched on, a careful mode picked, Save: the file has them
    make      the builder: "make a security gate" -> a preview, every widening line unticked, a ghost row in the
              list; Apply: the receipt with Undo, the agent reads only; Undo: it is gone
    write     Write it for me fills the box; Send; the preview's line; Apply: the form's instructions are the draft
    try       the cost line before; a test request; the result (reply, tools, cost) in the tab; marked seen
    delete    Delete asks on the page; Keep it
    shipped   3.6.0.15 O2-6: `planner` (ships with Halo) opened by name through Studio's edit door is read there: its
              band, every field and the model picker off, no Save, Discard or Delete, Try it there; Copy: my-planner
    made      (`made`, its own run over tests/helpers/studio_session_rig.py: a live session with a made-up helper)
              O2-6: the helper's "Save as an agent" fills the form, its note naming the helper and the body's model

    python -m tests.helpers.studio_crew [DIR]     DIR: also save studio-agents-tab.png and studio-builder-preview.png
    python -m tests.helpers.studio_crew made      the `made` run alone
No model is called beyond the mock upstream and the scripted builder."""
from __future__ import annotations

import base64
import json
import sys
from contextlib import contextmanager
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO))

from tests.helpers.chrome_driver import Driver  # noqa: E402
from tests.helpers.studio_agents import key  # noqa: E402

VIEW = "document.querySelector('[data-testid=\"agents\"]')?.dataset.view"
Q = "document.querySelector"
QA = "document.querySelectorAll"
SHOTS: list = []


def tid(t: str) -> str:
    return f"{Q}('[data-testid=\"{t}\"]')"


def click(c, t: str) -> None:
    c.wait(f"!!{tid(t)} && !{tid(t)}.disabled", 20)
    c.js(f"{tid(t)}.click(); 1")


def type_in(c, t: str, text: str) -> None:
    """Focus the field and type as a person does (Input.insertText: React sees the input event)."""
    c.wait(f"!!{tid(t)}", 20)
    c.js(f"{tid(t)}.focus(); {tid(t)}.select && {tid(t)}.select(); 1")
    c.call("Input.insertText", text=text)


def shot(c, name: str) -> None:
    if SHOTS:
        data = c.call("Page.captureScreenshot", format="png")["data"]
        (Path(SHOTS[0]) / name).write_bytes(base64.b64decode(data))


def first(c, rig) -> dict:
    c.go(rig.url("").replace("mode=agents", "mode=session"))
    c.wait(f"{QA}('[data-testid=\"section-tab\"]').length > 0", 40)
    c.js("document.activeElement?.blur(); 1")
    key(c, "2", alt=True)
    out = {"view": c.wait(f"{VIEW} === 'crew' && {VIEW}", 30), "slow_ms": rig.server.slow_ms}  # the latency flag, as it reached Studio
    c.wait(f"{QA}('[data-testid=\"crew-starter\"]').length >= 10 && !!{tid('builder-meta')}", 30)
    out["first"] = c.js(
        f"({{list: !!{Q}('.stage-drawer[data-panel-in=\"crew-list\"]'), conversation: !!{tid('builder-conversation')},"
        f" dialogs: {QA}('[role=dialog]').length, empty: {tid('crew-empty')}?.innerText.split('\\n')[0],"
        f" starters: [...{QA}('[data-testid=\"crew-starter\"]')].map((b) => b.dataset.name),"
        f" pressed: {tid('agents-view-crew')}?.getAttribute('aria-pressed'), meta: {tid('builder-meta')}?.innerText}})")
    return out


def copy(c, rig) -> dict:
    c.js(f"{Q}('[data-testid=\"crew-starter\"][data-name=\"reviewer\"]').click(); 1")
    c.wait(f"{tid('crew-name')}?.value === 'my-reviewer'", 20)
    out = {"copied": c.js(f"[{tid('crew-name')}.value, {tid('crew-note')}.innerText, {tid('crew-save')}.disabled]")}
    click(c, "crew-save")
    c.wait(f"!!{Q}('[data-testid=\"crew-item\"][data-name=\"my-reviewer\"]') && {tid('crew-note')}.innerText === 'Saved my-reviewer.'", 20)
    out["saved_row"] = c.js(f"[...{Q}('[data-testid=\"crew-item\"][data-name=\"my-reviewer\"]').querySelectorAll('.cw-tag')].map((t) => t.dataset.tag)")
    out["saved_note"] = c.js(f"{tid('crew-note')}.innerText")
    return out


def edit(c, rig) -> dict:
    click(c, "crew-use-bash")
    c.js(f"{Q}('[data-testid=\"crew-careful-ask-commands\"] input').click(); 1")
    state = f"[{tid('crew-note')}.innerText, {tid('crew-save')}.disabled, {tid('crew-use-bash')}.getAttribute('aria-checked')]"
    before = c.wait(f"{tid('crew-note')}.innerText === 'Not saved yet.' && {state}", 20)
    click(c, "crew-save")
    after = said(c, f"{tid('crew-note')}.innerText === 'Saved my-reviewer.' && {state}", state, 60)
    got = until(lambda: rig.api("GET", "crew/agent/my-reviewer")[1].get("agent") or {}, lambda a: "bash" in (a.get("uses") or []), 60)
    return {"edited": [got.get("uses"), got.get("careful")], "edit_states": [before, after]}


def said(c, expr: str, state: str, timeout: float):
    """`c.wait(expr)`; a timeout says what the page showed instead (the state the step asserts)."""
    try:
        return c.wait(expr, timeout)
    except TimeoutError:
        raise TimeoutError(f"waited {timeout}s for {expr[:120]}; the page shows {c.js(state)}") from None


def until(read, ok, timeout: float = 20):
    """`read()` again until `ok(value)` (the state a step asserts), the last value either way."""
    import time
    end, got = time.time() + timeout, None
    while time.time() < end:
        got = read()
        if ok(got):
            return got
        time.sleep(0.2)
    return got


def make(c, rig) -> dict:
    type_in(c, "builder-input", "make a security gate")
    click(c, "builder-send")
    c.wait(f"!!{tid('builder-preview')}", 30)
    out = {"ticks": c.js(f"[...{QA}('[data-testid=\"builder-tick\"]')].map((t) => [t.dataset.widen, t.checked])"),
           "ghost": c.js(f"[...{QA}('[data-testid=\"crew-ghost\"]')].map((g) => g.innerText.split('\\n')[0])"),
           "conversation": c.js(f"!!{tid('builder-conversation')}")}
    shot(c, "studio-builder-preview.png")
    click(c, "builder-apply")
    c.wait(f"!!{tid('builder-receipt')} && !!{Q}('[data-testid=\"crew-item\"][data-name=\"security-gate\"]')", 20)
    _st, got = rig.api("GET", "crew/agent/security-gate")
    out["applied"] = [got["agent"].get("uses"), got["agent"].get("careful")]
    click(c, "builder-undo")
    c.wait(f"!{Q}('[data-testid=\"crew-item\"][data-name=\"security-gate\"]') && !{tid('builder-receipt')}", 20)
    out["undone"] = rig.api("GET", "crew/agent/security-gate")[0]
    return out


def write(c, rig) -> dict:
    c.js(f"{Q}('[data-testid=\"crew-item\"][data-name=\"my-reviewer\"]').click(); 1")
    c.wait(f"{tid('crew-name')}?.value === 'my-reviewer'", 20)
    click(c, "crew-write")
    out = {"prefill": c.wait(f"{tid('builder-input')}.value && document.activeElement === {tid('builder-input')} && {tid('builder-input')}.value", 10)}
    click(c, "builder-send")
    c.wait(f"!!{tid('builder-preview')}", 30)
    out["lines"] = c.js(f"[...{QA}('[data-testid=\"builder-line\"]')].map((l) => l.dataset.kind)")
    click(c, "builder-apply")
    from tests.helpers.crew_rig import DRAFT
    out["instructions"] = c.wait(f"{tid('crew-instructions')}.value === {json.dumps(DRAFT)} && 'draft'", 20)
    return out


def try_it(c, rig) -> dict:
    c.wait(f"{tid('crew-try-estimate')}?.innerText.includes('Cost:')", 20)
    out = {"estimate": c.js(f"{tid('crew-try-estimate')}.innerText")}
    type_in(c, "crew-try-text", "Review the basket")
    click(c, "crew-try-send")
    c.wait(f"{tid('crew-try-state')}?.textContent === 'done'", 120)
    out["result"] = c.js(f"[{tid('crew-try-reply')}?.innerText, {tid('crew-try-used')}?.innerText]")
    from tests.helpers.crew_rig import TRY_REPLY
    out["reply_ok"] = out["result"][0] == TRY_REPLY
    return out


def seen(c, rig) -> dict:
    from halo_harness.crew import trial
    import time
    end, got = time.time() + 20, []
    while time.time() < end:
        got = [r.get("seen") for r in trial.recent(rig.state)]
        if got and all(got):
            break
        time.sleep(0.3)
    if c.js(f"{tid('builder-toggle')}?.getAttribute('aria-expanded') === 'true'"):
        click(c, "builder-toggle")
        c.wait(f"!{tid('builder-conversation')}", 10)
    c.js(f"{tid('crew-try-result')}.scrollIntoView({{block: 'center'}}); 1")
    shot(c, "studio-agents-tab.png")
    return {"seen": got}


def delete(c, rig) -> dict:
    click(c, "crew-delete")
    c.wait(f"!!{tid('crew-delete-ask')}", 10)
    out = {"ask": c.js(f"{tid('crew-delete-ask')}.innerText.split('\\n')[0]")}
    click(c, "crew-delete-no")
    out["kept"] = c.wait(f"!!{tid('crew-savebar')}", 10)
    out["still"] = rig.api("GET", "crew/agent/my-reviewer")[0]
    return out


SHIPPED = "planner ships with Halo: read it here; Copy makes it yours to change."


def shipped(c, rig) -> dict:
    """3.6.0.15 O2-6: a shipped agent opened by name (the edit door, as `halo agents edit planner` opens it). A control in
    a disabled fieldset is `:disabled` while its own `disabled` property stays false: the step asks `:disabled`."""
    c.go(rig.url("&edit=agent:planner"))
    c.wait(f"{tid('crew-form')}?.dataset.name === 'planner' && !!{tid('crew-readonly')}", 40)
    fields = f"{QA}('[data-testid=\"crew-fields\"] input, [data-testid=\"crew-fields\"] textarea, [data-testid=\"crew-fields\"] button')"
    out = {"shipped": c.js(
        f"({{band: {tid('crew-readonly')}.innerText, fields: {fields}.length, off: [...{fields}].every((e) => e.matches(':disabled')),"
        f" picker: !!{tid('crew-model')}?.querySelector('[data-testid=model-select]')?.matches(':disabled'), save: !!{tid('crew-save')}, discard: !!{tid('crew-discard')},"
        f" del: !!{tid('crew-delete')}, copy: !!{tid('crew-copy')}, try_it: !!{tid('crew-try-text')} && !{tid('crew-try-text')}.matches(':disabled')}})")}
    click(c, "crew-copy")
    c.wait(f"{tid('crew-name')}?.value === 'my-planner' && !{tid('crew-readonly')}", 20)
    out["shipped_copy"] = c.js(f"[{tid('crew-name')}.value, {tid('crew-note')}.innerText, !{tid('crew-name')}.matches(':disabled'), !!{tid('crew-save')}]")
    out["shipped_file"] = rig.api("GET", "crew/agent/my-planner")[0]  # not saved: nothing written
    return out


def made(c, rig, lv) -> dict:
    """3.6.0.15 O2-6: Save as an agent on a made-up helper's row (Agents -> 4 · Live) fills the form; its note names the
    helper and the filled body's model, the route's own line (studio/crew_live_api.py BUILT) letter for letter."""
    from tests.helpers.studio_map_live_steps import LWORLD, lq
    _st, r = rig.api("POST", "crew/from-live", {"session": lv.sid, "agent_id": "h3lp3r01"})  # writes nothing
    c.go(rig.url("agents", "&view=live"))
    c.wait(f"{VIEW} === 'live'", 40)
    row = lq(f'{LWORLD} [data-row="h3lp3r01"]')
    btn = f"{row}?.querySelector('[data-testid=map-save-agent]')"
    c.wait(f"!!{btn}", 30)
    c.js(f"{btn}.scrollIntoView({{block: 'nearest'}}); 1")
    c.click_on(btn)
    c.wait(f"{VIEW} === 'crew'", 20)
    note = c.wait(f"{tid('crew-note')}?.innerText.startsWith('Built from') && {tid('crew-note')}.innerText", 20)
    return {"made": {"note": note, "line": r.get("line"), "model": (r.get("agent") or {}).get("model"), "helper": (r.get("from") or {}).get("name"),
                     "save": c.js(f"!!{tid('crew-save')} && !{tid('crew-name')}.matches(':disabled')")}}


class MadeDriver(Driver):
    no_chrome = {"skip": "no Chrome found"}
    width, height = 1500, 900

    @contextmanager
    def session(self, c):
        from tests.helpers.studio_live_rig import Live
        from tests.helpers.studio_map_live import EXTRA, seed
        from tests.helpers.studio_session_rig import StudioSessionRig
        with StudioSessionRig() as rig:
            seed(rig)
            lv = Live(rig, extra=EXTRA[:1])
            lv.rows["h3lp3r01"]["crew"] = {"map": "shop", "box": "main", "made_up": True}
            lv.refresh(map="shop")
            yield ((made, (c, rig, lv)),)


class CrewDriver(Driver):
    no_chrome = {"skip": "no Chrome found"}
    width, height = 1500, 900

    @contextmanager
    def session(self, c):
        from tests.helpers.crew_rig import CrewRig
        SHOTS[:] = self.argv[:1]
        with CrewRig() as rig:
            rig.studio()
            yield tuple((fn, (c, rig)) for fn in (first, copy, edit, make, write, try_it, seen, delete, shipped))


if __name__ == "__main__":
    sys.exit(MadeDriver(sys.argv[2:]).main() if sys.argv[1:2] == ["made"] else CrewDriver(sys.argv[1:]).main())
