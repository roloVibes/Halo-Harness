"""tests.test_settings_catalog -- the Settings catalog (Halo 3.3.3.0 R2, halo_harness/settings_catalog.py): one
row per key of `~/.halo/config.json`, held to the config schema (schemas/config_json.py) and to docs/CONFIG.md's
key table, so a new key has to land in all three. No Studio, no network, no model call:

1. every top-level scalar and section of the schema is covered by at least one row;
2. every key in docs/CONFIG.md's table (the Key column, backticks stripped, placeholders kept) is a row, every
   row is in the table, and the table's Studio column names the row's page;
3. every row has a help line, a known group, a known kind, an effect; an enum row has choices; a keyed row has
   a placeholder; the keys are unique; the rows files are each under 250 lines;
4. `cli_line` writes `halo config set <key> <value>` and its value round-trips through `json.loads` for list
   and mapping rows; `match` finds a keyed row's entry;
5. a row's default passes its own kind's check (studio/settings_values.coerce).
Run: python -m tests.test_settings_catalog
"""

from __future__ import annotations

import json
import re
import shlex
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from tests.helpers.runner import Ctx, new_registry, print_results, run_all  # noqa: E402

test, TESTS = new_registry()
REPO = Path(__file__).resolve().parent.parent
CELL = re.compile(r"(?<!\\)\|")


def _table() -> "list[list[str]]":
    """docs/CONFIG.md's config.json key table: [key, default, set by, studio] per row."""
    lines = (REPO / "docs" / "CONFIG.md").read_text(encoding="utf-8").split("\n")
    head = lines.index("| Key | Default | Set by | Studio |")
    out = []
    for line in lines[head + 2:]:
        if not line.startswith("|"):
            break
        cells = [c.strip() for c in CELL.split(line)[1:-1]]
        out.append([cells[0].replace("`", "")] + cells[1:])
    return out


@test
def test_every_schema_key_has_a_row(ctx: Ctx):
    from halo_harness.schemas.config_json import _SCALARS, _SECTIONS, schema
    from halo_harness.settings_catalog import rows
    keys = [r.key for r in rows()]
    props = schema()["properties"]
    ctx.check(f"the schema's top level is the scalars, theme and the sections, got {len(props)}",
              set(props) == set(_SCALARS) | {"theme"} | set(_SECTIONS))
    missing = [k for k in props if not any(x == k or x.startswith(k + ".") for x in keys)]
    ctx.check(f"every top-level scalar and section has a row, missing {missing}", not missing)
    stray = sorted({k.split(".")[0] for k in keys} - set(props))
    ctx.check(f"every row lives under a schema key, stray {stray}", not stray)


@test
def test_the_config_doc_table_and_the_catalog_hold_the_same_keys(ctx: Ctx):
    from halo_harness.settings_catalog import row, rows, studio_page
    table = _table()
    doc_keys = [r[0] for r in table]
    keys = [r.key for r in rows()]
    ctx.check(f"the table has a row per catalog row ({len(keys)}), got {len(doc_keys)}", len(doc_keys) == len(keys))
    ctx.check(f"every documented key is a row, missing {sorted(set(doc_keys) - set(keys))}", set(doc_keys) <= set(keys))
    ctx.check(f"every row is documented, missing {sorted(set(keys) - set(doc_keys))}", set(keys) <= set(doc_keys))
    ctx.check("no key is documented twice", len(set(doc_keys)) == len(doc_keys))
    ctx.check("every table row has four cells", all(len(r) == 4 for r in table))
    wrong = [(r[0], r[3]) for r in table if row(r[0]) is not None and r[3] != studio_page(row(r[0]))]
    ctx.check(f"the Studio column names each row's page (Settings -> <group>), wrong {wrong[:5]}", not wrong)
    ctx.check("the table names Fleet's page for fleet.enabled", dict((r[0], r[3]) for r in table).get("fleet.enabled") == "Settings -> Fleet")


