"""halo_harness.design.sync -- a design system from what you already have
(Halo 3.0.1.0 round D2), like Claude Code's /design-sync: a codebase
(CSS custom properties, a Tailwind config, tokens.json / design-tokens
files, component names from components/ or ui/ folders), a URL (the page's
stylesheet tokens and fonts), or a folder of images and documents the model
reads later. Writes system.json with provenance; never guesses a value
that is not in a source.
"""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Optional

_CSS_VAR = re.compile(r"--([a-zA-Z0-9_-]+)\s*:\s*([^;{}]+?)\s*(?=[;}])")  # the last declaration may drop its ;
_FONT = re.compile(r"font-family\s*:\s*([^;{}]+?)\s*(?=[;}])")
_SKIP_DIRS = {"node_modules", ".git", "dist", "build", ".next", "__pycache__", ".venv", "venv"}
_COMPONENT_DIRS = ("components", "ui", "src/components", "src/ui", "app/components")


def _group(name: str) -> str:
    n = name.lower()
    if any(k in n for k in ("color", "colour", "bg", "fg", "primary", "accent", "surface", "border", "text")):
        return "colors"
    if any(k in n for k in ("font", "type", "text-size", "leading", "line-height", "weight")):
        return "typography"
    if any(k in n for k in ("space", "gap", "pad", "margin")):
        return "spacing"
    if any(k in n for k in ("radius", "rounded")):
        return "radii"
    if any(k in n for k in ("shadow", "elevation")):
        return "shadows"
    return "other"


def tokens_from_css(text: str) -> dict:
    out: dict = {}
    for name, value in _CSS_VAR.findall(text):
        out.setdefault(_group(name), {})[f"--{name}"] = value.strip()
    fonts = sorted({f.strip() for f in _FONT.findall(text)})
    if fonts:
        out.setdefault("typography", {})["font-families"] = ", ".join(fonts[:8])
    return out


def tokens_from_tailwind(text: str) -> dict:
    """A rough read of a tailwind.config.* `theme.extend`: colours, fonts,
    spacing, radii keys with their literal values when they are literals."""
    out: dict = {}
    for group, key in (("colors", "colors"), ("typography", "fontFamily"), ("spacing", "spacing"), ("radii", "borderRadius")):
        m = re.search(key + r"\s*:\s*\{([^{}]*)\}", text, re.S)  # one level: the literal leaves
        if not m:
            continue
        for k, v in re.findall(r"['\"]?([A-Za-z0-9_-]+)['\"]?\s*:\s*['\"]([^'\"]+)['\"]", m.group(1)):
            out.setdefault(group, {})[k] = v
    return out


def tokens_from_json(data) -> dict:
    """tokens.json / design-tokens style: nested objects whose leaves have a
    `value` (W3C design tokens) or are plain strings."""
    out: dict = {}

    def walk(node, path):
        if isinstance(node, dict):
            if "value" in node and not isinstance(node["value"], dict):
                out.setdefault(_group(".".join(path)), {})[".".join(path)] = str(node["value"])
                return
            for k, v in node.items():
                if k.startswith("$"):
                    continue
                walk(v, path + [str(k)])
        elif isinstance(node, (str, int, float)) and path:
            out.setdefault(_group(".".join(path)), {})[".".join(path)] = str(node)
    walk(data, [])
    return out


def components_in(root: Path) -> list:
    names = []
    for rel in _COMPONENT_DIRS:
        d = root / rel
        if not d.is_dir():
            continue
        for f in sorted(d.rglob("*")):
            if f.is_file() and f.suffix in (".tsx", ".jsx", ".vue", ".svelte", ".py", ".html") and not f.name.startswith(("index.", "_")):
                names.append({"name": f.stem, "path": str(f.relative_to(root)).replace("\\", "/")})
            if len(names) >= 200:
                break
    return names


def _merge(into: dict, more: dict) -> None:
    for group, vals in more.items():
        into.setdefault(group, {}).update(vals)


def scan_codebase(root: Path, *, max_files: int = 400) -> dict:
    root = Path(root)
    tokens: dict = {}
    sources = []
    seen = 0
    for f in root.rglob("*"):
        if seen >= max_files:
            break
        if any(part in _SKIP_DIRS for part in f.parts):
            continue
        if not f.is_file():
            continue
        name = f.name.lower()
        try:
            if f.suffix in (".css", ".scss", ".less") or name.endswith((".tcss",)):
                t = tokens_from_css(f.read_text(encoding="utf-8", errors="replace"))
            elif name.startswith("tailwind.config"):
                t = tokens_from_tailwind(f.read_text(encoding="utf-8", errors="replace"))
            elif name in ("tokens.json", "design-tokens.json", "design.tokens.json") or name.endswith(".tokens.json"):
                t = tokens_from_json(json.loads(f.read_text(encoding="utf-8", errors="replace")))
            else:
                continue
        except (OSError, ValueError):
            continue
        seen += 1
        if t:
            _merge(tokens, t)
            sources.append(str(f.relative_to(root)).replace("\\", "/"))
    return {"tokens": tokens, "components": components_in(root), "sources": [f"codebase:{root}"] + sources[:40]}


def capture_url(url: str, *, fetch: Optional[callable] = None) -> dict:
    """The page's own stylesheet tokens and fonts. `fetch(url) -> str` is the
    HTTP step (tests pass one); by default the harness's choke point."""
    if fetch is None:
        from halo_harness.providers.http import urlopen_tls  # the one network choke point

        def fetch(u: str) -> str:  # type: ignore[no-redef]
            with urlopen_tls(u, timeout=20) as r:
                return r.read(2_000_000).decode("utf-8", "replace")
    html = fetch(url)
    tokens = tokens_from_css(html)
    for href in re.findall(r"<link[^>]+rel=[\"']stylesheet[\"'][^>]+href=[\"']([^\"']+)", html)[:5]:
        try:
            css_url = href if href.startswith("http") else url.rstrip("/") + "/" + href.lstrip("/")
            _merge(tokens, tokens_from_css(fetch(css_url)))
        except Exception:
            continue
    return {"tokens": tokens, "components": [], "sources": [f"url:{url}"]}


def write_system(project, system: dict, *, name: str = "default") -> dict:
    current = project.system() or {}
    merged = {"name": current.get("name") or name, "tokens": current.get("tokens") or {}, "components": current.get("components") or [],
              "sources": list(current.get("sources") or [])}
    _merge(merged["tokens"], system.get("tokens") or {})
    known = {c.get("name") for c in merged["components"] if isinstance(c, dict)}
    merged["components"] += [c for c in system.get("components") or [] if isinstance(c, dict) and c.get("name") not in known]
    merged["sources"] += [s for s in system.get("sources") or [] if s not in merged["sources"]]
    project.save_system(merged)
    return merged
