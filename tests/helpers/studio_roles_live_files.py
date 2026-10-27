"""tests.helpers.studio_roles_live_files -- Roles follows the disk (Halo
3.2.2.0 R6, "I have to refresh the page") in headless Chrome on the driver
base, over capture_studio's seeded home with the live feed ON and the files
watcher (studio/files_live.py) on a 0.4 s poll. tests/test_studio_roles_live_files.py
runs it:

    python -m tests.helpers.studio_roles_live_files live

1. Roles opens on a seeded lineup; the test writes one more card into its
   YAML on disk: the canvas shows it without a reload (a marker set on the
   page before is still there);
2. the bio form open on a bio, a field typed in, that bio's file changed on
   disk: the typed value stays and "<name> changed on disk" shows; Reload
   puts the file's version in the form;
3. the bio's file deleted on disk: it leaves the Bios list, the form closes
   and the line says it was deleted;
4. config.json's `team` cleared on disk: the open lineup loses its "active" chip.

The last stdout line is a JSON object of what it saw (exit 2: no Chrome).
No model is called."""
from __future__ import annotations

import os
import shutil
import sys
import time
from contextlib import contextmanager
from pathlib import Path

import yaml

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO))
sys.path.insert(0, str(REPO / "tools"))

from tests.helpers.chrome_driver import Driver  # noqa: E402

POLL = "0.4"
LINEUP = "studio-tiers"
BIO = "disk-bio"
CARDS = "document.querySelectorAll('[data-testid=\"roles-card\"]')"
NEW_CARD = f"[...{CARDS}].some((n) => n.dataset.agent === '{BIO}' || (n.dataset.id || '').includes('disk-card'))"
FIELD = "document.querySelector('[data-testid=\"bio-form\"] [data-testid=\"bio-description\"]')"
NOTE = "document.querySelector('[data-testid=\"roles-disk-bio\"]')"
BIO_ROW = f"document.querySelector('[data-testid=\"roles-bio\"][data-name=\"{BIO}\"]')"


def write_yaml(path: Path, raw: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    for attempt in range(20):  # Windows: a reader holding the file open (PermissionError)
        try:
            path.write_text(yaml.safe_dump(raw, sort_keys=False), encoding="utf-8")
            return
        except PermissionError:
            if attempt == 19:
                raise
            time.sleep(0.05)


def press(c, expr: str, until: str, timeout: float = 10):
    """Click `expr` with the pointer; the Linux runner's pointer path misses at times: then the element's own click()."""
    c.js(f"{expr}.scrollIntoView({{block: 'center'}}); 1")
    time.sleep(0.2)
    c.click_on(expr)
    try:
        return c.wait(until, 3)
    except TimeoutError:
        c.js(f"{expr}.click(); 1")
        return c.wait(until, timeout)


def live(c, url: str, state: Path, raw: dict) -> dict:
    out: dict = {}
    c.go(url)
    c.wait(f"document.querySelector('[data-testid=\"roles-canvas\"]')?.dataset.lineup === '{LINEUP}' && {CARDS}.length > 0", 40)
    c.wait("!!document.querySelector('[data-testid=\"roles-active\"]')", 15)
    time.sleep(1.0)  # the first draw fits the canvas; the feed connects
    out["cards_before"] = c.js(f"{CARDS}.length")
    c.js("window.__r6_marker = 'still here'; 1")
    # 1. a card written into the lineup's YAML on disk (what a session's Edit tool does)
    raw = dict(raw, agents=list(raw["agents"]) + [{"agent": BIO, "role": "custom", "as": "disk-card"}])
    t0 = time.time()
    write_yaml(state / "teams" / f"{LINEUP}.yaml", raw)
    out["new_card"] = bool(c.wait(NEW_CARD, 20))
    out["new_card_s"] = round(time.time() - t0, 2)
    out["cards_after"] = c.js(f"{CARDS}.length")
    out["no_reload"] = c.js("window.__r6_marker || ''")
    # 2. the bio form with a typed draft; the bio's file changes on disk
    press(c, BIO_ROW, f"!!document.querySelector('[data-testid=\"bio-form\"][data-bio=\"{BIO}\"]') && !!{FIELD}")
    out["field_before"] = c.wait(f"{FIELD}?.value", 10)
    c.click_on(FIELD)
    c.js(f"{FIELD}.focus(); {FIELD}.select(); 1")
    c.type_text("typed in the form")
    c.js("document.activeElement && document.activeElement.blur(); 1")  # the edit commits: the draft holds it
    c.wait(f"{FIELD}.value === 'typed in the form'", 5)
    write_yaml(state / "agents" / f"{BIO}.yaml", {"description": "changed on disk by the test", "kind": "subagent"})
    out["note"] = c.wait(f"{NOTE} && !{NOTE}.hasAttribute('data-gone') && {NOTE}.textContent", 20)
    out["draft_kept"] = c.js(f"{FIELD}.value")
    out["note_buttons"] = c.js(f"[...{NOTE}.querySelectorAll('button')].map((b) => b.textContent)")
    press(c, "document.querySelector('[data-testid=\"roles-disk-bio-reload\"]')", f"{FIELD}?.value === 'changed on disk by the test'")
    out["after_reload"] = c.js(f"{FIELD}.value")
    out["note_after_reload"] = c.js(f"!!{NOTE}")
    # 3. the bio's file deleted on disk: the list drops it, the form closes, the line says so
    (state / "agents" / f"{BIO}.yaml").unlink()
    out["gone_note"] = c.wait(f"{NOTE}?.hasAttribute('data-gone') && {NOTE}.textContent", 20)
    out["gone_in_list"] = c.js(f"!!{BIO_ROW}")
    out["form_closed"] = c.js("!document.querySelector('[data-testid=\"bio-form\"]')")
    # 4. config.json's team cleared from outside (`halo teams` / `halo config` in a terminal)
    from halo_harness.theme import set_config_value
    set_config_value("team", "")
    out["chip_gone"] = bool(c.wait("!document.querySelector('[data-testid=\"roles-active\"]')", 20))
    out["still_no_reload"] = c.js("window.__r6_marker || ''")
    return out


class LiveFilesDriver(Driver):
    """`live`: Roles over a seeded home, the feed on, the files watcher on a short poll."""

    no_chrome = {"skip": "no Chrome found"}

    @contextmanager
    def session(self, c):
        from capture_roles import seed_catalog, seed_tiers
        from capture_studio import seeded_home, serve
        os.environ["HALO_STUDIO_FILES_POLL_S"] = POLL
        state = seeded_home()
        seed_catalog(state)
        raw = seed_tiers(state, LINEUP)
        write_yaml(state / "agents" / f"{BIO}.yaml", {"description": "first words", "kind": "subagent"})
        srv, url = serve(state, True)
        from tests.helpers.studio_full import full
        url = full(url)  # 3.3.2.0 R3: every panel open, the arrangement this driver works in
        url = url.replace("mode=orchestra&feed=off", "mode=roles&tour=off")  # the live feed on: it carries the frames
        try:
            yield ((live, (c, url, state, raw)),)
        finally:
            srv.shutdown()
            srv.server_close()
            shutil.rmtree(state.parent, ignore_errors=True)


if __name__ == "__main__":
    sys.exit(LiveFilesDriver(sys.argv[1:]).main())