@test
def test_every_row_is_complete(ctx: Ctx):
    from halo_harness.settings_catalog import EFFECTS, GROUP_TITLES, KINDS, groups, keyed_parts, rows
    rs = rows()
    ctx.check(f"seventeen groups in the brief's order, got {[g['id'] for g in groups()]}", [g["id"] for g in groups()] == [
        "general", "agents", "coach", "knowledge", "supervise", "steer", "models", "providers", "ollama", "network", "fleet",
        "remote", "packs", "connectors", "worktree", "update", "local"])
    ctx.check("every group holds a row", all(g["count"] > 0 for g in groups()))
    ctx.check("the keys are unique", len({r.key for r in rs}) == len(rs))
    for r in rs:
        ctx.check(f"{r.key}: a help line of one sentence", bool(r.help) and r.help.endswith(".") and "\n" not in r.help)
        ctx.check(f"{r.key}: a known group, kind and effect", r.group in GROUP_TITLES and r.kind in KINDS and r.effect in EFFECTS)
        ctx.check(f"{r.key}: a title", bool(r.title.strip()))
        if r.kind == "enum":
            ctx.check(f"{r.key}: an enum row has choices", len(r.choices) >= 1)
        if r.kind == "keyed":
            ctx.check(f"{r.key}: a keyed row has a placeholder", "<" in r.key or "[]" in r.key)
            ctx.check(f"{r.key}: its section is named", bool(keyed_parts(r)[0]))
        else:
            ctx.check(f"{r.key}: a plain row has no placeholder", "<" not in r.key and "[]" not in r.key)
    secret = [r.key for r in rs if r.secret]
    ctx.check(f"the rows named key, token or secret are secret, got {secret}",
              all(r.secret for r in rs if re.search(r"(^|[._])(api_key|token|secret)$", r.key)) and "embeddings.api_key" in secret)
    for name in ("settings_catalog_rows_a.py", "settings_catalog_rows_b.py", "settings_catalog_rows_c.py", "settings_catalog.py"):
        n = len((REPO / "halo_harness" / name).read_text(encoding="utf-8").splitlines())
        ctx.check(f"{name} is under 250 lines, got {n}", n < 250)


@test
def test_cli_line_and_match(ctx: Ctx):
    from halo_harness.settings_catalog import cli_line, match, rows
    ctx.check("a bool", cli_line("fleet.enabled", True) == "halo config set fleet.enabled true")
    ctx.check("an int", cli_line("fleet.hub.port", 7431) == "halo config set fleet.hub.port 7431")
    ctx.check("a word", cli_line("fleet.share", "full") == "halo config set fleet.share full")
    ctx.check("a string that reads as JSON stays a string", shlex.split(cli_line("fleet.name", "123"))[-1] == '"123"')
    ctx.check("unset: the placeholder", cli_line("model", None) == "halo config set model <value>")
    samples = {"list": ["gpu", "it's studio"], "mapping": {"gpt-5": "responses", "n": 2}}
    for r in rows():
        if r.kind in samples:
            line = cli_line(r.key, samples[r.kind])
            words = shlex.split(line)
            ctx.check(f"{r.key}: halo config set <key> <JSON>, round-trips, got {line!r}",
                      words[:4] == ["halo", "config", "set", r.key] and json.loads(words[4]) == samples[r.kind])
    ctx.check("a [] row's line sets its list", cli_line("ollama.hosts[].ssh", [{"name": "lan"}]).startswith("halo config set ollama.hosts '"))
    for key, want in (("connectors.gmail.enabled", ("connectors.<slug>.enabled", "gmail")), ("ollama.hosts[lan].ssh", ("ollama.hosts[].ssh", "lan")),
                      ("databricks.gateway.my-ep", ("databricks.gateway.<endpoint>", "my-ep")), ("roles.coder", ("roles.<role>", "coder")),
                      ("roles.enabled", ("roles.enabled", "")), ("fleet.enabled", ("fleet.enabled", "")), ("nope.key", (None, ""))):
        r, entry = match(key)
        ctx.check(f"match({key!r}) -> {want}, got {(r.key if r else None, entry)}", (r.key if r else None, entry) == want)


@test
def test_every_default_passes_its_own_check(ctx: Ctx):
    from halo_harness.settings_catalog import catalog_json, leaf_kind, rows
    from halo_harness.studio.settings_values import coerce
    for r in rows():
        if r.default is None:
            continue
        kind = leaf_kind(r)
        _v, problems = coerce(kind, r.choices, r.default, r.key)
        ctx.check(f"{r.key}: its default {r.default!r} is a good {kind}, got {problems}", not problems)
    data = catalog_json()
    ctx.check("the catalog is JSON with the groups, the rows and the kinds", json.loads(json.dumps(data)) == data and
              len(data["rows"]) == len(rows()) and data["kinds"][-1] == "keyed")
    keyed = next(x for x in data["rows"] if x["key"] == "providers.<name>.enabled")
    ctx.check(f"a keyed row names its leaf control, section and known entries, got {keyed}",
              keyed["leaf_kind"] == "bool" and keyed["section"] == "providers" and keyed["leaf"] == "enabled" and "openrouter" in keyed["entry_names"])


if __name__ == "__main__":
    ctx = Ctx()
    results, passed, failed, skipped = run_all(TESTS, ctx)
    sys.exit(print_results(results, passed, failed, skipped))
