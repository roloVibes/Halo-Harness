"""tests.test_pack_design -- the Design section as the shipped design pack (Halo 3.3.13.0 R2, F4 of the Focus plan):
`halo pack list` offers it, `halo pack install design` installs it, `--grant-all` enables it; the registry then
has its section with the page's module (`view`) and its routes; the section takes the first pack key (`Alt+0`) after
the nine core sections; `/design` is the pack's command that opens the section, and with the pack off one line saying
how to turn it on, as `halo design` and `halo studio --mode design` say; a route answers behind Studio's token; the
seam's failures (a routes module that raises, a disabled pack, a grant taken back) answer with one line; and
`halo pack test` passes it, its own test modules (moved from tests/ with the code) included. The Chrome checks are
tests/test_pack_design_ui.py (the full tier). Run: python -m tests.test_pack_design
"""

from __future__ import annotations

import contextlib
import io
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from tests.helpers.packs_home import PacksHome  # noqa: E402
from tests.helpers.runner import Ctx, new_registry, print_results, run_all  # noqa: E402

test, TESTS = new_registry()
REPO = Path(__file__).resolve().parent.parent
PACK = REPO / "halo_harness" / "templates" / "packs" / "design"
UI = REPO / "halo_harness" / "studio" / "ui" / "src"


@test
def test_the_shipped_pack_installs_and_brings_its_section_and_routes(ctx: Ctx):
    from halo_harness.packs.studio_registry import registry
    with PacksHome() as h:
        code, out, _err = h.cli("list", "--available")
        ctx.check(f"halo pack list --available offers design (a pack Halo ships), got {out[-400:]!r}", code == 0 and "design" in out)
        code, out, err = h.cli("install", "design")
        ctx.check(f"halo pack install design installs the shipped folder, got {code} {out[-300:]!r} {err[-300:]!r}", code == 0)
        reg = registry(cwd=h.repo, state_dir=h.state)
        ctx.check("installed but not enabled: nothing of it in Studio", not [p for p in reg["packs"] if p["id"] == "design"])
        code, out, err = h.cli("enable", "design", "--grant-all")
        ctx.check(f"enable --grant-all grants studio-script and studio-routes, got {out!r}",
                  code == 0 and "studio-script" in out and "studio-routes" in out)
        reg = registry(cwd=h.repo, state_dir=h.state)
        entry = next((p for p in reg["packs"] if p["id"] == "design"), {})
        sec = (entry.get("sections") or [{}])[0]
        ctx.check(f"its section is design--design, drawn by its module once granted, got {sec.get('id')} {sec.get('view')}",
                  sec.get("id") == "design--design" and sec.get("panels") == []
                  and (sec.get("view") or {}).get("file") == "api/pack/design/file/studio/design.js")
        ctx.check(f"its routes are granted under api/packs/design/design, got {entry.get('routes')}",
                  entry.get("routes") == {"prefix": "design", "api": "api/packs/design/design", "granted": True})
        ctx.check(f"the core a pack's panel may join is five (Design left), got {reg['core']}",
                  reg["core"] == ["session", "team", "roles", "fleet", "orchestra"])
        code, out, _err = h.cli("inspect", "design")
        ctx.check("inspect says what studio-routes lets it do", "runs this pack's Python inside Studio's server" in out)
        h.cli("disable", "design")
        reg = registry(cwd=h.repo, state_dir=h.state)
        ctx.check("disabled: the section leaves the registry", not [p for p in reg["packs"] if p["id"] == "design"])


@test
def test_the_section_takes_the_first_pack_key(ctx: Ctx):
    reg = (UI / "routes" / "packs" / "registry.ts").read_text(encoding="utf-8")
    ctx.check("FIRST_KEY 10 and LAST_KEY 10: the first pack section is Alt+0",
              "const FIRST_KEY = 10;" in reg and "const LAST_KEY = 10;" in reg and "`Alt+${n % 10}`" in reg)
    ctx.check("a section with a view is the pack's page (PackView), paged", "s.view ? { view: PackView, paged: true }" in reg)
    index = (UI / "routes" / "index.tsx").read_text(encoding="utf-8")
    ctx.check("no core Design section, and Local is Alt+9 with the Media panels",
              'id: "design"' not in index and 'id: "local", title: "Local", kbd: "Alt+9"' in index and "panels: mediaPanels(0)" in index)


@test
def test_design_opens_the_pack_section_and_says_how_to_turn_it_on(ctx: Ctx):
    from halo_harness.commands.registry import Registry
    from halo_harness.packs.contribute import pack_plugin_roots
    from halo_harness.studio import server as S
    with PacksHome() as h:
        off = Registry.discover(h.repo, home=h.home).resolve("/design")
        line = off.run("", type("F", (), {"cwd": h.repo, "session": None})()) if off else ""
        ctx.check(f"with the pack off, /design is one line naming the pack and how to turn it on, got {line!r}",
                  "design pack" in line and "halo pack enable design --grant-all" in line)
        h.cli("install", "design")
        h.cli("enable", "design", "--grant-all")
        roots = pack_plugin_roots(cwd=h.repo)
        cmd = Registry.discover(h.repo, home=h.home, plugin_roots=roots).resolve("/design")
        ctx.check(f"with the pack on, /design is the pack's command (design:design), got {cmd and cmd.name}",
                  cmd is not None and cmd.name == "design:design" and cmd.kind == "core")
        opened = []
        orig = S.webbrowser.open
        S.webbrowser.open = lambda url: opened.append(url)
        try:
            facade = type("F", (), {"cwd": h.repo, "session": object()})()
            out = cmd.run("url", facade) if cmd else ""
            no_browser = list(opened)
            out2 = cmd.run("", facade) if cmd else ""
        finally:
            S.webbrowser.open = orig
            srv = S._BACKGROUND.pop("server", None)
            if srv is not None:
                srv.shutdown()
                srv.server_close()
        ctx.check(f"/design url prints the section's address, no browser, got {out!r}", "?mode=design--design#t=" in out and not no_browser)
        ctx.check(f"/design opens the browser there, got {opened}", len(opened) == 1 and "?mode=design--design#t=" in opened[0] and "?mode=" in out2)


