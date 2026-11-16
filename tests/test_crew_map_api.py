"""tests.test_crew_map_api -- Halo 3.6.0.0 R3: the Map tab's routes (halo_harness/studio/crew_map_api.py) and
`halo maps` (halo_harness/maps_cli.py).

1. GET crew/maps: one row per name (yours over a starter), the one in use marked; GET crew/map/<name>: the map, each
   box's facts (an agent's model and what it does, a workflow's steps), the compile's problem lines;
2. PUT: a starter is saved as yours under its name; a new name makes a new map; a line that would make a circle is 422
   with the circle named; every write keeps its before-image (POST builder/undo puts it back byte for byte);
3. POST use {on}: config crew.map (undo puts config back); DELETE yours only; every write needs the owner's proof;
4. `halo maps list / show / use` say the same;
5. (R4) POST crew/from-live: an unsaved agent body from a session's made-up helper, nothing written, owner-only; GET
   live/replay names the map a session ran on and its hops (its log).
Run: python -m tests.test_crew_map_api
"""
from __future__ import annotations

import io
import json
import sys
from contextlib import redirect_stdout
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from tests.helpers.crew_rig import CrewRig  # noqa: E402
from tests.helpers.runner import Ctx, new_registry, print_results, run_all  # noqa: E402

test, TESTS = new_registry()


def _bytes(rig) -> dict:
    out = {str(p.relative_to(rig.state)): p.read_bytes() for p in (rig.state / "crew").rglob("*.yaml")} if (rig.state / "crew").is_dir() else {}
    cfg = rig.state / "config.json"
    out["config.json"] = cfg.read_bytes() if cfg.is_file() else b""
    return out


@test
def test_read_the_maps_and_one_map(ctx: Ctx):
    with CrewRig() as rig:
        rig.studio()
        st, r = rig.api("GET", "crew/maps")
        ctx.check(f"the two starters, the starter in use by default (3.6.0.0 R5), got {st} {[m['name'] for m in r['maps']]} {r['in_use']}",
                  st == 200 and {m["name"] for m in r["maps"]} == {"starter", "ship-it"} and r["in_use"] == "starter")
        st, m = rig.api("GET", "crew/map/ship-it")
        ctx.check(f"ship-it: its boxes' facts (a workflow's steps), no problem, got {st} {m.get('problems')}",
                  st == 200 and m["problems"] == [] and m["boxes"]["plan"]["kind"] == "workflow"
                  and m["boxes"]["plan"]["facts"][0]["steps"][0]["agents"] == ["planner"] and m["main"]["agent"] == "main")
        st, m = rig.api("GET", "crew/map/starter")
        ctx.check("starter: an agent box's model and what it does", m["boxes"]["coder"]["facts"][0]["model"] == "auto"
                  and "change" in m["boxes"]["coder"]["facts"][0]["does"])
        ctx.check("no such map: 404", rig.api("GET", "crew/map/nope")[0] == 404)
        st, r = rig.api("GET", "crew/maps")
        ctx.check(f"3.6.0.2 R50: a fresh home sets no map for new sessions: next is None, got {r.get('next', 'absent')}",
                  "next" in r and r["next"] is None)


def _map_body(name: str, boxes: int) -> dict:
    return {"format": "map/1", "name": name, "main": {"agent": "main"},
            "boxes": [{"id": f"b{i}", "agent": "coder"} for i in range(boxes)],
            "lines": [{"from": "main", "to": f"b{i}", "when": "always"} for i in range(boxes)]}


def _q(path) -> str:
    from urllib.parse import quote
    return quote(str(path), safe="")


