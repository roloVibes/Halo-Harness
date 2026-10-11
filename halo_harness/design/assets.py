"""halo_harness.design.assets -- a design project's assets/ folder (Halo
3.0.1.0 round D5): list it (name, size, kind by extension, a data-URL
thumbnail for images under 400 KB) and write an upload into it (the name is
cut to a safe basename; 15 MB at most). The folder is where a turn finds the
logos, photos and captures it is told to use.
"""

from __future__ import annotations

import base64
import binascii
import mimetypes
import re

MAX_BYTES = 15 * 1024 * 1024
THUMB_BYTES = 400 * 1024
_KINDS = {"image": (".png", ".jpg", ".jpeg", ".gif", ".webp", ".svg", ".avif", ".bmp", ".ico"),
          "font": (".woff", ".woff2", ".ttf", ".otf"), "video": (".mp4", ".mov", ".webm", ".mkv"),
          "audio": (".mp3", ".wav", ".ogg", ".m4a", ".flac"), "pdf": (".pdf",),
          "text": (".txt", ".md", ".json", ".csv", ".html", ".css", ".js")}


class TooBig(Exception):
    pass


def kind_of(name: str) -> str:
    ext = "." + name.rsplit(".", 1)[-1].lower() if "." in name else ""
    return next((k for k, exts in _KINDS.items() if ext in exts), "other")


def safe_name(name: str) -> str:
    base = re.split(r"[\\/]", str(name or ""))[-1].strip().lstrip(".")
    base = re.sub(r"[^A-Za-z0-9._-]+", "-", base).strip("-")
    return base[:120] or "asset"


def list_assets(project) -> list:
    root = project.path / "assets"
    out = []
    for f in sorted(root.iterdir()) if root.is_dir() else []:
        if not f.is_file():
            continue
        size, kind = f.stat().st_size, kind_of(f.name)
        row = {"name": f.name, "size": size, "kind": kind, "path": f"assets/{f.name}", "thumb": ""}
        if kind == "image" and size < THUMB_BYTES:
            mime = mimetypes.guess_type(f.name)[0] or "application/octet-stream"
            row["thumb"] = f"data:{mime};base64," + base64.b64encode(f.read_bytes()).decode("ascii")
        out.append(row)
    return out


def save_asset(project, name: str, data_base64: str) -> dict:
    """Write one upload. Raises TooBig past 15 MB and ValueError on bad base64."""
    text = str(data_base64 or "")
    if "," in text[:80] and text.startswith("data:"):
        text = text.split(",", 1)[1]
    if len(text) > MAX_BYTES * 4 // 3 + 8:
        raise TooBig(f"an asset is {MAX_BYTES // (1024 * 1024)} MB at most")
    try:
        raw = base64.b64decode(text, validate=True)
    except (binascii.Error, ValueError):
        raise ValueError("data_base64 is the file's bytes, base64 encoded")
    if len(raw) > MAX_BYTES:
        raise TooBig(f"an asset is {MAX_BYTES // (1024 * 1024)} MB at most")
    root = project.path / "assets"
    root.mkdir(exist_ok=True)
    base = safe_name(name)
    stem, dot, ext = base.rpartition(".") if "." in base else (base, "", "")
    target, n = root / base, 2
    while target.exists():
        target = root / f"{stem}-{n}{dot}{ext}"
        n += 1
    target.write_bytes(raw)
    return {"name": target.name, "size": len(raw), "kind": kind_of(target.name), "path": f"assets/{target.name}"}
