"""tests.helpers.studio_packs_roles -- the Roles-over-packs checks of
tests/test_packs_roles_studio.py (Halo 3.2.0.0 R2), real clicks in headless
Chrome through the driver base, over a scratch home with the shipped lineups
(halo-dev-cycle active) and the doc-review fixture pack installed and
enabled, a one-row catalog with a long context (`bio_models.ROWS`; this
process serves Studio in a thread, no provider, no model call):

1. Lineups and Bios: the group boxes in order (yours, project, pack
   doc-review, shipped), the empty ones collapsed, a pack row's actions;
2. Preview: the pack's lineup on the canvas, the Inspector's "from pack
   doc-review, read-only"; the pack's bio in the form, read-only, its model;
3. Clone: the writer bio (no collision: your writer with from_pack), again
   (yours has it: the confirm, Replace), the reviewer (Halo ships one: the
   confirm, another name); Customize: the lineup copied and opened;
4. Apply on the pack's row: the dialog names the pack and the lineup it
   replaces; Apply writes config.json only;
5. a file of yours named like the pack's reviewer: its row shadows, the
   pack's group says so; the pack disabled: its group is gone.

The last stdout line is the JSON of what it saw (exit 2: no Chrome)."""
from __future__ import annotations

import hashlib
import json
import shutil
import sys
import time
from contextlib import contextmanager
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO))
sys.path.insert(0, str(REPO / "tools"))

from tests.helpers.chrome_driver import Driver  # noqa: E402

LONG = [{"ref": "ol:long-1", "provider": "ollama", "context_tokens": 262144, "price_in_per_m": 0}]


def q(sel: str) -> str:
    return f"document.querySelector({json.dumps(sel)})"


def panel_groups(panel: str) -> str:
    return f"[...document.querySelectorAll('[data-testid=\"{panel}\"] [data-testid=\"roles-group\"]')]"


def row(kind: str, name: str) -> str:
    return q(f'[data-testid="{kind}"][data-name="{name}"]')


def act(kind: str, name: str, which: str) -> str:
    return f"{row(kind, name)}.closest('li').querySelector('[data-testid=\"roles-pack-{which}\"]')"


def press(c, expr: str) -> None:
    """A real click on `expr`, once it is scrolled into view and has settled there."""
    c.wait(f"!!({expr})", 10)
    c.js(f"({expr}).scrollIntoView({{block: 'center'}}); 1")
    time.sleep(0.3)
    c.click_on(expr)


def type_into(c, expr: str, text: str) -> None:
    c.js(f"""(() => {{ const i = {expr}; const set = Object.getOwnPropertyDescriptor(HTMLInputElement.prototype, 'value').set;
      set.call(i, {json.dumps(text)}); i.dispatchEvent(new Event('input', {{bubbles: true}})); return 1; }})()""")


def reload(c, url: str) -> None:
    """A fresh page (the same URL again is only a fragment change, which keeps the lists)."""
    c.go("about:blank")
    c.wait("location.href === 'about:blank'", 10)
    c.go(url)


def _hashes(folder: Path) -> dict:
    return {p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted(folder.glob("*.yaml"))}


def groups(c, url: str, state: Path) -> dict:
    out: dict = {}
    c.go(url)
    c.wait(f"!!{row('roles-lineup', 'doc-review--review')} && !!{row('roles-bio', 'doc-review--writer')}", 40)
    for key, panel in (("lineup_groups", "roles-lineups-list"), ("bio_groups", "roles-bios-body")):
        out[key] = c.js(f"{panel_groups(panel)}.map((g) => [g.dataset.group, g.open, g.dataset.empty !== undefined, "
                        f"g.querySelector('.rsg-label').textContent])")
    out["pack_actions"] = c.js(f"[...{row('roles-lineup', 'doc-review--review')}.closest('li').querySelectorAll('button')].map((b) => b.textContent).slice(1)")
    out["bio_actions"] = c.js(f"[...{row('roles-bio', 'doc-review--reviewer')}.closest('li').querySelectorAll('button')].map((b) => b.textContent).slice(1)")
    return out