@test
def test_get_reads_the_given_scope_and_path(ctx: Ctx):
    """3.6.0.2 R50: Studio reads THE file a session follows (its scope and path), never another file of that name."""
    from tests.helpers.trust_dir import trust
    with CrewRig() as rig:
        rig.studio()
        from halo_harness.crew import store
        mine = store.path_for("map", "shop", state_dir=rig.state)
        store.write_text(mine, store.dump(_map_body("shop", 1)))
        other = rig.root / "elsewhere"
        theirs = other / ".halo" / "crew" / "maps" / "shop.yaml"
        theirs.parent.mkdir(parents=True)
        theirs.write_text(store.dump(_map_body("shop", 2)), encoding="utf-8")
        trust(other)
        from halo_harness.history import append_history_entry  # a project Studio knows (P2 batch 8 repair)
        append_history_entry("work there", str(other))
        st, m = rig.api("GET", f"crew/map/shop?scope=project&path={_q(theirs)}")
        ctx.check(f"the project's file in another folder: its two boxes, its path, got {st} {sorted(m.get('boxes') or {})} {m.get('path')}",
                  st == 200 and sorted(m["boxes"]) == ["b0", "b1"] and m["path"] == str(theirs) and m["scope"] == "project")
        st, m = rig.api("GET", "crew/map/shop")
        ctx.check(f"no path: as today (yours, one box), got {st} {sorted(m.get('boxes') or {})}",
                  st == 200 and sorted(m["boxes"]) == ["b0"] and m["scope"] == "yours")
        st, m = rig.api("GET", f"crew/map/shop?scope=yours&path={_q(mine)}")
        ctx.check(f"yours by its path, got {st} {m.get('path')}", st == 200 and m["path"] == str(mine) and sorted(m["boxes"]) == ["b0"])
        shipped = store.SHIPPED / "maps" / "starter.yaml"
        st, m = rig.api("GET", f"crew/map/starter?scope=starter&path={_q(shipped)}")
        ctx.check(f"a starter by its path, got {st} {m.get('scope')}", st == 200 and m["scope"] == "starter" and "coder" in m["boxes"])
        stray = rig.root / "stray" / "shop.yaml"  # a shop.yaml outside any crew/maps folder
        stray.parent.mkdir()
        stray.write_text(store.dump(_map_body("shop", 3)), encoding="utf-8")
        cousin = other / ".halo" / "crew" / "maps" / "cousin.yaml"  # another name's file
        cousin.write_text(store.dump(_map_body("cousin", 3)), encoding="utf-8")
        untrusted = rig.root / "untrusted" / ".halo" / "crew" / "maps" / "shop.yaml"
        untrusted.parent.mkdir(parents=True)
        untrusted.write_text(store.dump(_map_body("shop", 3)), encoding="utf-8")
        append_history_entry("work there", str(rig.root / "untrusted"))  # known, still not trusted: never read
        for why, scope, p in (("a file outside crew/maps", "project", stray), ("another name's file", "project", cousin),
                              ("a project that is not trusted", "project", untrusted), ("the project's file as yours", "yours", theirs)):
            st, m = rig.api("GET", f"crew/map/shop?scope={scope}&path={_q(p)}")
            ctx.check(f"{why}: never read, 404 (never the other shop), got {st} {sorted(m.get('boxes') or {})}",
                      st == 404 and "boxes" not in m)
            st, m = rig.api("GET", f"crew/map/shop?scope={scope}&path={_q(p)}&soft=1")
            ctx.check(f"{why}, soft: 200 and not drawn (T12, Studio cannot read it here), got {st} {m}",
                      st == 200 and m.get("unreadable") is True and "boxes" not in m and m.get("path") == str(p))


@test
def test_soft_missing_answers_200_removed(ctx: Ctx):
    """3.6.0.2 R50 + R28: a page that asks softly for a map file that was removed gets 200 {removed}; the editor's 404 stays."""
    with CrewRig() as rig:
        rig.studio()
        from halo_harness.crew import store
        gone = store.path_for("map", "gone", state_dir=rig.state)
        store.write_text(gone, store.dump(_map_body("gone", 1)))
        ctx.check("while it is there it reads", rig.api("GET", f"crew/map/gone?scope=yours&path={_q(gone)}&soft=1")[0] == 200)
        gone.unlink()
        st, m = rig.api("GET", f"crew/map/gone?scope=yours&path={_q(gone)}&soft=1")
        ctx.check(f"removed, soft: 200 {{removed, map, scope, path}}, got {st} {m}",
                  st == 200 and m == {"removed": True, "map": "gone", "scope": "yours", "path": str(gone)})
        ctx.check("removed, not soft: 404 (the editor's)", rig.api("GET", f"crew/map/gone?scope=yours&path={_q(gone)}")[0] == 404)
        ctx.check("no such map, no path: 404 still", rig.api("GET", "crew/map/nope")[0] == 404)


