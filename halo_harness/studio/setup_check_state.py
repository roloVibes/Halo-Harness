"""halo_harness.studio.setup_check_state -- the Check and Linux fixes parts of
`GET setup/state` (Halo 3.3.0.0 R3, Studio's Setup section;
docs/STUDIO-setup.md "Check" and "Linux fixes"). Nothing here opens a
connection: the costs and the card read the cached catalog
(`catalog_by_ref`, no host probed).

    checks: [{key, title, what, cost, time, writes, default_on}]
                     start/checks.py CHECKS (doctor, catalog, hello, gym, start), each cost with its models' prices
    gym_models: [{ref, cost}]        the models the gym row offers (start/checks_run.gym_candidates)
    card: [lines]                    the guided first run's card (start/card.card_lines), shown before its row is ticked
    last_check: {when, ok, stopped, results: [{key, title, ok, lines}]} | null
                     <state>/studio/last-check.json, written when a Check job ends (studio/setup_check_job.py)
    linux_fixes: {needed, items: [{id, line}], platform}
                     the two fixes the wizard's Linux step applies, listed only when this box lacks them
    no_provider: bool                start/provider.ready() is false: nothing for a session to run on yet
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
    from halo_harness.start.provider import ready
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


# -- the five checks ------------------------------------------------------------------
def _costs(ctx, rows: dict) -> dict:
    """Each check's cost line as start/checks_run states it, the catalog read once for all of them."""
    from halo_harness.start import checks_run as R
    from halo_harness.start.card import estimate
    out = {}
    try:
        out["hello"] = ("one tiny call, " + R.call_price(ctx.model, *R.HELLO_TOKENS, rows=rows)) if ctx.model else R.hello_cost(ctx)
    except Exception as e:
        out["hello"] = f"one tiny call (the price could not be read: {type(e).__name__})"
    try:
        out["gym"] = R.gym_cost(ctx)
    except Exception as e:
        out["gym"] = f"free for local models (the models could not be read: {type(e).__name__})"
    try:
        out["start"] = estimate(fake=ctx.fake, default=ctx.model, rule=False, models_by_ref=rows) + " (halo start --explain shows the rule)"
    except Exception as e:
        out["start"] = f"the card's estimate (it could not be read: {type(e).__name__})"
    return out


def check_rows(ctx, rows: dict) -> list:
    from halo_harness.start.checks import CHECKS
    costs = _costs(ctx, rows)
    return [{"key": c["key"], "title": c["title"], "what": c["what"], "cost": costs.get(c["key"], c["cost"]), "time": c["time"],
             "writes": c["writes"], "default_on": bool(c["default_on"])} for c in CHECKS]


def gym_rows(ctx) -> list:
    """The gym row's models, each with its cost; `ctx.gym_models` becomes them, so the gym's cost line reads the same
    list (the candidates are read once)."""
    from halo_harness.start import checks_run as R
    try:
        ctx.gym_models = R.gym_candidates(ctx)
    except Exception:
        ctx.gym_models = []
    return [{"ref": ref, "cost": R.gym_model_cost(ref)} for ref in ctx.gym_models]


def card(cwd, state_dir, rows: dict) -> list:
    from halo_harness.start import fake
    from halo_harness.start.card import card_lines
    try:
        return card_lines(state_dir=state_dir, cwd=cwd, fake=fake.enabled(), models_by_ref=rows)
    except Exception as e:
        return [f"the card could not be read: {type(e).__name__}: {e}"]


def model_notes() -> list:
    from halo_harness.providers.local_models_cached import hosts_not_read
    try:
        return [f"Ollama ({h.name}): not read yet: Refresh" for h in hosts_not_read()]
    except Exception:
        return []


def check_blocks(cwd=None, state_dir=None) -> dict:
    from halo_harness.start.checks import default_ctx
    from halo_harness.tui.dialogs.team_preview import catalog_by_ref
    ctx = default_ctx(cwd, state_dir=state_dir)
    rows = catalog_by_ref()
    gym = gym_rows(ctx)
    return {"checks": check_rows(ctx, rows), "gym_models": gym, "card": card(cwd, state_dir, rows),
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
