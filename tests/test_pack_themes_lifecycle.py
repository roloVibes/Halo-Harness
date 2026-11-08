"""tests.test_pack_themes_lifecycle -- a pack palette's restore record (Halo 3.3.12.0 R2; themes/restore.py,
theme.persist_theme, packs/grants.disable, packs/remove.remove; docs/EXTENSION_API.md "Themes"):

1. choosing `pack-theme/linen` from `claude-dark` keeps `claude-dark` in `~/.halo/packs/.data/pack-theme/theme.json`,
   through every door (`persist_theme`, `halo config set theme`, the settings route, Setup's route);
2. `halo pack disable pack-theme` writes `theme: claude-dark` back and says so in one line; the record goes;
3. removing the pack while its palette is chosen does the same; with no theme saved before, the key is unset;
4. a core palette chosen after a pack one clears the record; moving between the pack's palettes keeps the first
   previous value; another pack's palette never becomes the value restored;
5. a gone pack's palette left in config.json reads like a removed game theme: one line, the default drawn, the doctor's
   warns row; a pack without themes and a user with none change nothing;
6. the terminal: `/theme pack-theme/nightshade` saves it and draws it at once, `/theme` lists it under the pack.
Run: python -m tests.test_pack_themes_lifecycle
"""

from __future__ import annotations

import contextlib
import io
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from tests.helpers.packs_home import PacksHome  # noqa: E402
from tests.helpers.runner import Ctx, new_registry, print_results, run_all  # noqa: E402

test, TESTS = new_registry()


def _home(h, *, enable: bool = True):
    h.install(h.source("pack-theme"), enable=enable)


def _record(h) -> "dict | None":
    p = h.packs / ".data" / "pack-theme" / "theme.json"
    return json.loads(p.read_text(encoding="utf-8")) if p.is_file() else None


def _post(h, path: str, body: dict):
    from halo_harness.studio.api import Request, dispatch
    return dispatch(Request(method="POST", path=path, query={}, body=body, cwd=h.repo, state_dir=h.state))


@test
def test_choose_then_disable_restores_the_previous_palette(ctx: Ctx):
    from halo_harness import theme as T
    with PacksHome() as h:
        _home(h)
        T.persist_theme("claude-dark")
        T.persist_theme("pack-theme/linen")
        rec = _record(h)
        ctx.check(f"theme.json holds claude-dark, got {rec}", rec and rec["previous"] == "claude-dark" and rec["theme"] == "pack-theme/linen")
        ctx.check("config.json names the pack palette", T.load_persisted_theme() == "pack-theme/linen")
        code, out, _err = h.cli("disable", "pack-theme")
        ctx.check(f"disable: exit 0 and the line, got {out!r}", code == 0
                  and "theme: pack-theme/linen was pack-theme's palette and the pack is disabled; restored claude-dark" in out)
        ctx.check(f"theme is claude-dark again, got {T.load_persisted_theme()}", T.load_persisted_theme() == "claude-dark")
        ctx.check("the record is gone", _record(h) is None)
        code, out, _err = h.cli("disable", "pack-theme")
        ctx.check("disabling again says nothing of a theme", code == 0 and "theme:" not in out)


@test
def test_every_door_keeps_the_record(ctx: Ctx):
    from halo_harness import theme as T
    from halo_harness.config_cli import _cmd_set
    with PacksHome() as h:
        _home(h)
        T.persist_theme("ember")
        with contextlib.redirect_stdout(io.StringIO()):
            code = _cmd_set(["theme", "pack-theme/nightshade"])
        ctx.check(f"halo config set theme: saved and recorded, got {code} {_record(h)}", code == 0
                  and (_record(h) or {}).get("previous") == "ember")
        T.persist_theme("dusk")
        status, got = _post(h, "settings/set", {"key": "theme", "value": "pack-theme/linen"})
        ctx.check(f"the settings route: 200 and recorded, got {status} {_record(h)}", status == 200
                  and (_record(h) or {}).get("previous") == "dusk")
        status, _got = _post(h, "settings/unset", {"key": "theme"})
        ctx.check("unsetting the key clears the record", status == 200 and _record(h) is None and T.load_persisted_theme() is None)
        status, got = _post(h, "setup/config", {"key": "theme", "value": "pack-theme/linen"})
        ctx.check(f"Setup's route: saved, recorded with no previous, got {status} {_record(h)}", status == 200
                  and _record(h) == {**(_record(h) or {}), "previous": None, "theme": "pack-theme/linen"})
        h.cli("disable", "pack-theme")
        ctx.check("nothing saved before: disable unsets the key", T.load_persisted_theme() is None and _record(h) is None)


@test
def test_remove_while_chosen_restores_too(ctx: Ctx):
    from halo_harness import theme as T
    with PacksHome() as h:
        _home(h)
        T.persist_theme("paper")
        T.persist_theme("pack-theme/nightshade-daltonized")
        code, out, _err = h.cli("remove", "pack-theme")
        ctx.check(f"remove: the line, got {out!r}", code == 0
                  and "theme: pack-theme/nightshade-daltonized was pack-theme's palette and the pack is removed; restored paper" in out)
        ctx.check("theme is paper again, the record gone", T.load_persisted_theme() == "paper" and _record(h) is None)


