"""tests.test_crew_map_api -- Halo 3.6.0.0 R3: the Map tab's routes (halo_harness/studio/crew_map_api.py) and
`halo maps` (halo_harness/maps_cli.py).

1. GET crew/maps: one row per name (yours over a starter), the one in use marked; GET crew/map/<name>: the map, each
   box's facts (an agent's model and what it does, a workflow's steps), the compile's problem lines;
2. PUT: a starter is saved as yours under its name; a new name makes a new map; a line that would make a circle is 422
   with the circle named; every write keeps its before-image (POST builder/undo puts it back byte for byte);
3. POST use {on}: config crew.map (undo puts config back); DELETE yours only; every write needs the owner's proof;
4. `halo maps list / show / use` say the same;
5. (R4) POST crew/from-live: an unsaved agent body from a session's made-up helper, nothing written, owner-only.
6. (3.6.0.12 SP) the card's body and the truth block's map body are the SESSION's project's, not Studio's folder's.
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
        ctx.check(f"the two shipped maps, Auto in use by default (3.6.0.0 R5, 3.6.0.5 A1), got {st} {[m['name'] for m in r['maps']]} {r['in_use']}",
                  st == 200 and {m["name"] for m in r["maps"]} == {"auto", "ship-it"} and r["in_use"] == "auto")
        st, m = rig.api("GET", "crew/map/ship-it")
        ctx.check(f"ship-it: its boxes' facts (a workflow's steps), no problem, got {st} {m.get('problems')}",
                  st == 200 and m["problems"] == [] and m["boxes"]["plan"]["kind"] == "workflow"
                  and m["boxes"]["plan"]["facts"][0]["steps"][0]["agents"] == ["planner"] and m["main"]["agent"] == "main")
        st, m = rig.api("GET", "crew/map/auto")
        ctx.check("auto: an agent box's model and what it does", m["boxes"]["coder"]["facts"][0]["model"] == "auto"
                  and "change" in m["boxes"]["coder"]["facts"][0]["does"])
        ctx.check("no such map: 404", rig.api("GET", "crew/map/nope")[0] == 404)
        st, r = rig.api("GET", "crew/maps")
        ctx.check(f"3.6.0.2 R50: a fresh home sets no map for new sessions: next is None, got {r.get('next', 'absent')}",
                  "next" in r and r["next"] is None)


@test
def test_a_map_answer_carries_the_hashes_of_what_it_bakes_in(ctx: Ctx):
    """3.6.0.9 V: GET / PUT crew/map carry `sig` (the map file's hash) and `deps` (each agent and workflow file whose
    facts the answer holds), the hashes Studio's watcher sends (studio/files_live.py), so the page re-reads a map only
    when one of them changed on disk."""
    from halo_harness.crew import store
    from halo_harness.studio.files_live import file_sig, sig
    with CrewRig() as rig:
        rig.studio()
        st, m = rig.api("GET", "crew/map/ship-it")
        flow = m["boxes"]["plan"]["names"][0]
        agents = {a for s in m["boxes"]["plan"]["facts"][0]["steps"] for a in s["agents"]}
        ctx.check(f"the map's own hash, got {m.get('sig')!r}", m.get("sig") == file_sig(m["path"]) and len(m["sig"]) == 16)
        deps = m.get("deps") or {}
        ctx.check(f"its workflow, the workflow's step agents and main, each the watcher's hash, got {deps}",
                  f"workflow:{flow}" in deps and {f"agent:{a}" for a in agents} <= set(deps) and "agent:main" in deps
                  and all(v == sig(k.split(":")[0], k.split(":", 1)[1], rig.proj, rig.state) for k, v in deps.items()))
        st, put = rig.api("PUT", "crew/map/mine", {"map": {"boxes": [{"id": "c", "agent": "coder"}], "lines": [{"from": "main", "to": "c", "when": "always"}]}})
        ctx.check(f"a save answers the written file's hash, got {st} {put.get('sig')!r}",
                  st == 200 and put.get("sig") == file_sig(store.path_for("map", "mine", state_dir=rig.state)))


@test
def test_a_hand_written_workflow_with_odd_step_agents_still_opens(ctx: Ctx):
    """3.6.0.9 V repair: a session's plain Write of a workflow whose step names an agent as a mapping or a number is a
    format problem, never a failed answer: GET crew/map still answers 200, and `deps` holds only the names that are
    names."""
    with CrewRig() as rig:
        rig.studio()
        st, m = rig.api("GET", "crew/map/ship-it")
        flow = m["boxes"]["plan"]["names"][0]
        p = rig.state / "crew" / "workflows" / f"{flow}.yaml"
        p.parent.mkdir(parents=True, exist_ok=True)
        for agents in ("\n      - name: coder\n", " [coder, 7]\n"):
            p.write_text(f"format: workflow/1\nname: {flow}\nfor: probe\nsteps:\n  - name: a\n    agents:{agents}",
                         encoding="utf-8")
            st, m = rig.api("GET", "crew/map/ship-it")
            deps = (m or {}).get("deps") or {}
            ctx.check(f"agents:{agents.strip()} answers 200 with string names in deps, got {st} {str(m)[:200]}",
                      st == 200 and f"workflow:{flow}" in deps and all(isinstance(k, str) for k in deps)
                      and "agent:7" not in deps)


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
        shipped = store.SHIPPED / "maps" / "auto.yaml"
        st, m = rig.api("GET", f"crew/map/auto?scope=starter&path={_q(shipped)}")
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


@test
def test_soft_by_name_missing_answers_200_removed(ctx: Ctx):
    """3.6.0.2 R28 (P3 batch 6): Session reads a just-built map by its name (the frame names no file); asked softly, a map
    of that name that is gone answers 200 {removed} (no failed /api on the page); not soft it is the editor's 404."""
    with CrewRig() as rig:
        rig.studio()
        from halo_harness.crew import store
        p = store.path_for("map", "built", state_dir=rig.state)
        store.write_text(p, store.dump(_map_body("built", 1)))
        st, m = rig.api("GET", "crew/map/built?soft=1")
        ctx.check(f"there, soft by name: read as ever, got {st}", st == 200 and "boxes" in m and m.get("map", {}).get("name") == "built")
        p.unlink()
        st, m = rig.api("GET", "crew/map/built?soft=1")
        ctx.check(f"gone, soft by name: 200 {{removed, map, scope, path}}, got {st} {m}",
                  st == 200 and m == {"removed": True, "map": "built", "scope": "", "path": ""})
        ctx.check("gone, not soft: 404 (the editor's)", rig.api("GET", "crew/map/built")[0] == 404)


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
    """3.6.0.2 R50 (F4): `next` is config crew.map, null when unset -- `in_use` says `auto` either way."""
    with CrewRig() as rig:
        rig.studio()
        st, r = rig.api("GET", "crew/maps")
        ctx.check(f"fresh: next None, in_use auto, got {r.get('next', 'absent')} {r.get('in_use')}",
                  st == 200 and "next" in r and r["next"] is None and r["in_use"] == "auto")
        st, m = rig.api("GET", "crew/map/auto")
        ctx.check(f"one map: next None, got {m.get('next', 'absent')}", "next" in m and m["next"] is None)
        rig.api("POST", "crew/map/ship-it/use", {"on": True})
        _st, r = rig.api("GET", "crew/maps")
        _st, m = rig.api("GET", "crew/map/auto")
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
        ctx.check("a map that ships with Halo is not deleted", rig.api("DELETE", "crew/map/auto")[0] == 409)


