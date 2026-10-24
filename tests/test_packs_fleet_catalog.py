"""tests.test_packs_fleet_catalog -- the packs' fleet capabilities in this
harness's capabilities catalog (Halo 3.2.0.0 R4, packs/fleet_registry.py,
fleet/capabilities_sources.py `packs`):

1. the `packs` section lists each running pack's capabilities, available here
   or not and why (the bash grant and a model with `tools`; no GPU); a
   disabled pack, or one with no contributes.fleet, adds nothing; a fleet with
   no pack is unchanged (summary, chips, the spec sheet);
2. summary and chips count them ("+1 pack cap"), the spec sheet lists them,
   `who` ranks them (one not available here at half, with why), and
   `halo fleet who` finds them;
3. paths in what a pack advertises are cut by the catalog's scrub: none in the
   section, the announce fields, the `capabilities` command's answer or the
   hub's copy;
4. the catalog goes stale on every pack change (enable, disable) and on a
   `pack_changed` Studio publishes for another process's change.

Run: python -m tests.test_packs_fleet_catalog
"""

from __future__ import annotations

import contextlib
import io
import json
import sys
from pathlib import Path
from types import SimpleNamespace

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from tests.helpers.packs_home import PacksHome  # noqa: E402
from tests.helpers.runner import Ctx, new_registry, print_results, run_all  # noqa: E402

test, TESTS = new_registry()
TOOLS_ROW = {"ref": "or:anthropic/claude-sonnet-4.6", "provider": "openrouter", "tools": True}
PATHS_PACK = """id: paths-pack
name: Paths in an advertisement
version: 0.1.0
halo_api: {min: "1.0"}
capabilities: [sync.push]
contributes:
  fleet:
    capabilities:
      - name: sync.push
        description: Pushes the build to the share
        requires:
          tools: ['C:\\Users\\someone\\tools\\sync.exe', /home/someone/bin/syncd, '%HOMEDIR%/bin/push']
    mission:
      metadata: {notes: 'C:\\Users\\someone\\notes\\plan.md', home: '%HOMEDIR%/notes/today.md'}
"""


def _gather(h):
    from halo_harness.fleet import capabilities as caps
    return caps.gather(h.state, cwd=h.repo)


def _setup(h) -> None:
    h.catalog([TOOLS_ROW])
    h.install(h.source(), enable=True, grants=["bash"])
    h.install(h.source("fleet-needs-gpu"), enable=True)


@test
def test_the_section_lists_running_packs_with_available_and_why(ctx: Ctx):
    from halo_harness.fleet import capabilities as caps
    from halo_harness.fleet.capabilities_view import spec_lines
    with PacksHome() as h:
        cat = _gather(h)
        ctx.check(f"no pack: an empty section, got {cat.get('packs')}", cat.get("packs") == [])
        plain = (caps.summary(cat), caps.chips(cat), [ln for ln in spec_lines(cat) if ln.strip().startswith("packs")])
        ctx.check(f"and the summary, chips and spec sheet say nothing of packs, got {plain}", "pack" not in plain[0]
                  and not any("pack" in c for c in plain[1]) and plain[2] == [])
        _setup(h)
        h.install(h.source("rare-caps"), enable=True)
        packs = {p["id"]: p for p in _gather(h)["packs"]}
        ctx.check(f"the running packs with a fleet part, in order, got {list(packs)}", list(packs) == ["doc-review", "fleet-needs-gpu"])
        doc = packs["doc-review"]["capabilities"][0]
        ctx.check(f"docs.review: available, why = the model and the grant, got {doc}", doc["available"] is True
                  and doc["why"] == "tools: or:anthropic/claude-sonnet-4.6; bash granted" and doc["capacity"] == {"parallel": 2})
        ctx.check("each check named", [(c["key"], c["ok"]) for c in doc["checks"]] == [("models", True), ("grants", True)])
        ctx.check("the inspector line and the metadata travel with it", packs["doc-review"]["inspector"]
                  == [{"label": "Review checklist", "source": "fleet/checklist.md"}]
                  and packs["doc-review"]["metadata"] == {"review": "docs", "style": "short"})
        gpu = packs["fleet-needs-gpu"]["capabilities"][0]
        ctx.check(f"gpu.render: not available, why = no GPU here, got {gpu['why']!r}", gpu["available"] is False and gpu["why"] == "no GPU here")
        from halo_harness.packs.grants import disable
        disable("fleet-needs-gpu")
        ctx.check("a disabled pack adds nothing", [p["id"] for p in _gather(h)["packs"]] == ["doc-review"])
        h.catalog([])
        doc = _gather(h)["packs"][0]["capabilities"][0]
        ctx.check(f"no model with tools: not available, said so, got {doc['why']!r}", doc["available"] is False
                  and doc["why"] == "no model in the catalog has tools")


