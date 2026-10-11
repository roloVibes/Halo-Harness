"""halo_harness.tui.widgets.scene_band -- the level band (Halo 2.0.11
round A3): three rows directly above the prompt that draw the active game
theme's `Scene` (tui/scene.py) and animate it with the turn.

The band owns one self-rescheduling timer: `LIVE_STEP_S` between frames
while the status bar's phase is live (the hero runs, the ground scrolls,
the enemy crosses), `IDLE_STEP_S` otherwise (a slow idle blink). The phase
is the HUD's face state (`hud.face_state_for` over the status bar's own
phase/error/needs-you), so the band and the HUD face always agree. Cues
(`fire_cue`, the same events the HUD gets) show the scene's cue sprite
beside the hero for `CUE_SECONDS`.

Visibility is decided here, every tick and on resize: a scene exists for
the theme, `theme_scene` is on (`/level`, `~/.halo/config.json`), the
terminal is at least `MIN_ROWS` x `MIN_COLS`, and no pending card is
docked (a card can take twelve rows; the band yields to it).
"""

from __future__ import annotations

import time

from textual.widgets import Static

from halo_harness.tui.scene import render_scene, scene_for

LIVE_STEP_S = 0.25
IDLE_STEP_S = 1.0
CUE_SECONDS = 2.0
MIN_ROWS = 30
MIN_COLS = 60
_LIVE = frozenset({"thinking", "writing", "tool", "waiting", "running", "compacting"})


def scene_enabled() -> bool:
    """`theme_scene` in ~/.halo/config.json, on by default (`/level`)."""
    from halo_harness.theme import get_config_value
    return bool(get_config_value("theme_scene", True))


class SceneBand(Static):
    def __init__(self) -> None:
        super().__init__("", id="scene-band", markup=False)
        self.scene = None
        self.variant = ""
        self.frame = 0
        self.scroll = 0
        self._timer = None
        self._cue = ""
        self._cue_until = 0.0
        self.display = False

    # -- theme ---------------------------------------------------------------

    def set_theme(self, theme: str, variant: str = "") -> None:
        self.scene = scene_for(theme) if scene_enabled() else None
        self.variant = variant or ""
        self.frame = self.scroll = 0
        self._cue = ""
        self._sync_visibility()
        self._refresh_band()
        self._arm()

    # -- phase -----------------------------------------------------------------

    def _bar(self):
        return getattr(self.app, "status_bar", None)

    def phase_state(self) -> str:
        from halo_harness.tui.hud import face_state_for
        bar = self._bar()
        if bar is None:
            return "idle"
        return face_state_for(bar.phase, error=bool(getattr(bar, "error", "")),
                              needs_you=bool(getattr(bar, "needs_you_count", 0)))

    def is_live(self) -> bool:
        bar = self._bar()
        return bar is not None and bar.phase in _LIVE

    # -- cues ------------------------------------------------------------------

    def fire_cue(self, event: str) -> bool:
        if self.scene is None or event not in self.scene.cues:
            return False
        self._cue = event
        self._cue_until = time.monotonic() + CUE_SECONDS
        self._refresh_band()
        return True

    # -- timer -----------------------------------------------------------------

    def on_mount(self) -> None:
        self._arm()

    def pause(self) -> None:
        """Stop the timer (a capture or a test wants a still frame)."""
        self._frozen = True
        if self._timer is not None:
            self._timer.stop()
            self._timer = None

    def freeze(self, frame: int, scroll: int, cue: str = "") -> None:
        """A still at exactly this animation state: stops the timer, sets
        the frame, the scroll and an optional cue, and redraws."""
        self.pause()
        self.frame, self.scroll, self._cue = frame, scroll, cue
        self._cue_until = float("inf") if cue else 0.0
        self._sync_visibility()
        self._refresh_band()

    def _arm(self) -> None:
        if self._timer is not None:
            self._timer.stop()
            self._timer = None
        if self.scene is None or not self.is_mounted or getattr(self, "_frozen", False):
            return
        self._timer = self.set_timer(LIVE_STEP_S if self.is_live() else IDLE_STEP_S, self._tick)

    def _tick(self) -> None:
        self._timer = None
        if self.scene is None:
            return
        self.frame += 1
        state = self.phase_state()
        if state in self.scene.scroll_phases:
            self.scroll += 2
        if self._cue and time.monotonic() >= self._cue_until:
            self._cue = ""
        self._sync_visibility()
        self._refresh_band()
        self._arm()

    # -- visibility and drawing ------------------------------------------------

    def _sync_visibility(self) -> None:
        app = self.app
        size = getattr(app, "size", None)
        rows = getattr(size, "height", 0) or 0
        cols = getattr(size, "width", 0) or 0
        pending = None
        try:
            pending = app.query_one("#pending-dock")
        except Exception:
            pass
        show = (self.scene is not None and rows >= MIN_ROWS and cols >= MIN_COLS
                and not (pending is not None and pending.display))
        if show != self.display:
            self.display = show

    def on_resize(self) -> None:
        self._sync_visibility()
        self._refresh_band()

    def _refresh_band(self) -> None:
        if self.scene is None or not self.display:
            return
        bar = self._bar()
        ascii_mode = getattr(bar, "hud_ascii", None) if bar is not None else None
        if ascii_mode is None:
            from halo_harness.theme import supports_truecolor
            ascii_mode = not supports_truecolor()
        try:
            bg = self.app.get_css_variables().get("bridge-bg", "#000000")
        except Exception:
            bg = "#000000"
        width = self.size.width or getattr(getattr(self.app, "size", None), "width", 0) or 80
        self.update(render_scene(self.scene, width, phase=self.phase_state(), frame=self.frame,
                                 scroll=self.scroll, ascii_mode=bool(ascii_mode), cue=self._cue, bg=bg,
                                 variant=self.variant))