@test
def test_saving_a_map_with_a_problem_answers_its_problems(ctx: Ctx):
    """3.6.0.11 SM: a map whose box names a missing workflow is saved, and new sessions on it run on Auto: the save's
    answer lists the same problem lines the GET does (it answered `problems: []`, so the red banner stayed away)."""
    with CrewRig() as rig:
        rig.studio()
        body = {"boxes": [{"id": "w", "workflow": "gone-flow"}], "lines": [{"from": "main", "to": "w", "when": "always"}]}
        st, r = rig.api("PUT", "crew/map/mine", {"map": body})
        _st, g = rig.api("GET", "crew/map/mine")
        ctx.check(f"the GET names the problem, got {g.get('problems')}",
                  any("gone-flow" in p for p in g.get("problems") or []))
        ctx.check(f"the save answers the same lines, got {st} {r.get('problems')}",
                  st == 200 and r.get("problems") == g.get("problems") and r.get("undo_id"))
        st, r = rig.api("PUT", "crew/map/ship-it", {"map": rig.api("GET", "crew/map/ship-it")[1]["map"]})
        ctx.check(f"a map with no problem still answers [], got {st} {r.get('problems')}", st == 200 and r.get("problems") == [])


@test
def test_a_map_names_the_model_a_new_session_on_it_starts_on(ctx: Ctx):
    """3.6.0.11 SM: `start` {model, origin} names the model a new session on the open map starts on (start_model.py):
    the default he picked, a pin in his copy of main (only off Auto), a /model remembered after the default."""
    from halo_harness import launch_state
    from halo_harness.theme import set_config_value
    with CrewRig() as rig:
        rig.studio()
        set_config_value("model", "or:new/default-x")
        got = {n: rig.api("GET", f"crew/map/{n}")[1].get("start") for n in ("auto", "ship-it")}
        want = {"model": "or:new/default-x", "origin": "config"}
        ctx.check(f"no pin: the default, origin config, on Auto and on ship-it, got {got}", got == {"auto": want, "ship-it": want})
        _st, a = rig.api("GET", "crew/agent/main")
        st, _r = rig.api("POST", "crew/agent/main", {"agent": {**a["agent"], "model": "or:old/pinned-p"}})
        got = {n: rig.api("GET", f"crew/map/{n}")[1].get("start") for n in ("auto", "ship-it")}
        ctx.check(f"a pin in his main: Auto keeps the default, ship-it names the pin, got {st} {got}", st == 200 and got == {
            "auto": want, "ship-it": {"model": "or:old/pinned-p", "origin": "pin"}})
        _st, m = rig.api("GET", "crew/map/auto")
        ctx.check(f"on Auto the answer still carries main's own model (the page's second line), got {m.get('main')}",
                  (m.get("main") or {}).get("model") == "or:old/pinned-p")
        launch_state.record_last_model("or:mock/slash-y", cwd=rig.proj)
        got = {n: rig.api("GET", f"crew/map/{n}")[1].get("start") for n in ("auto", "ship-it")}
        ctx.check(f"a /model after the default: Auto names it, the pin still outranks it, got {got}", got == {
            "auto": {"model": "or:mock/slash-y", "origin": "remembered"}, "ship-it": {"model": "or:old/pinned-p", "origin": "pin"}})


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
        ctx.check(f"halo maps use / list / show, got {text[:300]!r}", code == 0
                  and "New sessions run on Auto (the default); no map of yours is set." in text
                  and "* auto" in text and "line main -> plan: always" in text and "in use: Auto (the default)" in text)


