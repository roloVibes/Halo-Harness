"""halo_harness.theme_toggle -- the game-theme toggle contract (Halo 2.0.8
theme pack), pinned once for `/doom`, `/metroid` and `/mario`.

    /<game> while that theme is NOT active: remember the active theme as
        `theme_toggle_previous` in ~/.halo/config.json, apply the game theme
        (persisted as `theme`).
    /<game> while it IS active: restore `theme_toggle_previous` (default
        `claude-dark` when missing or unusable) and clear the key.
    Game -> game: the original non-game previous is kept, so `/doom`,
        `/metroid`, `/metroid` lands back on whatever was active before
        `/doom`.
    `/theme <name>` (the explicit form) records the previous the same way
        when it moves onto a game theme, and clears it when it moves off to
        a non-game theme.
    `/metroid <area>` and `/theme metroid <area>` (round 2), and round 3's
        `/mario <variant>` and `/theme mario <variant>`, also persist the
        theme's variant as `theme_variant`; the bare toggle is unchanged and
        leaves the variant alone.

Pure data and config.json I/O -- no Textual. The TUI handlers, the headless
slash builtins and the wizard all go through here so there is one contract.
"""

from __future__ import annotations

import os
from typing import Optional

from halo_harness import theme as theme_mod

PREVIOUS_KEY = "theme_toggle_previous"


def is_game_theme(name: Optional[str]) -> bool:
    return isinstance(name, str) and name in theme_mod.GAME_THEMES


def unset_config_value(key: str) -> None:
    """Remove a top-level key from ~/.halo/config.json (tmp + os.replace,
    every other key preserved). A missing file or key is a no-op."""
    path = theme_mod._config_path()
    if not path.exists():
        return
    data = theme_mod._load_config_for_write(path)
    if key not in data:
        return
    del data[key]
    import json
    tmp_path = path.with_name(path.name + f".tmp{os.getpid()}")
    tmp_path.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")
    os.replace(tmp_path, path)


def stored_previous() -> Optional[str]:
    """The remembered pre-game theme, or None when unset/unusable (not a
    string, not a valid theme, or itself a game theme)."""
    value = theme_mod.get_config_value(PREVIOUS_KEY, default=None)
    if theme_mod.is_valid_theme(value) and not is_game_theme(value):
        return value
    return None


def _remember_previous(active: Optional[str]) -> None:
    """Record `active` as the theme to come back to -- unless the active
    theme is already a game theme (game -> game keeps the original)."""
    if is_game_theme(active) or not theme_mod.is_valid_theme(active):
        return
    theme_mod.set_config_value(PREVIOUS_KEY, active)


def toggle_game_theme(game: str, active: Optional[str]) -> str:
    """Apply the toggle contract for `game` given the currently `active`
    theme name; persists the result and returns the theme name to apply."""
    if game not in theme_mod.GAME_THEMES:
        raise ValueError(f"not a game theme: {game!r}")
    if active == game:
        restored = stored_previous() or theme_mod.DEFAULT_THEME
        theme_mod.persist_theme(restored)
        unset_config_value(PREVIOUS_KEY)
        return restored
    _remember_previous(active)
    theme_mod.persist_theme(game)
    return game


def select_theme(name: str, active: Optional[str], variant: Optional[str] = None) -> str:
    """The explicit `/theme <name> [variant]` form: persists `name`, records
    the previous theme when moving onto a game theme from a non-game one,
    and clears a stale previous when moving onto a non-game theme. A
    `variant` (Halo 2.0.8 round 2, e.g. `/theme metroid norfair`) is
    persisted as `theme_variant`; an unknown one raises ValueError."""
    if variant is not None and not theme_mod.is_valid_variant(name, variant):
        raise ValueError(variant_error(name, variant))
    if is_game_theme(name):
        _remember_previous(active)
    else:
        unset_config_value(PREVIOUS_KEY)
    theme_mod.persist_theme(name)
    if variant is not None:
        theme_mod.set_config_value(theme_mod.VARIANT_KEY, variant)
    return name


def set_game_variant(game: str, variant: str, active: Optional[str]) -> str:
    """`/metroid <area>`: persist the variant and make sure the game theme
    is active (the previous theme is remembered when coming from a
    non-game one). Unlike the bare toggle it never switches the theme off,
    so naming an area while the theme is already active just re-tints it.
    Returns the theme name to apply."""
    if not theme_mod.is_valid_variant(game, variant):
        raise ValueError(variant_error(game, variant))
    theme_mod.set_config_value(theme_mod.VARIANT_KEY, variant)
    if active != game:
        _remember_previous(active)
        theme_mod.persist_theme(game)
    return game


def variant_error(game: str, variant: str) -> str:
    names = theme_mod.variants_of(game)
    if not names:
        return f"{game} has no variants"
    return f"not a {game} variant: {variant!r} (expected one of {', '.join(names)})"


def parse_theme_args(args: str) -> tuple:
    """`/theme` arguments -> (name, variant or None, extra words)."""
    words = (args or "").split()
    name = words[0] if words else ""
    variant = words[1].lower() if len(words) > 1 else None
    return name, variant, words[2:]


def toggle_message(game: str, applied: str) -> str:
    if applied == game:
        return f"Theme set to {game} (run /{game} again to go back)"
    return f"Theme restored to {applied}"


def variant_message(game: str, variant: str) -> str:
    return f"Theme set to {game}, {noun_of(game)} {variant} (run /{game} again to go back)"


def noun_of(game: str) -> str:
    """What `game` calls its variant in messages: "area" or "palette"."""
    return theme_mod.VARIANT_NOUNS.get(game, "variant")
