"""halo_harness.peers.needs -- whether a harness's capabilities catalog meets a need, in words (Halo 3.0.6.0 R7 as
fleet/mission_assign.has; 3.4.0.0 D: core, so a pack workflow's capability `requires` and a pack's capability rows are
checked with the fleet pack off too -- packs/capability_check.py reads it; the fleet pack's mission_assign re-exports it).

* `has(catalog, need)`: a capability name is an MCP server (`gridcraft`), one of its tools (`gridcraft/write_range` or
  `write_range`), a skill, a tag, a craft app, a CLI that is installed (`nmap`), a model id, `comfyui`, `gpu`, a word
  of a GPU's name (`4090`), an OS or distro (`kali`), `repo:<name>`, or a pack's capability that is available there
  (`docs.review`; why "pack doc-review: docs.review"). A `kind:` prefix (`mcp:`, `tool:`, `skill:`, `tag:`, `app:`,
  `cli:`, `model:`, `os:`, `pack:`) narrows it.
* `norm_need(need)`: lower case, one space between words.
"""

from __future__ import annotations

import re
from typing import Optional

KINDS = ("mcp", "tool", "skill", "tag", "app", "craft", "cli", "model", "os", "repo", "gpu", "pack")


def norm_need(need) -> str:
    return " ".join(str(need or "").strip().lower().split())


def has(cat: Optional[dict], need) -> Optional[str]:
    """Why `cat` meets `need` ("gridcraft (MCP server)"), or None."""
    if not isinstance(cat, dict):
        return None
    n = norm_need(need)
    kind, _, word = n.partition(":") if ":" in n and n.split(":", 1)[0] in KINDS else ("", "", n)
    if not word:
        return None
    k = kind or "any"
    for s in cat.get("mcp") or []:
        name = str(s.get("name") or "").lower()
        if k in ("any", "mcp", "app", "craft") and name == word:
            return f"{name} (MCP server)"
        for t in s.get("tools") or [] if isinstance(s.get("tools"), list) else []:
            tool = str(t.get("name") or "").lower()
            if k in ("any", "tool", "mcp") and word in (tool, f"{name}/{tool}"):
                return f"{name}/{tool} (MCP tool)"
    for key, label, kinds in (("skills", "skill", ("any", "skill")), ("tags", "tag", ("any", "tag")),
                              ("craft_apps", "craft app", ("any", "app", "craft"))):
        if k in kinds and word in [str(x).lower() for x in cat.get(key) or []]:
            return f"{word} ({label})"
    clis = cat.get("clis") if isinstance(cat.get("clis"), dict) else {}
    if k in ("any", "cli") and clis.get(word):
        return f"{word} {clis[word] if clis[word] != 'installed' else ''}".strip() + " (CLI)"
    for m in cat.get("models") or []:
        mid = str(m.get("id") or "").lower()
        if k in ("any", "model") and word in (mid, mid.split(":", 1)[-1], mid.rsplit("/", 1)[-1]):
            return f"{m.get('id')} (model)"
    media = cat.get("media") if isinstance(cat.get("media"), dict) else {}
    if k in ("any", "app") and word == "comfyui" and media.get("comfyui"):
        return "ComfyUI (media)"
    hw = cat.get("hardware") if isinstance(cat.get("hardware"), dict) else {}
    gpus = [str(g.get("name") or "") for g in hw.get("gpu") or [] if isinstance(g, dict)]
    if k in ("any", "gpu") and (word == "gpu" and gpus or any(word in re.findall(r"[a-z0-9]+", g.lower()) for g in gpus)):
        return f"{gpus[0] if word == 'gpu' else next(g for g in gpus if word in g.lower())} (GPU)"
    if k in ("any", "os") and word in (str(hw.get("os") or "").lower(), str(hw.get("distro") or "").lower()):
        return f"{word} (OS)"
    if k == "repo" and word in [str(p.get("repo") or p.get("name") or "").lower() for p in cat.get("projects") or []]:
        return f"the {word} repo"
    if k in ("any", "pack"):  # 3.2.0.0 R4: a pack's capability, only where it is available
        for p in cat.get("packs") or [] if isinstance(cat.get("packs"), list) else []:
            for c in p.get("capabilities") or [] if isinstance(p, dict) else []:
                if isinstance(c, dict) and c.get("available") and str(c.get("name") or "").lower() == word:
                    return f"pack {p.get('id')}: {c.get('name')}"
    return None
