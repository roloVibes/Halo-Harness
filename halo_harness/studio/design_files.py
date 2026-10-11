"""halo_harness.studio.design_files -- the raw artboard file route (Halo
3.0.1.0 round D3): `GET /design-files/<slug>/<artboard>/<file>` serves a
design artboard's own files (a prototype's index.html with its inline CSS and
JS, a render, `v<n>/<file>` for the version slider) to the page's sandboxed
iframes. It is not a JSON route and does not carry Studio's CSP: the page
embeds it as `<iframe sandbox="allow-scripts">` (no allow-same-origin), so
the prototype runs but cannot reach Studio's API or token. The path is
confined to design_root/<slug>/artboards/<artboard>/.
"""

from __future__ import annotations

import mimetypes
import re
from pathlib import Path
from typing import Optional
from urllib.parse import unquote

from halo_harness.design.store import design_root

PREFIX = "/design-files/"
CSP = "default-src 'self' 'unsafe-inline' data: blob:"
_NAME = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]*$")

EDIT_SCRIPT = """<!--halo-edit--><script id="halo-edit-script">(function(){
document.body.contentEditable="true";document.body.style.outline="none";
function send(){var c=document.documentElement.cloneNode(true);var s=c.querySelector("#halo-edit-script");if(s)s.remove();
c.querySelector("body").removeAttribute("contenteditable");
parent.postMessage({type:"halo-design-edit",html:"<!doctype html>\\n"+c.outerHTML},"*");}
document.addEventListener("keydown",function(e){if((e.ctrlKey||e.metaKey)&&e.key.toLowerCase()==="s"){e.preventDefault();send();}});
document.body.addEventListener("blur",send,true);})();</script><!--/halo-edit-->"""


def resolve(state_dir, url_path: str) -> Optional[Path]:
    """The file under one artboard folder that `url_path` names, or None."""
    rel = unquote(url_path)[len(PREFIX):]
    parts = rel.split("/")
    if len(parts) < 3 or not all(_NAME.match(p) for p in parts):
        return None
    base = (design_root(state_dir) / parts[0] / "artboards" / parts[1]).resolve()
    target = (base / "/".join(parts[2:])).resolve()
    return target if base in target.parents and target.is_file() else None


def read(state_dir, url_path: str, query: dict):
    """(status, body, content type) for one raw file request."""
    target = resolve(state_dir, url_path)
    if target is None:
        return 404, b'{"error": "not found"}', "application/json"
    data = target.read_bytes()
    ctype = mimetypes.guess_type(str(target))[0] or "application/octet-stream"
    if target.suffix.lower() in (".html", ".htm"):
        ctype = "text/html; charset=utf-8"
        if query.get("edit") == "1" and target.parent.parent.name == "artboards":  # the current version only
            text = data.decode("utf-8", "replace")
            i = text.lower().rfind("</body>")
            data = (text[:i] + EDIT_SCRIPT + text[i:] if i >= 0 else text + EDIT_SCRIPT).encode("utf-8")
    elif ctype.startswith("text/") or ctype in ("application/javascript", "application/json", "image/svg+xml"):
        ctype += "; charset=utf-8"
    return 200, data, ctype
