"""halo_harness.providers.balances -- Halo 2.0.4 round 3 (deliverable 2):
ONE shared balances surface (`halo balances`, `/balances`, the status-bar
chip, `halo doctor`) -- a cached background refresh, never on the UI
thread, with a TTL under the state dir, for every provider whose API
offers a balance/credit endpoint (2.0.3-brief part B): OpenRouter's `GET
/key`/`/credits` (`providers.openrouter_account`, already shipped --
reused here, never duplicated), Experiential Labs' `GET /credits`
(`providers.experiential_account.fetch_experiential_credits`, which had
no cache of its own before this round), Databricks (explicitly EXCLUDED
by the owner -- DBU billing is on the workspace side, part B item 5 --
always "not offered"), and Anthropic (no balance endpoint for a plain API
key; an Admin key's organisation usage/cost report when
`ANTHROPIC_ADMIN_KEY` is configured, else "not offered", part B item 2).
Every other provider (Hugging Face, OpenAI, Codex, Claude Code
subscription, Ollama) has no balance concept at all here -- "not
offered" uniformly, same as Databricks/a keyless Anthropic.

Persisted to `<state_dir>/balances.json` so a FRESH process (the `halo
balances` CLI, `halo doctor`) can show the last known reading instantly,
without waiting on a new fetch -- the TUI's own background workers are
what keeps it fresh while a session runs (see `tui/slash.py`'s balance
workers, one per provider, same shape the pre-existing OpenRouter-only
one already had).
"""

from __future__ import annotations

import json
import os
import time
from pathlib import Path
from typing import Optional

#: Same cadence OpenRouter's own pre-existing cache already used.
BALANCES_REFRESH_INTERVAL_S = 300.0
BALANCES_STALE_AFTER_S = 600.0

# The four providers part B actually discusses; every other provider name
# this harness knows about is "not offered" with no fetch attempted at all.
_BALANCE_PROVIDERS = ("openrouter", "experiential", "databricks", "anthropic")


def balances_json_path(state_dir) -> Path:
    return Path(state_dir) / "balances.json"


def _load(state_dir) -> dict:
    path = balances_json_path(state_dir)
    if not path.exists():
        return {}
    try:
        with open(path, encoding="utf-8") as f:
            data = json.load(f)
        return data if isinstance(data, dict) else {}
    except (json.JSONDecodeError, OSError):
        return {}


def _save(state_dir, data: dict) -> None:
    """Best-effort; swallows OSError -- same contract as every other
    write_*_json in this package. Atomic tmp-file + os.replace, same
    reasoning `anthropic_catalog.write_ant_models_json` already gives."""
    try:
        path = balances_json_path(state_dir)
        path.parent.mkdir(parents=True, exist_ok=True)
        tmp_path = path.with_name(f".{path.name}.{os.getpid()}.tmp")
        with open(tmp_path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2)
        os.replace(tmp_path, path)
    except OSError:
        pass


def _fetch_anthropic_usage(env: "Optional[dict]" = None) -> "Optional[dict]":
    """2.0.3-brief part B item 2: no balance endpoint for a plain API
    key; with an Admin key (`ANTHROPIC_ADMIN_KEY`), the organisation cost
    report gives spend for the period. The exact response shape is
    unverified (the research notes say so plainly) -- this reads the
    documented `GET /v1/organizations/cost_report` path and degrades to
    `None` ("not offered") on ANY failure (wrong shape, 404, network),
    exactly like every other best-effort account-endpoint reader in this
    package. Never the plain inference key -- an Admin key is a
    deliberately separate, higher-privilege credential this harness never
    assumes is present."""
    import os as _os
    e = env if env is not None else _os.environ
    admin_key = e.get("ANTHROPIC_ADMIN_KEY")
    if not admin_key:
        return None
    try:
        from halo_harness.providers.config import resolve_anthropic
        ant = resolve_anthropic(env)
        if ant is None:
            return None
        from halo_harness.providers.http import open_upstream
        import urllib.parse
        parsed = urllib.parse.urlparse(ant.base_url)
        host = parsed.hostname
        port = parsed.port or (443 if parsed.scheme == "https" else 80)
        tls = parsed.scheme == "https"
        path = parsed.path.rstrip("/") + "/v1/organizations/cost_report"
        headers = {"x-api-key": admin_key, "anthropic-version": "2023-06-01", "Accept-Encoding": "identity"}
        conn = open_upstream(host, port, tls)
        try:
            if conn.sock:
                conn.sock.settimeout(10.0)
            conn.request("GET", path, headers=headers)
            resp = conn.getresponse()
            raw = resp.read()
        finally:
            conn.close()
        if resp.status != 200:
            return None
        data = json.loads(raw.decode("utf-8", "replace"))
        total = 0.0
        for bucket in data.get("data") or []:
            for result in bucket.get("results") or []:
                amount = result.get("amount") or {}
                v = amount.get("value")
                if isinstance(v, (int, float, str)):
                    try:
                        total += float(v)
                    except (TypeError, ValueError):
                        pass
        return {"spend_usd": total}
    except Exception:
        return None