class _Touches:
    """Records every file-system look (stat, lstat, exists, lexists, realpath) whose path names `probe`."""

    def __init__(self, probe) -> None:
        import os
        self.probe, self.seen, self.os = os.path.normcase(str(probe)), [], os
        self.real = {"stat": os.stat, "lstat": os.lstat, "exists": os.path.exists, "lexists": os.path.lexists,
                     "realpath": os.path.realpath}

    def _wrap(self, name, fn):
        def look(p, *a, **k):
            try:
                if self.probe in self.os.path.normcase(self.os.fspath(p)):
                    self.seen.append(name)
            except TypeError:
                pass
            return fn(p, *a, **k)
        return look

    def __enter__(self):
        o = self.os
        o.stat, o.lstat = self._wrap("stat", self.real["stat"]), self._wrap("lstat", self.real["lstat"])
        o.path.exists, o.path.lexists = self._wrap("exists", self.real["exists"]), self._wrap("lexists", self.real["lexists"])
        o.path.realpath = self._wrap("realpath", self.real["realpath"])
        return self

    def __exit__(self, *exc):
        o = self.os
        o.stat, o.lstat, o.path.exists, o.path.lexists, o.path.realpath = (
            self.real["stat"], self.real["lstat"], self.real["exists"], self.real["lexists"], self.real["realpath"])
        return False


@test
def test_soft_read_is_no_file_oracle(ctx: Ctx):
    """3.6.0.2 R50 (P2 batch 8): the soft read touches the file system only for a path inside a folder maps live in
    (yours, a trusted project's, a pack's, the starters). Any other path -- there or not -- gets the one answer
    {unreadable} without a look at it, so a page holding Studio's token cannot learn whether a file exists."""
    from halo_harness.crew import store
    with CrewRig() as rig:
        rig.studio()
        cases = (("a file outside any maps folder", "", rig.root / "probe-stray" / "shop.yaml"),
                 ("a file that is no map at all", "yours", rig.root / "probe-secret" / "id.txt"),
                 ("an untrusted project's map", "project", rig.root / "probe-untrusted" / ".halo" / "crew" / "maps" / "shop.yaml"),
                 ("a folder named like yours elsewhere", "yours", rig.root / "probe-other" / "crew" / "maps" / "shop.yaml"))
        for why, scope, p in cases:
            p.parent.mkdir(parents=True, exist_ok=True)
            p.write_text(store.dump(_map_body("shop", 1)), encoding="utf-8")
            url = f"crew/map/shop?scope={scope}&path={_q(p)}&soft=1"
            with _Touches(p) as seen:
                there = rig.api("GET", url)
            p.unlink()
            with _Touches(p) as seen_gone:
                gone = rig.api("GET", url)
            ctx.check(f"{why}: the path itself is never looked at, got {seen.seen + seen_gone.seen}",
                      seen.seen == [] and seen_gone.seen == [])
            ctx.check(f"{why}: there and not there answer the same, got {there} vs {gone}",
                      there == gone and json.dumps(there[1]) == json.dumps(gone[1]))
            ctx.check(f"{why}: the one answer is 200 {{unreadable}}, got {gone}",
                      gone[0] == 200 and gone[1] == {"unreadable": True, "map": "shop", "scope": scope, "path": str(p)})
            ctx.check(f"{why}: not soft, 404 either way", rig.api("GET", f"crew/map/shop?scope={scope}&path={_q(p)}")[0] == 404)
        # inside a maps folder the calm answers stay: removed when nothing is there, the map when it is
        mine = store.path_for("map", "kept", state_dir=rig.state)
        store.write_text(mine, store.dump(_map_body("kept", 1)))
        ctx.check("yours, there: read", rig.api("GET", f"crew/map/kept?scope=yours&path={_q(mine)}&soft=1")[0] == 200
                  and "boxes" in rig.api("GET", f"crew/map/kept?scope=yours&path={_q(mine)}&soft=1")[1])
        mine.unlink()
        ctx.check("yours, removed: 200 {removed}",
                  rig.api("GET", f"crew/map/kept?scope=yours&path={_q(mine)}&soft=1")[1].get("removed") is True)


