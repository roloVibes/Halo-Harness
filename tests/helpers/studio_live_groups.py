"""tests.helpers.studio_live_groups -- Live in groups (Halo 3.3.16.3, the owner: "here's this one task and here's the
sub-agents in there, and it points to that group") in headless Chrome on the driver base, over
tests/helpers/studio_fleet_rig.py (halo-dev-cycle, this harness's real session) plus the agents an Auto main started
(tests/helpers/studio_live_rig.py rows, each with its `spawn` step as agent/agent_hooks.py writes it):

    three readers   one reply of main (`main#3`), picked by Auto: a task group titled from main's own line, its second
                    line the pick in plain words
    ten checkers    one reply (`main#4`): one group, a grid of four to a row, no two boxes overlapping
    a square        `media` (its row's `square` with its DOES line): a square group; its two helpers (one reply of the
                    square's agent) a task group inside it
    a scribe        alone in its reply: not boxed, its own edge from main

    python -m tests.helpers.studio_live_groups groups [--shots DIR]
        nothing opens on load; each group's bar (title, counts, why), main's edge into the group and none into its
        agents; the grid; the nesting; no text overflowing a bar; the group's hover card; the chevron folds the ten to
        their bar and a member waiting lights it; Session's timeline "by group" lists a title row per group

The last stdout line is a JSON object of what it saw (exit 2: no Chrome). No model is called."""
from __future__ import annotations

import sys
import time
from contextlib import contextmanager
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO))

from tests.helpers.chrome_driver import Driver  # noqa: E402
from tests.helpers.studio_hover_read import hover_card, away, none_for  # noqa: E402

Q = "document.querySelector"
MAP = f"{Q}('[data-testid=\"roles-live-map\"]')"
WHY = "a pdf in the task, the cheapest model that reads PDFs ($0.20/$0.80 per 1M)"
DOES = "Reads and makes images, audio, video and PDFs for a model that cannot, and hands back what it found."


def group(gid_part: str) -> str:
    return f"[...document.querySelectorAll('[data-testid=\"live-group\"]')].find((g) => g.dataset.group.endsWith({gid_part!r}))"


def bar(gid_part: str) -> str:
    return f"[...document.querySelectorAll('[data-testid=\"live-group-bar\"]')].find((g) => g.dataset.group.endsWith({gid_part!r}))"


def rows() -> list:
    now = time.time()
    out = []

    def add(aid, name, role, model, step, desc, lead="", parent="main", **more):
        out.append({"agent_id": aid, "parent": parent, "name": name, "role": role, "bio": role, "lineup": "auto", "model": model,
                    "kind": "member", "task": desc, "since": now - 40, "state": "running", "turns": 1, "cost_usd": 0.0012,
                    "current": "thinking", "last_text": "", "transcript": None,
                    "spawn": {"step": step, "description": desc, "lead": lead}, **more})
    for i in range(3):
        add(f"rd{i}", f"reader-{i + 1}", "reader", "or:mock/kimi-k3", "main#3", f"Read PDF {i + 1}",
            "I'll read the three PDFs side by side.", model_reason=WHY)
    for i in range(10):
        add(f"ck{i}", f"checker-{i + 1}", "checker", "or:mock/cheap-fast", "main#4", f"Check the links in doc {i + 1}")
    add("sqm1", "media", "media", "or:mock/gemini-vision", "main#5", "square media", square={"name": "media", "engine": "session", "does": DOES})
    add("sqh1", "listener", "listener", "or:mock/whisper-ish", "sqm1#1", "Transcribe the clip", "Splitting the clip between two helpers.", parent="sqm1")
    add("sqh2", "looker", "looker", "or:mock/gemini-vision", "sqm1#1", "Describe the frames", "Splitting the clip between two helpers.", parent="sqm1")
    add("scr1", "scribe", "scribe", "or:mock/glm-5-coder", "main#6", "Write up the findings")
    return out


