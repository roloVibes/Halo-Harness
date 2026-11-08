"""tests.test_studio_theme_api -- Studio's side of the one `theme` key (Halo 3.3.12.0 R1) over a scratch home, no
model call, no network:

1. `GET settings/themes`: the ten palettes with their tokens and -daltonized tokens (the registry's, value for
   value), the vocabulary, the modifiers, "follow the system" (holo / paper); `theme` null on a fresh home;
2. `POST settings/set {theme: ember}` lands in config.json and `GET settings/themes` says ember, dark; a name the
   registry does not know is a 422 naming the ten, config.json unchanged; `settings/unset` is "follow" again;
3. the served index.html: `data-theme` on <html> is the saved theme, "auto" when unset or not a palette, and the
   page carries exactly one `data-theme`;
4. the door: `settings:themes` / `halo settings themes` opens `?mode=settings&page=themes`, `--terminal` lists the ten;
5. scripts/themes_css.py --check passes (the drift test proper is tests/test_themes_css_drift.py);
6. (3.3.12.0 R2) an enabled pack's palettes follow the ten with `pack` and their tokens and Studio variables, only
   while the pack is enabled; the served page inlines a saved pack palette's variables in one `<style>` the CSP allows
   by its hash, and disabling the pack through the Pack Manager's route restores the previous theme.
Run: python -m tests.test_studio_theme_api
"""
from __future__ import annotations

import json
import os
import re
import sys
import tempfile
import threading
import urllib.request
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from tests.helpers.runner import Ctx, new_registry, print_results, run_all  # noqa: E402

test, TESTS = new_registry()


class _Home:
    def __enter__(self):
        self._saved = {k: os.environ.get(k) for k in ("BRIDGE_TEST_HOME", "BRIDGE_STATE_DIR")}
        os.environ.pop("BRIDGE_STATE_DIR", None)
        d = Path(tempfile.mkdtemp(prefix="theme-api-"))
        os.environ["BRIDGE_TEST_HOME"] = str(d)
        from halo_harness.providers.config import default_state_dir
        self.state_dir, self.cwd = Path(default_state_dir()), d / "project"
        self.state_dir.mkdir(parents=True, exist_ok=True)
        self.cwd.mkdir(parents=True)
        return self

    def __exit__(self, *exc):
        for k, v in self._saved.items():
            if v is None:
                os.environ.pop(k, None)
            else:
                os.environ[k] = v

    def call(self, method: str, path: str, body=None):
        from halo_harness.studio.api import Request, dispatch
        return dispatch(Request(method=method, path=path, query={}, body=body or {}, cwd=self.cwd, state_dir=self.state_dir))

    def config(self) -> dict:
        p = self.state_dir / "config.json"
        return json.loads(p.read_text(encoding="utf-8")) if p.is_file() else {}


@test
def test_the_registry_as_the_page_reads_it(ctx: Ctx):
    from halo_harness.themes import registry as R
    with _Home() as h:
        status, got = h.call("GET", "settings/themes")
        ids = [p["id"] for p in got.get("palettes", [])]
        ctx.check(f"200 and the ten in order, got {status} {ids}", status == 200 and ids == list(R.ids()))
        ctx.check("every palette's tokens are the registry's", all(p["tokens"] == R.tokens(p["id"]) and p["posture"] == R.posture(p["id"])
                                                                    and p["daltonized"] == R.tokens(p["id"] + "-daltonized") for p in got["palettes"]))
        ctx.check("the vocabulary, the modifiers, follow", len(got["tokens"]) == 17 and got["modifiers"] == ["daltonized", "ansi"]
                  and got["follow"] == {"dark": "holo", "light": "paper"})
        ctx.check(f"a fresh home follows the system, got {got.get('theme')!r}", got["theme"] is None and got["posture"] == "" and got["saved"] is None)