@test
def test_soft_read_asks_nothing_of_an_unknown_project(ctx: Ctx):
    """3.6.0.2 R50 (P2 batch 8 repair): a path shaped `<x>/.halo/crew/maps/<f>` is looked at only when `<x>` is a
    project Studio knows (its own folder, a live session's, a history line's). Before, Studio asked whether `<x>` is
    trusted, and that walks `<x>` and every folder above it for `.git`: under a trusted folder the answer told a page
    whether `.git` exists there. Now every such folder gets the one answer {unreadable} and nothing under it is looked at."""
    from halo_harness.crew import store
    from halo_harness.history import append_history_entry
    from tests.helpers.trust_dir import trust
    with CrewRig() as rig:
        rig.studio()
        top = rig.root / "probe-trusted"  # trusted, and no git repo
        (top / "secret-repo" / ".git").mkdir(parents=True)
        (top / "plain-folder").mkdir()
        trust(top)
        for sub in ("secret-repo", "plain-folder", "no-such-folder"):
            p = top / sub / ".halo" / "crew" / "maps" / "x.yaml"
            with _Touches(top / sub) as seen:
                got = rig.api("GET", f"crew/map/x?scope=project&path={_q(p)}&soft=1")
            ctx.check(f"{sub}: nothing at or under it is looked at, got {seen.seen}", seen.seen == [])
            ctx.check(f"{sub}: the one answer 200 {{unreadable}}, got {got}",
                      got[0] == 200 and got[1] == {"unreadable": True, "map": "x", "scope": "project", "path": str(p)})
        known = top / "plain-folder"  # once a session worked there, its map is read, and a removed one says so
        append_history_entry("work there", str(known))
        trust(known)
        p = known / ".halo" / "crew" / "maps" / "x.yaml"
        p.parent.mkdir(parents=True)
        p.write_text(store.dump(_map_body("x", 1)), encoding="utf-8")
        st, m = rig.api("GET", f"crew/map/x?scope=project&path={_q(p)}&soft=1")
        ctx.check(f"a known trusted project's map: read, got {st} {sorted(m)}", st == 200 and "boxes" in m)
        p.unlink()
        st, m = rig.api("GET", f"crew/map/x?scope=project&path={_q(p)}&soft=1")
        ctx.check(f"a known trusted project's map removed: 200 {{removed}}, got {st} {m}", st == 200 and m.get("removed") is True)


@test
def test_next_is_null_when_unset(ctx: Ctx):
    """3.6.0.2 R50 (F4): `next` is config crew.map, null when unset -- `in_use` says `starter` either way."""
    with CrewRig() as rig:
        rig.studio()
        st, r = rig.api("GET", "crew/maps")
        ctx.check(f"fresh: next None, in_use starter, got {r.get('next', 'absent')} {r.get('in_use')}",
                  st == 200 and "next" in r and r["next"] is None and r["in_use"] == "starter")
        st, m = rig.api("GET", "crew/map/starter")
        ctx.check(f"one map: next None, got {m.get('next', 'absent')}", "next" in m and m["next"] is None)
        rig.api("POST", "crew/map/ship-it/use", {"on": True})
        _st, r = rig.api("GET", "crew/maps")
        _st, m = rig.api("GET", "crew/map/starter")
        ctx.check(f"after use ship-it: next ship-it in both, got {r.get('next')} {m.get('next')}",
                  r.get("next") == "ship-it" and m.get("next") == "ship-it")


