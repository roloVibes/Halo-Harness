"""tests.helpers.studio_auto_map -- scene 5 of 3.6.0.5 "Auto and groups" (design section 6, the VM browser test) in a
browser on the Linux VM: a real Studio server (tests/helpers/crew_rig.py) over a scratch home holding his OLD file
named starter (maps/starter.yaml: main -> planner -> coder), his map review-flow and, in the trusted project shop, the
project's map shop; crew.map is not set (new sessions on Auto) and no session runs. At 1280 x 800:

    picker   Agents -> 3 · Map: the switcher's rows in order, Auto's plan line (M1) with no session on Auto
    old      his old row picked: its words, its one button, no switch and no Lock, HIS boxes drawn
    copy     its button pressed: my-map open on the Map, holding his boxes and lines; his file untouched
    setup    Setup's Map step: the rows in order, Auto's "in use", the old row; its name opens his file on the Map

Every step catches its own waits and returns what it saw (no step raises); `verdicts(got)` says, per assert, what a
person would have seen wrong.

    python -m tests.helpers.studio_auto_map        (the last stdout line is the JSON)
"""
from __future__ import annotations

import sys
import time
from contextlib import contextmanager
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO))

from tests.helpers.chrome_driver import Driver  # noqa: E402

OLD_MAP = """format: map/1
name: starter
boxes:
- {id: planner, agent: planner}
- {id: coder, agent: coder}
lines:
- {from: main, to: planner, when: always}
- {from: planner, to: coder, when: always}
"""
FLOW_MAP = """format: map/1
name: review-flow
boxes:
- {id: coder, agent: coder}
lines:
- {from: main, to: coder, when: always}
"""
SHOP_MAP = """format: map/1
name: shop
boxes:
- {id: reviewer, agent: reviewer}
lines:
- {from: main, to: reviewer, when: always}
"""
OPTIONS = ["Auto (the default)", "review-flow", "starter · your copy from before", "shop (this project's)",
           "ship-it (ships with Halo)", "+ New map"]
OLD_WORDS, COPY, COPY_2 = "starter · your copy from before", "Copy as my-map", "Copy as my-map-2"
SETUP_ORDER = ["auto", "my-map", "review-flow", "old:starter", "shop", "ship-it", "one-model"]  # by data-name (my-map
# is one of his rows since the copy step)
NOTHING = "Nothing runs on Auto right now."
W11 = "Main picks who works on each task; each one's model is picked for its task, and the reason is shown."
Q = "document.querySelector"
SW = f"{Q}('[data-testid=map-switcher]')"
OFF = (1279, 799)


def _fold(text) -> str:
    return " ".join(str(text or "").split())


def _wait(c, expr: str, timeout: float):
    try:
        return c.wait(expr, timeout)
    except TimeoutError:
        return None


def _go(c, rig, query: str) -> None:
    from halo_harness.studio.server import url_for
    u = url_for(rig.server, "agents")
    c.go(f"{u.split('?')[0]}?{query}&tour=off#t={u.split('#t=')[1]}")


def _boxes(raw) -> list:
    return sorted(b.get("id") for b in (raw or {}).get("boxes") or [] if isinstance(b, dict))


def _lines(raw) -> list:
    return sorted((x.get("from"), x.get("to")) for x in (raw or {}).get("lines") or [] if isinstance(x, dict))


def picker(c, rig, st) -> dict:
    # Auto by a link that names it: with no link the Map opens this project's map first (mapStore.ts firstName)
    _go(c, rig, "mode=agents&view=map&map=auto")
    _wait(c, f"!!{SW} && {SW}.options.length >= 4 && !!{Q}('[data-testid=map-auto-plan]')", 10)
    c.mouse("mouseMoved", *OFF)
    time.sleep(0.5)
    return {"picker": c.js(f"""({{options: [...({SW}?.options || [])].map((o) => [o.textContent, o.value]),
      plan: {Q}('[data-testid=map-auto-plan]')?.innerText || '', watch: !!{Q}('[data-testid=map-auto-watch]'),
      value: {SW}?.value || '', auto: !!{Q}('[data-testid=map-auto]'), canvas: !!{Q}('[data-testid=map-canvas]')}})""")}


def old(c, rig, st) -> dict:
    c.js(f"(() => {{ const s = {SW}; Object.getOwnPropertyDescriptor(HTMLSelectElement.prototype, 'value').set.call(s, 'yours:starter');"
         " s.dispatchEvent(new Event('change', {bubbles: true})); return 1; })()")
    _wait(c, f"!!{Q}('[data-testid=map-old-words]')", 5)
    time.sleep(0.5)
    got = c.js(f"""({{words: {Q}('[data-testid=map-old-words]')?.textContent || '', copy: {Q}('[data-testid=map-old-copy]')?.textContent || '',
      uses: !!{Q}('[data-testid=map-uses-default]') || !!{Q}('[data-testid=map-uses-none]'),
      lock: !!{Q}('[data-testid=map-lock]'),
      boxes: [...new Set([...document.querySelectorAll('[data-map-box]')].map((e) => e.dataset.mapBox))].sort()}})""") or {}
    status, body = rig.api("GET", "crew/map/starter?scope=yours")
    got["api_boxes"] = sorted((body.get("boxes") or {}).keys()) if status == 200 else f"HTTP {status}"
    return {"old": got}