THINK_PACK = """id: think-pack
name: Needs a reasoning model
version: 0.1.0
halo_api: {min: "1.0"}
capabilities: [plan.deep]
contributes:
  fleet:
    capabilities:
      - name: plan.deep
        description: Plans a long change with a model that reasons
        requires:
          models: [reasoning, open-weights]
"""


@test
def test_requires_models_takes_the_enriched_tags(ctx: Ctx):
    """3.2.1.0 R1: `requires.models` may name reasoning / open-weights / audio-out (bio_models.TAGS)."""
    with PacksHome() as h:
        src = h.sources / "think-pack"
        src.mkdir(parents=True)
        (src / "pack.yaml").write_text(THINK_PACK, encoding="utf-8")
        h.install(src, enable=True)
        h.catalog([dict(TOOLS_ROW, reasoning={"kind": "none"})])
        cap = next(p for p in _gather(h)["packs"] if p["id"] == "think-pack")["capabilities"][0]
        ctx.check(f"no row reasons: not available, one line per tag, got {cap['why']!r}", cap["available"] is False
                  and cap["why"] == "no model in the catalog has reasoning; no model in the catalog has open-weights")
        h.catalog([{"ref": "or:vendor/open-thinker", "provider": "openrouter", "reasoning": {"kind": "openai", "efforts": ["high"]},
                    "open_weights": True}])
        cap = next(p for p in _gather(h)["packs"] if p["id"] == "think-pack")["capabilities"][0]
        ctx.check(f"a row that reasons with open weights: available, got {cap['why']!r}", cap["available"] is True
                  and cap["why"] == "reasoning: or:vendor/open-thinker; open-weights: or:vendor/open-thinker")


@test
def test_summary_chips_spec_and_who_count_them(ctx: Ctx):
    from halo_harness.fleet import capabilities as caps
    from halo_harness.fleet.capabilities_view import spec_lines
    from halo_harness.fleet import capabilities_who as who
    with PacksHome() as h:
        _setup(h)
        cat = _gather(h)
        ctx.check(f"the summary counts the available ones, got {caps.summary(cat)!r}", "+1 pack cap" in caps.summary(cat))
        ctx.check(f"a chip after the tags, got {caps.chips(cat)}", caps.chips(cat)[0] == "+1 pack cap")
        row = [ln for ln in spec_lines(cat) if ln.strip().startswith("packs")]
        ctx.check(f"the spec sheet's packs row, got {row}", row == [
            "  packs      doc-review: docs.review, fleet-needs-gpu: gpu.render (not here: no GPU here)"])
        entries = [{"harness": "h1", "name": "me", "catalog": cat}]
        got = who.rank(entries, "docs review")
        ctx.check(f"who docs review: the pack capability, exact, got {got}", got and got[0]["matches"][0]["kind"] == "pack"
                  and got[0]["matches"][0]["name"] == "docs.review" and got[0]["matches"][0]["score"] == who.EXACT)
        got = who.rank(entries, "render frames")
        m = got[0]["matches"][0] if got else {}
        ctx.check(f"one not available here counts half, with why, got {m}", m.get("name") == "gpu.render" and m.get("score") == 2.5
                  and m.get("why", "").endswith("(not available here: no GPU here)"))
        caps.save(cat, h.state)
        from halo_harness.fleet import identity
        from halo_harness.fleet.cli_caps import cmd_who
        identity.forget_cache()
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            rc = cmd_who(["docs", "review"])
        ctx.check(f"halo fleet who docs review finds it, got {rc} {out.getvalue()!r}", rc == 0
                  and "pack       docs.review" in out.getvalue())