@test
def test_switch_off_reads_auto(ctx: Ctx):
    """3.6.0.5 A21 (W18): turning his map's "New sessions run on this" off answers that new sessions run on Auto."""
    with CrewRig() as rig:
        rig.studio()
        st, r = rig.api("POST", "crew/map/ship-it/use", {"on": True})
        ctx.check(f"on: ship-it in use, got {st} {r.get('in_use')}", st == 200 and r.get("in_use") == "ship-it")
        st, r = rig.api("POST", "crew/map/ship-it/use", {"on": False})
        ctx.check(f"off: Auto's words, got {st} {r.get('said')!r}",
                  st == 200 and r.get("said") == "New sessions run on Auto (the default); a running session keeps its own."
                  and r.get("in_use") == "auto")


@test
def test_run_new_sessions_on_auto_from_the_map_tab(ctx: Ctx):
    """3.6.0.11 SM: on Auto no switch is drawn; Agents -> Map's [Run new sessions on Auto (the default)] sends the
    switch's own request for Auto: crew.map is taken out and the receipt reads Auto's words."""
    with CrewRig() as rig:
        rig.studio()
        rig.api("POST", "crew/map/ship-it/use", {"on": True})
        st, r = rig.api("POST", "crew/map/auto/use", {"on": True})
        crew = json.loads((rig.state / "config.json").read_text(encoding="utf-8")).get("crew") or {}
        ctx.check(f"Auto: crew.map out, in use auto, Auto's words, got {st} {r} {crew}",
                  st == 200 and r.get("in_use") == "auto" and "map" not in crew
                  and r.get("said") == "New sessions run on Auto (the default); a running session keeps its own.")


