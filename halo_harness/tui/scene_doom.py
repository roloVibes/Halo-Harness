"""halo_harness.tui.scene_doom -- the DOOM theme's level (Halo 3.0.2.0,
second generation): a tech base under a black ceiling with a red hell-glow
at the floor. Far arches creep by, strobing ceiling lamps pool light on
the grating, steel pillars, barrels and a rusted door pass at ground
speed. The marine in green armour walks a four-frame stride and fires the
shotgun every half second while the model writes -- a muzzle flash that
lights the walls, a recoil frame, a shell casing arcing away. An imp stalks
in while the model thinks, throwing fireballs that trail light; a fireball
lands on an error (the marine flinches red); the helmet lamp blinks when
it needs you. A fallen imp when a sub-agent finishes, a health bonus when
a job completes. Original art in the spirit of 1993, nothing copied from
any game. See tui/scene.py.
"""

from __future__ import annotations

from halo_harness.tui.scene import Flash, Layer, Mover, Scene, Shot, register_scene
from halo_harness.tui.scene_fx import gradient

COLORS = {
    "G": "#5fa84f", "D": "#2f6f2a", "S": "#e0b080", "K": "#141414", "W": "#b8b8c0", "Y": "#ffe14d",
    "F": "#ff8c1a", "R": "#ff4040", "B": "#9b5b2a", "T": "#6a6a72", "L": "#9ea0a8", "M": "#3c3c44",
    "E": "#3f8f3f", "X": "#c0392b", "U": "#7a5230", "P": "#4080ff", "N": "#fff0a0", "A": "#1e1c22",
}

# The marine, 10 x 9: helmet, face, green armour, the shotgun held level to
# the right, boots. Writing frames alternate a recoil (gun back one px).
_HEAD = ("..GGGG....", ".GGGGGG...", ".GSSSSg...", "..SKSK....")
_ARMS = ((".GGGGGGWww", "GgGGGGWWWW", ".GGGGGg..."), (".GGGGGGww.", "GgGGGGWWW.", ".GGGGGg..."))
_LEGS = ((".DD..DD...", ".KK..KK..."), ("..DDDD....", "..KKKK...."), (".DD..DD...", "KK....KK.."), ("..DDDD....", "..KKKK...."))
_STAND = _HEAD + _ARMS[0] + (".DD..DD...", ".KK..KK...")
HERO = {
    "idle": (_STAND,),
    "writing": tuple(_HEAD + _ARMS[i % 2] + _LEGS[i] for i in range(4)),
    "thinking": (_STAND, _HEAD[:2] + (".GSSSSg...", "..KSKS....") + _STAND[4:]),
    "error": (("..GGGG....", ".GRRRRG...", ".RRRRRr...", "..RKRK....", ".RRRRRRWww", "RrRRRRWWWW", ".GGGGGg...", ".DD..DD...", ".KK..KK..."),),
    "needs_you": (_STAND, ("..YYYY....", ".GGGGGG...") + _STAND[2:]),
}
MUZZLE = Flash(sprite=("..YY", ".YFY", "YFFY", ".YFY", "..YY"), every=4, x=0, y=4, light=("#ffe14d", 7))
CASING = Shot(frames=(("y",), ("Y",)), speed=2, every=4, life=5, y=6, dx=1)

# The imp, 8 x 8: horns, red eyes, brown hide; walks, then throws.
IMP = Mover(frames=(("B.....B.", ".BBBBB..", ".BRBRB..", ".BBBBB..", "BBbBBbB.", ".BBBBB..", ".BB.BB..", ".bb.bb.."),
                    ("B.....B.", ".BBBBB..", ".BRBRB..", ".BBBBB..", "BBbBBbB.", ".BBBBB..", "..BBB...", "..bbb..."),
                    ("B.....B.", ".BBBBB..", ".BRBRB..", "FBBBBB..", "FBbBBbB.", ".BBBBB..", ".BB.BB..", ".bb.bb..")),
            phases=frozenset({"thinking"}), speed=1, y=0,
            shot=Shot(frames=(("fFF", "FYf"), ("FFf", "fYF")), speed=3, every=12, life=22, y=4, dx=-1, light=("#ff8c1a", 4)))

ARCH = ("MMMMMMMMMM", ".mmmmmmmm.", "..mAAAAm..", "..mAAAAm..", "..mAAAAm..", "..mAAAAm..", "..mAAAAm..", "..mAAAAm..", "..mAAAAm..")
LAMP = ("NNN", "nTn")
PILLAR = ("TLLT", "TmmT", "TLLT", "TmmT", "TLLT", "TmmT", "TLLT", "TmmT")
PANEL = ("TTTT", "TRGT", "TttT", "TTTT")
BARREL = ("EEEE", "EXXE", "EEEE", "eEEe")
DOOR = ("UUUUUUU", "UuuuuuU", "UuLLLuU", "UuLLLuU", "UuLLLuU", "UuLLLuU", "UuuuuuU", "uuuuuuu")

LAYERS = (
    Layer(sprites=(ARCH,), spacing=37, speed=0.3, y=0),
    Layer(sprites=(LAMP,), spacing=31, speed=1.0, y=7, twinkle=5, light=("#fff0a0", 9)),
    Layer(sprites=(DOOR,), spacing=127, speed=1.0, y=0),
    Layer(sprites=(PILLAR, BARREL, PANEL, PILLAR), spacing=41, speed=1.0, y=0),
)

GROUND = (("TLTTTLTT", "MmMMMmMM", "KKKKKKKK"),)

CUES = {
    "agent_done": ("R....R", "BBBBBB", "bbbbbb"),   # the imp, down
    "job_done": (".P.", "PWP", ".P."),              # a health bonus
}

ASCII = {
    "hero": (" n ", "[o]", "/|==", "|||"),
    "mover": ("v v", "(x)", "/|\\"),
    "tile": ("[#]", "[#]", "[#]", "[#]"),
    "ground": ("#",),
}

DOOM = Scene(
    name="doom", colors=COLORS, ground=GROUND, hero=HERO, ascii=ASCII, hero_x=10,
    layers=LAYERS, mover=IMP, cues=CUES, scroll_phases=frozenset({"writing"}),
    sky=gradient("#12100e", "#3e0e0b"), flash=MUZZLE, hero_shot=CASING,
)
register_scene(DOOM)
