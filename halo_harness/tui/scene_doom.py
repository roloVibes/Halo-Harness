"""halo_harness.tui.scene_doom -- the DOOM theme's level (Halo 3.0.2.0,
third generation): a tech base, sixteen pixels tall, under a black ceiling
with a red hell-glow at the floor and embers rising through it. Far arches
creep by, ceiling lamps breathe light onto the grating, pipes run along
the top, blinking panels, barrels, steel pillars and a rusted door pass at
ground speed. The marine in green armour (14 x 14: helmet with a visor
glare, the shotgun held level) runs a six-frame stride and fires every
half second while the model writes -- a two-frame muzzle flash that lights
the walls, a recoil, a shell casing arcing back over his shoulder. He pumps
the shotgun while the model thinks as an imp stalks in throwing fireballs
that trail light; a hunched husk shambles by in the writing phase; a
fireball lands on an error (the marine flinches red); the helmet lamp
lights when it needs you. The imp collapses when a sub-agent finishes, a
health bonus bobs when a job completes. Original art in the spirit of
1993, nothing copied from any game. See tui/scene.py.
"""

from __future__ import annotations

from halo_harness.tui.scene import Flash, Layer, Mover, Particle, Scene, Shot, register_scene
from halo_harness.tui.scene_fx import gradient

COLORS = {
    "G": "#5fa84f", "J": "#8fd07a", "D": "#2f6f2a", "S": "#e0b080", "K": "#141414", "W": "#c8c8d0",
    "Y": "#ffe14d", "F": "#ff8c1a", "R": "#ff4040", "B": "#9b5b2a", "T": "#6a6a72", "L": "#9ea0a8",
    "M": "#3c3c44", "E": "#3f8f3f", "X": "#c0392b", "U": "#7a5230", "P": "#4080ff", "N": "#fff0a0",
    "A": "#1e1c22", "H": "#7a7a84", "V": "#cfd4e0", "Q": "#2a2a30", "C": "#6e6a60", "I": "#3a3a40",
}

# -- the marine, 14 wide --------------------------------------------------------
_HELMET = ("....GGGGGG....", "...GGJJGGGG...", "...GSSSSSG....", "...GSKSKSG....", "....SSSSS.....")
_ARMS = ((".GGGGGGGGGLLLL", "GGJGGGGGGGWWWW", ".GGGGGGGG.....", "..GgGGGGgG...."),   # gun level
         (".GGGGGGGGLLLL.", "GGJGGGGGGWWWW.", ".GGGGGGGG.....", "..GgGGGGgG...."),   # recoil
         (".GGGGGGGGGLLL.", "GGJGGGGGGGWWWW", ".GGGGGGGGW....", "..GgGGGGgG...."))   # pump
_LEGS = (("...DDDDDD.....", "...DDD.DDD....", "...KKK.KKK....", "..KKKK.KKKK..."),   # contact
         ("...DDDDDD.....", "...DDDDD......", "...KKKDD......", "..KKKK.KKK...."),   # pass
         ("...DDDDDD.....", "..DDD...DDD...", ".KKK.....KKK..", "KKKK.....KKK.."),   # stride
         ("...DDDDDD.....", "....DDDD......", "....KKKK......", "...KKKKK......"),   # tuck
         ("...DDDDDD.....", "..DDD...DDD...", "KKK.......KKK.", "KKKK.....KKKK."),   # stride
         ("...DDDDDD.....", "...DDDDD......", "...KK..KKK....", "..KKK...KKK..."))   # pass
_STAND = _HELMET + _ARMS[0] + _LEGS[0]
_RUN = tuple(_HELMET + _ARMS[(1, 1, 0, 0, 1, 1)[i]] + _LEGS[i] for i in range(6))
_PUMP = (_HELMET + _ARMS[0] + _LEGS[0], _HELMET + _ARMS[2] + _LEGS[0], _HELMET + _ARMS[2] + _LEGS[0], _HELMET + _ARMS[0] + _LEGS[0])
_HIT = ("....RRRRRR....", "...RRRRRRRR...", "...RSSSSSR....", "...RSRSRSR....", "....SSSSS.....",
        ".RRRRRRRRRLLLL", "RRRRRRRRRRWWWW", ".RRRRRRRR.....", "..RrRRRRrR....") + _LEGS[0]
