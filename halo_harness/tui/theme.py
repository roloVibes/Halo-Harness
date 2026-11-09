"""halo_harness.tui.theme -- Textual CSS variables for each theme name
`halo_harness.theme` resolves (U0's module does the NAME resolution/
persistence, pure, no textual import; this module maps a resolved name to
actual colors).

3.3.12.0 R1: the colours come from the palette registry
(`halo_harness/themes`), the same tokens Studio's `styles/tokens.css` is
generated from; `-daltonized` swaps the accent and status pairs for blue and
orange, `-ansi` is the 16-colour set of the palette's posture.
"""

from __future__ import annotations

from halo_harness.theme import DEFAULT_THEME, is_valid_theme  # re-exported for tui/app.py
from halo_harness.themes import registry

# Textual variable <- registry token. `assistant` is body text; `thinking` is the dim decoration colour.
TOKEN_FOR = (
    ("bridge-bg", "bg"), ("bridge-surface", "bg2"), ("bridge-panel", "surface2"),
    ("bridge-text", "text"), ("bridge-muted", "muted"), ("bridge-border", "border"),
    ("bridge-accent", "accent"), ("bridge-success", "ok"), ("bridge-warning", "warn"),
    ("bridge-error", "bad"), ("bridge-user", "user"), ("bridge-assistant", "text"),
    ("bridge-tool", "tool"), ("bridge-thinking", "faint"),
)


def variables_for(theme_name: str) -> dict:
    """CSS custom-property values (no leading `$`) for `theme_name` --
    always returns a complete dict, falling back to the default's
    (`instrument` since 3.3.15.0 R4, `claude-dark` before) palette for an
    unrecognized name rather than raising (a stale/typo'd
    theme must never crash startup, matching `halo_harness.theme`'s own
    fallback philosophy)."""
    if not is_valid_theme(theme_name):
        theme_name = DEFAULT_THEME
    tokens = registry.tokens(theme_name) or registry.tokens(DEFAULT_THEME)
    return {var: tokens[token] for var, token in TOKEN_FOR}


MODE_GLYPHS = {
    "default": "⏸ manual", "acceptEdits": "⏩ accept edits",
    "plan": "\U0001f4dd plan", "auto": "⏩ auto",
    "dontAsk": "⏩ don't ask", "bypassPermissions": "⚠ bypass",
}


def mode_glyph(mode: str) -> str:
    return MODE_GLYPHS.get(mode, mode or "?")