@test
def test_save_a_circle_a_new_map_and_undo(ctx: Ctx):
    with CrewRig() as rig:
        rig.studio()
        before = _bytes(rig)
        _st, m = rig.api("GET", "crew/map/ship-it")
        body = m["map"]
        loop = {**body, "lines": body["lines"] + [{"from": "review", "to": "plan", "when": "always"}]}
        st, r = rig.api("PUT", "crew/map/ship-it", {"map": loop})
        ctx.check(f"a circle: 422 naming it, nothing written, got {st} {r.get('error')!r}",
                  st == 422 and "circle (plan -> code -> review -> plan)" in r["error"] and _bytes(rig) == before)
        two = {**body, "boxes": body["boxes"] + [{"id": "tester", "agent": "tester"}]}
        st, r = rig.api("PUT", "crew/map/ship-it", {"map": two})
        ctx.check(f"saved as yours under its name, got {st} {r.get('scope')}", st == 200 and r["scope"] == "yours" and r["undo_id"])
        st, _ = rig.api("POST", "builder/undo", {"undo_id": r["undo_id"]})
        ctx.check("Undo: byte for byte", st == 200 and _bytes(rig) == before)
        st, r = rig.api("PUT", "crew/map/release-day", {"map": {"boxes": [], "lines": []}})
        ctx.check(f"+ New map: a map with main only, got {st}", st == 200 and r["map"]["main"] == {"agent": "main"} and r["map"]["format"] == "map/1")
        st, r = rig.api("DELETE", "crew/map/release-day")
        ctx.check("delete yours", st == 200 and rig.api("GET", "crew/map/release-day")[0] == 404)
        ctx.check("a starter is not deleted", rig.api("DELETE", "crew/map/starter")[0] == 409)


@test
def test_use_the_owner_and_the_cli(ctx: Ctx):
    with CrewRig() as rig:
        rig.studio()
        before = _bytes(rig)["config.json"]
        st, r = rig.api("POST", "crew/map/ship-it/use", {"on": True})
        ctx.check(f"in use: ship-it, got {st} {r}", st == 200 and r["in_use"] == "ship-it" and rig.api("GET", "crew/maps")[1]["in_use"] == "ship-it")
        rig.api("POST", "builder/undo", {"undo_id": r["undo_id"]})
        ctx.check("Undo puts config.json back byte for byte", _bytes(rig)["config.json"] == before)
        for method, path in (("PUT", "crew/map/ship-it"), ("POST", "crew/map/ship-it/use"), ("DELETE", "crew/map/ship-it")):
            st, _r = rig.api(method, path, {"map": {}, "on": True}, owner=False)
            ctx.check(f"{method} {path} without the owner's proof: 403, got {st}", st == 403)
        from halo_harness.maps_cli import cmd_maps
        import os
        cwd = os.getcwd()
        os.chdir(rig.proj)
        try:
            out = io.StringIO()
            with redirect_stdout(out):
                code = cmd_maps(["use", "starter"]) + cmd_maps(["list"]) + cmd_maps(["show", "ship-it"])
        finally:
            os.chdir(cwd)
        text = out.getvalue()
        ctx.check(f"halo maps use / list / show, got {text[:300]!r}", code == 0 and "New sessions run as by default" in text
                  and "* starter" in text and "line main -> plan: always" in text and "in use: starter (default)" in text)