@test
def test_set_unset_and_a_refusal(ctx: Ctx):
    with _Home() as h:
        status, ans = h.call("POST", "settings/set", {"key": "theme", "value": "ember"})
        ctx.check(f"set ember: 200 and config.json has it, got {status} {h.config()}", status == 200 and h.config().get("theme") == "ember")
        _s, got = h.call("GET", "settings/themes")
        ctx.check(f"themes says ember, dark, got {got['theme']} {got['posture']}", got["theme"] == "ember" and got["posture"] == "dark")
        before = (h.state_dir / "config.json").read_bytes()
        status, ans = h.call("POST", "settings/set", {"key": "theme", "value": "solarized"})
        ctx.check(f"an unknown name: 422 naming the ten, got {status} {ans}", status == 422 and "the palettes: claude-dark, claude-light, holo"
                  in ans["error"] and "dawn" in ans["error"])
        ctx.check("config.json unchanged", (h.state_dir / "config.json").read_bytes() == before)
        status, _ans = h.call("POST", "settings/set", {"key": "theme", "value": "paper-daltonized"})
        _s, got = h.call("GET", "settings/themes")
        ctx.check(f"a modifier saves, light, got {got['theme']} {got['posture']}", status == 200 and got["theme"] == "paper-daltonized"
                  and got["posture"] == "light")
        status, _ans = h.call("POST", "settings/unset", {"key": "theme"})
        _s, got = h.call("GET", "settings/themes")
        ctx.check("unset: follow the system again", status == 200 and "theme" not in h.config() and got["theme"] is None)
        from halo_harness.theme import set_config_value
        set_config_value("theme", "doom")
        _s, got = h.call("GET", "settings/themes")
        ctx.check(f"a saved game theme draws as follow, the saved word kept, got {got['theme']} {got['saved']}",
                  got["theme"] is None and got["saved"] == "doom")


@test
def test_the_served_page_paints_the_saved_theme_first(ctx: Ctx):
    from halo_harness.studio.server import start_server
    from halo_harness.studio.theme_boot import theme_attr
    from halo_harness.theme import set_config_value, unset_config_value
    with _Home() as h:
        ctx.check("theme_attr: unset is auto", b'data-theme="auto"' in theme_attr(b'<html lang="en" data-theme="dark"><body>'))
        ctx.check("a page with no attribute gains one", theme_attr(b"<html><body>").startswith(b'<html data-theme="auto"'))
        srv = start_server(port=0, cwd=h.cwd, state_dir=h.state_dir)
        threading.Thread(target=srv.serve_forever, daemon=True).start()
        try:
            def page() -> str:
                with urllib.request.urlopen(f"http://127.0.0.1:{srv.server_address[1]}/", timeout=10) as r:
                    return r.read().decode("utf-8")
            for saved, want in ((None, "auto"), ("midnight", "midnight"), ("claude-light-ansi", "claude-light-ansi"), ("not-one", "auto")):
                if saved is None:
                    unset_config_value("theme")
                else:
                    set_config_value("theme", saved)
                head = re.search(r"<html[^>]*>", page())
                tag = head.group(0) if head else ""
                ctx.check(f"theme {saved!r}: <html data-theme={want!r}>, got {tag!r}", f'data-theme="{want}"' in tag and tag.count("data-theme=") == 1)
        finally:
            srv.shutdown()
            srv.server_close()


@test
def test_the_door_to_settings_themes(ctx: Ctx):
    from halo_harness.settings_cli import group_lines
    from halo_harness.studio.settings_door import SettingsTarget, group_word, parse
    with _Home():
        target, why = parse("settings:themes")
        ctx.check(f"settings:themes is a target, got {target} {why!r}", target == SettingsTarget(group="themes") and not why)
        ctx.check("its address is ?page=themes", target.query() == "?mode=settings&page=themes" and target.display == "Settings (Themes)")
        ctx.check("`theme` is the same page", group_word("theme") == ("themes", ""))
        lines = group_lines("themes")
        ctx.check(f"`halo settings themes --terminal` lists the ten, got {lines[:2]}", len(lines) == 13 and lines[0].startswith("Current theme"))


