"""halo_harness.remote.signing_words -- the 256-word list behind the signing
secret's phrase. An original list of short, common English words (not a copy
of BIP39 or any other published list); the word's index is its byte value, so
one word carries exactly 8 bits and a 32-byte secret is 32 words."""

WORDS = (
    "acorn", "alarm", "amber", "anchor", "apple", "arrow", "atlas", "autumn",
    "badge", "baker", "balcony", "banner", "barrel", "basket", "beach", "beacon",
    "berry", "bicycle", "bishop", "blanket", "bottle", "branch", "bridge", "bronze",
    "bucket", "button", "cabin", "cactus", "camel", "candle", "canyon", "carpet",
    "castle", "cedar", "cellar", "cherry", "circle", "clover", "cobalt", "comet",
    "copper", "coral", "cotton", "cradle", "crystal", "curtain", "daisy", "dancer",
    "desert", "diamond", "dolphin", "dragon", "drawer", "dune", "eagle", "ember",
    "engine", "falcon", "feather", "fender", "ferry", "fiddle", "field", "finch",
    "flame", "flute", "forest", "fossil", "fountain", "galaxy", "garden", "garlic",
    "ginger", "glacier", "globe", "goblet", "granite", "grove", "guitar", "hammer",
    "harbor", "harvest", "hazel", "helmet", "heron", "hollow", "honey", "horizon",
    "island", "ivory", "jacket", "jasmine", "jungle", "kettle", "kitten", "ladder",
    "lagoon", "lantern", "lemon", "lilac", "linen", "lizard", "lumber", "magnet",
    "mango", "maple", "marble", "meadow", "melody", "mirror", "mitten", "monkey",
    "mortar", "mosaic", "mountain", "muffin", "nectar", "needle", "nickel", "noodle",
    "oasis", "ocean", "olive", "onion", "orange", "orchid", "otter", "oyster",
    "paddle", "palace", "pantry", "parrot", "pearl", "pebble", "pencil", "pepper",
    "piano", "pigeon", "pillow", "pirate", "planet", "plum", "pocket", "poppy",
    "puzzle", "quartz", "quiver", "rabbit", "radish", "raven", "ribbon", "river",
    "rocket", "saddle", "salmon", "sapphire", "scarf", "shadow", "shovel", "silver",
    "sketch", "slipper", "spider", "spruce", "square", "squirrel", "stable", "statue",
    "sunset", "swallow", "table", "tablet", "teapot", "temple", "thimble", "thistle",
    "thunder", "ticket", "timber", "tomato", "trumpet", "tulip", "tunnel", "turtle",
    "umbrella", "valley", "velvet", "violin", "walnut", "wagon", "willow", "window",
    "winter", "wizard", "wolf", "yellow", "zebra", "zephyr", "anvil", "bagel",
    "bamboo", "barley", "cheese", "cinder", "cliff", "cocoa", "crumb", "dagger",
    "ditch", "fabric", "flint", "frost", "gadget", "grape", "gravel", "hatch",
    "icicle", "jigsaw", "kernel", "lava", "lotus", "mallet", "moss", "nutmeg",
    "pasta", "pecan", "quill", "raisin", "sandal", "tassel", "tiger", "vessel",
    "wafer", "walrus", "yarn", "zipper", "almond", "bonnet", "cargo", "dewdrop",
    "ankle", "badger", "cobweb", "drizzle", "eclipse", "fennel", "gopher", "hickory",
    "jersey", "koala", "lobster", "magpie", "nettle", "parsley", "radar", "sparrow",
)

assert len(WORDS) == 256 and len(set(WORDS)) == 256, "the signing word list must be 256 distinct words"