@test
def test_core_after_pack_clears_and_moves_keep_the_first_previous(ctx: Ctx):
    from halo_harness import theme as T
    from halo_harness.themes import registry as R
    from halo_harness.themes.palettes import PALETTES
    with PacksHome() as h:
        _home(h)
        T.persist_theme("forest")
        T.persist_theme("pack-theme/linen")
        T.persist_theme("pack-theme/nightshade")
        ctx.check(f"between the pack's own palettes: still forest, got {_record(h)}", (_record(h) or {}).get("previous") == "forest")
        T.persist_theme("slate")
        ctx.check("a core palette after a pack one: the record clears", _record(h) is None)
        holo = next(p for p in PALETTES if p["id"] == "holo")
        try:
            R.register("other", {"id": "glow", "label": "Other", "posture": "dark", "tokens": dict(holo["tokens"])})
            T.persist_theme("other/glow")
            T.persist_theme("pack-theme/linen")
            ctx.check(f"from another pack's palette: its previous carries over, got {_record(h)}", (_record(h) or {}).get("previous") == "slate")
            lines = h.cli("disable", "pack-theme")[1]
            ctx.check(f"so the restore lands on a core palette, got {T.load_persisted_theme()}", T.load_persisted_theme() == "slate"
                      and "restored slate" in lines)
        finally:
            R.unregister("other")


@test
def test_a_gone_pack_palette_reads_as_a_removed_theme(ctx: Ctx):
    from halo_harness import theme as T
    from halo_harness.doctor_config import config_findings
    with PacksHome() as h:
        _home(h, enable=False)
        T.set_config_value("theme", "pack-theme/linen")
        using = T.resolve_theme(env={"COLORTERM": "truecolor"}, persisted_theme=T.load_persisted_theme())
        ctx.check(f"the default is drawn, got {using}", using == "claude-dark")
        line = T.removed_theme_notice(using)
        ctx.check(f"one line, like a removed game theme, got {line!r}", line == "theme: pack-theme/linen is a palette of the pack "
                  "pack-theme, which is not enabled here (or no longer has it); using claude-dark")
        found = [f for f in config_findings(h.repo) if f.get("key") == "theme"]
        ctx.check(f"doctor --config: one warns row with that line, got {found}", len(found) == 1 and found[0]["severity"] == "warns"
                  and found[0]["text"].startswith("theme: pack-theme/linen is a palette of the pack pack-theme"))
        from halo_harness.studio.theme_boot import saved_theme
        ctx.check("Studio follows the system", saved_theme() == "auto")
        h.cli("enable", "pack-theme")
        ctx.check("enabled again: it is a theme again, no notice", T.is_valid_theme("pack-theme/linen")
                  and T.removed_theme_notice("pack-theme/linen") is None)


@test
def test_the_terminal_takes_it_at_once(ctx: Ctx):
    import asyncio
    from halo_harness import theme as T
    from halo_harness.testing.fake_controller import FakeController
    from halo_harness.tui.app import BridgeApp
    from halo_harness.tui.slash import handle_slash

    async def body(h):
        app = BridgeApp(FakeController(), cwd=str(h.repo), theme_name="claude-dark")
        async with app.run_test(size=(120, 40)) as pilot:
            await pilot.pause(0.2)
            await handle_slash(app, "theme", "pack-theme/nightshade")
            await pilot.pause(0.2)
            ctx.check(f"/theme pack-theme/nightshade: saved and drawn, got {T.load_persisted_theme()!r} {app.theme_name!r}",
                      T.load_persisted_theme() == "pack-theme/nightshade" and app.get_css_variables()["bridge-bg"] == "#0d0b14")
            await handle_slash(app, "theme", "")
            await pilot.pause(0.1)
            listing = [n.message for n in app._notifications if n.message.startswith("Current theme")]
            ctx.check("/theme lists it under the pack's name", listing and "From the pack pack-theme (Pack themes):" in listing[-1])
    with PacksHome() as h:
        _home(h)
        T.persist_theme("claude-dark")
        asyncio.run(body(h))
        ctx.check("the record keeps claude-dark", (_record(h) or {}).get("previous") == "claude-dark")


@test
def test_zero_change_without_pack_themes(ctx: Ctx):
    from halo_harness import theme as T
    with PacksHome() as h:
        h.install(h.source("doc-review"), enable=True)
        T.persist_theme("holo")
        T.persist_theme("dawn")
        ctx.check("no record anywhere", not list((h.packs / ".data").glob("*/theme.json")) if (h.packs / ".data").is_dir() else True)
        code, out, _err = h.cli("disable", "doc-review")
        ctx.check("disable says nothing of a theme and leaves it", code == 0 and "theme:" not in out and T.load_persisted_theme() == "dawn")
        ctx.check("a core name never gets the pack line", T.removed_theme_notice("dawn", persisted="dawn") is None
                  and T.removed_theme_notice("x", persisted="solarized") is None)


if __name__ == "__main__":
    ctx = Ctx()
    results, passed, failed, skipped = run_all(TESTS, ctx)
    sys.exit(print_results(results, passed, failed, skipped))