_LAMP = ("....GGYYGG....", "...GGYYYYGG...", "...GSSSSSG....", "...GSKSKSG....", "....SSSSS.....") + _ARMS[0] + _LEGS[0]
HERO = {
    "idle": (_STAND, _HELMET + _ARMS[2] + _LEGS[0]),
    "writing": _RUN,
    "thinking": _PUMP,
    "error": (_HIT,),
    "needs_you": (_LAMP, _STAND),
}
MUZZLE = Flash(frames=(("...YY", "..YFY", ".YFFY", "YFFFY", ".YFFY", "..YFY", "...YY"),
                       ("..Y..", ".YFY.", "YFFFY", ".YFY.", "..Y..")),
               every=4, x=0, y=5, light=("#ffe14d", 8))
CASING = Shot(frames=(("y",), ("Y",)), speed=1, every=4, life=9, y=8, dx=-1, vy=1.6, gravity=0.22)
PELLETS = Shot(frames=(("WW",), ("w.",)), speed=7, every=4, life=7, y=6, dx=1)   # the shot itself, fast and short

# -- the enemies ---------------------------------------------------------------
# The imp, 12 x 12: horns, red eyes, brown hide with spines; walks, then throws.
_IMP_TOP = ("B.........B.", ".B..BBBB..B.", "..BBBBBBBB..", "..BBRBBRBB..", "..BBBBBBBB..", "...BbBBbB...")
IMP = Mover(frames=(_IMP_TOP + ("BBBBBBBBBBB.", "B.BBBBBBB.B.", "..BBBBBBB...", "..BBB.BBB...", "..BB...BB...", "..bb...bb..."),
                    _IMP_TOP + ("BBBBBBBBBBB.", "B.BBBBBBB.B.", "..BBBBBBB...", "...BBBBB....", "...BB.BB....", "...bb.bb...."),
                    _IMP_TOP + ("BBBBBBBBBBB.", "B.BBBBBBB.B.", "..BBBBBBB...", "..BBB.BBB...", ".BB.....BB..", ".bb.....bb.."),
                    _IMP_TOP + ("FBBBBBBBBBB.", "FBBBBBBBBBB.", "..BBBBBBB...", "..BBB.BBB...", "..BB...BB...", "..bb...bb...")),
            phases=frozenset({"thinking"}), speed=1, y=0,
            shot=Shot(frames=(("fFFF", "FYYf"), ("FFFf", "fYYF")), speed=3, every=12, life=22, y=7, dx=-1, light=("#ff8c1a", 5)))
# A hunched husk, 10 x 12: grey skin, torn brown fatigues, a rifle dragged along.
HUSK = Mover(frames=(("...HHHH...", "..HHKHKH..", "...HHHH...", "..CCCCCC..", ".CCCCCCCC.", "HCCCCCCCC.", "..CCCCCC..",
                      "..UUUUUU..", "..UUU.UUU.", "..UU...UU.", "..KK...KK.", ".KKK...KKK"),
                     ("...HHHH...", "..HHKHKH..", "...HHHH...", "..CCCCCC..", ".CCCCCCCC.", "HCCCCCCCC.", "..CCCCCC..",
                      "..UUUUUU..", "...UUUUU..", "...UU.UU..", "...KK.KK..", "..KKK.KKK.")),
             phases=frozenset({"writing"}), speed=1, y=0)

# -- scenery -------------------------------------------------------------------
ARCH = ("MMMMMMMMMMMM", ".mmmmmmmmmm.", "..mAAAAAAm..", "..mAAAAAAm..", "..mAAAAAAm..", "..mAAAAAAm..", "..mAAAAAAm..",
        "..mAAAAAAm..", "..mAAAAAAm..", "..mAAAAAAm..", "..mAAAAAAm..")
