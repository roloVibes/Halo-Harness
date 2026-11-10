"""halo_harness.providers.copilot_config -- the `copilot.*` settings and the fixed facts of the two doors (Halo
3.3.17.0 R1, docs/PROVIDERS-copilot.md).

    copilot.tenant     the Entra tenant (a GUID or a domain); no default
    copilot.client_id  the user's own Entra app registration, a public client; no default
    copilot.api        workiq (default, the Work IQ API's A2A door) | graph-beta (Graph /beta Copilot Chat API)
    copilot.web        true: Copilot may ground on the web (graph-beta's webContext.isWebEnabled)
    copilot.timezone   the IANA zone sent with each turn; unset, this system's zone, else UTC
    copilot.scopes     a space-separated scope list that replaces the api's own (a tenant that names Work IQ's
                       delegated scope differently)

Nothing here holds a tenant, an app id or a token of a real person: the docs and tests say `pretend-tenant` and
`00000000-0000-0000-0000-000000000000`.

Test seams (test-only, read only here): `HALO_COPILOT_AUTHORITY` (the Entra host, default
https://login.microsoftonline.com), `HALO_COPILOT_WORKIQ_URL` (the A2A endpoint), `HALO_COPILOT_GRAPH_URL` (the Graph
root) -- the mock server (tests/helpers/mock_copilot.py) stands in for all three.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

APIS = ("workiq", "graph-beta")
DEFAULT_API = "workiq"
REF = "cp:work"
SECRET_ENV = "HALO_SECRET_COPILOT_REFRESH"
AUTHORITY = "https://login.microsoftonline.com"
WORKIQ_URL = "https://workiq.svc.cloud.microsoft/a2a/"
GRAPH_URL = "https://graph.microsoft.com"
OIDC = ("offline_access", "openid", "profile")

# Graph /beta Copilot Chat API: every one of these delegated permissions (learn.microsoft.com "Microsoft 365
# Copilot Chat API overview", permissions section) plus the OIDC ones for a refresh token and the account's name.
GRAPH_SCOPES = ("Sites.Read.All", "Mail.Read", "People.Read.All", "OnlineMeetingTranscript.Read.All", "Chat.Read",
                "ChannelMessage.Read.All", "ExternalItem.Read.All") + OIDC

# Work IQ API: the exact delegated scope name is the one fact the research left open (plans/ROADMAP.md 3.3.17.0).
# Check learn.microsoft.com "Work IQ API -- authentication and permissions" before relying on it; until then the
# resource's `.default` asks for whatever delegated permission the app registration lists for the resource.
# `copilot.scopes` replaces it when the tenant names it differently.
WORKIQ_SCOPE = "https://workiq.svc.cloud.microsoft/.default"
WORKIQ_SCOPES = (WORKIQ_SCOPE,) + OIDC


@dataclass(frozen=True)
class CopilotConfig:
    tenant: str = ""
    client_id: str = ""
    api: str = DEFAULT_API
    web: bool = True
    timezone: str = ""
    scopes: tuple = ()

    @property
    def configured(self) -> bool:
        return bool(self.tenant and self.client_id)

    def scope_list(self, api: Optional[str] = None) -> tuple:
        """The scopes asked for: `copilot.scopes` when set, else the api's own."""
        if self.scopes:
            return self.scopes
        return WORKIQ_SCOPES if (api or self.api) == "workiq" else GRAPH_SCOPES

    def consent_scopes(self, api: Optional[str] = None) -> list:
        """The scopes an admin consents to (the OIDC ones need no admin)."""
        return [s for s in self.scope_list(api) if s not in OIDC]


def _get(key: str, default=None):
    try:
        from halo_harness.theme import get_config_value
        return get_config_value(key, default)
    except Exception:
        return default


def system_timezone(env: Optional[dict] = None) -> str:
    """This machine's IANA zone: TZ, /etc/timezone, the /etc/localtime link; '' when none says."""
    env = os.environ if env is None else env
    tz = str(env.get("TZ") or "").strip().lstrip(":")
    if "/" in tz:
        return tz
    try:
        text = Path("/etc/timezone").read_text(encoding="utf-8").strip()
        if "/" in text:
            return text
    except OSError:
        pass
    try:
        target = os.path.realpath("/etc/localtime")
        if "zoneinfo/" in target:
            return target.split("zoneinfo/", 1)[1]
    except OSError:
        pass
    return ""


def load(env: Optional[dict] = None) -> CopilotConfig:
    """The `copilot.*` keys as one value; a bad value falls back to its default."""
    api = str(_get("copilot.api", DEFAULT_API) or DEFAULT_API).strip().lower()
    web = _get("copilot.web", True)
    raw_scopes = _get("copilot.scopes", None)
    if isinstance(raw_scopes, (list, tuple)):
        scopes = tuple(str(s).strip() for s in raw_scopes if str(s).strip())
    else:
        scopes = tuple(str(raw_scopes or "").split())
    tz = str(_get("copilot.timezone", "") or "").strip() or system_timezone(env) or "UTC"
    return CopilotConfig(tenant=str(_get("copilot.tenant", "") or "").strip(),
                         client_id=str(_get("copilot.client_id", "") or "").strip(),
                         api=api if api in APIS else DEFAULT_API, web=web is not False, timezone=tz, scopes=scopes)


def authority(tenant: str) -> str:
    """`<host>/<tenant>/oauth2/v2.0` (the test seam may move the host)."""
    host = (os.environ.get("HALO_COPILOT_AUTHORITY") or AUTHORITY).rstrip("/")
    return f"{host}/{tenant}/oauth2/v2.0"


def workiq_url() -> str:
    return os.environ.get("HALO_COPILOT_WORKIQ_URL") or WORKIQ_URL


def graph_url() -> str:
    return (os.environ.get("HALO_COPILOT_GRAPH_URL") or GRAPH_URL).rstrip("/")


def state_dir() -> Path:
    from halo_harness.config.paths import bridge_home
    return bridge_home() / "copilot"
