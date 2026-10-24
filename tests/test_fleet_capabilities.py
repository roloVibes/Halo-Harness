"""tests.test_fleet_capabilities -- Halo 3.0.6.0 "Fleet Missions" round R6:
every harness says what it can do. gather() is pure (it writes nothing,
starts nothing under BRIDGE_TEST_NO_BACKGROUND_NET), never lists a full local
path or a hidden name; a slow MCP server does not hold it up; `who` ranks the
harness that has the thing first; the CLI verbs print and `--json`
round-trips; `/fleet who` answers in the TUI. The hub side (a member's
catalog over the HubRig, once per hash, refresh and the frame):
tests/test_fleet_capabilities_hub.py.

Run: python -m tests.test_fleet_capabilities
"""
from __future__ import annotations

import json
import os
import sys
import tempfile
import time
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO))

from tests.helpers.provider_env_defaults import ensure_default_provider_credentials

ensure_default_provider_credentials()

from tests.helpers.runner import Ctx, new_registry, print_results, run_all  # noqa: E402

test, TESTS = new_registry()
FAKE = {"type": "stdio", "command": sys.executable, "args": ["-m", "tests.helpers.fake_mcp_server"], "cwd": str(REPO)}


class _Home:
    """A fresh BRIDGE_TEST_HOME (+ BRIDGE_TEST_NO_BACKGROUND_NET=1) for one test, restored after."""

    def __enter__(self):
        self.saved = {k: os.environ.get(k) for k in ("BRIDGE_TEST_HOME", "BRIDGE_STATE_DIR", "BRIDGE_TEST_NO_BACKGROUND_NET")}
        os.environ.pop("BRIDGE_STATE_DIR", None)
        self.root = Path(tempfile.mkdtemp(prefix="caps-"))
        os.environ.update(BRIDGE_TEST_HOME=str(self.root), BRIDGE_TEST_NO_BACKGROUND_NET="1")
        from halo_harness.config.paths import bridge_home
        from halo_harness.fleet import identity
        identity.forget_cache()
        self.home = bridge_home()
        self.home.mkdir(parents=True, exist_ok=True)
        return self

    def config(self, data: dict) -> None:
        from halo_harness.fleet import identity
        (self.home / "config.json").write_text(json.dumps(data), encoding="utf-8")
        identity.forget_cache()

    def __exit__(self, *exc):
        for k, v in self.saved.items():
            if v is None:
                os.environ.pop(k, None)
            else:
                os.environ[k] = v
        return False


@test
def test_gather_is_pure_and_hides_paths_and_hidden_names(ctx: Ctx):
    from halo_harness.fleet import capabilities as caps
    from tests.helpers.fleet_caps_seed import mcp_setup
    with _Home() as h:
        h.config({"fleet": {"name": "bob@member", "tags": ["data", "linux"],
                            "capabilities": {"hide": ["private-notes", "gridcraft/delete_sheet"]}}})
        deep = str(h.root / "work" / "books" / "q3.xlsx")
        mcp_setup(h.root, h.home, {"gridcraft": FAKE, "private-notes": FAKE, "plain": FAKE},
                  {"gridcraft": [("write_range", f"Write a range; saves to {deep}"), ("delete_sheet", "Delete a sheet")],
                   "private-notes": [("read_note", "Read a note")]})
        (h.home / "history.jsonl").write_text(json.dumps({"display": "x", "project": str(REPO)}) + "\n", encoding="utf-8")
        t0 = time.monotonic()
        cat = caps.gather(h.home, cwd=h.root)
        took = time.monotonic() - t0
        text = json.dumps(cat)
        servers = {s["name"]: s for s in cat["mcp"]}
        ctx.check(f"gather took {took:.1f} s with nothing started", took < 20)
        ctx.check("gather wrote no catalog file", not caps.cache_path(h.home).exists())
        ctx.check(f"the hidden server and the hidden tool are gone, got {sorted(servers)}",
                  "private-notes" not in servers and "delete_sheet" not in text and "read_note" not in text)
        grid = servers.get("gridcraft") or {}
        ctx.check(f"gridcraft lists its cached tool, got {grid}", [t["name"] for t in grid.get("tools") or []] == ["write_range"])
        ctx.check("an uncached server is listed with tools null and a note, never started",
                  servers.get("plain", {}).get("tools") is None and "no cached tool list" in servers["plain"].get("note", ""))
        ctx.check("no full local path anywhere (home, repo, the server's cwd, a path in a description)",
                  str(h.root) not in text and str(REPO) not in text and "q3.xlsx" in text and ":\\\\" not in text)
        ctx.check(f"projects are a basename and a repo, got {cat['projects']}",
                  any(p["name"] == REPO.name and p["repo"] for p in cat["projects"]))
        ctx.check("tags, craft apps and the hardware are there",
                  cat["tags"] == ["data", "linux"] and cat["craft_apps"] == ["gridcraft"] and cat["hardware"].get("cores"))
        again = caps.gather(h.home, cwd=h.root)
        ctx.check("the same harness gathers to the same hash", again["hash"] == cat["hash"])
        ctx.check(f"the summary counts and names the tags, got {caps.summary(cat)!r}",
                  caps.summary(cat).startswith("2 MCP servers (1 tools)") and "tags: data, linux" in caps.summary(cat))
        ctx.check(f"chips start with the tags, got {caps.chips(cat)}", caps.chips(cat)[:2] == ["data", "linux"])
        cat2, changed = caps.refresh(h.home, cwd=h.root)
        ctx.check("refresh caches it with its hash", changed and caps.load(h.home)["hash"] == cat2["hash"])
        caps.invalidate(h.home)
        ctx.check("`halo mcp add/remove` marks it stale", caps.stale(caps.load(h.home)))


