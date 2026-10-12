"""halo_harness.tui.scene_alien -- the Alien theme's level (Halo 3.0.2.0):
the ribbed corridor of a deep-space freighter, or the resin of a hive.
Far bulkheads creep by, chains sway, consoles blink green, steam rises
from the floor vents, an airlock and the eggs pass at ground speed. The
officer in a beige jumpsuit (12 x 13: dark hair, the flamethrower held
level) runs a six-frame stride and torches the dark while the model
writes -- jets of flame that light the ribs; the motion tracker pings in
her hand while the model thinks as the creature (18 x 13: the long smooth
head, the tail) stalks in; a facehugger scuttles by in the writing phase
and latches on in an error; the flashlight comes on when it needs you.
Acid splashes when a sub-agent finishes, the ship's cat sits down when a
job completes. Original art in the spirit of the film, nothing copied.
See tui/scene.py.
"""

from __future__ import annotations

from halo_harness.tui.scene import Flash, Layer, Mover, Particle, Scene, Shot, register_scene
from halo_harness.tui.scene_fx import gradient

COLORS = {
    "K": "#0a0c10", "M": "#2a3038", "L": "#4a525e", "H": "#8a95a8", "G": "#58ff7a", "S": "#e8c8a8",
    "B": "#c8b89a", "D": "#3a2a20", "F": "#ff8c1a", "Y": "#ffe14d", "R": "#ff3a3a", "A": "#9cff3a",
    "P": "#d8a090", "W": "#e8ecf0", "T": "#30c0b0", "N": "#b8c0c8", "X": "#3a2a18", "V": "#1a1e24",
    "C": "#e89040", "Q": "#11161c", "I": "#1e242c", "E": "#5a4a3a",
}

# -- the officer, 12 wide --------------------------------------------------------
_HAIR = ("...DDDDDD...", "..DDDDDDDD..")
_FACE = ("..DSSSSSSD..", "..DSKSSKSD..", "...SSSSSS...")
_ARMS = ((".BBBBBBBBLLL", "SBBBbBBBMMMM", ".BBBBBBBBB.."),     # flamethrower level
         (".BBBBBBBBLL.", "SBBBbBBBMMM.", ".BBBBBBBBB.."),     # recoil
         (".BBBBBBBBB..", "SBBBbBBBBTT.", ".BBBBBBBBB.."))     # the tracker held up
_WAIST = ("..BbBBBBbB..",)
_LEGS = (("..BBB..BBB..", "..BBB..BBB..", "..KKK..KKK.."),   # contact
         ("..BBBBB.....", "..BBBB......", "..KKK.KKK..."),   # pass
         (".BBB....BBB.", "BBB......BBB", "KKK......KKK"),   # stride
         ("...BBBB.....", "...BBBB.....", "..KKKKK....."),   # tuck
         (".BBB....BBB.", "BB........BB", "KKK......KKK"),   # stride
         ("..BBBBB.....", "..BB..BB....", "..KKK..KKK.."))   # pass
_STAND = _HAIR + _FACE + _ARMS[0] + _WAIST + _LEGS[0]
_RUN = tuple(_HAIR + _FACE + _ARMS[(1, 0, 0, 1, 0, 0)[i]] + _WAIST + _LEGS[i] for i in range(6))
_TRACK = (_HAIR + _FACE + _ARMS[2] + _WAIST + _LEGS[0], _HAIR + _FACE + (".BBBBBBBBB..", "SBBBbBBBBTG.", ".BBBBBBBBB..") + _WAIST + _LEGS[0])
_HUGGED = ("...DDDDDD...", "..DDDDDDDD..", "..DPPPPPPD..", "..PPPPPPPP..", ".PPPPPPPPPP.", ".P.BBBBBB.P.", ".P.BBBBBBLLL", "P.BBbBBBMMMM",
           "..BBBBBBBBB.") + _WAIST + _LEGS[0]
_TORCH = _HAIR + _FACE + (".BBBBBBBBWYY", "SBBBbBBBMMMM", ".BBBBBBBBB..") + _WAIST + _LEGS[0]
HERO = {
    "idle": (_STAND, _HAIR + _FACE + _ARMS[1] + _WAIST + _LEGS[0]),
    "writing": _RUN,
    "thinking": _TRACK,
    "error": (_HUGGED,),
    "needs_you": (_TORCH, _TORCH, _STAND),
}
FLAME = Flash(frames=(("..YFF...", ".YFFFFF.", "YFFFFFFF", ".YFFFFF.", "..YFF..."), ("...YF...", ".YFFFF..", "YFFFFFF.", ".YFFFF..", "...YF...")),
              every=3, x=0, y=5, light=("#ff8c1a", 8))
FIRE = Shot(frames=(("FF", "fF"), ("Ff", "FF"), ("f.", ".f")), speed=3, every=3, life=11, y=5, dx=1, vy=0.3, light=("#ffb040", 3))

# -- the creatures -----------------------------------------------------------------
# The xenomorph, 24 x 13: the long smooth dome swept back over the
# shoulders, a lipless mouth of teeth, ribbed arms, a bladed tail curling
# behind. Dark grey over black, a highlight along the dome.
_XENO = ("..............HHHHHHHHHH", "...........LLLLLLLLLLLLH", "..........LLLHLLLLLLLLL.", ".........LLLLWWWWWLLL...",
         "........LLLLKLLLLLL.....", ".......LLLHLLLLL........", "......LLLLLLLLL.........", "L....LLLKLLLLLL.........",
         "LL..LLLLLLLKLLL.........", ".LLLLLLHLLLLLL..........")
