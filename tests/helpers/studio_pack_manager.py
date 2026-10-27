"""tests.helpers.studio_pack_manager -- the Pack Manager checks of
tests/test_packs_manager_ui.py (Halo 3.2.0.0 R6), real keys and clicks in
headless Chrome through the driver base, over a scratch home with no pack
installed (the shipped Documentation Review pack is in Sources); this process
serves Studio in a thread with the live feed on (no provider, no model call):

1. Packs is the seventh tab, Alt+7 opens it (Setup the eighth, 3.3.0.0 R1): Installed is empty, Sources
   lists the shipped doc-review with Install;
2. Install: the row shows, disabled, the last action's lines are install's;
3. Details: the API range beside this Halo's, no dependency, the contributes
   block; a Grant toggle on a disabled pack picks it for Enable;
4. Enable (with the picked grant): the row runs, 1/3 granted, the pack's own
   section tab comes after Setup on Alt+9; a Grant toggle on the enabled pack
   grants at once (2/3);
4b. 3.2.0.0 R7: Update from a newer source asks first with the dry run's lines
   (its migration note), then swaps it in: Roll back to 1.0.0 shows, Details
   names the grant the new version asks for; Roll back brings 1.0.0 back;
5. Templates: Run review opens Orchestra's Start view with the workflow form
   filled in (the ref, its inputs, style at its default);
5b. 3.2.1.0 R2: "a blank goal instead" leaves the goal form with the picker
   under it ("or run a pack's workflow": the running pack's workflows); a pick
   fills in the same form;
6. Disable: the row reads disabled, 0/3, the section tab is gone, Templates
   says enable it first; Orchestra's Start view has no picker;
7. Remove: the confirm names the command (and --keep-config when ticked);
   Remove deletes the pack: the row goes, Sources offers Install again.

The last stdout line is the JSON of what it saw (exit 2: no Chrome)."""
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
from tests.helpers.studio_packs_steps import CUR, TABS, alt, press, q, qa  # noqa: E402

ROW = "[data-testid=pm-installed-row][data-id=doc-review]"
SRC = "[data-testid=pm-source][data-kind=shipped] [data-testid=pm-source-pack][data-id=doc-review]"


def _text(sel: str) -> str:
    return f"({q(sel)}?.textContent || '')"


def w(c, expr: str, timeout: float = 20):
    """`c.wait`; on a timeout a screenshot lands at $PM_SHOT when it is set (debugging a red run)."""
    try:
        return c.wait(expr, timeout)
    except TimeoutError:
        import os
        if os.environ.get("PM_SHOT"):
            c.shot(os.environ["PM_SHOT"])
        raise


def section(c, url, ctx) -> dict:
    out: dict = {}
    c.go(url)
    w(c, f"{TABS}.length >= 8", 40)
    out["tabs"] = c.js(f"{TABS}.map((t) => t.querySelector('.tab-label').textContent)")
    out["kbds"] = c.js(f"{TABS}.map((t) => t.dataset.kbd || '')")  # 3.3.2.0 R1: the icon rail keeps the key as data-kbd, never printed
    alt(c, 7)
    out["alt7"] = w(c, f"{CUR}.startsWith('Packs') && {CUR}", 10)
    out["empty"] = bool(w(c, f"!!{q('[data-testid=pm-installed-empty]')}", 30))
    out["source_install"] = w(c, _text(f"{SRC} [data-testid=pm-install]"), 20)
    out["panels"] = c.js(f"{qa('[data-section=packs] .panel-title')}.map((t) => t.textContent)")
    return out


def install(c, url, ctx) -> dict:
    press(c, q(f"{SRC} [data-testid=pm-install]"))
    try:
        w(c, f"!!{q(ROW)}", 30)
    except TimeoutError:
        raise TimeoutError(f"no row; the last lines: {c.js(_text('[data-testid=pm-last]'))!r}, toasts: "
                           f"{c.js(qa('.toast') + '.map((t) => t.textContent)')!r}")
    return {"installed_state": w(c, _text(f"{ROW} [data-testid=pm-state]"), 10),
            "installed_last": w(c, f"{_text('[data-testid=pm-last] .pm-lines')}.split('\\n')[0]", 10),
            "source_after": w(c, _text(f"{SRC} [data-testid=pm-source-installed]"), 15),
            "on_disk": (ctx["state"] / "packs" / "doc-review" / "pack.yaml").is_file()}