@test
def test_use_receipt_says_when_the_start_mode_changes(ctx: Ctx):
    """3.6.0.1: the person's own doors ask nothing new, but their receipt says so when the switch changes the mode new
    sessions start in (a map of yours whose main of yours is `careful: own`: auto)."""
    with CrewRig() as rig:
        rig.studio()
        from halo_harness.crew import store
        for name, careful in (("mine", "own"), ("calm", "ask-changes")):
            boss = f"{name}-boss"
            store.write_text(store.path_for("agent", boss, state_dir=rig.state), store.dump(
                {"format": "agent/1", "name": boss, "does": "Runs the session.", "model": "auto", "uses": ["read"], "careful": careful}))
            store.write_text(store.path_for("map", name, state_dir=rig.state), store.dump(
                {"format": "map/1", "name": name, "boxes": [], "lines": [], "main": {"agent": boss}}))
        st, r = rig.api("POST", "crew/map/mine/use", {"on": True})
        ctx.check(f"Studio's switch to mine: the receipt says they start in auto mode, got {st} {r.get('said')!r}",
                  st == 200 and r["in_use"] == "mine" and "New sessions run on mine; a running session keeps its own" in str(r.get("said"))
                  and "start in auto mode" in str(r.get("said")))
        st, r = rig.api("POST", "crew/map/calm/use", {"on": True})
        ctx.check(f"from mine to calm: back to default mode, said, got {r.get('said')!r}", st == 200 and "start in default mode" in str(r.get("said")))
        st, r = rig.api("POST", "crew/map/ship-it/use", {"on": True})
        ctx.check(f"from calm to ship-it (no mode change): the receipt as before, got {r.get('said')!r}",
                  st == 200 and r.get("said") == "New sessions run on ship-it; a running session keeps its own.")
        from halo_harness.maps_cli import cmd_maps
        import os
        cwd = os.getcwd()
        os.chdir(rig.proj)
        try:
            out = io.StringIO()
            with redirect_stdout(out):
                code = cmd_maps(["use", "mine"])
            first = out.getvalue()
            out = io.StringIO()
            with redirect_stdout(out):
                code += cmd_maps(["use", "starter"])
            back = out.getvalue()
        finally:
            os.chdir(cwd)
        ctx.check(f"halo maps use mine says main runs in auto, from default, once (main's own line, no second "
                  f"receipt clause), got {first!r}",
                  code == 0 and "main runs in auto (careful: own)" in first and "your own mode was default" in first
                  and "start in auto mode" not in first and first.count("auto") == 1)
        ctx.check(f"halo maps use starter (from mine) says they start in default mode again, got {back!r}",
                  "New sessions run as by default" in back and "start in default mode" in back)


@test
def test_use_receipt_says_the_mode_outside_a_trusted_project(ctx: Ctx):
    """jf-mapuse: config `crew.map` is global. In a trusted project whose settings start sessions in acceptEdits, a map
    whose main asks only before commands changes nothing HERE, but sessions in every other folder rise default ->
    acceptEdits: Studio's switch and `halo maps use` say so in their receipt (no new question)."""
    import json
    with CrewRig() as rig:
        rig.studio()
        from halo_harness.config.paths import claude_json_path
        from halo_harness.crew import store
        for name, careful in (("mine", "ask-commands"), ("calm", "ask-changes")):
            boss = f"{name}-boss"
            store.write_text(store.path_for("agent", boss, state_dir=rig.state), store.dump(
                {"format": "agent/1", "name": boss, "does": "Runs the session.", "model": "auto", "uses": ["read"], "careful": careful}))
            store.write_text(store.path_for("map", name, state_dir=rig.state), store.dump(
                {"format": "map/1", "name": name, "boxes": [], "lines": [], "main": {"agent": boss}}))
        d = Path(rig.proj) / ".claude"
        d.mkdir(parents=True, exist_ok=True)
        (d / "settings.json").write_text(json.dumps({"permissions": {"defaultMode": "acceptEdits"}}), encoding="utf-8")
        cj = claude_json_path()
        cj.parent.mkdir(parents=True, exist_ok=True)
        # the folder under both of its spellings: as the rig names it (what Studio's server was given) and as a
        # process inside it reads its own folder (`halo maps use` below; on macOS the temp folder is reached through
        # a link, so the two differ, and trust is looked up by the spelling, as Claude Code's own file keeps it)
        import os
        keys = {str(Path(rig.proj).absolute()).replace("\\", "/"), os.path.realpath(rig.proj).replace("\\", "/")}
        cj.write_text(json.dumps({"projects": {k: {"hasTrustDialogAccepted": True} for k in sorted(keys)}}), encoding="utf-8")
        st, r = rig.api("POST", "crew/map/mine/use", {"on": True})
        said = str(r.get("said"))
        ctx.check(f"Studio's switch to mine: the receipt says sessions outside this project start in acceptEdits, got {st} {said!r}",
                  st == 200 and "outside this project they start in acceptEdits mode (until now default)" in said)
        st, r = rig.api("POST", "crew/map/calm/use", {"on": True})
        said = str(r.get("said"))
        ctx.check(f"back to calm (main asks before changes): here and outside alike they start in default, said once, got {said!r}",
                  st == 200 and "they start in default mode (until now acceptEdits)" in said and "outside" not in said)
        from halo_harness.maps_cli import cmd_maps
        import os
        cwd = os.getcwd()
        os.chdir(rig.proj)
        try:
            with redirect_stdout(io.StringIO()):
                code = cmd_maps(["use", "starter"])  # from calm both places move alike; from the starter only outside does
            out = io.StringIO()
            with redirect_stdout(out):
                code += cmd_maps(["use", "mine"])
        finally:
            os.chdir(cwd)
        ctx.check(f"halo maps use mine in the project (from the starter) says the same, got {out.getvalue()!r}",
                  code == 0 and "outside this project they start in acceptEdits mode (until now default)" in out.getvalue())