XENO = Mover(frames=(_XENO + ("...LLLLLLL..LLL.........", "..LLL....LLL..LL........", "..LL......LL...L........"),
                     _XENO + ("...LLLLLLL..LLL.........", "....LLL..LLL..LL........", "...LL.....LL...L........"),
                     _XENO + ("...LLLLLLL..LLL.........", ".LLL.....LLL..LL........", ".LL.......LLL..L........")),
             phases=frozenset({"thinking", "writing"}), speed=1, y=0)
# A facehugger, 10 x 5: a pale crab with a whipping tail.
HUGGER = Mover(frames=(("..PPPPPP..", ".PPPPPPPP.", "PP.P.P.P.P", "P.P.P.P.PP", "......P..."),
                       ("..PPPPPP..", ".PPPPPPPP.", "P.P.P.P.PP", "PP.P.P.P.P", "....P.....")),
               phases=frozenset({"writing"}), speed=2, y=0)

# -- scenery -----------------------------------------------------------------------
RIB = (".LLLLLLLLLL.", "LLHLLLLLLHLL", "LL........LL", "LL........LL", "LL........LL", "LM........ML", "LM........ML",
       "LM........ML", "LM........ML", "LM........ML", "LM........ML", "LM........ML", "LM........ML", "MM........MM")
BULKHEAD = ("IIIIIIIIIIIIIIII", "IIIIIIIIIIIIIIII", "IIIIQQQQQQQQIIII", "IIIIQQQQQQQQIIII", "IIIIQQQQQQQQIIII", "IIIIQQQQQQQQIIII",
            "IIIIIIIIIIIIIIII", "IIIIIIIIIIIIIIII")
CHAIN = ("H", "h", "H", "h", "H", "h")
CONSOLE_A = ("MMMMMM", "MGGTGM", "MggtgM", "MMMMMM", "MMMMMM")
CONSOLE_B = ("MMMMMM", "MTGGGM", "MtgggM", "MMMMMM", "MMMMMM")
AIRLOCK = ("LLLLLLLLL", "LMMMMMMML", "LMLWWWLML", "LMLWWWLML", "LMMMMMMML", "LMLLLLLML", "LMLLLLLML", "LMMMMMMML", "LLLLLLLLL")
VENT = ("VVVVVV", "VvVvVv")
EGG = ("..XX..", ".XAAX.", ".XXXX.", "XXXXXX", "XXXXXX")
STEAM = (("n",), ("N",), ("NN",), ("n.",))
PING = (("G",), ("g",), ("G",))

LAYERS = (
    Layer(sprites=(BULKHEAD,), spacing=61, speed=0.3, y=2),
    Layer(sprites=(RIB,), spacing=41, speed=1.0, y=0),
    Layer(sprites=(CHAIN,), spacing=29, speed=0.8, y=8, twinkle=0),
    Layer(sprites=(CONSOLE_A, CONSOLE_B), spacing=73, speed=1.0, y=0, animate=5, light=("#58ff7a", 4), flicker=3),
    Layer(sprites=(AIRLOCK,), spacing=167, speed=1.0, y=0),
    Layer(sprites=(VENT, EGG, VENT), spacing=53, speed=1.0, y=0),
)
PARTICLES = (
    Particle(frames=STEAM, every=4, life=18, anchor="world", y=1, spread_y=2, dx=0.1, vy=0.4),
    Particle(frames=PING, every=4, life=8, anchor="hero", x=11, y=8, spread_x=1, dx=0.3, vy=0.3,
             phases=frozenset({"thinking"}), light=("#58ff7a", 4)),
)

GRATE = (("LMLLLLMLLLLM", "MKMMMMKMMMMK", "KKKKKKKKKKKK"),)
RESIN = (("XxXXXXxXXXXx", "xXxxxxXxxxxX", "xxxxxxxxxxxx"),)

CUES = {
    "agent_done": ((".A.", "AAA", ".A."), ("A.A", ".A.", "A.A"), ("A...A", ".....", "A...A")),
    "job_done": ((".CC...", ".CCCC.", "CCCCC.", ".CCCCC", ".C.C.."), (".CC...", ".CCCC.", "CCCCC.", ".CCCC.", ".C.CC.")),
}
CUE_RISE = {"agent_done": (0, 2, 4, 5), "job_done": (0,)}

ASCII = {
    "hero": (" o ", "(=)=", "/|\\", "|||", "/ \\"),
    "mover": ("__/", "(x)", "/^\\"),
    "tile": ("||", "||", "||", "||"),
    "ground": ("#",),
}

VARIANTS = {
    "nostromo": {},
    "hive": {"I": "#2a1c0e", "Q": "#1a1008", "L": "#4a3a28", "M": "#2e2418", "H": "#7a6a50", "V": "#1e1810"},
}
SKIES = {
    "nostromo": gradient("#0b1016", "#1c2630"),
    "hive": gradient("#0e0c08", "#2a1c0e"),
}

ALIEN = Scene(
    name="alien", colors=COLORS, ground=GRATE, hero=HERO, ascii=ASCII, hero_x=16,
    layers=LAYERS, mover=XENO, movers=(HUGGER,), cues=CUES, cue_rise=CUE_RISE, scroll_phases=frozenset({"writing"}),
    variants=VARIANTS, sky=SKIES["nostromo"], skies=SKIES, grounds={"hive": RESIN}, flash=FLAME, hero_shot=FIRE,
    particles=PARTICLES, hero_light=("#ffe8a0", 7), hero_light_phases=frozenset({"needs_you"}),
)
register_scene(ALIEN)
