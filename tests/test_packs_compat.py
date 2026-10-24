"""tests.test_packs_compat -- the compatibility policy, enforced (Halo 3.2.0.0
R7, halo_harness/ext/compat.py, packs/resolve.py compat_lines,
packs/deprecations.py; docs/EXTENSION_API.md "Compatibility and migration"):
`api_version()`, `compatible(range)` (max inclusive at its precision; no max:
the min's major only), `range_words`, `deprecations()` (empty in 1.0); the
one line per range problem in the policy's words, the same on the CLI and in
Studio's Pack Manager; a pack using a name announced for removal gets a
doctor row naming the version it goes away in; the doc carries the policy
and its two example lines.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from tests.helpers.packs_studio import PackStudio  # noqa: E402
from tests.helpers.runner import Ctx, new_registry, print_results, run_all  # noqa: E402

test, TESTS = new_registry()
REPO = Path(__file__).resolve().parent.parent


def _with_range(src: Path, api: str, halo: str = "") -> None:
    text = (src / "pack.yaml").read_text(encoding="utf-8").replace('halo_api: {min: "1.0", max: "1.9"}', api)
    if halo:
        text = text.replace('halo: {min: "3.1"}', halo)
    (src / "pack.yaml").write_text(text, encoding="utf-8")


@test
def test_the_policy_functions(ctx: Ctx):
    import halo_harness.ext as ext
    from halo_harness.ext.compat import range_words
    ctx.check("api_version() is API_VERSION", ext.api_version() == ext.API_VERSION == "1.0")
    cases = [({"min": "1.0", "max": "1.9"}, "1.0", True), ({"min": "1.0", "max": "1.9"}, "1.9.4", True),
             ({"min": "1.0", "max": "1.9"}, "2.0", False), ({"min": "1.2", "max": "1.9"}, "1.0", False),
             ({"min": "1.0"}, "1.7", True), ({"min": "1.0"}, "2.0", False), ({"min": "2.0"}, "1.0", False),
             ({"max": "1.9"}, "1.0", True), ({"min": "x"}, "1.0", False), ("1.0", "1.0", False)]
    for rng, version, want in cases:
        ctx.check(f"compatible({rng}, {version}) is {want}", ext.compatible(rng, version) is want)
    ctx.check("compatible(range) reads this Halo's API by default", ext.compatible({"min": "1.0"}) is True)
    words = {"1.0 to 1.9": {"min": "1.0", "max": "1.9"}, "1.2 or a later 1.x": {"min": "1.2"}, "<= 1.9": {"max": "1.9"}}
    for want, rng in words.items():
        ctx.check(f"range_words({rng}) is {want!r}, got {range_words(rng)!r}", range_words(rng) == want)
    ctx.check("nothing is announced for removal in 1.0", ext.deprecations() == [])
    from halo_harness.ext import compat
    compat.DEPRECATED["read_yaml"] = {"since": "1.3", "removed_in": "2.0", "use": "read_file"}
    try:
        ctx.check(f"a listed name, got {ext.deprecations()}",
                  ext.deprecations() == [{"name": "read_yaml", "since": "1.3", "removed_in": "2.0", "use": "read_file"}])
    finally:
        compat.DEPRECATED.clear()


@test
def test_the_policy_lines(ctx: Ctx):
    from halo_harness.packs.discover import Pack
    from halo_harness.packs.resolve import compat_lines

    def lines(api, halo=None, *, at="1.0", this="3.2.0.0"):
        m = {"id": "doc-review", "halo_api": api, **({"halo": halo} if halo else {})}
        return compat_lines(Pack(id="doc-review", root=Path("nowhere"), scope="user", manifest=m), api_version=at, halo_version=this)
    ctx.check("the brief's API line", lines({"min": "1.2", "max": "1.9"}) == ["pack doc-review needs extension API 1.2 to 1.9; this Halo has 1.0"])
    ctx.check("too old: a pack for an API this Halo is past", lines({"min": "0.5", "max": "0.9"})
              == ["pack doc-review needs extension API 0.5 to 0.9; this Halo has 1.0"])
    ctx.check("a new major without max", lines({"min": "1.0"}, at="2.0") == ["pack doc-review needs extension API 1.0 or a later 1.x; this Halo has 2.0"])
    ctx.check("the brief's Halo line", lines({"min": "1.0"}, {"min": "3.3"}, this="3.2.0") == ["pack doc-review needs Halo >= 3.3; this is 3.2.0"])
    ctx.check("both at once: two lines, API first", len(lines({"min": "1.2"}, {"max": "3.1"})) == 2)
    ctx.check("in range: no line", lines({"min": "1.0", "max": "1.9"}, {"min": "3.1"}) == [])


@test
def test_the_same_line_on_the_cli_and_in_studio(ctx: Ctx):
    with PackStudio() as s:
        src = s.source()
        _with_range(src, 'halo_api: {min: "1.2", max: "1.9"}')
        code, _out, err = s.cli("install", str(src))
        line = "pack doc-review needs extension API 1.2 to 1.9; this Halo has 1.0"
        ctx.check(f"the CLI refuses with the one line, got {err!r}", code == 1 and err.strip() == f"halo pack: {line}")
        status, body, _ = s.call("POST", "pack/install", {"source": str(src)})
        ctx.check(f"Studio's Install answers the same line, got {status} {body}", status == 422 and body["problems"] == [line])
        s.config({"packs": {"sources": [str(src.parent)]}})
        status, body, _ = s.call("GET", "pack/manager")
        details = [p["details"] for row in body["sources"] for p in row["packs"] if p["id"] == "doc-review" and p.get("details")]
        ctx.check(f"the Manager's Details for the source pack, first, got {details[:1] and details[0]['compat']}",
                  details and details[0]["compat"][0] == line)
        ctx.check("nothing was installed", not (s.packs / "doc-review").exists())


@test
def test_a_deprecated_name_gets_a_doctor_row(ctx: Ctx):
    from halo_harness.ext import compat
    with PackStudio() as s:
        s.install_pack(grants=["hooks"])
        code, out, _err = s.cli("doctor")
        ctx.check("nothing announced: no deprecated row", "deprecated since" not in out)
        compat.DEPRECATED["get_config"] = {"since": "1.3", "removed_in": "2.0", "use": "settings"}
        try:
            from halo_harness.packs.deprecations import used_names
            from halo_harness.packs.discover import find
            used = used_names(find("doc-review", cwd=s.repo))
            ctx.check(f"the walk finds the pack's ext names, got {used}", ("mcp/lint_server.py", 15, "get_config") in used
                      and any(n == "publish_event" and f == "hooks/note.py" for f, _l, n in used))
            text = ("doc-review: mcp/lint_server.py line 15 uses ext.get_config, deprecated since API 1.3; "
                    "it goes away in API 2.0 (use ext.settings)")
            code, out, _err = s.cli("doctor")
            ctx.check(f"halo pack doctor names the version it goes away in, got {out}", f"[WARN] {text} -> use ext.settings" in out)
            status, body, _ = s.call("GET", "pack/manager")
            health = [h["text"] for p in body["packs"] for h in p["health"] if h["check"] == "deprecated"]
            ctx.check(f"the Manager's health shows the same line, got {health}", status == 200 and health == [text])
        finally:
            compat.DEPRECATED.clear()


@test
def test_the_doc_states_the_policy(ctx: Ctx):
    doc = (REPO / "docs" / "EXTENSION_API.md").read_text(encoding="utf-8")
    section = doc.split("## Compatibility and migration", 1)[1].split("\n## ", 1)[0]
    for needle in ("pack doc-review needs extension API 1.2 to 1.9; this Halo has 1.0", "pack x needs Halo >= 3.3; this is 3.2.0.0",
                   "### Changes in 1.x", "### Updating a pack", "### Rolling back", "deprecations()", "compatible(", "api_version()"):
        ctx.check(f"the section has {needle!r}", needle in section)
    rows = [r for r in doc.split("## Status of each part", 1)[1].split("\n## ", 1)[0].splitlines() if r.startswith("| [")]
    ctx.check(f"every part is stable or removed, got {[r.split('|')[2].strip() for r in rows]}",
              rows and all(r.split("|")[2].strip() == "stable" or r.split("|")[2].strip().startswith("removed") for r in rows))
    init = (REPO / "halo_harness" / "ext" / "__init__.py").read_text(encoding="utf-8")
    ctx.check("ext's docstring states the policy next to API_VERSION", "The version policy" in init and "a minor adds names" in init)
    data = json.loads((REPO / "halo_harness" / "packs" / "schema" / "pack.schema.json").read_text(encoding="utf-8"))
    ctx.check("the JSON schema's migration entry takes settings",
              "settings" in data["properties"]["migrations"]["items"]["properties"])


if __name__ == "__main__":
    ctx = Ctx()
    results, passed, failed, skipped = run_all(TESTS, ctx)
    sys.exit(print_results(results, passed, failed, skipped))
