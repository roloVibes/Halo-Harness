"""The fixture's doctor rows: one OK line with the level it reads, one row that needs a fix."""

from halo_harness.ext import get_config


def rows(ctx) -> list:
    level = get_config(ctx.pack_id, "level", 2)
    return [f"level {level}", {"ok": False, "text": "no name set", "fix": "halo config set packs.settings.contrib-rows.name x"}]