def open_live(c, rig) -> dict:
    from tests.helpers.studio_live_rig import Live
    lv = rig.groups_live = Live(rig, extra=())
    for r in rows():
        lv.rows[r["agent_id"]] = r
    lv.refresh()
    c.go(rig.url("agents", "&view=live&scope=here"))
    out = {"nodes": c.wait(f"{MAP} && +{MAP}.dataset.nodes >= 20 && +{MAP}.dataset.nodes", 40)}
    c.wait(f"document.querySelectorAll('[data-testid=\"live-group\"]').length >= 4", 20)
    out["quiet"] = none_for(c, 1.0)  # nothing opens on load: no hover card
    out["inspector_on_load"] = c.js(f"{Q}('[data-testid=\"live-inspector\"]')?.dataset.pick || ''")
    out["all_open"] = c.js("[...document.querySelectorAll('[data-testid=\"live-group\"]')].every((g) => g.dataset.open === 'true')")
    return out


READ_GROUPS = """[...document.querySelectorAll('[data-testid="live-group"]')].map((g) => {
  const t = (el, s) => el.querySelector(s)?.textContent || '';
  const bar = document.querySelector(`[data-testid="live-group-bar"][data-group="${g.dataset.group}"]`);
  const cut = [...bar.querySelectorAll('.lg-title, .lg-counts, .lg-why')].filter((e) => e.scrollWidth > e.clientWidth + 1 && getComputedStyle(e).textOverflow !== 'ellipsis');
  return {id: g.dataset.group, kind: g.dataset.kind, count: +g.dataset.count, outer: g.dataset.outer || '', open: g.dataset.open === 'true',
          title: t(bar, '[data-testid="live-group-title"]'), counts: t(bar, '[data-testid="live-group-counts"]'), why: t(bar, '[data-testid="live-group-why"]'),
          spill: bar.scrollHeight > bar.clientHeight + 1, cut: cut.length};
})"""

IN_GROUP = """((gexp, ids) => { const g = gexp; if (!g) return null; const gr = g.getBoundingClientRect();
  const bar = document.querySelector(`[data-testid="live-group-bar"][data-group="${g.dataset.group}"]`).getBoundingClientRect();
  const rs = ids.map((id) => document.querySelector(`[data-testid="roles-live-node"][data-agent$="${id}"]`)).filter(Boolean).map((n) => n.getBoundingClientRect());
  const inside = rs.every((r) => r.left >= gr.left - 0.5 && r.right <= gr.right + 0.5 && r.top >= bar.bottom - 0.5 && r.bottom <= gr.bottom + 0.5);
  let overlap = 0;
  for (let i = 0; i < rs.length; i++) for (let j = i + 1; j < rs.length; j++) {
    const a = rs[i], b = rs[j];
    if (a.left < b.right - 0.5 && b.left < a.right - 0.5 && a.top < b.bottom - 0.5 && b.top < a.bottom - 0.5) overlap++;
  }
  return {n: rs.length, inside, overlap, tops: new Set(rs.map((r) => Math.round(r.top))).size};
})"""


def the_groups(c, rig) -> dict:
    out = {"groups": c.js(READ_GROUPS)}
    ids = lambda p, n: [f"{p}{i}" for i in range(n)]  # noqa: E731
    out["readers_box"] = c.js(f"{IN_GROUP}({group('main#3')}, {ids('rd', 3)!r})")
    out["ten_box"] = c.js(f"{IN_GROUP}({group('main#4')}, {ids('ck', 10)!r})")
    out["square_box"] = c.js(f"{IN_GROUP}({group('sqm1')}, ['sqm1', 'sqh1', 'sqh2'])")
    edges = "[...document.querySelectorAll('[data-testid=\"roles-live-edge\"]')]"
    out["edge_to_group"] = c.js(f"{edges}.filter((e) => (e.dataset.to || '').endsWith('main#3')).map((e) => e.dataset.from.split('|').pop())")
    out["edges_to_readers"] = c.js(f"{edges}.filter((e) => /\\|?rd[0-9]$/.test(e.dataset.to || '')).length")
    out["scribe_edge"] = c.js(f"{edges}.filter((e) => (e.dataset.to || '').endsWith('scr1')).map((e) => e.dataset.from.split('|').pop())")
    out["scribe_boxed"] = c.js(f"[...document.querySelectorAll('[data-testid=\"live-group\"]')].some((g) => {{ const n = {Q}('[data-testid=\"roles-live-node\"][data-agent$=\"scr1\"]'); "
                               "const a = g.getBoundingClientRect(), b = n.getBoundingClientRect(); return b.left >= a.left && b.right <= a.right && b.top >= a.top && b.bottom <= a.bottom; })")
    return out