def refresh_all_balances(state_dir, *, env: "Optional[dict]" = None) -> dict:
    """One attempt per balance-bearing provider, best-effort, persisted
    to `balances.json` on return -- never raises, never blocks longer
    than each underlying fetch's own bounded timeout. Each entry:
    `{"status": "ok"|"not_offered"|"unreachable", "amount", "kind",
    "note", "fetched_at_wall"}` (fields beyond `status` optional).
    Reuses OpenRouter's EXISTING cache/fetch (`providers.
    openrouter_account`) unchanged -- this function is additive, never a
    replacement for that module's own status-bar-chip contract."""
    from halo_harness.providers.enablement import is_enabled_with_env
    now = time.time()
    out: dict = {}

    if is_enabled_with_env("openrouter", env):
        from halo_harness.providers.config import resolve_openrouter, resolve_openrouter_management_key
        from halo_harness.providers.openrouter_account import refresh_cached_openrouter_balance
        orc = resolve_openrouter(env)
        if orc is not None:
            management_key = resolve_openrouter_management_key(env)
            entry = refresh_cached_openrouter_balance(orc.base_url, orc.api_key, management_key=management_key)
            if entry is not None:
                out["openrouter"] = {"status": "ok", "amount": entry["amount"], "kind": entry["kind"],
                                      "label": entry.get("label"), "fetched_at_wall": entry.get("fetched_at_wall", now),
                                      "total_credits": entry.get("total_credits"),
                                      "total_usage": entry.get("total_usage")}
            else:
                out["openrouter"] = {"status": "unreachable"}
        else:
            out["openrouter"] = {"status": "not_offered", "note": "not configured"}
    else:
        out["openrouter"] = {"status": "not_offered", "note": "not configured"}

    if is_enabled_with_env("experiential", env):
        from halo_harness.providers.experiential_account import fetch_experiential_credits
        credits = fetch_experiential_credits(env)
        if isinstance(credits, dict) and isinstance(credits.get("total_credits"), (int, float)):
            total = credits["total_credits"]
            used = credits.get("total_usage") or 0.0
            out["experiential"] = {"status": "ok", "amount": total - used, "kind": "credits",
                                    "note": f"of ${total:.2f} total credits", "fetched_at_wall": now}
        else:
            out["experiential"] = {"status": "unreachable"}
    else:
        out["experiential"] = {"status": "not_offered", "note": "not configured"}

    # 2.0.3-brief part B item 5: Databricks is explicitly excluded by the
    # owner (DBU billing is on the workspace side) -- never a fetch,
    # unconditionally "not offered", regardless of enablement.
    out["databricks"] = {"status": "not_offered",
                          "note": "DBU billing is on the workspace side -- not available as a balance here"}

    usage = _fetch_anthropic_usage(env)
    if usage is not None:
        out["anthropic"] = {"status": "ok", "amount": usage["spend_usd"], "kind": "spend",
                             "note": "organisation spend this period (Admin key)", "fetched_at_wall": now}
    else:
        out["anthropic"] = {"status": "not_offered",
                             "note": "balance not exposed by this API for a plain key "
                                      "(set ANTHROPIC_ADMIN_KEY for organisation spend)"}

    persisted = _load(state_dir)
    persisted.update(out)
    _save(state_dir, persisted)
    return out


def cached_balances(state_dir) -> dict:
    """Read-only, never makes a network call -- the `halo balances`/
    `/balances`/doctor read path, and what a fresh CLI process shows
    before (or instead of) triggering its own refresh."""
    return _load(state_dir)


def format_balance_entry(provider_label: str, entry: "Optional[dict]") -> str:
    """One plain line -- `"OpenRouter: $12.40 left (key: my-key, as of
    14:32:05)"` / `"Databricks: not offered (DBU billing is on the "
    "workspace side...)"` / `"Anthropic: not fetched yet"`."""
    import datetime
    if not entry:
        return f"{provider_label}: not fetched yet"
    status = entry.get("status")
    if status == "not_offered":
        note = entry.get("note") or "not offered by this API"
        return f"{provider_label}: not offered ({note})"
    if status == "unreachable":
        return f"{provider_label}: could not fetch (network/auth) -- last known reading, if any, is below"
    amount = entry.get("amount")
    if not isinstance(amount, (int, float)):
        return f"{provider_label}: not fetched yet"
    kind = entry.get("kind")
    verb = "remaining" if kind in ("limit_remaining", "credits") else ("spent" if kind == "spend" else "used")
    # 2.0.7 balances-remaining round (rolo: "you want what's LEFT, not
    # '$145 used'"): REMAINING leads everywhere it exists, and the
    # total/used breakdown rides the same line whenever the provider
    # offered it -- a used/spent figure never stands alone without its
    # remaining twin.
    if kind == "spend" and isinstance(entry.get("total_credits"), (int, float)):
        remaining = entry["total_credits"] - amount
        total_note = f" (of ${entry['total_credits']:.2f} total, ${amount:.2f} used, ${remaining:.2f} left)"
    elif kind in ("limit_remaining", "credits") and isinstance(entry.get("total_credits"), (int, float)):
        total_note = (f" (of ${entry['total_credits']:.2f} total, "
                      f"${entry.get('total_usage') or 0:.2f} used)")
    else:
        total_note = ""
    when = ""
    if isinstance(entry.get("fetched_at_wall"), (int, float)):
        when = f", as of {datetime.datetime.fromtimestamp(entry['fetched_at_wall']).strftime('%H:%M:%S')}"
    note = f" ({entry['note']})" if entry.get("note") else ""
    label = f" (key: {entry['label']})" if entry.get("label") else ""
    return f"{provider_label}: ${amount:.2f} {verb}{total_note}{note}{label}{when}"


def format_balances_table(entries: dict) -> "list[str]":
    """Shared rendering for `halo balances` and `/balances` -- one line
    per provider, in `enablement.PROVIDER_NAMES`'s own fixed order (never
    this module's internal dict order, which depends on insertion)."""
    from halo_harness.providers.enablement import PROVIDER_NAMES, label_with_prefix
    lines = []
    for name in PROVIDER_NAMES:
        entry = entries.get(name)
        if entry is None:
            entry = {"status": "not_offered", "note": "no balance concept for this provider"}
        lines.append(format_balance_entry(label_with_prefix(name), entry))
    return lines
