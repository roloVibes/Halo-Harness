"""halo_harness.studio.owner_proof -- the two values Studio derives from its launch token (Halo 3.3.14.0 R1, the
review's #4 and #5; 3.4.1.2, SERVERS-1/2/4 and PACKS-2; docs/STUDIO-shell.md "The owner's page and a pack's key").

**The owner proof.** A pack's page (a bundle panel, a section's view) runs in the shell's own page with Studio's token,
so the token alone cannot tell the owner's clicks from a pack's script. The shell holds one more value: a per-launch
salt the served index.html carries as `data-owner-salt` on <html>, which the shell reads once and removes before any
pack module loads (studio/ui/src/lib/owner.ts). Its own requests send `X-Halo-Owner: <hex HMAC-SHA256(token, salt)>`.
3.4.1.2: EVERY write (any method but GET and HEAD) answers 403 `NEEDS_OWNER` without it, except a pack page's own
routes (`PACK_PAGE`, the set packlib/scoped.ts `allowed` names, with the pack id taken from the path and checked to be
a running pack); the handlers that end in a control-socket call or change what runs also check it themselves
(`owner_only`), so a route that reaches them another way is refused there too. The salt goes only into a page the
browser marks as a navigation the person made (`user_navigation`: `Sec-Fetch-Site: none`, `Sec-Fetch-Dest:
document`, `Sec-Fetch-Mode: navigate`): the address bar, a bookmark, the browser's reload, `halo studio` opening the
browser. A script-opened window, a frame, a fetch, a link or a cross-site bounce gets the page without it, and so does
a browser that sends no Fetch Metadata; such a page can look but not change things, and says how to open Studio. A
CLI on this machine reads the salt from the private studio.json (`cli_headers`).

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
NEEDS_OWNER = ("this needs the owner's own page: open Studio yourself (run `halo studio`, or paste its address into the "
               "address bar) and do it there; a pack's page, or a tab a page or a script opened, can look but not change things")
_ID = r"[a-z][a-z0-9-]*"
# 3.4.1.2 (SERVERS-2): the writes a pack's page may send without the proof, packlib/scoped.ts `allowed` (method, path)
PACK_PAGE = ((None, re.compile(rf"^packs/(?P<id>{_ID})/")),
             ("POST", re.compile(rf"^pack/(?P<id>{_ID})/(publish|attention)$")),
             ("PUT", re.compile(rf"^layout/(?P<id>{_ID}):[^/]+$")))
READS = ("GET", "HEAD")
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


def pack_page_id(method: str, path: str):
    """The pack id when `method path` (unquoted, after /api/) is one of a pack page's own writes, else None."""
    for verb, pattern in PACK_PAGE:
        m = pattern.match(path)
        if m and (verb is None or verb == method):
            return m["id"]
    return None


def needs_owner(method: str, path: str) -> bool:
    """3.4.1.2: any write that is not a pack page's own route (`path` is the unquoted path after /api/)."""
    return method not in READS and pack_page_id(method, path) is None


def pack_runs(pack_id: str, cwd, state_dir) -> bool:
    """The id a pack-page route names is a pack that runs here (a stale or made-up id is not a pack's route)."""
    try:
        from halo_harness.packs.studio_registry import active_pack
        return active_pack(pack_id, cwd=cwd, state_dir=state_dir) is not None
    except Exception:
        return False


def refused(handler, method: str, path: str) -> bool:
    """The router's check (server.py `_api`): a write without the proof that is not a running pack's own route; on a
    clip's filming Studio (`only_gets`, live/replay_clip.py) anything but those GETs."""
    only = getattr(handler.server, "only_gets", None)
    if only is not None:
        return method not in READS or not any(re.match(p, path) for p in only)
    if method in READS or owner_ok(handler):
        return False
    pid = pack_page_id(method, path)
    return pid is None or not pack_runs(pid, handler.server.cwd, handler.server.state_dir)


def owner_ok(handler) -> bool:
    got = handler.headers.get(HEADER) or ""
    return bool(got) and hmac.compare_digest(got, header_for(handler.server))


def owner_only(fn):
    """A handler that ends in a control-socket call or changes what runs: 403 unless the request carried the proof
    (`Request.owner`, set by the server from the header; False for a request made any other way)."""
    def gated(req, *a, **kw):
        if not getattr(req, "owner", False):
            return 403, {"error": NEEDS_OWNER}
        return fn(req, *a, **kw)
    gated.__name__, gated.__doc__, gated.owner_only = fn.__name__, fn.__doc__, True
    return gated


def cli_headers(info: dict) -> dict:
    """A CLI's headers for the running Studio (`halo studio --stop`, `--edit`, `halo fleet`): its token from the
    private studio.json, and the owner proof made from the salt the same file names."""
    token = str((info or {}).get("token") or "")
    heads = {"Authorization": "Bearer " + token, "Content-Type": "application/json"}
    if token and (info or {}).get("owner_salt"):
        heads[HEADER] = proof(token, str(info["owner_salt"]))
    return heads


def raw_key(token: str, pack_id: str) -> str:
    """The pack's key: what `?k=` carries on a GET of its own routes and files."""
    return _hmac(token, "pack-raw:" + pack_id)


def raw_key_ok(url: str, token: str, method: str) -> bool:
    """`?k=` is that pack's key, on a GET of its own `/api/packs/<id>/...` or `/api/pack/<id>/file/...`."""
    if method not in READS:
        return False
    parts = urlsplit(url)
    m = _RAW.match(unquote(parts.path))
    presented = (parse_qs(parts.query).get("k") or [""])[-1]
    return bool(m and presented) and hmac.compare_digest(presented, raw_key(token, m["routes"] or m["files"]))


def user_navigation(handler) -> bool:
    """3.4.1.2 (SERVERS-4): the browser marks this request a navigation the person made: the address bar, a bookmark,
    a program opening the browser (`Sec-Fetch-Site: none`), or the person's reload of a Studio page (Chrome marks a
    reload of a page whose address the page itself tidied with history.replaceState `same-origin`, with `Sec-Fetch-User:
    ?1` and `Cache-Control: max-age=0`; a reload a script starts in another window carries no `?1`, and a reload of the
    script's own window starts a fresh shell that takes the salt before any pack loads). A window a script opened, a
    frame, a fetch, a link, a cross-site bounce, or a browser that sends no Fetch Metadata, is not. The page also says
    `Cross-Origin-Opener-Policy: noopener-allow-popups` (server.py), so a window a script opens is cut off from it."""
    get = lambda name: (handler.headers.get(name) or "").strip().lower()  # noqa: E731
    if get("Sec-Fetch-Dest") != "document" or get("Sec-Fetch-Mode") != "navigate":
        return False
    if get("Sec-Fetch-Site") == "none":
        return True
    reload = "max-age=0" in get("Cache-Control") or "no-cache" in get("Cache-Control")
    return get("Sec-Fetch-Site") == "same-origin" and get("Sec-Fetch-User") == "?1" and reload


def owner_attr(page: bytes, handler) -> bytes:
    """index.html with `data-owner-salt` on <html> for a navigation the person made (`user_navigation`), else as is."""
    if not user_navigation(handler) or b"<html" not in page:
        return page
    return page.replace(b"<html", b'<html data-owner-salt="' + salt(handler.server).encode("ascii") + b'"', 1)


def redact(line: str) -> str:
    """An access-log line with the value of `t=` and `k=` replaced by `...` (#33)."""
    return _SECRET_QUERY.sub(r"\1...", line)