@test
def test_pack_palettes_only_while_the_pack_is_enabled(ctx: Ctx):
    from halo_harness.studio.api import Request, dispatch
    from halo_harness.studio.server import start_server
    from halo_harness.themes.studio_css import studio_vars
    from tests.helpers.packs_home import PacksHome
    with PacksHome() as h:
        def call(method: str, path: str, body=None):
            return dispatch(Request(method=method, path=path, query={}, body=body or {}, cwd=h.repo, state_dir=h.state))
        h.install(h.source("pack-theme"))
        ids = [p["id"] for p in call("GET", "settings/themes")[1]["palettes"]]
        ctx.check(f"installed, disabled: the ten only, got {len(ids)}", len(ids) == 10)
        call("POST", "pack/pack-theme/enable")
        got = call("GET", "settings/themes")[1]
        packs = [p for p in got["palettes"] if p.get("pack")]
        ctx.check(f"enabled: two pack palettes after the ten, got {[p['id'] for p in packs]}", [p["id"] for p in got["palettes"][10:]]
                  == ["pack-theme/nightshade", "pack-theme/linen"] and all(p["pack"] == "pack-theme" and p["pack_name"] == "Pack themes" for p in packs))
        night = packs[0]
        ctx.check("its tokens, -daltonized tokens and Studio variables", night["tokens"]["accent"] == "#b48cff"
                  and night["vars"] == dict(studio_vars(night["tokens"], "dark")) and night["daltonized_vars"]["--accent"] == night["daltonized"]["accent"])
        call("POST", "settings/set", {"key": "theme", "value": "claude-light"})
        status, _ = call("POST", "settings/set", {"key": "theme", "value": "pack-theme/nightshade"})
        ctx.check("a pack palette saves through the route", status == 200 and call("GET", "settings/themes")[1]["theme"] == "pack-theme/nightshade")
        srv = start_server(port=0, cwd=h.repo, state_dir=h.state)
        threading.Thread(target=srv.serve_forever, daemon=True).start()
        try:
            with urllib.request.urlopen(f"http://127.0.0.1:{srv.server_address[1]}/", timeout=10) as r:
                page, csp = r.read().decode("utf-8"), r.headers.get("Content-Security-Policy", "")
        finally:
            srv.shutdown()
            srv.server_close()
        style = re.search(r'<style id="halo-pack-theme">(.*?)</style>', page, re.S)
        body = style.group(1) if style else ""
        ctx.check(f"the page: data-theme the pack palette and one inline rule, got {body[:90]!r}",
                  'data-theme="pack-theme/nightshade"' in page and page.count('id="halo-pack-theme"') == 1
                  and body.startswith(':root[data-theme="pack-theme/nightshade"] {') and "--accent: #b48cff;" in body)
        import base64
        import hashlib
        digest = base64.b64encode(hashlib.sha256(body.encode("utf-8")).digest()).decode("ascii")
        ctx.check(f"the CSP allows exactly that rule, got {csp!r}", f"style-src 'self' 'sha256-{digest}'" in csp and "unsafe-inline" not in csp)
        status, ans = call("POST", "pack/pack-theme/disable")
        ctx.check(f"disable through the route: the restore line, got {ans.get('lines')}", status == 200
                  and any("restored claude-light" in ln for ln in ans.get("lines", [])))
        got = call("GET", "settings/themes")[1]
        ctx.check("the ten again, the theme claude-light", got["theme"] == "claude-light" and len(got["palettes"]) == 10)


@test
def test_the_generated_css_matches_the_registry(ctx: Ctx):
    import importlib.util
    path = Path(__file__).resolve().parent.parent / "scripts" / "themes_css.py"
    spec = importlib.util.spec_from_file_location("themes_css_check", path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    ctx.check("themes_css --check exits 0", mod.main(["--check"]) == 0)


if __name__ == "__main__":
    os.environ.setdefault("BRIDGE_TEST_NO_BACKGROUND_NET", "1")
    ctx = Ctx()
    results, passed, failed, skipped = run_all(TESTS, ctx)
    sys.exit(print_results(results, passed, failed, skipped))