@test
def test_the_old_words_point_at_the_pack(ctx: Ctx):
    from halo_harness.cli import main as halo_main
    from halo_harness.studio.modes import check
    with PacksHome() as h:
        err = io.StringIO()
        with contextlib.redirect_stderr(err):
            code = halo_main(["design", "list"])
        ctx.check(f"halo design ... is one line pointing at the pack, exit 2, got {code} {err.getvalue()!r}",
                  code == 2 and "halo pack enable design" in err.getvalue() and "/design" in err.getvalue())
        mode, why = check("design", cwd=h.repo, state_dir=h.state)
        ctx.check(f"--mode design with the pack off is the same line, got {why!r}", mode is None and "design pack" in why)
        h.cli("install", "design")
        h.cli("enable", "design", "--grant-all")
        ctx.check("with it on, --mode design and design--design open its section",
                  check("design", cwd=h.repo, state_dir=h.state) == ("design--design", "")
                  and check("design--design", cwd=h.repo, state_dir=h.state) == ("design--design", ""))
        ctx.check("an unknown pack section is a line, never a crash", check("nope--x", cwd=h.repo, state_dir=h.state)[0] is None)


@test
def test_a_route_answers_and_the_seam_says_what_failed(ctx: Ctx):
    """In-process Studio with the pack linked (ext.testing.studio): `GET ping`; the pack's key in `?k=` for a GET; a grant
    taken back is a 403 naming it; disabled is a 404; a routes module that raises is a 500 with one line and a doctor row."""
    from halo_harness.ext import testing
    from halo_harness.packs.doctor import problems
    with PacksHome() as h:
        with testing.studio(PACK, cwd=h.repo) as s:
            status, body = s.call("GET", s.route("ping"))
            ctx.check(f"GET ping answers 200 with the pack's id, got {status} {body}", status == 200 and body.get("pack") == "design")
            ctx.check("a wrong token is a 401", s.call("GET", s.route("ping"), token="wrong")[0] == 401)
            status, _h, raw = s.raw(s.route("ping"))
            ctx.check(f"a GET takes the pack's key in ?k= (an iframe sends no header), got {status}", status == 200 and b'"pack"' in raw)
            from tests.helpers.owner_rig import fetch
            ctx.check("3.3.14.0 R1: the launch token in ?t= is not taken on a pack GET (401)",
                      fetch(f"{s.base}{s.route('ping')}?t={s.token}")[0] == 401)
            for q in (f"t={s.token}", f"k={s.key}"):
                post = fetch(f"{s.base}{s.route('render')}?{q}", method="POST", data=b"{}")[0]
                ctx.check(f"a POST takes neither the token nor the key from the query ({q[:2]}): 401, got {post}", post == 401)
            routes = s.module("server/routes.py")
            orig = routes.handle
            routes.handle = lambda *a: 1 / 0
            try:
                status, body = s.call("GET", s.route("ping"))
            finally:
                routes.handle = orig
            ctx.check(f"a handle that raises is a 500 with one line, got {status} {body}",
                      status == 500 and "ZeroDivisionError" in body.get("error", ""))
            rows = [p for p in problems(cwd=h.repo, state_dir=s.state) if p["check"] == "studio-routes"]
            ctx.check(f"and halo pack doctor shows it, got {rows}", rows and "ZeroDivisionError" in rows[0]["text"])
            h.cli("grant", "design", "studio-routes", "--off")
            status, body = s.call("GET", s.route("ping"))
            ctx.check(f"the grant taken back: 403 naming it, got {status} {body}",
                      status == 403 and "halo pack enable design --grant studio-routes" in body.get("error", ""))
            h.cli("disable", "design")
            ctx.check("disabled: 404", s.call("GET", s.route("ping"))[0] == 404)


@test
def test_halo_pack_test_passes_the_pack_and_its_own_tests(ctx: Ctx):
    from halo_harness.ext import testing
    report = testing.run(PACK)
    own = [c for c in report.checks if c["kind"] == "tests"]
    ctx.check(f"every check passes (the craft apps not on PATH are skips):\n{report.text()}", report.ok and report.failed == 0)
    ctx.check(f"the pack's own nine test modules ran and passed, got {len(own)}", len(own) == 9 and all(c["ok"] for c in own))


if __name__ == "__main__":
    ctx = Ctx()
    results, passed, failed, skipped = run_all(TESTS, ctx)
    sys.exit(print_results(results, passed, failed, skipped))