@test
def test_hide_reaches_a_pack_capability(ctx: Ctx):
    """3.2.1.0 R3: `fleet.capabilities.hide` drops a pack capability by `name` or `<pack>/<name>` (any case), like a
    built-in one; the pack's other capabilities, its inspector lines and a catalog with no packs are unchanged."""
    from halo_harness.fleet import capabilities as caps
    cap = lambda n: {"name": n, "available": True, "why": "", "capacity": {}}  # noqa: E731
    cat = {"mcp": [], "skills": ["xlsx"], "craft_apps": [], "packs": [
        {"id": "doc-review", "capabilities": [cap("docs.review"), cap("docs.lint")], "inspector": [{"label": "x", "source": "a.md"}]},
        {"id": "other", "capabilities": [cap("docs.review")], "inspector": []}]}
    names = lambda c: [(p["id"], [x["name"] for x in p["capabilities"]]) for p in c["packs"]]  # noqa: E731
    got = caps.apply_hide(cat, {"doc-review/docs.review"})
    ctx.check(f"<pack>/<name>: that pack's only, got {names(got)}", names(got) == [("doc-review", ["docs.lint"]), ("other", ["docs.review"])]
              and got["packs"][0]["inspector"] == [{"label": "x", "source": "a.md"}] and got["skills"] == ["xlsx"])
    got = caps.apply_hide(cat, {"docs.review"})
    ctx.check(f"a bare name: every pack's, got {names(got)}", names(got) == [("doc-review", ["docs.lint"]), ("other", [])])
    ctx.check("nothing hidden: the catalog as it was", caps.apply_hide(cat, set()) is cat)
    plain = {"mcp": [], "skills": [], "craft_apps": []}
    ctx.check("a catalog with no packs section gets none", "packs" not in caps.apply_hide(plain, {"docs.review"}))


@test
def test_a_slow_mcp_server_does_not_block_gather(ctx: Ctx):
    from halo_harness.fleet import capabilities as caps
    from tests.helpers.fleet_caps_seed import mcp_setup
    with _Home() as h:
        slow = {**FAKE, "env": {"FAKE_MCP_MODE": "slow", "FAKE_MCP_SLEEP_S": "40"}}
        mcp_setup(h.root, h.home, {"quick": FAKE, "sleepy": slow}, {})
        t0 = time.monotonic()
        cat = caps.gather(h.home, cwd=h.root, spawn=True, mcp_timeout=12.0)  # the test starts its own fake servers
        took = time.monotonic() - t0
        servers = {s["name"]: s for s in cat["mcp"]}
        ctx.check(f"gather came back in {took:.1f} s (the slow server sleeps 40)", took < 25)
        names = [t["name"] for t in servers["quick"].get("tools") or []]
        ctx.check(f"the quick server was connected once and listed, got {names}", "echo" in names)
        ctx.check(f"the slow one is listed with tools null and a note, got {servers['sleepy']}",
                  servers["sleepy"]["tools"] is None and "no answer within" in servers["sleepy"].get("note", ""))
        ctx.check("the quick server's tool list is cached for the next gather",
                  (h.home / "mcp" / "tools-cache" / "quick.json").is_file())