def details(c, url, ctx) -> dict:
    w(c, f"{q('[data-testid=pm-details-body]')}?.dataset.id === 'doc-review'", 20)
    out = {"api": c.js(_text("[data-testid=pm-api]")), "requires": c.js(_text("[data-testid=pm-requires]")),
           "contributes": c.js(_text("[data-testid=pm-contributes]")),
           "perms": c.js(f"{qa('[data-testid=pm-perm]')}.map((p) => p.dataset.name)")}
    press(c, q("[data-testid=pm-grant][data-name=bash]"))
    out["picked"] = w(c, f"{q('[data-testid=pm-grant][data-name=bash]')}?.checked === true", 10)
    out["enable_label"] = w(c, _text(f"{ROW} [data-testid=pm-enable]") + ".includes('1 grant') && " + _text(f"{ROW} [data-testid=pm-enable]"), 10)
    out["enable_title"] = c.js(f"{q(ROW + ' [data-testid=pm-enable]')}?.title")
    return out


def enable(c, url, ctx) -> dict:
    press(c, q(f"{ROW} [data-testid=pm-enable]"))
    w(c, f"{q(ROW)}?.dataset.state === 'running'", 30)
    out = {"granted": w(c, _text(f"{ROW} [data-testid=pm-grants]") + ".startsWith('1/3') && " + _text(f"{ROW} [data-testid=pm-grants]"), 15)}
    w(c, f"{TABS}.some((t) => t.textContent.startsWith('Docs review'))", 20)
    out["tabs_on"] = c.js(f"{TABS}.map((t) => t.querySelector('.tab-label').textContent)")
    out["pack_kbd"] = c.js(f"{TABS}.find((t) => t.textContent.startsWith('Docs review'))?.dataset.kbd")
    press(c, q("[data-testid=pm-grant][data-name=hooks]"))
    out["granted_more"] = w(c, _text(f"{ROW} [data-testid=pm-grants]") + ".startsWith('2/3') && " + _text(f"{ROW} [data-testid=pm-grants]"), 20)
    rec = json.loads((ctx["state"] / "packs" / "state.json").read_text(encoding="utf-8"))["installed"]["doc-review"]
    out["state_json"] = [rec.get("enabled"), rec.get("granted")]
    return out


