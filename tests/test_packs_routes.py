"""tests.test_packs_routes -- a pack's own Studio routes, what loads and unloads them (Halo 3.3.14.0 R1, the November
review's #6, #7, #8, #34; studio/packs_routes.py, packs/contribute.py), over a real server and the routes-pack fixture:

1. #7: a request to `/api/packs/<id>.server/...` (an id no pack has) leaves `sys.modules` and the loaded set as they
   were; a registry read that raises leaves the loaded module in place (the last good read stands); the design pack's
   modules, loaded, survive the same request (the finding's probe); a package gone from `sys.modules` is one fresh import.
2. #8: `halo pack update` that changes only a sibling module (routes.py's time unchanged) answers the new value at once;
   a changed install record alone loads the module afresh.
3. #6: a raw answer with no CSP gets `sandbox; default-src 'none'`; one with its own keeps it, other headers dropped.
4. #34: turning the pack off runs the routes module's own `unload()`.
"""

from __future__ import annotations

import os
import shutil
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from tests.helpers.owner_rig import fetch  # noqa: E402
from tests.helpers.packs_studio import PackStudio  # noqa: E402
from tests.helpers.runner import Ctx, new_registry, print_results, run_all  # noqa: E402

test, TESTS = new_registry()
PKG = "halo_packs.routes_pack"


def _mods(prefix: str = PKG) -> set:
    return {m for m in sys.modules if m == prefix or m.startswith(prefix + ".")}


def _get(s, rest: str):
    status, body, heads = s.call("GET", f"packs/routes-pack/r/{rest}")
    return status, body, heads


@test
def test_a_made_up_id_or_a_failed_read_unloads_nothing(ctx: Ctx):
    from halo_harness.packs import registry
    from halo_harness.studio import packs_routes as PR
    with PackStudio() as s:
        s.install_pack("routes-pack", grants=["studio-routes"])
        ctx.check("the value route answers", _get(s, "value")[:2] == (200, {"value": 1}))
        before, loaded = _mods(), dict(PR._loaded)
        status, _b, _h = s.call("GET", "packs/routes-pack.server/r/ping")
        ctx.check(f"<id>.server: 404, got {status}", status == 404)
        ctx.check(f"sys.modules unchanged, dropped {sorted(before - _mods())}", _mods() == before)
        ctx.check("the loaded set unchanged", PR._loaded.keys() == loaded.keys())
        real = registry.active

        def broken(**_kw):
            raise OSError("a pack folder mid-update")
        registry.active = broken
        try:
            status, body, _h = _get(s, "value")
            PR.drop_inactive()
        finally:
            registry.active = real
        ctx.check(f"a raising registry: the last good read stands, got {status} {body}", (status, body) == (200, {"value": 1}))
        ctx.check("and the module stays loaded", "routes-pack" in PR._loaded and PR._loaded["routes-pack"]["module"]
                  is loaded["routes-pack"]["module"])
        first = PR._loaded["routes-pack"]["module"]
        for m in _mods():
            sys.modules.pop(m, None)
        ctx.check("its package gone: the next request answers", _get(s, "value")[:2] == (200, {"value": 1}))
        ctx.check("from one fresh import", PR._loaded["routes-pack"]["module"] is not first and PKG in sys.modules)


@test
def test_the_design_packs_modules_survive_a_made_up_id(ctx: Ctx):
    from halo_harness.ext import testing
    from tests.helpers.packs_home import PacksHome, SHIPPED
    with PacksHome() as h:
        with testing.studio(SHIPPED / "design", cwd=h.repo) as s:
            ctx.check("the design pack answers", s.call("GET", s.route("projects"))[0] == 200)
            before = _mods("halo_packs.design")
            ctx.check(f"its modules are loaded, got {len(before)}", len(before) >= 5)
            status = s.call("GET", "/api/packs/design.server/x/y")[0]
            ctx.check(f"/api/packs/design.server/x/y: 404, none dropped, got {status} {sorted(before - _mods('halo_packs.design'))}",
                      status == 404 and before <= _mods("halo_packs.design"))


@test
def test_an_update_of_a_sibling_module_answers_at_once(ctx: Ctx):
    from halo_harness.packs import state as S
    from halo_harness.packs.update import update
    from halo_harness.studio import packs_routes as PR
    with PackStudio() as s:
        src = s.source("routes-pack")
        s.install(src, enable=True, grants=["studio-routes"])
        ctx.check("v1 answers 1", _get(s, "value")[:2] == (200, {"value": 1}))
        installed = s.packs / "routes-pack" / "server" / "routes.py"
        st = installed.stat()
        os.utime(src / "server" / "routes.py", ns=(st.st_atime_ns, st.st_mtime_ns))  # routes.py's time stays the same
        (src / "server" / "value.py").write_text("VALUE = 2\n", encoding="utf-8")
        ok, lines = update("routes-pack", cwd=s.repo, state_dir=s.state)
        ctx.check(f"the update ran, got {lines[-2:]}", ok)
        ctx.check(f"routes.py kept its time, got {installed.stat().st_mtime_ns} vs {st.st_mtime_ns}",
                  installed.stat().st_mtime_ns == st.st_mtime_ns)
        ctx.check(f"the next request answers the new value, got {_get(s, 'value')[:2]}", _get(s, "value")[:2] == (200, {"value": 2}))
        first = PR._loaded["routes-pack"]["module"]
        S.put("routes-pack", {"version": "1.0.1"}, s.state)  # the record alone moves: no file, no notify
        _get(s, "ping")
        ctx.check("a changed install record loads the module afresh", PR._loaded["routes-pack"]["module"] is not first)


@test
def test_a_raw_answer_gets_a_csp_and_unload_runs_the_hook(ctx: Ctx):
    from halo_harness.studio.packs_routes import DEFAULT_CSP
    marker = Path(tempfile.mkdtemp(prefix="halo-unload-")) / "unload.txt"
    try:
        with PackStudio() as s:
            from halo_harness.studio.packs_routes import unload
            unload("routes-pack")  # an earlier test's copy (another home) goes first, before the hook is watched
            os.environ["ROUTES_PACK_UNLOAD_FILE"] = str(marker)
            s.install_pack("routes-pack", grants=["studio-routes"])
            status, heads, _b = fetch(f"{s.base}/api/packs/routes-pack/r/page", headers={"Authorization": "Bearer " + s.token})
            ctx.check(f"a page with no CSP of its own gets the default, got {heads.get('Content-Security-Policy')!r}",
                      status == 200 and heads.get("Content-Security-Policy") == DEFAULT_CSP == "sandbox; default-src 'none'")
            status, heads, _b = fetch(f"{s.base}/api/packs/routes-pack/r/styled", headers={"Authorization": "Bearer " + s.token})
            ctx.check("its own CSP stays, another header is dropped",
                      heads.get("Content-Security-Policy") == "default-src 'self'" and "X-Other" not in heads)
            ctx.check("JSON keeps Studio's headers", _get(s, "ping")[0] == 200)
            ctx.check("loaded, no unload yet", not marker.exists())
            from halo_harness.packs.grants import disable
            disable("routes-pack", state_dir=s.state)
            ctx.check("turned off: its unload() ran once", marker.is_file()
                      and marker.read_text(encoding="utf-8") == "unloaded\n")
    finally:
        os.environ.pop("ROUTES_PACK_UNLOAD_FILE", None)
        shutil.rmtree(marker.parent, ignore_errors=True)


if __name__ == "__main__":
    ctx = Ctx()
    results, passed, failed, skipped = run_all(TESTS, ctx)
    sys.exit(print_results(results, passed, failed, skipped))
