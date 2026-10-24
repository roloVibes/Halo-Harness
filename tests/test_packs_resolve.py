"""tests.test_packs_resolve -- which enabled packs run, and in what order
(Halo 3.2.0.0 R1, halo_harness/packs/resolve.py): a missing dependency, a
disabled one, one at a version outside the range, an extension API or Halo
version outside the pack's range and a requires cycle are each one line and
keep the pack (and the packs requiring it) from running; the order puts
every pack after what it requires; on disk, the registry runs only packs
enabled for their own folder.
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from tests.helpers.packs_home import PacksHome  # noqa: E402
from tests.helpers.runner import Ctx, new_registry, print_results, run_all  # noqa: E402

test, TESTS = new_registry()


def _pack(pid: str, *, version="1.0.0", requires=(), api=None, halo=None):
    from halo_harness.packs.discover import Pack
    manifest = {"id": pid, "name": pid, "version": version, "halo_api": api or {"min": "1.0"}}
    if requires:
        manifest["requires"] = list(requires)
    if halo:
        manifest["halo"] = halo
    return Pack(id=pid, root=Path("/nowhere") / pid, scope="user", manifest=manifest)


def _resolve(packs, enabled=None, **kw):
    from halo_harness.packs.resolve import resolve
    return resolve(packs, enabled=enabled if enabled is not None else [p.id for p in packs],
                   api_version=kw.get("api", "1.0"), halo_version=kw.get("halo", "3.2.0.0"))


@test
def test_order_puts_dependencies_first(ctx: Ctx):
    packs = [_pack("app", requires=[{"pack": "lib", "version": "1.2"}]), _pack("lib", version="1.4.0"),
             _pack("tools", requires=[{"pack": "app"}])]
    order, problems = _resolve(packs)
    ctx.check(f"lib, app, tools; got {order}", order == ["lib", "app", "tools"] and problems == {})


@test
def test_a_missing_or_disabled_dependency(ctx: Ctx):
    order, problems = _resolve([_pack("app", requires=[{"pack": "lib"}])])
    ctx.check(f"missing: one line, got {problems}", order == [] and problems["app"] == ["app requires lib, which is not installed"])
    packs = [_pack("app", requires=[{"pack": "lib"}]), _pack("lib")]
    order, problems = _resolve(packs, enabled=["app"])
    ctx.check(f"disabled: one line naming the enable, got {problems}",
              order == [] and len(problems["app"]) == 1 and "halo pack enable lib" in problems["app"][0])
    packs = [_pack("app", requires=[{"pack": "lib", "version": {"min": "2.0", "max": "2.9"}}]), _pack("lib", version="1.4.0")]
    order, problems = _resolve(packs)
    ctx.check(f"a version outside the range, got {problems}",
              order == ["lib"] and problems["app"] == ["app requires lib 2.0 to 2.9; 1.4.0 is installed"])
    packs = [_pack("app", requires=[{"pack": "lib"}]), _pack("lib", api={"min": "2.0"})]
    order, problems = _resolve(packs)
    ctx.check(f"a dependency that does not run takes its dependents with it, got {order} {problems}",
              order == [] and any("lib, which does not run" in ln for ln in problems["app"]))


@test
def test_an_incompatible_api_or_halo_version(ctx: Ctx):
    order, problems = _resolve([_pack("app", api={"min": "2.0"})])
    ctx.check(f"API: one line, got {problems}", order == [] and problems["app"] == ["pack app needs extension API 2.0 or a later 2.x; this Halo has 1.0"])
    order, problems = _resolve([_pack("app", api={"min": "0.5", "max": "0.9"})])
    ctx.check("an API range that ends below 1.0", order == [] and "0.5 to 0.9" in problems["app"][0])
    order, problems = _resolve([_pack("app", halo={"min": "3.3"})])
    ctx.check(f"Halo: one line, got {problems}", order == [] and problems["app"] == ["pack app needs Halo >= 3.3; this is 3.2.0.0"])
    order, _problems = _resolve([_pack("app", halo={"min": "3.1", "max": "3.2"})])
    ctx.check("Halo 3.2.0.0 is inside 3.1 to 3.2", order == ["app"])
    from halo_harness.packs.resolve import compat_lines
    from halo_harness import ext
    ctx.check("the defaults come from ext.API_VERSION and __version__",
              compat_lines(_pack("app", api={"min": ext.API_VERSION})) == [])


@test
def test_a_requires_cycle(ctx: Ctx):
    packs = [_pack("a", requires=[{"pack": "b"}]), _pack("b", requires=[{"pack": "c"}]), _pack("c", requires=[{"pack": "a"}]),
             _pack("d")]
    order, problems = _resolve(packs)
    ctx.check(f"only d runs, got {order}", order == ["d"])
    ctx.check(f"each pack of the cycle has one cycle line, got {problems}",
              all(sum("requires cycle" in ln for ln in problems[p]) == 1 for p in "abc"))
    ctx.check("the line walks the cycle", "a -> b -> c -> a" in problems["a"][-1])


@test
def test_on_disk_only_packs_enabled_for_their_own_folder_run(ctx: Ctx):
    from halo_harness.packs import registry
    from halo_harness.packs import state as S
    with PacksHome() as h:
        ctx.check("an empty home: nothing", registry.active(cwd=h.repo) == [])
        h.install(h.source())
        ctx.check("installed, disabled: nothing runs", registry.active(cwd=h.repo) == [])
        S.put("doc-review", {"enabled": True}, None)
        ctx.check("enabled for its folder: it runs", [p.id for p in registry.active(cwd=h.repo)] == ["doc-review"])
        S.put("doc-review", {"root": str(h.repo / "elsewhere")}, None)
        ctx.check("a record naming another folder: it does not run", registry.active(cwd=h.repo) == [])


@test
def test_a_bio_edit_inside_an_installed_pack_shows_at_once(ctx: Ctx):
    """3.2.1.0 R1: the registry's key stats the pack's agents/, teams/ and workflows/ files, so a hand edit
    there drops (or restores) the pack at the next lookup, with no invalidate() call."""
    from halo_harness.packs import discover as D
    from halo_harness.packs import registry
    from halo_harness.packs.doctor import problems
    with PacksHome() as h:
        h.install(h.source(), enable=True)
        ctx.check("enabled: it runs", [p.id for p in registry.active(cwd=h.repo)] == ["doc-review"])
        bio = h.packs / "doc-review" / "agents" / "reviewer.yaml"
        good = bio.read_text(encoding="utf-8")
        before = D.signature(cwd=h.repo)
        bio.write_text(good.replace("  capabilities: [long-context]\n", "  provider: openrouter\n  capabilities: [long-context]\n"),
                       encoding="utf-8")
        ctx.check("the signature names the bio file and moved with the edit", before != D.signature(cwd=h.repo)
                  and any("agents/reviewer.yaml" in str(part) for part in D.signature(cwd=h.repo)))
        ctx.check("a provider in its bio: the pack is dropped, no invalidate() needed", registry.active(cwd=h.repo) == [])
        rows = [r for r in problems(cwd=h.repo) if r["pack"] == "doc-review" and r["check"] == "resolve"]
        ctx.check(f"the doctor row names the file and the key, got {[r['text'] for r in rows]}",
                  any("agents/reviewer.yaml" in r["text"] and "models.provider" in r["text"] for r in rows))
        bio.write_text(good, encoding="utf-8")
        ctx.check("the edit undone: it runs again", [p.id for p in registry.active(cwd=h.repo)] == ["doc-review"])
        (h.packs / "doc-review" / "teams" / "extra.yaml").write_text("agents:\n  - {agent: writer, role: main}\n", encoding="utf-8")
        ctx.check("a new lineup file is seen too (the doctor's undeclared row)",
                  any(r["check"] == "undeclared" and "teams/extra.yaml" in r["text"] for r in problems(cwd=h.repo)))


if __name__ == "__main__":
    ctx = Ctx()
    results, passed, failed, skipped = run_all(TESTS, ctx)
    sys.exit(print_results(results, passed, failed, skipped))
