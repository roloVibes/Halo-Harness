"""halo_harness.design.store_posts -- the readers for a project's `posts.json`
(a list of post entries, flows R4) and `metrics.jsonl` (one sample per line)."""

from __future__ import annotations

from typing import Optional

from halo_harness.design.jsonio import _read_json, _read_jsonl_line


class PostsMixin:
    def posts(self) -> list:
        rows = _read_json(self.path / "posts.json", [])
        return [r for r in rows if isinstance(r, dict)] if isinstance(rows, list) else []

    def metrics(self, limit: Optional[int] = None) -> list:
        p = self.path / "metrics.jsonl"
        try:
            lines = p.read_text(encoding="utf-8").splitlines() if p.is_file() else []
        except OSError:
            lines = []
        rows = [r for r in (_read_jsonl_line(l) for l in lines) if isinstance(r, dict)]
        return rows[-int(limit):] if limit else rows
