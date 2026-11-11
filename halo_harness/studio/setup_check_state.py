"""halo_harness.studio.setup_check_state -- the Check and Linux fixes parts of
`GET setup/state` (Halo 3.3.0.0 R3, Studio's Setup section;
docs/STUDIO-setup.md "Check" and "Linux fixes"). Nothing here opens a
connection: the costs and the card read the cached catalog
(`catalog_by_ref`, no host probed).

    checks: [{key, title, what, cost, time, writes, default_on}]
                     checks/catalog.py CHECKS (doctor, catalog, hello, steward, gym), each cost with its models' prices
                     (3.4.0.0 B: the guided first run is the first-run pack's Setup check row when that pack is on)
    gym_models: [{ref, cost}]        the models the gym row offers (checks/run.gym_candidates)
    last_check: {when, ok, stopped, results: [{key, title, ok, lines}]} | null
                     <state>/studio/last-check.json, written when a Check job ends (studio/setup_check_job.py)
    linux_fixes: {needed, items: [{id, line}], platform}
                     the two fixes the wizard's Linux step applies, listed only when this box lacks them
    no_provider: bool                checks/provider.ready() is false: nothing for a session to run on yet
    model_notes: [lines]             a configured Ollama host nothing has read yet: "not read yet: Refresh"

`boot_attrs(page)` marks the served index.html `data-no-provider="1"` in that
state, so the page's first section is Setup (lib/store.ts initialSection).
"""

from __future__ import annotations

import json
import os
import sys
import threading
import time
from pathlib import Path

LAST_CHECK = "last-check.json"
_LINUX_TTL = 60.0
_LINUX: dict = {"items": None, "at": 0.0}
_LOCK = threading.Lock()


def platform_name() -> str:
    """`sys.platform` (a test seam: the Linux fixes are only offered off Windows)."""
    return sys.platform


def rg_on_path() -> bool:
    import shutil
    return bool(shutil.which("rg"))


def no_provider() -> bool:
    from halo_harness.checks.provider import ready
    try:
        return not ready()[0]
    except Exception:
        return False


# -- the last check ---------------------------------------------------------------
def last_check_path(state_dir) -> Path:
    if state_dir is None:
        from halo_harness.config.paths import bridge_home
        state_dir = bridge_home()
    return Path(state_dir) / "studio" / LAST_CHECK


def read_last_check(state_dir) -> "dict | None":
    try:
        got = json.loads(last_check_path(state_dir).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    return got if isinstance(got, dict) and "when" in got else None


def write_last_check(state_dir, record: dict) -> None:
    path = last_check_path(state_dir)
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(f".{os.getpid()}.tmp")
    tmp.write_text(json.dumps(record, indent=1), encoding="utf-8")
    os.replace(tmp, path)


# -- the Linux fixes ----------------------------------------------------------------
def linux_items() -> list:
    """The fixes this box is missing, the same two checks the wizard's Linux step makes (none on Windows); a
    minute's cache, since the PATH check starts a shell."""
    if platform_name() == "win32":
        return []
    with _LOCK:
        if _LINUX["items"] is not None and time.monotonic() - _LINUX["at"] < _LINUX_TTL:
            return list(_LINUX["items"])
    from halo_harness import linux_fixes as LF
    items = []
    if not rg_on_path():
        items.append({"id": "ripgrep", "line": "install a static ripgrep (rg) into ~/.local/bin"})
    try:
        on_path = LF.local_bin_on_noninteractive_path()
    except Exception:
        on_path = True
    if not on_path:
        items.append({"id": "path", "line": f"add ~/.local/bin to PATH via {LF.rc_file_for_shell()}"})
    with _LOCK:
        _LINUX.update(items=list(items), at=time.monotonic())
    return items


def forget_linux() -> None:
    with _LOCK:
        _LINUX.update(items=None, at=0.0)


def linux_block() -> dict:
    items = linux_items()
    return {"needed": bool(items), "items": items, "platform": platform_name()}


# -- the core checks ------------------------------------------------------------------
def _costs(ctx, rows: dict) -> dict:
    """Each check's cost line as checks/run.py states it, the catalog read once for all of them."""
    from halo_harness.checks import run as R
    out = {}
    try:
        out["hello"] = ("one tiny call, " + R.call_price(ctx.model, *R.HELLO_TOKENS, rows=rows)) if ctx.model else R.hello_cost(ctx)
    except Exception as e:
        out["hello"] = f"one tiny call (the price could not be read: {type(e).__name__})"
    try:  # 3.3.7.0 R5: the steward candidates row: free, or the download it names
        from halo_harness.checks.steward import cost as steward_cost
        out["steward"] = steward_cost(ctx)
    except Exception as e:
        out["steward"] = f"free, or the download it names (the candidates could not be read: {type(e).__name__})"
    try:
        out["gym"] = R.gym_cost(ctx)
    except Exception as e:
        out["gym"] = f"free for local models (the models could not be read: {type(e).__name__})"
    return out


def check_rows(ctx, rows: dict) -> list:
    from halo_harness.checks.catalog import default_on, offered
    costs = _costs(ctx, rows)
    return [{"key": c["key"], "title": c["title"], "what": c["what"], "cost": costs.get(c["key"], c["cost"]), "time": c["time"],
             "writes": c["writes"], "default_on": default_on(c, ctx)} for c in offered()]  # 3.3.7.0 R5: the steward row's


def gym_rows(ctx) -> list:
    """The gym row's models, each with its cost; `ctx.gym_models` becomes them, so the gym's cost line reads the same
    list (the candidates are read once)."""
    from halo_harness.checks import run as R
    try:
        ctx.gym_models = R.gym_candidates(ctx)
    except Exception:
        ctx.gym_models = []
    return [{"ref": ref, "cost": R.gym_model_cost(ref)} for ref in ctx.gym_models]


def model_notes() -> list:
    from halo_harness.providers.local_models_cached import hosts_not_read
    try:
        return [f"Ollama ({h.name}): not read yet: Refresh" for h in hosts_not_read()]
    except Exception:
        return []


def check_blocks(cwd=None, state_dir=None) -> dict:
    from halo_harness.checks.catalog import default_ctx
    from halo_harness.tui.dialogs.team_preview import catalog_by_ref
    ctx = default_ctx(cwd, state_dir=state_dir)
    rows = catalog_by_ref()
    gym = gym_rows(ctx)
    return {"checks": check_rows(ctx, rows), "gym_models": gym,
            "last_check": read_last_check(state_dir), "linux_fixes": linux_block(), "no_provider": no_provider(),
            "model_notes": model_notes()}


def boot_attrs(page: bytes, state_dir=None) -> bytes:
    """index.html with `data-no-provider="1"` on its <html> tag when no provider is set up (else unchanged).
    3.3.3.0 R1: not once Setup's Done was pressed for this home (`state_dir`): a reload stays where Done went."""
    if b"<html" not in page or not no_provider():
        return page
    if state_dir is not None:
        from halo_harness.studio.setup_done import setup_done_at
        if setup_done_at(state_dir):
            return page
    return page.replace(b"<html", b'<html data-no-provider="1"', 1)
