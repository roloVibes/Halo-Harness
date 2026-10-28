"""tools/library_snapshot.py -- Halo 3.3.5.0 R2: take halo_harness/models_library/snapshot_ollama.json.

    python tools/library_snapshot.py [--top 150] [--delay 0.25] [--out PATH]

Reads ollama.com/library (the catalog, most pulled first), each of the top N models' tags page, and for each tag a
size chip names (else `latest`) the registry manifest and its config blob (two small JSON documents: no layer is
fetched). Run it with a scratch BRIDGE_TEST_HOME and without BRIDGE_TEST_NO_BACKGROUND_NET; it writes one model per
line so a re-take diffs well.
"""
from __future__ import annotations

import argparse
import json
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))

from halo_harness.models_library import cache  # noqa: E402
from halo_harness.models_library.ollama_library import CATALOG_URL, TAGS_URL, parse_catalog, parse_tags  # noqa: E402
from halo_harness.models_library.ollama_registry import (ACCEPT, blob_url, manifest_url, parse_config,  # noqa: E402
                                                         parse_manifest)

MAX_TAGS = 24
PREFER = ("q4_k_m", "q8_0", "fp16", "bf16", "q4_0")
KEEP = ("name", "description", "capabilities", "cloud", "sizes", "pulls", "pulls_n", "tags_count", "updated", "updated_at")


def _tag_row(t: dict) -> dict:
    return {"tag": t["tag"], "size_bytes": t["size_bytes"], "size_text": t["size_text"], "context": t["context"],
            "context_text": t["context_text"], "input": t["input"], "latest": t["latest"]}


def _pick(tags: list, sizes: list) -> list:
    """At most MAX_TAGS: latest and the size tags first, then each size's common quantizations, then the rest."""
    def rank(t):
        tag = t["tag"].lower()
        if tag == "latest" or tag in sizes:
            return 0
        return 1 + next((i for i, q in enumerate(PREFER) if tag.endswith(q)), len(PREFER))
    keep = sorted(tags, key=rank)[:MAX_TAGS]
    order = {id(t): i for i, t in enumerate(tags)}
    return sorted(keep, key=lambda t: order[id(t)])


def _manifest(model: str, tag: str) -> dict:
    m = parse_manifest(cache.fetch(manifest_url(model, tag), ACCEPT))
    conf = parse_config(cache.fetch(blob_url(model, m["config_digest"]))) if m.get("config_digest") else {}
    return {"weights": m["weights"], "projector": m["projector"], "total": m["total"],
            "family": conf.get("family", ""), "params": conf.get("params"), "quant": conf.get("quant", "")}


def take(top: int, delay: float) -> dict:
    entries = parse_catalog(cache.fetch(CATALOG_URL))
    entries = [e for e in entries if not (e["cloud"] and not e["sizes"] and not e["capabilities"])]
    entries.sort(key=lambda e: -(e.get("pulls_n") or 0))
    out = []
    for i, e in enumerate(entries[:top]):
        row = {k: e[k] for k in KEEP}
        try:
            tags = parse_tags(cache.fetch(TAGS_URL.format(model=e["name"])), e["name"])
        except Exception as ex:  # one model's page: noted, the rest go on
            print(f"  {e['name']}: tags {ex}", file=sys.stderr)
            tags = []
        time.sleep(delay)
        row["tags"] = [_tag_row(t) for t in _pick([t for t in tags if t["size_bytes"]], e["sizes"])]
        names = {t["tag"] for t in row["tags"]}
        want = [s for s in e["sizes"] if s in names] or (["latest"] if "latest" in names else [])
        row["manifests"] = {}
        for tag in want:
            try:
                row["manifests"][tag] = _manifest(e["name"], tag)
            except Exception as ex:
                print(f"  {e['name']}:{tag}: manifest {ex}", file=sys.stderr)
            time.sleep(delay)
        out.append(row)
        print(f"{i + 1:3d} {e['name']}: {len(row['tags'])} tags, {len(row['manifests'])} manifests", file=sys.stderr)
    now = datetime.now(timezone.utc)
    return {"taken": now.strftime("%Y-%m-%d"), "taken_at": int(now.timestamp()),
            "source": "ollama.com/library (most pulled first), each model's tags page, registry.ollama.ai manifests",
            "models": out}


def write(data: dict, out: Path) -> None:
    head = {k: v for k, v in data.items() if k != "models"}
    lines = ["{" + json.dumps(head, ensure_ascii=False)[1:-1] + ', "models": [']
    lines += [json.dumps(m, ensure_ascii=False, separators=(",", ":")) + ("," if i < len(data["models"]) - 1 else "")
              for i, m in enumerate(data["models"])]
    lines.append("]}")
    out.write_text("\n".join(lines) + "\n", encoding="utf-8", newline="\n")


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="take the shipped Ollama library snapshot")
    ap.add_argument("--top", type=int, default=150)
    ap.add_argument("--delay", type=float, default=0.25)
    ap.add_argument("--out", type=Path, default=REPO / "halo_harness" / "models_library" / "snapshot_ollama.json")
    a = ap.parse_args(argv)
    data = take(a.top, a.delay)
    write(data, a.out)
    print(f"wrote {a.out} ({len(data['models'])} models, {a.out.stat().st_size:,} bytes)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