def preview(c, url: str, state: Path) -> dict:
    out: dict = {}
    press(c, act("roles-lineup", "doc-review--review", "preview"))
    out["canvas"] = c.wait(f"{q('[data-testid=roles-canvas]')}?.dataset.lineup === 'doc-review--review' && 'doc-review--review'", 20)
    out["readonly"] = c.wait(f"{q('[data-testid=roles-inspector-readonly]')}?.textContent", 10)
    out["bar_scope"] = c.js(f"{q('.rc-bar .rc-scope')}?.textContent")
    press(c, act("roles-bio", "doc-review--reviewer", "preview"))
    form = q('[data-testid="bio-form"][data-bio="doc-review--reviewer"]')
    c.wait(f"!!{form}", 15)
    out["bio_readonly"] = c.js(f"{form}.querySelector('[data-testid=bio-readonly]')?.textContent")
    out["bio_disabled"] = c.js(f"{form}.querySelector('fieldset.rb-fields').disabled")
    out["bio_buttons"] = c.js(f"[!!{form}.querySelector('[data-testid=bio-customize]'), !!{form}.querySelector('[data-testid=bio-save]')]")
    out["bio_model"] = c.wait(f"{form}.querySelector('[data-testid=bio-model-info]')?.textContent", 10)
    return out


def clones(c, url: str, state: Path) -> dict:
    out: dict = {}
    pack_files = _hashes(state / "packs" / "doc-review" / "agents")
    press(c, act("roles-bio", "doc-review--writer", "clone"))
    out["writer_row"] = c.wait(f"{row('roles-bio', 'writer')}?.closest('[data-testid=roles-group]').dataset.group", 15)
    out["writer_chip"] = c.js(f"{row('roles-bio', 'writer')}.textContent.includes('from doc-review@1.0.0')")
    writer = state / "agents" / "writer.yaml"
    out["writer_file"] = writer.is_file() and "from_pack: doc-review@1.0.0" in writer.read_text(encoding="utf-8")
    before = writer.read_bytes()
    press(c, act("roles-bio", "doc-review--writer", "clone"))
    dlg = q('[data-testid="roles-clone-dialog"]')
    out["yours_title"] = c.wait(f"{dlg}?.querySelector('.dialog-title')?.textContent", 10)
    out["unwritten_before_confirm"] = writer.read_bytes() == before
    out["replace_label"] = c.js(f"{dlg}.querySelector('[data-testid=roles-clone-go]').textContent")
    press(c, f"{dlg}.querySelector('[data-testid=roles-clone-go]')")
    out["replaced_closed"] = c.wait(f"!{dlg}", 10)
    press(c, act("roles-bio", "doc-review--reviewer", "clone"))
    out["shipped_title"] = c.wait(f"{dlg}?.querySelector('.dialog-title')?.textContent", 10)
    type_into(c, f"{dlg}.querySelector('[data-testid=roles-clone-name]')", "doc-reviewer")
    out["rename_label"] = c.wait(f"{dlg}.querySelector('[data-testid=roles-clone-go]').textContent.includes('doc-reviewer') && "
                                 f"{dlg}.querySelector('[data-testid=roles-clone-go]').textContent", 5)
    press(c, f"{dlg}.querySelector('[data-testid=roles-clone-go]')")
    out["renamed_row"] = c.wait(f"!!{row('roles-bio', 'doc-reviewer')}", 15)
    out["no_reviewer_file"] = not (state / "agents" / "reviewer.yaml").exists()
    press(c, act("roles-lineup", "doc-review--review", "customize"))
    out["customized"] = c.wait(f"{q('[data-testid=roles-canvas]')}?.dataset.lineup === 'review' && 'review'", 20)
    out["customized_readonly"] = c.js(f"!!{q('[data-testid=roles-inspector-readonly]')}")
    out["customized_tab"] = c.js(f"{q('[data-testid=roles-tab-lineup]')}?.getAttribute('aria-selected')")
    lineup = state / "teams" / "review.yaml"
    out["lineup_file"] = lineup.is_file() and "from_pack: doc-review@1.0.0" in lineup.read_text(encoding="utf-8")
    out["pack_untouched"] = _hashes(state / "packs" / "doc-review" / "agents") == pack_files
    return out