def update_rollback(c, url, ctx) -> dict:
    """3.2.0.0 R7: a newer source (1.0.1 also requests network, one migration note); Update asks with the dry run's
    lines, then swaps it in; Details names the grant it asks for; Roll back brings 1.0.0 back."""
    from halo_harness.packs import state as S
    from tests.helpers.packs_home import DOC_REVIEW
    newer = ctx["state"].parent / "next" / "doc-review"
    shutil.copytree(DOC_REVIEW, newer, ignore=shutil.ignore_patterns("__pycache__"))
    text = (newer / "pack.yaml").read_text(encoding="utf-8").replace("version: 1.0.0", "version: 1.0.1")
    text = text.replace('permissions: ["mcp:lint", hooks, bash]', 'permissions: ["mcp:lint", hooks, bash, network]')
    (newer / "pack.yaml").write_text(text + "  - {from: 1.0.0, to: 1.0.1, note: it also asks for network}\n", encoding="utf-8")
    S.put("doc-review", {"source": str(newer)})
    press(c, q(f"{ROW} [data-testid=pm-update]"))
    w(c, f"!!{q('[data-testid=pm-update-dialog]')}", 15)
    out = {"update_lines": c.js(f"{_text('[data-testid=pm-update-lines]')}.split('\\n')"),
           "update_cmd": c.js(_text("[data-testid=pm-update-cmd]")), "untouched": not (ctx["state"] / "packs" / "doc-review.previous").exists()}
    press(c, q("[data-testid=pm-update-yes]"))
    try:
        w(c, f"!{q('[data-testid=pm-update-dialog]')}", 10)
    except TimeoutError:  # the Windows runner's click on Apply missed once (ee033ec): click the button itself
        c.js(f"{q('[data-testid=pm-update-yes]')}?.click(); 1")
        out["update_yes_by"] = "element"
        w(c, f"!{q('[data-testid=pm-update-dialog]')}", 15)
    last = _text('[data-testid=pm-last] .pm-lines')
    out["updated_last"] = w(c, f"/(1[.]0[.]0 -> 1[.]0[.]1|stays as it is|is up to date)/.test({last}) && {last}.split('\\n')", 30)
    try:
        out["rollback_label"] = w(c, _text(f"{ROW} [data-testid=pm-rollback]"), 30)
    except TimeoutError as e:
        raise TimeoutError(f"{e}; the update said {out['updated_last']}") from None
    out["version_after"] = c.js(_text(f"{ROW} .pm-row-ver"))
    press(c, q(f"{ROW} .pm-row-main"))
    out["compat_after"] = w(c, f"{qa('[data-testid=pm-compat] li')}.map((l) => l.textContent).filter((t) => t.includes('network'))", 20)
    press(c, q(f"{ROW} [data-testid=pm-rollback]"))
    w(c, f"!{q(ROW + ' [data-testid=pm-rollback]')} && {_text(ROW + ' .pm-row-ver')} === '1.0.0'", 30)
    out["rolled_last"] = w(c, f"{_text('[data-testid=pm-last] .pm-lines')}.split('\\n')[0]", 10)
    out["previous_gone"] = not (ctx["state"] / "packs" / "doc-review.previous").exists()
    return out


def templates(c, url, ctx) -> dict:
    run = q("[data-testid=pm-workflow][data-ref='doc-review/review'] [data-testid=pm-run-workflow]")
    w(c, f"!!{run}", 20)
    out = {"lineups": c.js(f"{qa('[data-testid=pm-template][data-kind=lineup]')}.map((r) => r.dataset.name)")}
    press(c, run)
    out["section_after_run"] = w(c, f"{CUR}.startsWith('Orchestra') && {CUR}", 15)
    w(c, f"!!{q('[data-testid=orchestra-workflow-form]')}", 20)
    out["wf_ref"] = c.js(_text("[data-testid=orchestra-workflow-ref]"))
    out["wf_inputs"] = c.js(f"{qa('[data-testid=orchestra-workflow-input]')}.map((i) => [i.dataset.key, i.value])")
    out["wf_title"] = c.js(_text(".fl-start-title"))
    alt(c, 7)
    w(c, f"{CUR}.startsWith('Packs')", 10)
    return out


PICK = q("[data-testid=orchestra-workflow-pick]")


def picker(c, url, ctx) -> dict:
    """3.2.1.0 R2: Orchestra's Start view with no workflow filled in: the picker under the goal form; a pick fills in
    the form Run <workflow> fills."""
    alt(c, 6)
    w(c, f"{CUR}.startsWith('Orchestra') && !!{q('[data-testid=orchestra-workflow-form]')}", 15)
    press(c, q("[data-testid=orchestra-workflow-clear]"))
    w(c, f"!!{PICK}", 20)
    out = {"pick_options": c.js(f"[...{PICK}.options].map((o) => o.value)"),
           "pick_label": c.js(_text("[data-testid=orchestra-workflow-picker] label")),
           "pick_under_goal": c.js(f"!!{q('[data-testid=orchestra-goal-form] ~ [data-testid=orchestra-workflow-picker]')}")}
    c.js(f"(() => {{ const s = {PICK}; const set = Object.getOwnPropertyDescriptor(HTMLSelectElement.prototype, 'value').set; "
         f"set.call(s, 'doc-review/review'); s.dispatchEvent(new Event('change', {{bubbles: true}})); return 1; }})()")
    w(c, f"!!{q('[data-testid=orchestra-workflow-form]')}", 15)
    out["picked_ref"] = c.js(_text("[data-testid=orchestra-workflow-ref]"))
    out["picked_inputs"] = c.js(f"{qa('[data-testid=orchestra-workflow-input]')}.map((i) => [i.dataset.key, i.value])")
    out["picked_title"] = c.js(_text(".fl-start-title"))
    press(c, q("[data-testid=orchestra-workflow-clear]"))
    w(c, f"!!{PICK}", 10)
    alt(c, 7)
    w(c, f"{CUR}.startsWith('Packs')", 10)
    return out