PIPES = ("TTTTTTTTTTTTTTTTTTTTTTTT", "ttttIIIIttttttttIIIItttt", "....tttt........tttt....")
LAMP = ("NNNNN", ".nTn.")
PILLAR = ("TLLLT", "TmmmT", "TLLLT", "TmmmT", "TLLLT", "TmmmT", "TLLLT", "TmmmT", "TLLLT", "TmmmT")
PANEL_A = ("TTTTTT", "TRGPGT", "TttttT", "TVVVVT", "TTTTTT")
PANEL_B = ("TTTTTT", "TGRPRT", "TttttT", "TvvvvT", "TTTTTT")
BARREL = ("EEEEE", "EXXXE", "EXkXE", "EXXXE", "EEEEE", "eEEEe")
DOOR = ("UUUUUUUUU", "UuuuuuuuU", "UuLLLLLuU", "UuLLLLLuU", "UuLlLlLuU", "UuLLLLLuU", "UuLLLLLuU", "UuLLLLLuU", "UuuuuuuuU",
        "uuuuuuuuu")
EMBER = (("f",), ("F",), ("f",), ("x",))

LAYERS = (
    Layer(sprites=(ARCH,), spacing=41, speed=0.3, y=0),
    Layer(sprites=(PIPES,), spacing=24, speed=0.7, y=13),
    Layer(sprites=(LAMP,), spacing=37, speed=1.0, y=11, twinkle=7, light=("#fff0a0", 10), flicker=2),
    Layer(sprites=(DOOR,), spacing=139, speed=1.0, y=0),
    Layer(sprites=(PILLAR, BARREL, PANEL_A, PILLAR, PANEL_B), spacing=43, speed=1.0, y=0, animate=6),
)
PARTICLES = (
    Particle(frames=EMBER, every=3, life=26, anchor="world", y=0, spread_y=2, dx=0.15, vy=0.45, light=("#ff8c1a", 1)),
)

GROUND = (("TLTTTTLTTTTL", "MmMMMMmMMMMm", "KKxKKKKxKKKK"),)

CUES = {   # the imp goes down in four frames; the health bonus bobs
    "agent_done": (_IMP_TOP + ("BBBBBBBBBBB.", "B.BBBBBBB.B.", "..BBBBBBB...", "..BBB.BBB...", "..BB...BB...", "..bb...bb..."),
                   ("B.........B.", ".B..BBBB..B.", "..BBRBBRBB..", "..BBBBBBBB..", "BBBBBBBBBBB.", "..BBBBBBB...", "..BBBBBBB...", "..bbb.bbb..."),
                   ("............", "B..BBBBBB.B.", "..BBRBBRBBB.", "BBBBBBBBBBB.", "..bbbbbbb..."),
                   ("B.BBBBBBBBB.", "BBBRBBRBBBB.", "bbbbbbbbbbbb"),
                   ("B.BBBBBBBBB.", "BBBRBBRBBBB.", "bbbbbbbbbbbb")),
    "job_done": ((".PP.", "PWWP", "PWWP", ".PP."), (".PP.", "PWwP", "PwWP", ".PP.")),
}
CUE_RISE = {"agent_done": (0,), "job_done": (0, 1, 2, 2, 1, 0)}

ASCII = {
    "hero": (" n ", "[o]", "/|==", "|||", "/ \\"),
    "mover": ("v v", "(x)", "/|\\", "/ \\"),
    "tile": ("[#]", "[#]", "[#]", "[#]", "[#]"),
    "ground": ("#",),
}

DOOM = Scene(
    name="doom", colors=COLORS, ground=GROUND, hero=HERO, ascii=ASCII, hero_x=16,
    layers=LAYERS, mover=IMP, movers=(HUSK,), cues=CUES, cue_rise=CUE_RISE, scroll_phases=frozenset({"writing"}),
    sky=gradient("#0e0c0a", "#3e0e0b"), flash=MUZZLE, hero_shot=PELLETS, hero_eject=CASING, particles=PARTICLES,
    hero_light=("#ffe14d", 5), hero_light_phases=frozenset({"needs_you"}),
)
register_scene(DOOM)
