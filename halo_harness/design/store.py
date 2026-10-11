"""halo_harness.design.store -- the design project on disk (Halo 3.0.1.0
round D2). A project is a folder under ~/.halo/design/<slug>/: design.json
(name, created, model, systems[], artboards[]), artboards/<id>/ (the CURRENT
files: index.html for a prototype, render.png/.svg/.pdf/.mp4 + source.json for
a craft render, controls.json for the knobs), artboards/<id>/v<n>/ (a snapshot
after each turn), comments.json (pins), assets/, system.json (the design
system with provenance), history.jsonl (one line per turn). The model edits
artboards/<id>/ directly; `snapshot()` versions what changed. Pure file I/O.
"""

from __future__ import annotations

import hashlib
import json
import re
import shutil
import time
from pathlib import Path
from typing import Optional

ARTBOARD_KINDS = ("prototype", "page", "deck", "vector", "photo", "motion", "video", "pdf", "image")
RENDER_NAMES = ("render.png", "render.svg", "render.pdf", "render.mp4", "index.html")


def slugify(name: str) -> str:
    s = re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")
    return s[:48] or "design"


def design_root(state_dir: Optional[Path] = None) -> Path:
    if state_dir is None:
        from halo_harness.providers.config import default_state_dir
        state_dir = Path(default_state_dir())
    return Path(state_dir) / "design"


def _now() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%S", time.gmtime())


def _read_json(p: Path, default):
    try:
        return json.loads(p.read_text(encoding="utf-8")) if p.is_file() else default
    except (OSError, ValueError):
        return default


def _read_jsonl_line(line: str):
    try:
        return json.loads(line) if line.strip() else None
    except ValueError:
        return None


def _write_json(p: Path, data) -> None:
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")


