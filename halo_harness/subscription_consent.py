"""halo_harness.subscription_consent -- Halo 2.0.7 fix pass round 7b: the
`cc:`/`cx:` subscription routes are OFF until the user types the exact
acceptance phrase, once per machine.

Owner's decision (rolo, 2026-10-09 ~23:10): "if Halo discovers subscription
creds that might lead to a ban, that feature should be off by default and
then a big alert and acceptance needs to happen before that even turns on."
This is a consent gate the owner chose for his users -- it is NOT safety or
refusal logic, and the words used everywhere are "accepted" / "not
accepted" / "available after acceptance", never "safety"/"refuse"/
"blocked". The config default is off; no migration (fresh install or
upgrade) ever flips it on by itself.

Stored at `~/.halo/config.json`'s own `"subscription_routes"` key:
`{"accepted": bool, "accepted_at": "<iso8601>"|None, "accepted_version":
int|None, "routes": ["cc", "cx"]}`. `NOTICE_VERSION` below is bumped
whenever the notice's own wording changes in a way that matters -- a
machine that accepted an OLDER version is treated as not-accepted again
(`is_accepted`) until it accepts the current text.
"""

from __future__ import annotations

import time
from typing import Optional

from halo_harness.providers.routing import InvalidModelError

NOTICE_VERSION = 1

CONFIG_KEY = "subscription_routes"

GATED_ROUTES = ("cc", "cx")

ACCEPT_PHRASE = "I accept"

NOTICE_TITLE = "Your subscription, a third-party harness"

# The owner's own facts (brief: "Facts to state in the notice and the
# docs"), five short paragraphs, verbatim in meaning everywhere this notice
# appears (the TUI screen, the CLI form, and docs/MODELS.md).
NOTICE_PARAGRAPHS = (
    "Halo never reads the Claude Code OAuth token (~/.claude/.credentials.json) "
    "or Codex's own stored credentials.",
    "The cc: route drives the official `claude` binary in its documented headless "
    "mode; the cx: route drives the official `codex` binary the same way.",
    "Both routes still use your own personal subscription, through a third-party "
    "harness that is not the provider's own product.",
    "The provider's own terms govern your account -- not Halo's.",
    "There have been public reports of account restrictions for tools that use "
    "subscription tokens outside the provider's own products. Halo makes no claim "
    "about any individual case.",
)

PROVIDER_TERMS = (
    ("Anthropic Consumer Terms of Service", "https://www.anthropic.com/legal/consumer-terms"),
    ("OpenAI Terms of Use", "https://openai.com/policies/row-terms-of-use/"),
)

RESPONSIBILITY_SENTENCE = "Your account, and what happens to it, is your own responsibility."

ACCEPTANCE_SENTENCE = f'Type "{ACCEPT_PHRASE}" (exact) and Enter to accept. Escape or anything else leaves the routes off.'


def notice_text() -> str:
    """The exact words shown by both the TUI screen and the plain-text CLI
    form -- one assembled string so the two surfaces can never drift."""
    lines = [NOTICE_TITLE, ""]
    lines.extend(NOTICE_PARAGRAPHS)
    lines.append("")
    for title, url in PROVIDER_TERMS:
        lines.append(f"{title}: {url}")
    lines.append("")
    lines.append(RESPONSIBILITY_SENTENCE)
    lines.append("")
    lines.append(ACCEPTANCE_SENTENCE)
    return "\n".join(lines)


class SubscriptionConsentRequiredError(InvalidModelError):
    """Raised by `model.parse_model_ref` for a `cc:`/`cx:` ref while the
    subscription routes are off -- a SEPARATE exception type (not just the
    plain `is_provider_disabled_message` wording) so a caller that wants to
    open the notice instead of showing a plain error (the TUI's `/model`)
    can tell this case apart from an ordinary disabled/unresolvable ref."""

    def __init__(self, route: str):
        self.route = route
        super().__init__(gate_message(route))


def _default_state() -> dict:
    return {"accepted": False, "accepted_at": None, "accepted_version": None, "routes": list(GATED_ROUTES)}


def consent_state() -> dict:
    """The raw `subscription_routes` block -- the default (not accepted)
    shape when the key is missing, malformed, or this is a fresh/upgraded
    install that has never written it (no migration ever flips this on)."""
    from halo_harness.theme import get_config_value
    block = get_config_value(CONFIG_KEY, default=None)
    if not isinstance(block, dict):
        return _default_state()
    state = _default_state()
    state.update({k: block.get(k, state[k]) for k in state})
    return state


def is_accepted() -> bool:
    """True only when `accepted` is True AND the acceptance was recorded
    against the CURRENT `NOTICE_VERSION` -- a changed notice (a version
    bump) asks again, exactly like an unaccepted machine."""
    state = consent_state()
    return bool(state.get("accepted")) and state.get("accepted_version") == NOTICE_VERSION


def record_acceptance(*, now: Optional[str] = None) -> dict:
    """Writes `accepted: true` with the current date and `NOTICE_VERSION`.
    `now` (tests only) overrides the timestamp; real callers always get a
    fresh UTC ISO-8601 stamp."""
    from halo_harness.theme import set_config_value
    stamp = now if now is not None else time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    state = {"accepted": True, "accepted_at": stamp, "accepted_version": NOTICE_VERSION, "routes": list(GATED_ROUTES)}
    set_config_value(CONFIG_KEY, state)
    return state


def revoke() -> dict:
    """Returns the routes to off -- per-machine, same as acceptance. The
    prior `accepted_at`/`accepted_version` are kept as a plain historical
    record; only `accepted` (what `is_accepted()` actually checks) flips."""
    from halo_harness.theme import set_config_value
    state = consent_state()
    state["accepted"] = False
    set_config_value(CONFIG_KEY, state)
    return state


def gate_message(route: str) -> str:
    label = "cc:" if route == "cc" else "cx:" if route == "cx" else f"{route}:"
    return (f"{label} is available after acceptance -- run `halo subscriptions accept` "
            f"(or /subscriptions in the TUI) to review \"{NOTICE_TITLE}\" and accept it once per machine")


def refuse_if_not_accepted(route: str) -> None:
    """Raises `SubscriptionConsentRequiredError` for a gated route (`cc`/
    `cx`) while the routes are off. A no-op for any other route, and a
    no-op once accepted -- never consulted for `ant:`/`oai:`/anything else
    ("nothing else changes for API-key routes", the brief's own words)."""
    if route in GATED_ROUTES and not is_accepted():
        raise SubscriptionConsentRequiredError(route)


def status_line() -> str:
    """`halo doctor`/`/providers`'s own one-line summary: "subscription
    routes: off (not accepted)" or "subscription routes: on (accepted
    <date>, v<version>)"."""
    state = consent_state()
    if is_accepted():
        date = (state.get("accepted_at") or "")[:10]
        return f"subscription routes: on (accepted {date}, v{state.get('accepted_version')})"
    return "subscription routes: off (not accepted)"


def read_typed_acceptance(prompt=input) -> bool:
    """`halo subscriptions accept`'s own stdin read -- True only on an
    exact `"I accept"` line. Non-interactive stdin (no TTY, nothing to
    read, piped from /dev/null) raises `EOFError`/`OSError` on the first
    read, caught here and treated as "did not accept" -- it must never
    accept on behalf of a script or a CI run that supplied no input at
    all."""
    try:
        typed = prompt("Type \"I accept\" and press Enter to accept, or anything else to decline: ")
    except (EOFError, OSError):
        return False
    return (typed or "").strip() == ACCEPT_PHRASE