@test
def test_paths_are_scrubbed_before_anything_leaves(ctx: Ctx):
    from halo_harness.fleet import capabilities as caps
    from halo_harness.fleet import control
    from halo_harness.fleet.hub_capabilities import _trim
    with PacksHome() as h:
        src = h.sources / "paths-pack"
        src.mkdir(parents=True)
        text = PATHS_PACK.replace("%HOMEDIR%", str(h.home).replace("\\", "/"))
        bad = (text.replace("Pushes the build to the share", f"Pushes {h.home} to the share")
               .replace("{notes: ", "{key: ghp_abcdefghijklmnopqrstuvwxyz0123456789, notes: ")
               .replace("/home/someone/bin/syncd", "$SYNC_HOME/syncd"))
        (src / "pack.yaml").write_text(bad, encoding="utf-8")
        code, _out, err = h.cli("install", str(src))
        lines = err.strip().splitlines()
        ctx.check(f"the manifest refuses the token, the env reference and the description's path, got {lines}", code == 1
                  and len(lines) == 3 and any("metadata.key: a token-shaped value" in ln for ln in lines)
                  and any("tools[1]: an environment reference ($SYNC_HOME)" in ln for ln in lines)
                  and any("description: holds a path" in ln for ln in lines) and "ghp_" not in err)
        (src / "pack.yaml").write_text(text, encoding="utf-8")
        h.install(src, enable=True)
        cat = _gather(h)
        sec = next(p for p in cat["packs"] if p["id"] == "paths-pack")
        tools = sec["capabilities"][0]["requires"]["tools"]
        ctx.check(f"each tool path cut to its last part, got {tools}", tools == ["sync.exe", "syncd", "push"])
        ctx.check(f"so is the metadata, got {sec['metadata']}", sec["metadata"] == {"notes": "plan.md", "home": "today.md"})
        ctx.check(f"and the why, got {sec['capabilities'][0]['why']!r}", sec["capabilities"][0]["why"] == "no sync.exe here; no syncd here; no push here")
        home_fwd = str(h.home).replace("\\", "/")

        def clean(obj) -> bool:
            blob = json.dumps(obj)
            return "Users\\\\someone" not in blob and "/home/someone" not in blob and home_fwd not in blob and str(h.home) not in blob
        ctx.check("nothing private in the catalog", clean(cat))
        caps.save(cat, h.state)
        ann = caps.announce_fields(h.state)
        ctx.check(f"the announce fields carry the summary and hash only, got {ann}", set(ann) == {"capabilities_summary", "capabilities_hash"}
                  and clean(ann))
        handle = SimpleNamespace(session=SimpleNamespace(), _note=lambda _m: None, kind="tui", controller=None)
        got = control.run(handle, {"cmd": "capabilities", "fields": {}}, {"share": "full", "allow_control": "none", "allow_answers": False})
        ctx.check("the capabilities command's answer: the scrubbed catalog", got.get("state") == "done" and clean(got.get("result"))
                  and any(p["id"] == "paths-pack" for p in got["result"]["packs"]))
        ctx.check("and the hub's copy of it", clean(_trim(got["result"])))


@test
def test_the_catalog_goes_stale_on_a_pack_change(ctx: Ctx):
    from halo_harness.fleet import capabilities as caps
    from halo_harness.studio import packs_studio_live as live
    with PacksHome() as h:
        h.catalog([TOOLS_ROW])
        before = caps.refresh(h.state, cwd=h.repo)[0]
        h.install(h.source(), enable=True, grants=["bash"])
        ctx.check("enable marked the cached catalog stale", caps.stale(caps.load(h.state)))
        after = caps.current(h.state, cwd=h.repo)
        ctx.check("the next read gathers the pack's capability: a new hash", after["hash"] != before["hash"]
                  and [p["id"] for p in after["packs"]] == ["doc-review"])
        h.cli("disable", "doc-review")
        ctx.check("disable too", caps.stale(caps.load(h.state)))
        caps.refresh(h.state, cwd=h.repo)
        ctx.check("fresh again", not caps.stale(caps.load(h.state)))
        live.publish(SimpleNamespace(cwd=h.repo, state_dir=h.state), "changed")
        ctx.check("a pack_changed (another process's change, seen by Studio's watch) marks it stale",
                  caps.stale(caps.load(h.state)))


if __name__ == "__main__":
    ctx = Ctx()
    results, passed, failed, skipped = run_all(TESTS, ctx)
    sys.exit(print_results(results, passed, failed, skipped))
