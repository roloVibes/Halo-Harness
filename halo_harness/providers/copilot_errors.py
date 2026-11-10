"""halo_harness.providers.copilot_errors -- the Copilot door's failures in plain words, each with its one next step
(Halo 3.3.17.0 R1; docs/PROVIDERS-copilot.md "Troubleshooting" lists every line).

    not signed in        Copilot: not signed in -- run `halo copilot signin`.
    expired              Copilot: the sign-in has expired and the refresh failed (<why>) -- run `halo copilot signin`.
    consent              Copilot: the tenant has not consented to <scopes> -- an admin must grant consent ...
    licence              Copilot: this account has no Microsoft 365 Copilot licence -- ...
    billing              Copilot: Work IQ needs consumptive billing (Copilot Credits) enabled -- ...
    throttled            Copilot: throttled (429) again after waiting <n> s -- try again in a minute.
    offline              Copilot: offline mode: not connecting to <host> (...)   (copilot_net.request)
"""

from __future__ import annotations

from halo_harness.providers.copilot_net import CopilotError, Reply, error_text

SIGNIN = "run `halo copilot signin`"
REGISTER = "docs/PROVIDERS-copilot.md \"Register the app\""
_CONSENT_WORDS = ("aadsts65001", "invalid_scope", "aadsts70011", "consent", "aadsts650057")
_LICENCE_WORDS = ("licen", "not entitled", "no copilot")
_BILLING_WORDS = ("billing", "consumptive", "credits", "payment")


def not_signed_in() -> CopilotError:
    return CopilotError(f"Copilot: not signed in -- {SIGNIN}.", "signin")


def not_set_up() -> CopilotError:
    return CopilotError("Copilot: not set up -- halo config set copilot.tenant <tenant> and copilot.client_id <app id> "
                        f"(see {REGISTER}).", "setup")


def consent(scopes, why: str = "") -> CopilotError:
    names = " ".join(scopes) if not isinstance(scopes, str) else scopes
    tail = f" ({why})" if why else ""
    return CopilotError(f"Copilot: the tenant has not consented to {names}{tail} -- an admin must grant consent to "
                        f"the app for these scopes ({REGISTER}).", "consent")


def expired(why: str) -> CopilotError:
    return CopilotError(f"Copilot: the sign-in has expired and the refresh failed ({why}) -- {SIGNIN}.", "expired")


def _has(text: str, words) -> bool:
    low = text.lower()
    return any(w in low for w in words)


def token_error(reply: Reply, scopes, *, refreshing: bool) -> CopilotError:
    """A token endpoint's refusal: consent / scope first, then an expired grant, then the words it gave."""
    why = error_text(reply) or f"HTTP {reply.status}"
    code = str(reply.data.get("error") or "") if isinstance(reply.data, dict) else ""
    if _has(why + " " + code, _CONSENT_WORDS):
        return consent(scopes, why.split(":", 1)[0] if why.upper().startswith("AADSTS") else code or "")
    if refreshing:
        return expired(why)
    return CopilotError(f"Copilot: the sign-in failed: {why} -- {SIGNIN} again.", "signin", reply.status)


def api_error(reply: Reply, api: str, scopes, *, waited: float = 0.0) -> CopilotError:
    """The Work IQ / Graph answer's failure, by status and the words it carried."""
    why = error_text(reply) or f"HTTP {reply.status}"
    status = reply.status
    if status == 429:
        return CopilotError(f"Copilot: throttled (429) again after waiting {waited:.0f} s -- try again in a minute.",
                            "throttled", status)
    if status == 402 or _has(why, _BILLING_WORDS):
        return CopilotError("Copilot: Work IQ needs consumptive billing (Copilot Credits) enabled for the tenant -- "
                            "an admin turns it on in the Microsoft 365 admin center, or set copilot.api graph-beta.",
                            "billing", status)
    if status in (401, 403) and _has(why, _LICENCE_WORDS):
        return CopilotError("Copilot: this account has no Microsoft 365 Copilot licence -- an admin assigns one "
                            "(the graph-beta door needs it; copilot.api workiq bills Copilot Credits instead).",
                            "licence", status)
    if status in (401, 403):
        return consent(scopes, f"{api} answered {status}: {why}")
    return CopilotError(f"Copilot: {api} answered {status}: {why}", "answer", status)
