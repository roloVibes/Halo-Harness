"""halo_harness.studio.owner_proof -- the two values Studio derives from its launch token (Halo 3.3.14.0 R1, the
review's #4 and #5; docs/STUDIO-shell.md "The owner's page and a pack's key").

**The owner proof (#4).** A pack's page (a bundle panel, a section's view) runs in the shell's own page, so the
launch token alone cannot tell the owner's clicks from a pack's script. The shell holds one more value: a per-launch
salt the served index.html carries as `data-owner-salt` on <html>, which the shell reads once and removes before any
pack module loads (studio/ui/src/lib/owner.ts). Its own requests send `X-Halo-Owner: <hex HMAC-SHA256(token, salt)>`;
the routes that change what runs here (`OWNER_ROUTES`: a pack's grant, enable, disable, install, sources, update,
rollback, remove, service, settings and config; the bundles; Setup and Settings; a session started or typed into;
3.4.1.0 R4: an attention row answered, from Attention or the glance)
answer 403 `NEEDS_OWNER` without it. The salt goes only into a page the browser navigates to (`Sec-Fetch-Dest:
document`, or a client that sends none): a script's `fetch("/")` or a frame of `/` gets the page without it.

**A pack's key (#5).** What a page embeds where no header can go (an iframe, an image, a video, a module import)
takes `?k=<hex HMAC-SHA256(token, "pack-raw:" + pack id)>`: a GET of that pack's own routes (`/api/packs/<id>/...`)
or its own files (`/api/pack/<id>/file/...`), never a write, another pack's path or a core route. The launch token
is not taken from `?t=` there any more. `GET pack/registry` gives the shell each running pack's key.
"""

from __future__ import annotations

import hashlib
import hmac
import re
import secrets
from urllib.parse import parse_qs, unquote, urlsplit

HEADER = "X-Halo-Owner"
NEEDS_OWNER = ("this needs the owner's own page: Studio's Pack Manager, Setup, Settings, Session, Attention or the glance sends it "
               "(a pack's page does not)")
_ID = r"[a-z][a-z0-9-]*"
OWNER_ROUTES = tuple(re.compile(p) for p in (
    r"^pack/(install|sources)$",
    rf"^pack/{_ID}/(enable|grant|disable|update|rollback|remove|service|settings|config)$",
    r"^pack/bundle/",
    r"^(setup|settings|sessions)(/|$)",
    r"^fleet/attention/answer$",  # 3.4.1.0 R4: an answer lets a tool run (Attention, the glance; studio/fleet_answer.py)
))
_RAW = re.compile(rf"^/api/(?:packs/(?P<routes>{_ID})/|pack/(?P<files>{_ID})/file/)")
_SECRET_QUERY = re.compile(r"([?&](?:t|k)=)[^&\s\"]*")


def _hmac(token: str, message: str) -> str:
    return hmac.new(str(token).encode("utf-8"), message.encode("utf-8"), hashlib.sha256).hexdigest()


def new_salt() -> str:
    return secrets.token_urlsafe(18)


def salt(server) -> str:
    """This launch's salt (made with the server, `_Server.owner_salt`)."""
    got = getattr(server, "owner_salt", "")
    if not got:
        got = server.owner_salt = new_salt()
    return got


def proof(token: str, salt_value: str) -> str:
    """The owner header's value: HMAC-SHA256 keyed by the launch token over the salt, as hex."""
    return _hmac(token, salt_value)


def header_for(server) -> str:
    """The value the shell sends as `X-Halo-Owner` for this server (a test's client sends it the same way)."""
    return proof(server.token, salt(server))


def needs_owner(method: str, path: str) -> bool:
    """A write to one of `OWNER_ROUTES` (`path` is the unquoted path after /api/)."""
    return method not in ("GET", "HEAD") and any(p.match(path) for p in OWNER_ROUTES)


def owner_ok(handler) -> bool:
    got = handler.headers.get(HEADER) or ""
    return bool(got) and hmac.compare_digest(got, header_for(handler.server))


def raw_key(token: str, pack_id: str) -> str:
    """The pack's key: what `?k=` carries on a GET of its own routes and files."""
    return _hmac(token, "pack-raw:" + pack_id)


def raw_key_ok(url: str, token: str, method: str) -> bool:
    """`?k=` is that pack's key, on a GET of its own `/api/packs/<id>/...` or `/api/pack/<id>/file/...`."""
    if method not in ("GET", "HEAD"):
        return False
    parts = urlsplit(url)
    m = _RAW.match(unquote(parts.path))
    presented = (parse_qs(parts.query).get("k") or [""])[-1]
    return bool(m and presented) and hmac.compare_digest(presented, raw_key(token, m["routes"] or m["files"]))


def owner_attr(page: bytes, handler) -> bytes:
    """index.html with `data-owner-salt` on <html> for a navigation (a fetch or a frame of the page gets none)."""
    dest = (handler.headers.get("Sec-Fetch-Dest") or "document").strip().lower()
    if dest != "document" or b"<html" not in page:
        return page
    return page.replace(b"<html", b'<html data-owner-salt="' + salt(handler.server).encode("ascii") + b'"', 1)


def redact(line: str) -> str:
    """An access-log line with the value of `t=` and `k=` replaced by `...` (#33)."""
    return _SECRET_QUERY.sub(r"\1...", line)