@test
def test_switch_off_a_map_not_in_use_says_so(ctx: Ctx):
    """3.6.0.5 (RULINGS 7): off for a map that is NOT the one in use, while another of his is set, changes nothing and
    says so -- never "New sessions run on no map", which would be false."""
    with CrewRig() as rig:
        rig.studio()
        from halo_harness.crew import store
        for name in ("shop", "review-flow"):
            store.write_text(store.path_for("map", name, state_dir=rig.state), store.dump(
                {"format": "map/1", "name": name, "main": {"agent": "main"}, "boxes": [{"id": "x", "agent": "coder"}], "lines": []}))
        rig.api("POST", "crew/map/shop/use", {"on": True})
        st, r = rig.api("POST", "crew/map/review-flow/use", {"on": False})
        crew = json.loads((rig.state / "config.json").read_text(encoding="utf-8")).get("crew") or {}
        ctx.check(f"review-flow off while shop is set: the line, crew.map still shop, got {st} {r.get('said')!r} {crew}",
                  st == 200 and r.get("said") == "review-flow was not in use; new sessions still run on shop."
                  and crew.get("map") == "shop" and r.get("in_use") == "shop")


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
                  "New sessions run on Auto (the default); no map of yours is set" in back and "start in default mode" in back)


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
def test_from_live_builds_an_unsaved_agent(ctx: Ctx):
    """R4: POST crew/from-live {session, agent_id} -> an unsaved agent/1 body (main's uses and careful), nothing written,
    owner-only. (3.6.0.3 B: the old playback's route left, and this test's half that read it.)"""
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


def _two_projects(rig):
    """3.6.0.12 SP: Studio's folder A (the rig's project) and another project B, both trusted, each with its own `main`
    (other `uses`) and B with an agent named as the helper's words would name it."""
    from halo_harness.crew import store
    from tests.helpers.trust_dir import trust
    a, b = rig.proj, rig.root / "other"
    b.mkdir(exist_ok=True)
    for proj, uses in ((a, ["read"]), (b, ["read", "web"])):
        trust(proj)
        p = store.path_for("agent", "main", cwd=proj, project=True)
        p.parent.mkdir(parents=True, exist_ok=True)
        store.write_text(p, store.dump({"format": "agent/1", "name": "main", "does": "the lead", "instructions": "lead", "uses": uses}))
    taken = store.path_for("agent", "list-what-repo", cwd=b, project=True)
    store.write_text(taken, store.dump({"format": "agent/1", "name": "list-what-repo", "does": "x", "instructions": "y"}))
    return a, b


def _tree(folder) -> dict:
    return {str(p): p.read_bytes() for p in sorted(Path(folder).rglob("*")) if p.is_file()}