def disable(c, url, ctx) -> dict:
    press(c, q(f"{ROW} [data-testid=pm-disable]"))
    w(c, f"{q(ROW)}?.dataset.state === 'disabled'", 30)
    w(c, f"!{TABS}.some((t) => t.textContent.startsWith('Docs review'))", 20)
    out = {"disabled_state": c.js(_text(f"{ROW} [data-testid=pm-state]")), "disabled_grants": c.js(_text(f"{ROW} [data-testid=pm-grants]")),
           "disabled_enable": c.js(f"!!{q(ROW + ' [data-testid=pm-enable]')}"),
           "tabs_off": c.js(f"{TABS}.map((t) => t.querySelector('.tab-label').textContent)"),
           "templates_off": bool(w(c, f"!!{q('[data-testid=pm-templates-off]')}", 10))}
    alt(c, 6)  # 3.2.1.0 R2: no running pack with a workflow, no picker
    w(c, f"{CUR}.startsWith('Orchestra') && !!{q('[data-testid=orchestra-goal-form]')}", 15)
    out["picker_off"] = bool(w(c, f"!{PICK}", 15))
    alt(c, 7)
    w(c, f"{CUR}.startsWith('Packs')", 10)
    return out


def remove(c, url, ctx) -> dict:
    press(c, q(f"{ROW} [data-testid=pm-remove]"))
    w(c, f"!!{q('[data-testid=pm-remove-dialog]')}", 10)
    out = {"remove_cmd": c.js(_text("[data-testid=pm-remove-cmd]"))}
    press(c, q("[data-testid=pm-keep-config]"))
    out["remove_cmd_keep"] = w(c, _text("[data-testid=pm-remove-cmd]") + ".endsWith('--keep-config') && " + _text("[data-testid=pm-remove-cmd]"), 10)
    press(c, q("[data-testid=pm-keep-config]"))
    w(c, f"!{_text('[data-testid=pm-remove-cmd]')}.endsWith('--keep-config')", 10)
    out["on_disk_before"] = (ctx["state"] / "packs" / "doc-review").is_dir()
    press(c, q("[data-testid=pm-remove-yes]"))
    w(c, f"!{q(ROW)} && !!{q('[data-testid=pm-installed-empty]')}", 30)
    out["removed_last"] = w(c, f"{_text('[data-testid=pm-last] .pm-lines')}.split('\\n')[0]", 10)
    out["install_again"] = w(c, _text(f"{SRC} [data-testid=pm-install]"), 15)
    out["on_disk_after"] = (ctx["state"] / "packs" / "doc-review").exists()
    return out


class PackManagerDriver(Driver):
    no_chrome = {"skip": "no Chrome found"}

    @contextmanager
    def session(self, c):
        from capture_studio import seeded_home, serve
        from halo_harness.packs import bio_models
        from tests.helpers.workflow_rig import TOOLS_ROW
        state = seeded_home()
        bio_models.ROWS = lambda _s, _c: [dict(TOOLS_ROW)]
        srv, url = serve(state, True)
        url = url.replace("mode=orchestra&feed=off", "mode=roles&tour=off&view=workspace")
        ctx = {"state": state, "srv": srv}
        try:
            yield tuple((fn, (c, url, ctx)) for fn in (section, install, details, enable, update_rollback, templates, picker, disable,
                                                remove))
        finally:
            bio_models.ROWS = None
            srv.shutdown()
            srv.server_close()
            shutil.rmtree(state.parent, ignore_errors=True)


if __name__ == "__main__":
    sys.exit(PackManagerDriver(sys.argv[1:]).main())
