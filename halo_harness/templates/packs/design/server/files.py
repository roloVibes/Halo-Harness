"""The design pack's server/files.py (was halo_harness.studio.design_files) -- the raw artboard file route (Halo
3.0.1.0 round D3; 3.3.13.0 R2: the pack's `GET _files/<slug>/<artboard>/<file>`, under /api/packs/design/design/,
and this module's CSP passed through by Studio; it was `/design-files/...` in the core). An iframe sends no header,
so the URL carries the design pack's key in `?k=` (3.3.14.0 R1, #5: a GET-only key Studio derives from its token
for this pack's own routes, studio/owner_proof.py): a prototype that reads its own address finds that key, never
Studio's token, and the key opens nothing but GETs of the design pack's routes. `_files/<slug>/<artboard>/<file>`
serves a design artboard's own files (a prototype's index.html with its inline CSS and JS, a render, `v<n>/<file>`
for the version slider) to the page's sandboxed iframes. It is not a JSON route and does not carry Studio's CSP:
the page embeds it as `<iframe sandbox="allow-scripts">` (no allow-same-origin), so the prototype runs in an opaque
origin and cannot reach Studio's API; the server adds a `sandbox allow-scripts` CSP directive to every response
whose type is not an image, a video, an audio file, a PDF or a font (`csp_for`, 3.3.14.0 R1, #6: HTML, SVG, XHTML,
XML, XSL, JS, JSON, text and any type it does not know), so the same holds when a file is framed without the
attribute or opened on its own. The path is confined to design_root/<slug>/artboards/<artboard>/
(an artboard folder that is a symlink is not served). 3.0.7.0 R3:
`_files/<slug>/_assets/<name>` is a file of the project's assets/
folder (the Assets panel's Download; `_assets` is never an artboard id).
3.0.7.0 R3b: `?edit=pick` on the current index.html carries the double-click
picker of the React Design section (studio/design_api_edit.py).
"""

from __future__ import annotations

import mimetypes
import re
from pathlib import Path
from typing import Optional
from urllib.parse import unquote

from .store import design_root

PREFIX = "_files/"  # the route's path, after the pack's prefix
CSP = "default-src 'self' 'unsafe-inline' data: blob:"
INERT = ("image/", "video/", "audio/", "font/")  # 3.3.14.0 R1 (#6): no script in these (SVG aside); all else sandboxed
INERT_TYPES = ("application/pdf", "application/font-woff", "application/font-sfnt", "application/vnd.ms-fontobject",
               "application/x-font-ttf", "application/x-font-otf")
# 3.0.4.0 R5: a ComfyUI video render plays in a plain <video> (no sandbox
# needed); the type is pinned here, never left to the platform's mime table.
MEDIA_TYPES = {".mp4": "video/mp4", ".webm": "video/webm", ".mov": "video/quicktime", ".png": "image/png",
               ".webp": "image/webp", ".wav": "audio/wav", ".mp3": "audio/mpeg", ".flac": "audio/flac"}
_NAME = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]*$")
ASSETS = "_assets"

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
    assets = len(parts) == 3 and parts[1] == ASSETS
    if len(parts) < 3 or not all(_NAME.match(p) for i, p in enumerate(parts) if not (assets and i == 1)):
        return None
    root = design_root(state_dir).resolve()
    folder = root / parts[0] / "assets" if assets else root / parts[0] / "artboards" / parts[1]
    if folder.is_symlink():
        return None
    base = folder.resolve()
    target = (base / "/".join(parts[2:])).resolve()
    inside = root in base.parents and base in target.parents and root in target.parents
    return target if inside and target.is_file() else None


def csp_for(ctype: str) -> str:
    """The CSP header for a response of this content type: every type that is not an image (SVG is not), a video, an
    audio file, a PDF or a font also gets an opaque origin (3.3.14.0 R1, #6: an allow-list, so XHTML, XML, XSL, an
    `.svgz` and a type nobody named are sandboxed too)."""
    kind = ctype.split(";")[0].strip().lower()
    inert = (kind.startswith(INERT) and kind != "image/svg+xml") or kind in INERT_TYPES
    return CSP if inert else CSP + "; sandbox allow-scripts"


def read(state_dir, url_path: str, query: dict):
    """(status, body, content type) for one raw file request."""
    target = resolve(state_dir, url_path)
    if target is None:
        return 404, b'{"error": "not found"}', "application/json"
    data = target.read_bytes()
    ctype = MEDIA_TYPES.get(target.suffix.lower()) or mimetypes.guess_type(str(target))[0] or "application/octet-stream"
    if target.suffix.lower() in (".html", ".htm"):
        ctype = "text/html; charset=utf-8"
        if query.get("edit") in ("1", "pick") and target.parent.parent.name == "artboards":  # the current version only
            from .api_edit import PICK_SCRIPT, inject
            # 1: the classic page's contenteditable body; pick (3.0.7.0 R3b): a double-click posts the text to Studio's editor
            data = inject(data.decode("utf-8", "replace"), EDIT_SCRIPT if query.get("edit") == "1" else PICK_SCRIPT).encode("utf-8")
    elif ctype.startswith("text/") or ctype in ("application/javascript", "application/json", "image/svg+xml"):
        ctype += "; charset=utf-8"
    return 200, data, ctype
