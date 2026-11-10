"""halo_harness.providers.copilot_doctor -- `halo doctor`'s one Copilot row (Halo 3.3.17.0 R2).

No network: it reads the settings, whether a refresh token is stored and the account record
(`~/.halo/copilot/account.json`, written by every sign-in, refresh and failed call). One row, one next step:

    not set up          [OK]   Copilot at work: not set up (optional) -- ... (an info line: nothing is wrong)
    not signed in       [WARN] ... -> fix: halo copilot signin
    token expired       [WARN] ... -> fix: halo copilot signin
    consent missing     [WARN] ... -> see: docs/PROVIDERS-copilot.md (an admin consents to the scopes it names)
    billing not enabled [WARN] ... -> see: docs/PROVIDERS-copilot.md
    no licence          [WARN] ... -> see: docs/PROVIDERS-copilot.md
    signed in           [OK]   Copilot at work: signed in as <who> (tenant, door) until <when>
"""

from __future__ import annotations

import time

DOC = "docs/PROVIDERS-copilot.md"
SIGNIN = "halo copilot signin"


def row() -> str:
    from halo_harness.doctor import OK, WARN, _fix
    from halo_harness.providers import copilot_account as A
    from halo_harness.providers.copilot_config import load
    from halo_harness.providers.copilot_tokens import refresh_token
    cfg = load()
    if not cfg.configured:
        return (f"{OK} Copilot at work: not set up (optional) -- set copilot.tenant and copilot.client_id, then "
                f"`{SIGNIN}` ({DOC} \"Register the app\")")
    if not refresh_token():
        return _fix(f"{WARN} Copilot at work: set up for tenant {cfg.tenant}, not signed in", cmd=SIGNIN)
    acct = A.load()
    err = acct.get("last_error") if isinstance(acct.get("last_error"), dict) else None
    kind = (err or {}).get("kind")
    who = acct.get("username") or acct.get("name") or "your account"
    if kind == "expired":
        return _fix(f"{WARN} Copilot at work: the token expired and the refresh failed for {who}", cmd=SIGNIN)
    if kind == "consent":
        return _fix(f"{WARN} Copilot at work: consent missing -- an admin consents to "
                    f"{' '.join(cfg.consent_scopes())}", see=f"{DOC} \"Register the app\"")
    if kind == "billing":
        return _fix(f"{WARN} Copilot at work: billing not enabled -- Work IQ needs consumptive billing (Copilot Credits) "
                    "on the tenant, or set copilot.api graph-beta", see=f"{DOC} \"The two doors\"")
    if kind == "licence":
        return _fix(f"{WARN} Copilot at work: {who} has no Microsoft 365 Copilot licence (graph-beta needs one), or set "
                    "copilot.api workiq", see=f"{DOC} \"The two doors\"")
    until = acct.get("access_expires_at")
    when = A.when(until)
    if isinstance(until, (int, float)) and until < time.time():
        tail = f"; the last access token ended {when} (a new one is fetched on the next call)"
    else:
        tail = f" until {when}" if when else ""
    return f"{OK} Copilot at work: signed in as {who} (tenant {cfg.tenant}, {cfg.api}){tail}"


def entries() -> list:
    try:
        return [("copilot", row())]
    except Exception as e:
        from halo_harness.doctor import WARN
        return [("copilot", f"{WARN} Copilot at work: the check failed ({type(e).__name__}: {e})")]