@test
def test_from_live_builds_an_unsaved_agent_and_a_replay_knows_its_map(ctx: Ctx):
    """R4: POST crew/from-live {session, agent_id} -> an unsaved agent/1 body (main's uses and careful), nothing written,
    owner-only; GET live/replay?session= says the map the session ran on and its hops (from its log)."""
    import json
    from halo_harness.peers import local_view
    with CrewRig() as rig:
        rig.studio()
        row = {"session_id": "s-live-1", "map": "starter", "agents": [
            {"agent_id": "main", "name": "main", "state": "running"},
            {"agent_id": "a7", "parent": "main", "name": "general-purpose", "state": "running", "model": "or:vendor/fast",
             "task": "List what the repo holds for the release notes\nthen stop", "crew": {"map": "starter", "box": "main", "made_up": True}}]}
        saved = local_view.sessions
        local_view.sessions = lambda list_live=None: [row]
        try:
            before = _bytes(rig)
            st, r = rig.api("POST", "crew/from-live", {"session": "s-live-1", "agent_id": "a7"})
            a = r.get("agent") or {}
            ctx.check(f"an unsaved body from the helper, got {st} {a}", st == 200 and a.get("format") == "agent/1" and
                      a.get("name") == "list-what-repo" and a.get("does") == "List what the repo holds for the release notes"
                      and a.get("model") == "or:vendor/fast" and r.get("problems") == [])
            ctx.check(f"what it may use: main's uses and careful, got {a.get('uses')} {a.get('careful')}",
                      a.get("uses") == ["read", "edit", "bash", "web"] and a.get("careful") == "ask-changes")
            ctx.check("nothing written", _bytes(rig) == before)
            ctx.check("no such helper: 404", rig.api("POST", "crew/from-live", {"session": "s-live-1", "agent_id": "zz"})[0] == 404)
            ctx.check("without the owner's proof: 403", rig.api("POST", "crew/from-live", {"session": "s-live-1", "agent_id": "a7"}, owner=False)[0] == 403)
        finally:
            local_view.sessions = saved
        log = rig.state / "sessions" / "proj" / "s-past-1.jsonl"
        log.parent.mkdir(parents=True, exist_ok=True)
        nodes = [{"type": "meta", "ts": 1.0, "title": "a past run"},
                 {"type": "user", "ts": 2.0, "content": "fix it"},
                 {"type": "receipt", "kind": "map", "event": "map_start", "ts": 2.0, "data": {"map": "starter", "t": 2.0}},
                 {"type": "receipt", "kind": "map", "event": "map_hop", "ts": 3.0,
                  "data": {"map": "starter", "line": "main -> coder", "from": "main", "to": "coder", "state": "start", "t": 3.0}}]
        log.write_text("".join(json.dumps(n) + "\n" for n in nodes), encoding="utf-8")
        st, r = rig.api("GET", "live/replay?session=s-past-1&harness=local")
        ctx.check(f"the replay says its map and its hops, got {st} {r.get('map')} {r.get('map_events')}",
                  st == 200 and r.get("map") == "starter" and [e["data"]["line"] for e in r.get("map_events") or []] == ["main -> coder"])


if __name__ == "__main__":
    ctx = Ctx()
    results, passed, failed, skipped = run_all(TESTS, ctx)
    sys.exit(print_results(results, passed, failed, skipped))
