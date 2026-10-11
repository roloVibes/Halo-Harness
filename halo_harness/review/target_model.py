"""halo_harness.review.target_model -- the `ReviewTarget` a review runs on, the
per-file split of its diff, and the shards the reviewers receive.

Large diffs are split per file and packed into shards of at most
`DEFAULT_SHARD_CHARS`; one reviewer per dimension runs on each shard.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Optional

DEFAULT_SHARD_CHARS = 48_000
MAX_SHARDS = 6
EXCERPT_CHARS = 12_000

_DIFF_HEAD = re.compile(r"^diff --git a/(.+?) b/(.+)$")


class TargetError(Exception):
    """The target could not be resolved; the message is shown to the user as is."""


@dataclass
class Shard:
    index: int                      # 1-based
    total: int
    text: str
    files: "list[str]"
    omitted: "list[str]" = field(default_factory=list)   # files past MAX_SHARDS, listed by name only

    @property
    def label(self) -> str:
        return f"{self.index}/{self.total}"


@dataclass
class ReviewTarget:
    kind: str                       # branch | worktree | range | pr | paths
    label: str
    diff_text: str
    files: "list[str]"
    base: Optional[str] = None
    head: Optional[str] = None
    cwd: str = ""
    chunks: "dict[str, str]" = field(default_factory=dict)   # per-file text; filled for the paths kind

    def file_diffs(self) -> "dict[str, str]":
        """`{file: its slice of the diff}` in diff order."""
        if self.chunks:
            return dict(self.chunks)
        out: "dict[str, str]" = {}
        name = None
        buf: "list[str]" = []
        for line in self.diff_text.splitlines(keepends=True):
            m = _DIFF_HEAD.match(line.rstrip("\r\n"))
            if m:
                if name is not None:
                    out[name] = out.get(name, "") + "".join(buf)
                name, buf = m.group(2), [line]
            else:
                buf.append(line)
        if name is not None:
            out[name] = out.get(name, "") + "".join(buf)
        return out

    def excerpt_for(self, file: Optional[str], limit: int = EXCERPT_CHARS) -> str:
        """The part of the diff that concerns `file` (the whole diff head when
        the file is unknown), capped."""
        diffs = self.file_diffs()
        text = diffs.get(file or "")
        if text is None:
            text = self.diff_text
        if len(text) > limit:
            text = text[:limit] + "\n... [excerpt truncated]\n"
        return text

    def shards(self, max_chars: int = DEFAULT_SHARD_CHARS, max_shards: int = MAX_SHARDS) -> "list[Shard]":
        diffs = self.file_diffs() or ({"(diff)": self.diff_text} if self.diff_text else {})
        packed: "list[tuple[list[str], list[str]]]" = []     # ([text pieces], [files])
        sizes: "list[int]" = []
        for name, text in diffs.items():
            if len(text) > max_chars:
                text = text[:max_chars] + "\n... [truncated; use Read or `git diff` for the rest]\n"
            if packed and sizes[-1] + len(text) <= max_chars:
                packed[-1][0].append(text)
                packed[-1][1].append(name)
                sizes[-1] += len(text)
            else:
                packed.append(([text], [name]))
                sizes.append(len(text))
        if not packed:
            return [Shard(1, 1, "", [])]
        omitted: "list[str]" = []
        if len(packed) > max_shards:
            for _texts, names in packed[max_shards:]:
                omitted.extend(names)
            packed = packed[:max_shards]
        total = len(packed)
        shards = [Shard(i + 1, total, "".join(texts), names) for i, (texts, names) in enumerate(packed)]
        shards[-1].omitted = omitted
        return shards

    def to_json(self) -> dict:
        return {"kind": self.kind, "label": self.label, "base": self.base, "head": self.head,
                "files": list(self.files)}
