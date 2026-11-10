"""halo_harness.copilot_cli -- `halo copilot`: sign in to your work's Copilot and ask it (Halo 3.3.17.0 R1;
docs/COMMANDS-copilot.md, docs/PROVIDERS-copilot.md).

    halo copilot                      the same as `halo copilot status`
    halo copilot signin [--device]    the browser sign-in (PKCE + a one-shot loopback); --device: a code to type instead
    halo copilot signout              forget the refresh token, the access token and the account record
    halo copilot status               signed in as whom, the tenant, the api, until when; the scopes to consent to
    halo copilot ask "<prompt>" [--file URL]... [--no-web] [--api workiq|graph-beta] [--json]
                                      the answer, then its citations numbered
"""

from __future__ import annotations

import argparse
import json
import sys
from typing import Optional

VERBS = ("signin", "signout", "status", "ask")


def status_lines(cfg=None) -> list:
    """What `status`, Studio's card and the doctor say, one fact per line (no network)."""
    from halo_harness.providers import copilot_account as A
    from halo_harness.providers.copilot_config import load
    from halo_harness.providers.copilot_tokens import refresh_token
    cfg = cfg or load()
    if not cfg.configured:
        return ["Copilot: not set up -- halo config set copilot.tenant <tenant> and copilot.client_id <app id> "
                "(docs/PROVIDERS-copilot.md \"Register the app\")."]
    acct = A.load()
    lines = [f"tenant: {cfg.tenant} · app: {cfg.client_id} · api: {cfg.api} · web: {'on' if cfg.web else 'off'} · "
             f"time zone: {cfg.timezone}"]
    if not refresh_token():
        lines.insert(0, "Copilot: not signed in -- run `halo copilot signin`.")
    else:
        who = acct.get("username") or acct.get("name") or "an account whose name the sign-in did not give"
        until = A.when(acct.get("access_expires_at"))
        lines.insert(0, f"Copilot: signed in as {who}" + (f"; the last access token is valid until {until}" if until else ""))
        err = acct.get("last_error") if isinstance(acct.get("last_error"), dict) else None
        if err and err.get("line"):
            lines.append(f"last problem: {err['line']}")
    lines.append("scopes an admin consents to: " + " ".join(cfg.consent_scopes()))
    return lines


def _parser(verb: str) -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog=f"halo copilot {verb}")
    if verb == "signin":
        p.description = "Sign in in the browser (or with a device code) to your work's Copilot."
        p.add_argument("--device", action="store_true", help="type a code on another device instead of the browser")
    elif verb == "signout":
        p.description = "Forget the refresh token, the access token and the account record."
    elif verb == "status":
        p.description = "Signed in as whom, the tenant, the api, until when."
        p.add_argument("--json", action="store_true", help="the facts as JSON")
    else:
        p.description = "Ask your work's Copilot; prints the answer, then its citations numbered."
        p.add_argument("prompt", help="what to ask")
        p.add_argument("--file", action="append", default=[], metavar="URL", help="a OneDrive or SharePoint file's URL (repeatable)")
        p.add_argument("--no-web", action="store_true", help="answer from your work data only, no web grounding")
        p.add_argument("--api", choices=("workiq", "graph-beta"), help="which door (default: copilot.api)")
        p.add_argument("--json", action="store_true", help="the answer as JSON: text, citations, sensitivity, conversation, api")
    return p


def cmd_copilot(argv: Optional[list] = None) -> int:
    argv = list(argv or [])
    if argv and argv[0] in ("-h", "--help"):
        print(__doc__.split("\n\n", 1)[1].rstrip())
        return 0
    verb = argv[0] if argv and argv[0] in VERBS else "status"
    rest = argv[1:] if argv and argv[0] in VERBS else argv
    if argv and argv[0] not in VERBS and not argv[0].startswith("-"):
        print(f"halo copilot: no verb {argv[0]!r} (one of {', '.join(VERBS)})", file=sys.stderr)
        return 2
    args = _parser(verb).parse_args(rest)
    from halo_harness.providers.copilot_net import CopilotError
    try:
        return globals()[f"_do_{verb}"](args)
    except CopilotError as e:
        print(e.line, file=sys.stderr)
        return 1


def _do_status(args) -> int:
    if getattr(args, "json", False):
        from halo_harness.providers import copilot_account as A
        from halo_harness.providers.copilot_config import load
        from halo_harness.providers.copilot_tokens import refresh_token
        cfg = load()
        acct = A.load()
        print(json.dumps({"configured": cfg.configured, "signed_in": bool(cfg.configured and refresh_token()),
                          "tenant": cfg.tenant, "client_id": cfg.client_id, "api": cfg.api, "web": cfg.web,
                          "timezone": cfg.timezone, "username": acct.get("username") or "",
                          "access_expires_at": acct.get("access_expires_at"), "last_error": acct.get("last_error"),
                          "consent_scopes": cfg.consent_scopes()}, indent=2))
        return 0
    for line in status_lines():
        print(line)
    return 0


def _do_signin(args) -> int:
    from halo_harness.providers.copilot_auth import signin
    from halo_harness.providers.copilot_config import load
    acct = signin(load(), device=bool(args.device))
    who = acct.get("username") or acct.get("name") or "your account"
    print(f"Copilot: signed in as {who} (tenant {acct.get('tenant')}, api {acct.get('api')}). "
          "The refresh token is in the env file; `halo copilot signout` removes it.")
    return 0


def _do_signout(args) -> int:
    from halo_harness.providers.copilot_tokens import signout
    print("Copilot: signed out -- " + "; ".join(signout()) + ".")
    return 0


def _do_ask(args) -> int:
    from halo_harness.providers.copilot import ask, format_answer
    answer = ask(args.prompt, files=args.file, web=False if args.no_web else None, api=args.api)
    print(json.dumps(answer, indent=2, ensure_ascii=False) if args.json else format_answer(answer))
    return 0
