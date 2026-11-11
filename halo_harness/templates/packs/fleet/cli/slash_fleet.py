"""The fleet pack's `/fleet` (`contributes.slash`): every harness, session and agent this machine sees (Studio's fleet
view, this machine's hub, or this harness alone), the same table as `halo fleet --once`; `/fleet who <query>` and
`/fleet capabilities [name]` as before. The terminal's live table dialog stayed in the core until 3.4.0.0; a pack's
slash command prints, so `halo fleet` in a terminal of its own is the live table now."""

from __future__ import annotations


def run(args_text: str, facade) -> str:
    from ..fleet.cli_caps import slash_text
    text = slash_text(args_text or "")
    if text is not None:
        return text
    from ..fleet.table import render, rows, snapshot
    view, source = snapshot()
    where = {"studio": "Studio's fleet view", "hub": "this machine's hub", "local": "this harness only"}
    return f"Fleet ({where.get(source, source)}):\n" + render(rows(view))
