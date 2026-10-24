"""halo_harness.ext.memory -- a note in a pack's memory namespace, with its
provenance (extension API 1.x; Halo 3.2.0.0 R5, packs/memory_meta.py).

    from halo_harness.ext import memory
    memory.write("doc-review/reviews", "docs/guide.md: a dead link on line 3",
                 {"retention": "days:30", "shared": ["release-notes"]})

`namespace` is `<pack id>/<name>` (a bare id is the pack's own default
namespace); `provenance` is `{source, run, stage, retention, shared}`, every
key optional: `source` is workflow run | bio | user (a stage's worker gets
workflow run, its run and its stage from the environment), `retention` keep
(the default) | days:<n> | run, `shared` the packs that may read it. Returns
the note's path; ValueError (one line per problem) for a bad namespace or
provenance. The note is a recall entry of that namespace (`halo recall
--namespace <pack>/<name> --provenance`).
"""

from __future__ import annotations


def write(namespace: str, text: str, provenance=None, *, name=None, state_dir=None):
    from halo_harness.packs.memory_meta import write_entry
    return write_entry(namespace, text, provenance, name=name, state_dir=state_dir)


__all__ = ["write"]
