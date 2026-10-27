"""halo_harness.ollama_steward -- Halo 3.3.4.0 "The Ollama steward".

R1 ships two things the later rounds read: the steward's knowledge
(`knowledge/*.md`, plain Markdown with every claim tagged to a row of
`knowledge/SOURCES.md`) and the hardware card of a host
(`hardware.hardware_card`, printed by `halo ollama hardware`). Nothing in
this package writes to an Ollama server or changes a model on it.
"""

from __future__ import annotations

from pathlib import Path

KNOWLEDGE_DIR = Path(__file__).resolve().parent / "knowledge"


def knowledge_files() -> "list[Path]":
    """Every knowledge file shipped with the package, SOURCES.md included,
    sorted by name."""
    return sorted(KNOWLEDGE_DIR.glob("*.md"))