@test
def test_who_ranks_the_harness_that_has_it_first(ctx: Ctx):
    from halo_harness.fleet import capabilities_who as who
    from tests.helpers.fleet_caps_seed import hub_catalog, member_catalog
    a = {"harness": "A", "name": "alice@hub", "catalog": hub_catalog({"id": "A", "name": "alice@hub"})}
    b = {"harness": "B", "name": "bob@member", "catalog": member_catalog({"id": "B", "name": "bob@member"})}
    got = who.rank([a, b], "gridcraft")
    ctx.check(f"gridcraft: only the member, exact name first, got {got}",
              [r["harness"] for r in got] == ["B"] and got[0]["matches"][0]["why"] == "name is the query")
    got = who.rank([b, a], "who has a 4090")
    ctx.check(f"a 4090: the hub, from its GPU, got {got}", got and got[0]["harness"] == "A"
              and any(m["kind"] == "hardware" for m in got[0]["matches"]))
    got = who.rank([a, b], "make a spreadsheet chart")
    ctx.check(f"a spreadsheet chart: the member (tool and app descriptions), got {[r['harness'] for r in got]}",
              got and got[0]["harness"] == "B")
    tag = who.score_item("tag", "studio", "", ["studio"])[0]
    ctx.check("a tag counts double", tag == 2 * who.EXACT)
    ctx.check("filler words alone are no query", who.query_words("who can do it") == [])
    ctx.check("the text names the winner first", "1. bob@member" in "\n".join(who.lines(who.rank([a, b], "gridcraft"), "x")))


@test
def test_the_cli_verbs_print_and_json_round_trips(ctx: Ctx):
    from tests.helpers.fleet_caps_seed import member_catalog, seed
    from tests.helpers.fleet_hub_rig import cli
    with _Home() as h:
        h.config({"fleet": {"name": "bob@member"}})
        from halo_harness.fleet.identity import harness
        cat = seed(h.home, member_catalog(harness(h.home)))
        rc, out, err = cli(str(h.root), "capabilities", "--json")
        got = json.loads(out) if rc == 0 else {}
        row = (got.get("harnesses") or [{}])[0]
        ctx.check(f"--json: this harness, from its cache, rc {rc} {err[-300:]}", rc == 0 and got.get("source") == "local")
        ctx.check("--json round-trips the catalog exactly", row.get("catalog") == cat and row.get("hash") == cat["hash"])
        rc, out, _ = cli(str(h.root), "capabilities")
        ctx.check(f"the spec sheet: hardware, mcp with tool counts, tags, got {out[:400]!r}", rc == 0
                  and "hardware" in out and "gridcraft 2 tools" in out and "linux, data" in out)
        rc, out, _ = cli(str(h.root), "capabilities", "local", "--tools")
        ctx.check("--tools lists every tool", rc == 0 and "write_range" in out and "insert_chart" in out)
        rc, out, _ = cli(str(h.root), "capabilities", "nobody")
        ctx.check("an unknown harness is exit 1", rc == 1)
        rc, out, _ = cli(str(h.root), "who", "gridcraft")
        ctx.check(f"who gridcraft names this harness, got {out!r}", rc == 0 and "1. bob@member" in out)
        rc, out, _ = cli(str(h.root), "who", "gridcraft", "--json")
        ctx.check("who --json: the ranked rows", rc == 0 and json.loads(out)["results"][0]["name"] == "bob@member")
        rc, _out, _ = cli(str(h.root), "who", "the")
        ctx.check("who with no word is exit 1", rc == 1)
        from halo_harness.commands.builtins import _cmd_fleet
        text = _cmd_fleet("who gridcraft", None)
        ctx.check(f"/fleet who in the TUI answers with the ranking, got {text!r}", "1. bob@member" in text)
        ctx.check("/fleet capabilities prints the spec sheet", "gridcraft 2 tools" in _cmd_fleet("capabilities", None))


if __name__ == "__main__":
    ctx = Ctx()
    results, passed, failed, skipped = run_all(TESTS, ctx)
    sys.exit(print_results(results, passed, failed, skipped, label="fleet capabilities tests"))