def copy(c, rig, st) -> dict:
    from halo_harness.crew import store
    c.click_on(f"{Q}('[data-testid=map-old-copy]')")
    _wait(c, f"{SW}?.value === 'my-map' || {SW}?.value?.endsWith(':my-map')", 5)
    time.sleep(0.5)
    mine = store.read(store.path_for("map", "my-map", state_dir=rig.state)) or {}
    return {"copy": {"value": c.js(f"{SW}?.value || ''"), "bar": bool(c.js(f"!!{Q}('[data-testid=map-bar]')")),
                     "boxes": _boxes(mine), "lines": _lines(mine),
                     "old_same": st["old_path"].read_bytes() == st["old_bytes"]}}


ROWS = """[...document.querySelectorAll('[data-testid=setup-map]')].map((r) => ({name: r.dataset.name || '', old: r.dataset.old === '1',
  text: (r.innerText || '').replace(/\\s+/g, ' ').trim(), in_use: !!r.querySelector('[data-testid=setup-map-in-use]'),
  old_btn: !!r.querySelector('[data-testid=setup-map-old]'), copy: r.querySelector('[data-testid=map-old-copy]')?.textContent || '',
  input: !!r.querySelector('input')}))"""


def setup(c, rig, st) -> dict:
    _go(c, rig, "mode=setup&block=team")
    _wait(c, "document.querySelectorAll('[data-testid=setup-map]').length >= 4", 10)
    c.mouse("mouseMoved", *OFF)
    time.sleep(0.5)
    rows = c.js(ROWS) or []
    opened, press = False, ""
    btn = f"{Q}('[data-testid=setup-map-old]')"
    hit = c.js(f"""(() => {{ const e = {btn}; if (!e) return 'no button'; const r = e.getBoundingClientRect();
      const at = document.elementFromPoint(r.left + r.width / 2, r.top + r.height / 2);
      return at === e || e.contains(at) ? 'the button' : (at ? (at.className || at.tagName) + ': ' + (at.textContent || '').slice(0, 60) : 'nothing'); }})()""")
    try:
        c.click_on(btn)
        opened = bool(_wait(c, f"!!{Q}('[data-testid=map-old-words]') && !!{Q}('[data-testid=map-bar]')", 5))
    except Exception as e:  # what the press could not do is said
        press = f"{type(e).__name__}: {e}"[:200]
    where = c.js(f"""({{url: location.search, value: {SW}?.value || '', words: !!{Q}('[data-testid=map-old-words]'),
      shown: [...document.querySelectorAll('.section-view')].filter((s) => s.offsetParent).map((s) => s.dataset.section)}})""")
    return {"setup": {"rows": rows, "opened": opened, "press": press, "where": where, "hit": hit}}


def _picker_says(p: dict) -> list:
    if not p:
        return ["not run"]
    says = []
    texts = [_fold(t) for t, _v in p.get("options") or []]
    if texts != OPTIONS:
        says.append(f"the switcher's rows are {texts}, not {OPTIONS}")
    if dict((_fold(t), v) for t, v in p.get("options") or []).get(OLD_WORDS) != "yours:starter":
        says.append("the old row's value is not yours:starter")
    for t in texts:
        if "starter (the default)" in t or "· in use" in t:
            says.append(f"a row says {t!r}")
    return says


def _m1_says(p: dict) -> list:
    if not p:
        return ["not run"]
    says = []
    if NOTHING not in _fold(p.get("plan")):
        says.append(f"Auto's plan line does not say {NOTHING!r}: {_fold(p.get('plan'))[:160]!r}")
    if p.get("watch"):
        says.append("Auto's plan line shows [Watch it in Live] with no session on Auto")
    return says


def _old_says(o: dict, st: dict) -> list:
    if not o:
        return ["not run"]
    says = []
    if _fold(o.get("words")) != OLD_WORDS:
        says.append(f"the old row's words are {_fold(o.get('words'))!r}")
    if _fold(o.get("copy")) != COPY:
        says.append(f"its button reads {_fold(o.get('copy'))!r}, not {COPY!r}")
    if o.get("uses"):
        says.append("a switch for new sessions is shown on his old file")
    if o.get("lock"):
        says.append("a Lock control is shown on his old file")
    if o.get("boxes") != ["coder", "main", "planner"]:
        says.append(f"the drawn boxes are {o.get('boxes')}, not his main, planner and coder")
    if o.get("api_boxes") != st.get("old_boxes"):
        says.append(f"the API's boxes are {o.get('api_boxes')}, not his {st.get('old_boxes')}")
    return says