class Project:
    def __init__(self, path: Path):
        self.path = Path(path)
        self.slug = self.path.name

    # -- lifecycle -------------------------------------------------------------
    @classmethod
    def create(cls, name: str, *, model: str = "", systems: Optional[list] = None, state_dir: Optional[Path] = None) -> "Project":
        root = design_root(state_dir)
        slug = slugify(name)
        path = root / slug
        n = 2
        while path.exists():
            path = root / f"{slug}-{n}"
            n += 1
        for sub in ("artboards", "assets"):
            (path / sub).mkdir(parents=True)
        p = cls(path)
        p.save_meta({"name": name, "created": _now(), "model": model, "systems": list(systems or []), "artboards": []})
        _write_json(path / "comments.json", [])
        return p

    @classmethod
    def open(cls, slug: str, *, state_dir: Optional[Path] = None) -> Optional["Project"]:
        path = design_root(state_dir) / slug
        return cls(path) if (path / "design.json").is_file() else None

    @classmethod
    def list(cls, *, state_dir: Optional[Path] = None) -> list:
        root = design_root(state_dir)
        out = []
        for p in sorted(root.iterdir()) if root.is_dir() else []:
            if (p / "design.json").is_file():
                meta = _read_json(p / "design.json", {})
                out.append({"slug": p.name, "name": meta.get("name", p.name), "created": meta.get("created", ""),
                            "model": meta.get("model", ""), "artboards": len(meta.get("artboards") or [])})
        return out

    def meta(self) -> dict:
        return _read_json(self.path / "design.json", {})

    def save_meta(self, meta: dict) -> None:
        _write_json(self.path / "design.json", meta)

    # -- artboards --------------------------------------------------------------------
    def artboard_dir(self, aid: str) -> Path:
        return self.path / "artboards" / aid

    def artboards(self) -> list:
        meta = self.meta()
        out = []
        for a in meta.get("artboards") or []:
            d = self.artboard_dir(a["id"])
            files = sorted(f.name for f in d.iterdir() if f.is_file()) if d.is_dir() else []
            versions = sorted((int(v.name[1:]) for v in d.glob("v*") if v.is_dir() and v.name[1:].isdigit()), reverse=True) if d.is_dir() else []
            out.append({**a, "files": files, "versions": versions, "latest": versions[0] if versions else 0,
                        "render": next((f for f in RENDER_NAMES if f in files), ""), "controls": _read_json(d / "controls.json", [])})
        return out

    def add_artboard(self, title: str, kind: str = "prototype", app: str = "") -> dict:
        meta = self.meta()
        aid = slugify(title) or "artboard"
        existing = {a["id"] for a in meta.get("artboards") or []}
        base, n = aid, 2
        while aid in existing:
            aid = f"{base}-{n}"
            n += 1
        entry = {"id": aid, "title": title, "kind": kind if kind in ARTBOARD_KINDS else "prototype", "app": app, "created": _now()}
        meta.setdefault("artboards", []).append(entry)
        self.save_meta(meta)
        self.artboard_dir(aid).mkdir(parents=True, exist_ok=True)
        return entry

    def remove_artboard(self, aid: str) -> bool:
        meta = self.meta()
        before = len(meta.get("artboards") or [])
        meta["artboards"] = [a for a in meta.get("artboards") or [] if a["id"] != aid]
        self.save_meta(meta)
        shutil.rmtree(self.artboard_dir(aid), ignore_errors=True)
        return len(meta["artboards"]) < before

    def discover_artboards(self) -> list:
        """Folders under artboards/ the model created without registering them."""
        meta = self.meta()
        known = {a["id"] for a in meta.get("artboards") or []}
        found = []
        for d in sorted((self.path / "artboards").iterdir()) if (self.path / "artboards").is_dir() else []:
            if d.is_dir() and d.name not in known and not d.name.startswith("v"):
                src = _read_json(d / "source.json", {})
                kind = src.get("kind") if src.get("kind") in ARTBOARD_KINDS else ("prototype" if (d / "index.html").is_file() else "image")
                entry = {"id": d.name, "title": src.get("title") or d.name.replace("-", " ").title(), "kind": kind,
                         "app": src.get("app", ""), "created": _now()}
                meta.setdefault("artboards", []).append(entry)
                found.append(entry)
        if found:
            self.save_meta(meta)
        return found

    # -- versions ------------------------------------------------------------------------
    def _fingerprint(self, d: Path) -> str:
        h = hashlib.sha256()
        for f in sorted(p for p in d.iterdir() if p.is_file()):
            h.update(f.name.encode())
            h.update(f.read_bytes())
        return h.hexdigest()

    def snapshot(self, note: str = "") -> list:
        """Version every artboard whose current files differ from its latest
        version. Returns [(artboard id, new version number)]."""
        self.discover_artboards()
        out = []
        for a in self.meta().get("artboards") or []:
            d = self.artboard_dir(a["id"])
            if not d.is_dir() or not any(p.is_file() for p in d.iterdir()):
                continue
            versions = sorted((int(v.name[1:]) for v in d.glob("v*") if v.is_dir() and v.name[1:].isdigit()))
            fp = self._fingerprint(d)
            if versions:
                last = d / f"v{versions[-1]}"
                if _read_json(last / "version.json", {}).get("fingerprint") == fp:
                    continue
            n = (versions[-1] + 1) if versions else 1
            target = d / f"v{n}"
            target.mkdir()
            for f in d.iterdir():
                if f.is_file():
                    shutil.copy2(f, target / f.name)
            _write_json(target / "version.json", {"version": n, "created": _now(), "note": note, "fingerprint": fp})
            out.append((a["id"], n))
        return out

    def restore(self, aid: str, version: int) -> bool:
        d = self.artboard_dir(aid)
        src = d / f"v{version}"
        if not src.is_dir():
            return False
        for f in d.iterdir():
            if f.is_file():
                f.unlink()
        for f in src.iterdir():
            if f.is_file() and f.name != "version.json":
                shutil.copy2(f, d / f.name)
        return True

    # -- comments, controls, system, history ----------------------------------------------
    def comments(self) -> list:
        return _read_json(self.path / "comments.json", [])

    def add_comment(self, artboard: str, text: str, *, x: float = 0, y: float = 0, path: str = "", version: int = 0) -> dict:
        rows = self.comments()
        c = {"id": f"c{len(rows) + 1}-{int(time.time())}", "artboard": artboard, "version": version, "x": x, "y": y,
             "path": path, "text": text, "resolved": False, "created": _now()}
        rows.append(c)
        _write_json(self.path / "comments.json", rows)
        return c

    def resolve_comments(self, ids: list) -> int:
        rows = self.comments()
        hits = [c for c in rows if c["id"] in ids and not c.get("resolved")]
        for c in hits:
            c["resolved"] = True
        _write_json(self.path / "comments.json", rows)
        return len(hits)

    def controls(self, aid: str) -> list:
        return _read_json(self.artboard_dir(aid) / "controls.json", [])

    def set_control(self, aid: str, name: str, value) -> Optional[dict]:
        rows = self.controls(aid)
        hit = next((c for c in rows if c.get("name") == name), None)
        if hit is None:
            return None
        hit["value"] = value
        _write_json(self.artboard_dir(aid) / "controls.json", rows)
        return hit

    def system(self) -> dict:
        return _read_json(self.path / "system.json", {})

    def save_system(self, system: dict) -> None:
        _write_json(self.path / "system.json", system)

    def log_turn(self, entry: dict) -> None:
        with (self.path / "history.jsonl").open("a", encoding="utf-8") as fh:
            fh.write(json.dumps({"ts": _now(), **entry}, ensure_ascii=False) + "\n")

    def history(self) -> list:
        p = self.path / "history.jsonl"
        lines = p.read_text(encoding="utf-8").splitlines() if p.is_file() else []
        return [r for r in (_read_jsonl_line(l) for l in lines) if r is not None]
