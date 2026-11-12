"""tests.test_packs_grant_lines -- every grant says what it gives, and a pack Halo does not ship gets a grant that runs
its code only on an explicit yes (Halo 3.4.1.2, the 2026-11-12 review's PACKS-6 and SERVERS-2's grant line;
packs/grants.py, packs/cli_ask.py, studio/packs_manager_api.py `_needs_yes`, docs/PACKS.md "Permissions"):

1. PACKS-6: `doctor` and `cli:<verb>` say they run the pack's Python inside halo with your rights and Halo's keys; no
   permission a manifest may request has a blank line; `studio-script` says it runs INSIDE Studio's page with Studio's
   power (SERVERS-2: no "a client scoped to this pack's own routes").
2. `--grant-all` on a pack Halo does not ship refuses without a yes and prints each grant that runs its code; a yes
   (`confirm`, `--yes`) gives them; naming each grant is that yes; a shipped pack is never asked.
3. Studio: a Grant / Enable of such a grant for such a pack answers 409 `needs_yes` with the lines, and `yes: true` gives it.
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from tests.helpers.packs_home import SHIPPED, PacksHome  # noqa: E402
from tests.helpers.packs_studio import PackStudio  # noqa: E402
from tests.helpers.runner import Ctx, new_registry, print_results, run_all  # noqa: E402

test, TESTS = new_registry()


@test
def test_packs_6_every_grant_says_what_it_gives(ctx: Ctx):
    from halo_harness.packs import grants as G
    from halo_harness.packs.manifest import PERMISSIONS
    for perm in PERMISSIONS + ("cli:fleet", "mcp:lint"):
        ctx.check(f"{perm}: a line, got {G.what(perm)!r}", bool(G.what(perm)))
    ctx.check("doctor names the pack's Python inside halo, your rights and Halo's keys",
              all(w in G.what("doctor") for w in ("Python inside halo", "your rights", "Halo's keys")))
    ctx.check("cli:<verb> too, with the verb", all(w in G.what("cli:mission") for w in ("Python inside halo", "halo mission", "Halo's keys")))
    ctx.check("studio-script runs INSIDE Studio's page with Studio's power",
              "INSIDE Studio's page" in G.what("studio-script") and "starting sessions that run commands" in G.what("studio-script")
              and "scoped to this pack's own routes" not in G.what("studio-script"))
    ctx.check("studio-routes, services and hooks say your rights", all("your rights" in G.what(p) for p in ("studio-routes", "services", "hooks")))


@test
def test_grant_all_on_a_pack_halo_does_not_ship_needs_a_yes(ctx: Ctx):
    from halo_harness.packs import state as S
    from halo_harness.packs.discover import find
    from halo_harness.packs.grants import enable
    with PacksHome() as h:
        h.install(h.source("routes-pack"))
        pack = find("routes-pack", cwd=h.repo, state_dir=h.state)
        ok, lines = enable(pack, grant_all=True, state_dir=h.state)
        ctx.check(f"refused without a yes, each grant said, got {ok} {lines}", not ok and any("studio-routes: runs this pack's Python" in ln for ln in lines)
                  and not (S.entry("routes-pack", h.state) or {}).get("enabled"))
        asked: list = []
        ok, lines = enable(pack, grant_all=True, state_dir=h.state, confirm=lambda look: asked.extend(look) or False)
        ctx.check(f"a no gives nothing, got {ok}", not ok and any("studio-routes" in ln for ln in asked))
        ok, lines = enable(pack, grant_all=True, state_dir=h.state, confirm=lambda _l: True)
        ctx.check(f"a yes gives them, got {ok} {S.granted('routes-pack', S.load(h.state))}", ok and "studio-routes" in S.granted("routes-pack", S.load(h.state)))
        h.cli("disable", "routes-pack")
        code, _out, err = h.cli("enable", "routes-pack", "--grant-all")
        ctx.check(f"the CLI with no terminal and no --yes refuses and says how, got {code} {err!r}", code == 1 and "--yes" in err)
        code, out, err = h.cli("enable", "routes-pack", "--grant", "studio-routes")
        ctx.check(f"naming the grant is the yes, got {code} {err!r}", code == 0)
        h.cli("disable", "routes-pack")
        code, out, err = h.cli("enable", "routes-pack", "--grant-all", "--yes")
        ctx.check(f"--yes gives them, got {code} {err!r}", code == 0)
        from halo_harness.packs.install import install
        ok, lines = install(str(SHIPPED / "coach"), cwd=h.repo, state_dir=h.state)
        ok2, lines2 = enable(find("coach", cwd=h.repo, state_dir=h.state), grant_all=True, state_dir=h.state)
        ctx.check(f"a pack Halo ships is never asked, got {ok} {ok2} {lines2[:1]}", ok and ok2)


@test
def test_studio_asks_the_owner_before_a_grant_that_runs_a_packs_code(ctx: Ctx):
    with PackStudio() as s:
        s.install_pack("service-pack", grants=[])
        status, got, _h = s.call("POST", "pack/service-pack/grant", {"need": "services"})
        ctx.check(f"409 needs_yes with the line, got {status} {got}", status == 409 and got.get("needs_yes") is True
                  and any("services: runs a program of this pack" in ln for ln in got.get("problems", [])))
        status, got, _h = s.call("POST", "pack/service-pack/grant", {"need": "bash"})
        ctx.check(f"bash is not one that runs its code itself: no question, got {status}", status == 200)
        status, got, _h = s.call("POST", "pack/service-pack/grant", {"need": "services", "yes": True})
        ctx.check(f"with yes it is given, got {status} {got.get('lines', [''])[:1]}", status == 200)


if __name__ == "__main__":
    ctx = Ctx()
    results, passed, failed, skipped = run_all(TESTS, ctx)
    sys.exit(print_results(results, passed, failed, skipped))