def _copy_says(cp: dict, st: dict) -> list:
    if not cp:
        return ["not run"]
    says = []
    if cp.get("value") != "my-map" or not cp.get("bar"):
        says.append(f"the Map shows {cp.get('value')!r}, not my-map")
    if cp.get("boxes") != st.get("old_boxes") or cp.get("lines") != st.get("old_lines"):
        says.append(f"my-map holds {cp.get('boxes')} {cp.get('lines')}, not his {st.get('old_boxes')} {st.get('old_lines')}")
    if not cp.get("old_same"):
        says.append("his starter.yaml changed")
    return says


def _setup_says(s: dict) -> list:
    if not s:
        return ["not run"]
    rows = s.get("rows") or []
    says = []
    order = [("old:" if r.get("old") else "") + r.get("name", "") for r in rows]
    if order != SETUP_ORDER:
        says.append(f"the rows are {order}, not Auto, his rows, shop, ship-it, then One model for everything")
    if not rows or not _fold(rows[-1].get("text")).startswith("One model for everything"):
        says.append("the last row does not read One model for everything")
    auto = next((r for r in rows if r.get("name") == "auto" and not r.get("old")), None)
    if not auto or not _fold(auto.get("text")).startswith("Auto (the default)") or W11 not in _fold(auto.get("text")) \
            or not auto.get("in_use"):
        says.append(f"Auto's row reads {_fold((auto or {}).get('text'))!r} (in use: {(auto or {}).get('in_use')}), not "
                    "Auto (the default) with W11 and in use")
    oldr = next((r for r in rows if r.get("old")), None)
    if not oldr or not _fold(oldr.get("text")).startswith(OLD_WORDS) or not oldr.get("old_btn") \
            or _fold(oldr.get("copy")) != COPY_2 or oldr.get("input"):
        says.append(f"the old row is {oldr}, not {OLD_WORDS!r} with its name's button and {COPY_2!r} and no input")
    ship = next((r for r in rows if r.get("name") == "ship-it"), None)
    if not ship or not _fold(ship.get("text")).startswith("ship-it (ships with Halo)"):
        says.append(f"ship-it's row reads {_fold((ship or {}).get('text'))!r}")
    if any("starter (the default)" in _fold(r.get("text")) for r in rows):
        says.append("a row says starter (the default)")
    if not s.get("opened"):
        says.append("pressing the old row's name did not open his file on Agents -> 3 · Map")
    return says


def verdicts(got: dict) -> list:
    """One line per assert a person would have seen wrong: '(picker) ...', '(old) ...', '(copy) ...', '(setup) ...'."""
    st = got.get("his") or {}
    out = []
    for name, says in (("picker", _picker_says(got.get("picker") or {})), ("old", _old_says(got.get("old") or {}, st)),
                       ("copy", _copy_says(got.get("copy") or {}, st)), ("setup", _setup_says(got.get("setup") or {}))):
        if says:
            out.append(f"({name}) " + "; ".join(says))
    return out


def m1_verdicts(got: dict) -> list:
    says = _m1_says(got.get("picker") or {})
    return ["(picker) " + "; ".join(says)] if says else []


class AutoMapDriver(Driver):
    no_chrome = {"skip": "no Chrome found"}
    width, height = 1280, 800

    @contextmanager
    def session(self, c):
        from halo_harness.crew import store
        from tests.helpers.crew_rig import CrewRig
        from tests.helpers.trust_dir import trust
        t0 = time.monotonic()
        with CrewRig() as rig:
            old_path = store.path_for("map", "starter", state_dir=rig.state)
            store.write_text(old_path, OLD_MAP)
            store.write_text(store.path_for("map", "review-flow", state_dir=rig.state), FLOW_MAP)
            trust(rig.proj)
            shop = rig.proj / ".halo" / "crew" / "maps" / "shop.yaml"
            shop.parent.mkdir(parents=True, exist_ok=True)
            shop.write_text(SHOP_MAP, encoding="utf-8")
            his = store.read(old_path) or {}
            st = {"old_path": old_path, "old_bytes": old_path.read_bytes()}
            self.out["his"] = {"old_boxes": _boxes(his), "old_lines": _lines(his)}
            rig.studio()
            yield tuple((fn, (c, rig, st)) for fn in (picker, old, copy, setup))
        self.out["seconds"] = round(time.monotonic() - t0, 1)


if __name__ == "__main__":
    sys.exit(AutoMapDriver(sys.argv[1:]).main())
