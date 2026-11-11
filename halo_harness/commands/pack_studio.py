"""halo_harness.commands.pack_studio -- a pack's command that opens its own Studio section, and the slash words a
core section had before it went to a pack (Halo 3.3.13.0 R2, extension API 1.2).

A pack's `commands/<name>.md` whose frontmatter says `studio: <section id>` (one of the pack's own sections) is not a
prompt: `/<name>` opens Studio on `<pack id>--<section id>` (the browser too) and `/<name> url` prints the address,
exactly as `/studio <pack id>--<section id>` does; the body is the command's help text. A word in `MOVED`
(studio/modes.py: `design`) that no enabled pack answers is a command of its own that says which pack has it now and
how to turn it on, so `/design` with the design pack off is one line, not an unknown command.

    studio_run(pack_id, section)   the run function of such a command
    register_moved(reg, cwd)       the moved words' one-line commands, where nothing else took the name; 3.4.0.0 B:
                                   then packs/contrib_slash.register (a pack's own /<name>, a word that left the core)
"""

from __future__ import annotations


def studio_run(pack_id: str, section: str):
    def _run(args_text: str, facade) -> str:
        from halo_harness.commands.builtins import _cmd_studio
        if getattr(facade, "session", None) is None and not getattr(facade, "studio_ok", False):
            # a fake session (halo pack test): say what it opens, start nothing
            return (f"/{section} opens Studio on {pack_id}--{section}, the {pack_id} pack's section; "
                    f"/{section} url prints its address")
        return _cmd_studio(f"{pack_id}--{section} {args_text or ''}".strip(), facade)
    return _run


def register_moved(reg, cwd=None) -> None:
    from halo_harness.commands.registry import SlashCommand
    from halo_harness.studio.modes import MOVED, moved_line
    for word in MOVED:
        if reg.resolve(word) is None:
            reg.add(SlashCommand(name=word, description=f"The {word.title()} section is a pack now: says how to turn it on",
                                 kind="core", source="builtin", run=lambda _a, _f, w=word: f"halo: {moved_line(w)}"))
    from halo_harness.packs.contrib_slash import register  # 3.4.0.0 B: a pack's own /<name>; a word that left the core
    register(reg, cwd)
