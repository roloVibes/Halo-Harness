"""halo_harness.packs.capability_rules -- what a pack's `contributes.capabilities` may say (Halo 3.2.0.0 R4,
docs/EXTENSION_API.md "Pack capabilities"; API 1.4: its name before 3.5.0.0, `contributes.fleet`, is still read and
its `mission` key ignored).

The shape is schemas/pack_yaml.py `capabilities_block()`; these are the meanings, checked with the manifest
(`manifest.validate_manifest`), one line each naming the key and, with a root, `pack.yaml line N`:

- a capability's `name` is one of the pack's top-level `capabilities:`, once;
- its `requires` keys are REQUIRES_KEYS (another key names the closest one); `hardware` is `{gpu: true | false | <a
  word of the GPU's name>, ram_gb}`; `grants` are permissions the pack requests; `locality` kinds are LOCALITY;
  `platform` and `runtimes` are words; `capacity.parallel` is 1..64;
- its `description` holds no path (a drive path, /home/..., ~/...);
- no string under the contribution (names, descriptions, requires, labels) looks like a secret (a token shape the
  privacy scan knows, a Bearer value) or an environment reference ($VAR, ${VAR}, %VAR%): Studio, `halo pack inspect`
  and reports show it;
- an inspector line is `{label, source}`, the source a markdown, text or JSON file inside the pack's folder.

    contribution_lines(manifest, root)   # [] when the contribution is fine
    contribution_of(manifest)            # contributes.capabilities (or .fleet) as a dict ({} when absent)
    contribution_key(manifest)           # "contributes.capabilities" or "contributes.fleet", the one it uses
    capabilities_of(manifest)            # the capability entries (dicts with a name)
"""

from __future__ import annotations

import re
from pathlib import Path

LOCALITY = ("repo", "pack-data")  # and repo:<name>
WORD_RE = re.compile(r"^[a-z][a-z0-9_.+-]*$")
ENV_RE = re.compile(r"\$\{?[A-Za-z_][A-Za-z0-9_]*\}?|%[A-Za-z_][A-Za-z0-9_]*%")
TILDE_RE = re.compile(r"(?:^|[\s\"'(=])~[\\/]")
INSPECTOR_SUFFIXES = (".md", ".markdown", ".txt", ".json")
PARALLEL = (1, 64)


def contribution_key(manifest) -> str:
    """The key the manifest uses: `contributes.capabilities`, else its old name `contributes.fleet` ('' for neither)."""
    contributes = manifest.get("contributes") if isinstance(manifest, dict) else None
    for name in ("capabilities", "fleet"):
        if isinstance(contributes, dict) and isinstance(contributes.get(name), dict):
            return f"contributes.{name}"
    return ""


def contribution_of(manifest) -> dict:
    key = contribution_key(manifest)
    return manifest["contributes"][key.split(".")[1]] if key else {}


def _list(d, key: str) -> list:
    v = d.get(key) if isinstance(d, dict) else None
    return v if isinstance(v, list) else []


def capabilities_of(manifest) -> "list[dict]":
    return [c for c in _list(contribution_of(manifest), "capabilities") if isinstance(c, dict) and isinstance(c.get("name"), str)]


def has_path(text: str) -> bool:
    from halo_harness.peers.catalog import _DRIVE, _POSIX
    return bool(_DRIVE.search(text) or _POSIX.search(text) or TILDE_RE.search(text))


def secret_word(text: str) -> str:
    """What makes `text` look like a secret or an environment reference ('' when nothing does)."""
    from halo_harness.redact import _BEARER_RE, _TOKEN_PATTERNS
    if ENV_RE.search(text):
        return f"an environment reference ({ENV_RE.search(text).group(0)})"
    if any(p.search(text) for p in _TOKEN_PATTERNS) or _BEARER_RE.search(text):
        return "a token-shaped value"
    return ""


class _Lines:
    def __init__(self, text: str):
        self.text, self.out = text, []

    def line(self, name: str, value=None) -> int:
        from halo_harness.packs.bio_rules import _line_of
        if not self.text:
            return 0
        n = _line_of(self.text, name, value) if name else 0
        if not n and value is not None:
            n = next((i for i, ln in enumerate(self.text.splitlines(), 1) if str(value) in ln), 0)
        return n or (_line_of(self.text, name) if name else 0)

    def add(self, key: str, msg: str, name: str = "", value=None) -> None:
        n = self.line(name or key.rsplit(".", 1)[-1].split("[")[0], value)
        self.out.append(f"pack.yaml line {n}: {key}{msg}" if n else f"{key}{msg}")


def _strings(obj, path: str):
    """`(key path, last key name, text)` for every string under `obj`, dict keys included."""
    if isinstance(obj, dict):
        for k, v in obj.items():
            sub = f"{path}.{k}"
            if isinstance(k, str):
                yield sub, k, k
            yield from _strings(v, sub)
    elif isinstance(obj, list):
        for i, v in enumerate(obj):
            yield from ((p, n, t) for p, n, t in _strings(v, f"{path}[{i}]"))
    elif isinstance(obj, str):
        yield path, path.rsplit(".", 1)[-1].split("[")[0], obj


def _secrets(L: _Lines, block: dict, where: str) -> None:
    for key, name, text in _strings({k: v for k, v in block.items() if k != "mission"}, where):
        word = secret_word(text)
        if word:
            L.add(key, f": {word}; Studio, halo pack inspect and reports show this text, so it never holds a secret "
                  "or an environment value", name, text)


