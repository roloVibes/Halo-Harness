"""halo_harness.tui.scene_metroid -- the Metroid theme's level (Halo 2.0.11
round A3): a hunter in a power suit with an arm cannon running through a
cavern of rock pillars, hatches and stalactites; a floating alien drifts
in while the model thinks and latches on when a turn errors; an energy
tank when a sub-agent finishes, a missile pickup when a job completes.
The ground follows the area: rock in Crateria, growth in Brinstar, lava
in Norfair, water in Maridia, machine floor in Tourian. Original art in
the spirit of the 8-bit caverns; nothing here is copied from any game.
"""

from __future__ import annotations

from halo_harness.tui.scene import Layer, Mover, Scene, register_scene

COLORS = {
    "O": "#f28a1e", "V": "#5de06a", "A": "#9aa3b0", "H": "#d93a3a", "E": "#ffb020",
    "G": "#7df27d", "R": "#e33b3b", "F": "#f4f6ff", "K": "#2d2a3e", "M": "#4a4660", "B": "#3a7bd5",
    "g": "#4a4660", "k": "#302c40",
}

HERO = {
    "idle": ((".OOO.", ".OVV.", "OOOAA", ".OO..", ".O.O."),),
    "writing": ((".OOO.", ".OVV.", "OOOAA.", ".OO..", "O...O"),
                (".OOO.", ".OVV.", "OOOAAE", ".OO..", ".OO..")),
    "thinking": ((".OOO.", ".OVV.", "OOOAA", ".OO..", ".O.O."),
                 (".OOO.", ".OHH.", "OOOAA", ".OO..", ".O.O.")),
    "error": ((".GGG.", "GRGRG", "OOOAA", ".OO..", ".O.O."),),
    "needs_you": ((".OOO.", ".OVV.", "OOOAA", ".OO..", ".O.O."),
                  ("EEEEE", ".OVV.", "OOOAA", ".OO..", ".O.O.")),
}

ALIEN = Mover(frames=((".GGG.", "GRGRG", "GGRGG", "F.F.F"),
                      (".GGG.", "GRGRG", ".GRG.", ".F.F.")),
              phases=frozenset({"thinking"}), speed=1, y=2)

PILLAR_TALL = (".KK.", ".KM.", ".KM.", "KKMM")
PILLAR_SHORT = (".KM.", "KKMM")
HATCH = (".BB.", "BEEB", "BEEB", "BEEB")
STALACTITE = ("MMM", ".M.")

LAYERS = (
    Layer(sprites=(STALACTITE,), spacing=23, speed=1.0, y=4),
    Layer(sprites=(HATCH,), spacing=89, speed=1.0, y=0),
    Layer(sprites=(PILLAR_TALL, PILLAR_SHORT, PILLAR_SHORT), spacing=37, speed=1.0, y=0),
)

CUES = {
    "agent_done": ("EEE", "EOE", "EEE"),   # an energy tank
    "job_done": (".R.", "RRR", "FFF"),     # a missile pickup
}

ASCII = {
    "hero": (" A ", "[o]", "|||"),
    "mover": ("(o)", " ^ "),
    "tile": (" ||", " ||", "_||"),
    "ground": ("-",),
}

VARIANTS = {
    "crateria": {},
    "brinstar": {"g": "#3f8f4f", "k": "#2a5e34", "K": "#1f3a24", "M": "#356b3d"},
    "norfair": {"g": "#ff5a1a", "k": "#ffb020", "K": "#3a1a10", "M": "#6b3220"},
    "maridia": {"g": "#2b6fd6", "k": "#1a4aa0", "K": "#1a2a4a", "M": "#2f4f8a"},
    "tourian": {"g": "#6a6f78", "k": "#4a4f57", "K": "#2a2c30", "M": "#45484f"},
}

METROID = Scene(
    name="metroid", colors=COLORS, ground=("gkgg",), hero=HERO, ascii=ASCII, hero_x=8,
    layers=LAYERS, mover=ALIEN, cues=CUES, scroll_phases=frozenset({"writing"}), variants=VARIANTS,
)
register_scene(METROID)