def apply(c, url: str, state: Path) -> dict:
    out: dict = {}
    mine = _hashes(state / "agents"), _hashes(state / "teams")
    press(c, act("roles-lineup", "doc-review--review", "apply"))
    dlg = q('[data-testid="roles-apply-dialog"]')
    out["apply_pack"] = c.wait(f"{dlg}?.querySelector('[data-testid=roles-apply-pack]')?.textContent", 15)
    out["apply_replaces"] = c.js(f"{dlg}.querySelector('[data-testid=roles-apply-replaces]').textContent")
    press(c, f"{dlg}.querySelector('[data-testid=roles-apply-dialog-yes]')")
    c.wait(f"!{dlg}", 10)
    out["active"] = c.wait(f"{row('roles-lineup', 'doc-review--review')}?.textContent.includes('active') && 'doc-review--review'", 15)
    out["config_team"] = json.loads((state / "config.json").read_text(encoding="utf-8")).get("team")
    out["files_unchanged"] = (_hashes(state / "agents"), _hashes(state / "teams")) == mine
    return out


def shadow_and_disable(c, url: str, state: Path) -> dict:
    out: dict = {}
    (state / "agents" / "doc-review--reviewer.yaml").write_text("description: mine\nkind: reviewer\n", encoding="utf-8")
    reload(c, url)
    c.wait(f"{row('roles-bio', 'doc-review--reviewer')}?.closest('[data-testid=roles-group]')?.dataset.group === 'yours'", 30)
    out["shadow_group"] = c.js(f"{row('roles-bio', 'doc-review--reviewer')}.closest('[data-testid=roles-group]').dataset.group")
    out["shadow_chip"] = c.js(f"{row('roles-bio', 'doc-review--reviewer')}.querySelector('[data-testid=roles-shadows]')?.textContent")
    shadowed = q('[data-testid=roles-bios-body] [data-group="pack:doc-review"] [data-testid=roles-shadowed]')
    out["shadowed_line"] = c.js(f"{shadowed}?.textContent")
    from halo_harness.packs.grants import disable
    disable("doc-review")
    reload(c, url)
    c.wait(f"!!{row('roles-lineup', 'halo-dev-cycle')} && !{row('roles-lineup', 'doc-review--review')}", 30)
    out["disabled_groups"] = c.js(f"{panel_groups('roles-lineups-list')}.map((g) => g.dataset.group)")
    return out


class PacksRolesDriver(Driver):
    no_chrome = {"skip": "no Chrome found"}

    @contextmanager
    def session(self, c):
        from capture_studio import seeded_home, serve
        from halo_harness.packs import bio_models
        from halo_harness.packs.discover import find
        from halo_harness.packs.grants import enable
        from halo_harness.packs.install import install
        state = seeded_home()
        from tests.helpers.packs_home import DOC_REVIEW  # 3.2.0.0 R6: the shipped reference pack
        ok, lines = install(str(DOC_REVIEW))
        assert ok, lines
        ok, lines = enable(find("doc-review"), grant=["hooks"])
        assert ok, lines
        bio_models.ROWS = lambda _s, _c: list(LONG)
        srv, url = serve(state, True)
        url = url.replace("mode=orchestra", "mode=roles").replace("feed=off", "feed=off&tour=off&view=workspace")
        try:
            yield tuple((fn, (c, url, state)) for fn in (groups, preview, clones, apply, shadow_and_disable))
        finally:
            srv.shutdown()
            srv.server_close()
            shutil.rmtree(state.parent, ignore_errors=True)


if __name__ == "__main__":
    sys.exit(PacksRolesDriver(sys.argv[1:]).main())