def hover(c, rig) -> dict:
    b = bar("main#3")
    c.js(f"{b}.scrollIntoView({{block: 'center', inline: 'center'}}); 1")
    gid = c.js(f"{group('main#3')}.dataset.group")
    got = hover_card(c, b, "group", gid, 0.5, 0.3)
    away(c)
    return {"hover": {k: got.get(k) for k in ("title", "is", "rows", "over")} if got else None}


def fold(c, rig) -> dict:
    lv = rig.groups_live
    g = group("main#4")
    nodes = "document.querySelectorAll('[data-testid=\"roles-live-node\"]').length"
    before = c.js(nodes)
    c.js(f"{g}.scrollIntoView({{block: 'center', inline: 'center'}}); 1")
    toggle = f"{bar('main#4')}.querySelector('[data-testid=\"live-group-toggle\"]')"
    c.click_on(toggle)
    out = {"folded": c.wait(f"{g} && !{g}.dataset.open && {nodes} === {before - 10} && [{nodes}, Math.round({g}.getBoundingClientRect().height)]", 10)}
    lv.rows["ck3"]["state"] = "waiting"
    lv.refresh()
    out["asks"] = c.wait(f"{bar('main#4')}?.dataset.asks === 'true' && {bar('main#4')}.querySelector('[data-testid=\"live-group-counts\"]').textContent", 20)
    c.click_on(toggle)
    out["reopened"] = c.wait(f"{g}?.dataset.open === 'true' && {nodes} === {before} && {nodes}", 10)
    return out


def shots(c, rig, folder: str) -> dict:
    """For the worker's own look (not asserted): Live with its groups in Focus, fitted, then at 100% on the groups."""
    if not folder:
        return {}
    Path(folder).mkdir(parents=True, exist_ok=True)
    c.call("Emulation.setDeviceMetricsOverride", width=1800, height=1100, deviceScaleFactor=1, mobile=False)
    c.go(rig.url("agents", "&view=live&scope=here"))
    c.wait(f"document.querySelectorAll('[data-testid=\"live-group\"]').length >= 4 && {MAP} && +{MAP}.dataset.nodes >= 20", 40)
    c.click_on(f"{Q}('[data-testid=\"focus-toggle\"]')")
    time.sleep(0.8)
    c.click_on(f"{Q}('[data-testid=\"roles-live-fit\"]')")
    time.sleep(0.6)
    c.shot(str(Path(folder) / "live-groups.png"), 1800, 1100, 1)
    for _ in range(12):
        if float(c.js(f"+{Q}('[data-testid=\"roles-live-world\"]').dataset.zoom") or 1) >= 0.99:
            break
        c.click_on(f"{Q}('[data-testid=\"roles-live-zoom-in\"]')")
        time.sleep(0.15)
    for i, part in enumerate(("main#3", "main#4", "sqm1")):
        c.js(f"{group(part)}.scrollIntoView({{block: 'start', inline: 'start'}}); 1")
        time.sleep(0.4)
        c.shot(str(Path(folder) / f"live-groups-{i}.png"), 1800, 1100, 1)
    return {"shots": folder}


def timeline(c, rig) -> dict:
    c.go(rig.url("session"))
    btn = f"{Q}('[data-testid=\"session-live-timeline-by-group\"]')"
    c.wait(f"!!{btn} && document.querySelectorAll('[data-testid=\"session-live-timeline\"] [data-testid=\"fleet-lane\"]').length >= 15", 40)
    c.click_on(btn)
    heads = "[...document.querySelectorAll('[data-testid=\"session-live-timeline\"] [data-testid=\"fleet-lane-group\"]')]"
    return {"timeline_groups": c.wait(f"{heads}.length >= 3 && {heads}.map((h) => h.textContent)", 15),
            "by_group_pressed": c.js(f"{btn}.getAttribute('aria-pressed')")}


class LiveGroupsDriver(Driver):
    no_chrome = {"skip": "no Chrome found"}

    @contextmanager
    def session(self, c):
        from tests.helpers.studio_fleet_rig import StudioFleetRig
        folder = self.argv[self.argv.index("--shots") + 1] if "--shots" in self.argv else ""
        with StudioFleetRig() as rig:
            a = (c, rig)
            yield ((open_live, a), (the_groups, a), (hover, a), (fold, a), (shots, (c, rig, folder)), (timeline, a))


if __name__ == "__main__":
    sys.exit(LiveGroupsDriver(sys.argv[1:]).main())