def _requires(L: _Lines, key: str, req, manifest) -> None:
    from halo_harness.schemas.check import closest_key
    from halo_harness.schemas.pack_yaml import REQUIRES_KEYS
    if not isinstance(req, dict):
        return
    for k in req:
        if k not in REQUIRES_KEYS:
            near = closest_key(str(k), REQUIRES_KEYS)
            L.add(f"{key}.{k}", f" is not a requires key ({', '.join(REQUIRES_KEYS)})"
                  + (f"; closest: {near}" if near else ""), str(k))
    asked = [p for p in _list(manifest, "permissions") if isinstance(p, str)]
    for g in _list(req, "grants"):
        if g not in asked:
            L.add(f"{key}.grants", f": {g!r} is not a permission the pack requests ({', '.join(asked) or 'none'})", "grants", g)
    for k in ("platform", "runtimes"):
        for w in _list(req, k):
            if not isinstance(w, str) or not WORD_RE.match(w):
                L.add(f"{key}.{k}", f": {w!r} is not a word (lower-case: linux, windows, darwin, python ...)", k, w)
    for w in _list(req, "locality"):
        if not (w in LOCALITY or (isinstance(w, str) and w.startswith("repo:") and len(w) > 5)):
            L.add(f"{key}.locality", f": {w!r} is not one of {', '.join(LOCALITY)}, repo:<name>", "locality", w)
    for k in ("tools", "models"):
        for w in _list(req, k):
            if not isinstance(w, str) or not w.strip() or " " in w.strip():
                L.add(f"{key}.{k}", f": {w!r} is not a name", k, w)
    hw = req.get("hardware")
    if isinstance(hw, dict):
        gpu, ram = hw.get("gpu"), hw.get("ram_gb")
        if isinstance(gpu, str) and not gpu.strip():
            L.add(f"{key}.hardware.gpu", ": true, false or a word of the GPU's name (4090, nvidia)", "gpu")
        if ram is not None and (isinstance(ram, bool) or not isinstance(ram, (int, float)) or ram < 0):
            L.add(f"{key}.hardware.ram_gb", f" {ram!r} is not a number of GB", "ram_gb", ram)


def _capabilities(L: _Lines, manifest, block: dict, where: str) -> None:
    declared = [c for c in _list(manifest, "capabilities") if isinstance(c, str)]
    seen: "dict[str, str]" = {}
    for i, c in enumerate(_list(block, "capabilities")):
        key = f"{where}.capabilities[{i}]"
        if not isinstance(c, dict):
            continue
        name = c.get("name")
        if not isinstance(name, str) or not name.strip():
            L.add(f"{key}.name", ": required (one of the pack's capabilities:)", "name")
        elif name not in declared:
            L.add(f"{key}.name", f" {name!r} is not in the pack's capabilities: list ({', '.join(declared) or 'none'})",
                  "name", name)
        elif name in seen:
            L.add(f"{key}.name", f" {name!r} is declared twice ({seen[name]} has it)", "name", name)
        else:
            seen[name] = key
        desc = c.get("description")
        if isinstance(desc, str) and has_path(desc):
            L.add(f"{key}.description", ": holds a path; a capability's description names what it does, "
                  "never where a file is on this machine", "description", desc[:40])
        _requires(L, f"{key}.requires", c.get("requires"), manifest)
        cap = c.get("capacity") if isinstance(c.get("capacity"), dict) else {}
        par = cap.get("parallel")
        if par is not None and (isinstance(par, bool) or not isinstance(par, int) or not PARALLEL[0] <= par <= PARALLEL[1]):
            L.add(f"{key}.capacity.parallel", f" {par!r} is not {PARALLEL[0]}..{PARALLEL[1]}", "parallel", par)


def _inspector(L: _Lines, block: dict, root, where: str) -> None:
    for i, ln in enumerate(_list(block, "inspector")):
        key = f"{where}.inspector[{i}]"
        if not isinstance(ln, dict):
            continue
        if not str(ln.get("label") or "").strip():
            L.add(f"{key}.label", ": required (the inspector line's label)", "label")
        src = ln.get("source")
        if not isinstance(src, str) or not src.strip():
            L.add(f"{key}.source", ": required (a markdown or JSON file in the pack)", "source")
            continue
        rel = Path(src)
        if rel.is_absolute() or ".." in rel.parts or src.startswith(("/", "\\")) or ":" in src:
            L.add(f"{key}.source", f" {src!r} is outside the pack's folder", "source", src)
        elif rel.suffix.lower() not in INSPECTOR_SUFFIXES:
            L.add(f"{key}.source", f" {src!r}: an inspector line reads a {', '.join(INSPECTOR_SUFFIXES)} file", "source", src)
        elif root is not None and not (Path(root) / rel).is_file():
            L.add(f"{key}.source", f" {src} is not in the pack", "source", src)


def contribution_lines(manifest, root=None) -> "list[str]":
    block, where = contribution_of(manifest), contribution_key(manifest)
    if not block:
        return []
    text = ""
    if root is not None:
        try:
            text = (Path(root) / "pack.yaml").read_text(encoding="utf-8")
        except OSError:
            text = ""
    L = _Lines(text)
    _secrets(L, block, where)
    _capabilities(L, manifest, block, where)
    _inspector(L, block, root, where)
    return L.out