@test
def test_from_live_reads_the_sessions_own_project(ctx: Ctx):
    """3.6.0.12 SP: Live's card builds the helper's agent from the project of the SESSION (its row's `cwd`), not from
    the folder Studio was started in: main's `uses` and the names taken are B's; Studio's folder only when the row
    names none. Its Save writes a new agent of yours and changes neither project."""
    from halo_harness.crew import store
    from halo_harness.peers import local_view
    with CrewRig() as rig:
        rig.studio()
        a, b = _two_projects(rig)
        row = {"session_id": "s-b", "cwd": str(b), "map": "auto", "agents": [
            {"agent_id": "a7", "parent": "main", "name": "general-purpose", "state": "running",
             "task": "List what the repo holds", "crew": {"map": "auto", "box": "main", "made_up": True}}]}
        saved = local_view.sessions
        local_view.sessions = lambda list_live=None: [row]
        try:
            st, r = rig.api("POST", "crew/from-live", {"session": "s-b", "agent_id": "a7"})
            got = r.get("agent") or {}
            ctx.check(f"main's uses are B's main's, got {st} {got.get('uses')}", st == 200 and got.get("uses") == ["read", "web"])
            ctx.check(f"a name B has is never reused, got {got.get('name')}", got.get("name") == "list-what-repo-2")
            before_a, before_b = _tree(a / ".halo"), _tree(b / ".halo")
            st, w = rig.api("POST", f"crew/agent/{got.get('name')}", {"agent": got})
            ctx.check(f"Save writes a new agent of yours, got {st} {w.get('path')}",
                      st == 200 and Path(w["path"]) == store.path_for("agent", got["name"], state_dir=rig.state))
            ctx.check("A's project and B's project are byte-equal after the Save",
                      _tree(a / ".halo") == before_a and _tree(b / ".halo") == before_b)
            row["cwd"] = None  # a row naming no folder: Studio's own
            st, r = rig.api("POST", "crew/from-live", {"session": "s-b", "agent_id": "a7"})
            ctx.check(f"no folder in the row: Studio's folder's main, got {st} {(r.get('agent') or {}).get('uses')}",
                      st == 200 and (r.get("agent") or {}).get("uses") == ["read"])
        finally:
            local_view.sessions = saved


TRUTH_BODY = Path(__file__).resolve().parent.parent / "halo_harness" / "studio" / "ui" / "src" / "routes" / "session" / "truthBody.ts"
TRUTH_JS = """const m = await import(%s);
const W = {scope: 'project', path: %s};
console.log(JSON.stringify({own: m.bodyAsk('shop', 'shop', W), other: m.bodyAsk('shop', 'cart', W),
  none: m.bodyAsk('shop', 'shop', {scope: null, path: null})}));"""


@test
def test_truth_block_reads_the_sessions_own_map_file(ctx: Ctx):
    """3.6.0.12 SP: Session's truth block asks for the body of the map the session runs on by its row's scope and path
    (session/truthBody.ts `bodyAsk`, as the drawing does), so a session in B reads B's file, not Studio's folder's map
    of that name; a map that is not the session's own (no file in its row) is read by name, as before."""
    import json
    from halo_harness.crew import store
    from halo_harness.history import append_history_entry
    from tests.helpers import node_ts
    with CrewRig() as rig:
        rig.studio()
        a, b = _two_projects(rig)
        for proj, flow in ((a, "flow-a"), (b, "flow-b")):
            p = store.path_for("map", "shop", cwd=proj, project=True)
            p.parent.mkdir(parents=True, exist_ok=True)
            store.write_text(p, store.dump({"format": "map/1", "name": "shop", "main": {"agent": "main"},
                                             "boxes": [{"id": "b0", "workflow": flow}],
                                             "lines": [{"from": "main", "to": "b0", "when": "always"}]}))
        append_history_entry("work there", str(b))  # a project Studio knows (a live session's, a history line's)
        theirs = store.path_for("map", "shop", cwd=b, project=True)
        asks = node_ts.run(TRUTH_JS % (json.dumps(TRUTH_BODY.resolve().as_uri()), json.dumps(str(theirs))))
        own = asks.get("own") or {}
        st, m = rig.api("GET", own.get("url") or "crew/map/shop")
        flows = [x.get("workflow") for x in (m.get("map") or {}).get("boxes") or []]
        ctx.check(f"the session's own map: B's file, got {own.get('url')} -> {st} {flows}", st == 200 and flows == ["flow-b"])
        ctx.check(f"another map, or a row with no file: by name, got {asks.get('other')} {asks.get('none')}",
                  (asks.get("other") or {}).get("url") == "crew/map/shop" and (asks.get("none") or {}).get("url") == "crew/map/shop"
                  and (asks.get("other") or {}).get("at") == "" and own.get("at") not in (None, ""))


if __name__ == "__main__":
    ctx = Ctx()
    results, passed, failed, skipped = run_all(TESTS, ctx)
    sys.exit(print_results(results, passed, failed, skipped))
