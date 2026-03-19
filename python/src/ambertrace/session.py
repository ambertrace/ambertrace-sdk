"""Human-readable session ID generation for AmberTrace SDK."""

import random
from datetime import datetime, timezone

# 256 adjectives â compact word list for readable session IDs
ADJECTIVES = [
    "amber", "azure", "bold", "brave", "bright", "calm", "clear", "cool",
    "coral", "crisp", "cyan", "dark", "deep", "dry", "dusk", "fair",
    "fast", "fine", "firm", "flat", "fond", "free", "fresh", "full",
    "glad", "gold", "good", "gray", "green", "half", "happy", "hard",
    "high", "hot", "keen", "kind", "late", "lean", "left", "light",
    "live", "long", "lost", "loud", "low", "lush", "main", "mild",
    "mint", "neat", "new", "next", "nice", "odd", "old", "open",
    "pale", "past", "pink", "plain", "prime", "pure", "quick", "quiet",
    "rare", "raw", "real", "red", "rich", "ripe", "rose", "ruby",
    "rust", "safe", "sage", "salt", "shy", "slim", "slow", "soft",
    "solid", "sour", "stark", "still", "stone", "swift", "tall", "tame",
    "thin", "tidy", "true", "vast", "warm", "west", "wide", "wild",
    "wise", "young", "zen", "acid", "airy", "arch", "ashy", "avid",
    "bare", "base", "best", "blue", "blunt", "bone", "born", "busy",
    "cold", "coy", "damp", "dear", "dense", "dim", "dire", "drab",
    "dual", "dull", "each", "easy", "edge", "epic", "even", "ever",
    "evil", "face", "fawn", "fell", "few", "fiery", "flat", "fond",
    "foul", "four", "gale", "gild", "glow", "grim", "gust", "hale",
    "hazy", "hemp", "hero", "holy", "huge", "iced", "idle", "iron",
    "jade", "just", "keen", "knit", "lace", "lake", "lame", "last",
    "lazy", "lime", "mad", "many", "mere", "mile", "mini", "mint",
    "more", "much", "mute", "near", "noon", "norm", "null", "oily",
    "once", "only", "opal", "oval", "pale", "peak", "plum", "plus",
    "posh", "primal", "proud", "quad", "rain", "rank", "rift", "rude",
    "same", "sand", "seek", "semi", "slab", "snap", "snug", "solo",
    "some", "sooty", "sore", "star", "stem", "such", "tart", "teal",
    "that", "tiny", "torn", "trim", "twin", "upon", "used", "very",
    "void", "wary", "wavy", "wiry", "worn", "zero", "zinc", "zonal",
]

# 256 nouns â animals, nature, and objects for readable session IDs
NOUNS = [
    "ant", "ape", "bat", "bear", "bee", "bird", "buck", "bull",
    "calf", "cat", "clam", "claw", "cod", "colt", "crab", "crow",
    "cub", "deer", "doe", "dog", "dove", "duck", "eagle", "eel",
    "elk", "emu", "ewe", "fawn", "fin", "fish", "flea", "fly",
    "foal", "fox", "frog", "goat", "goose", "gull", "hare", "hawk",
    "hen", "hog", "horse", "jay", "kite", "koi", "lamb", "lark",
    "lion", "lynx", "mink", "mole", "moth", "mouse", "mule", "newt",
    "owl", "ox", "paw", "pike", "pony", "puma", "quail", "ram",
    "rat", "raven", "ray", "robin", "seal", "shark", "slug", "snail",
    "swan", "toad", "trout", "vole", "wasp", "wren", "wolf", "yak",
    "ash", "bay", "birch", "bloom", "bolt", "bone", "brook", "cave",
    "clay", "cliff", "cloud", "coal", "cone", "cove", "dale", "dawn",
    "dew", "drift", "dune", "dust", "edge", "elm", "fall", "fern",
    "field", "fire", "flame", "flint", "fog", "ford", "frost", "gale",
    "gate", "gem", "glen", "grove", "hail", "haze", "heath", "hill",
    "ice", "isle", "jade", "lake", "leaf", "mist", "moon", "moss",
    "oak", "ore", "palm", "peak", "peat", "pine", "pond", "rain",
    "reef", "ridge", "rock", "root", "rose", "sage", "sand", "seed",
    "shade", "shell", "shore", "sky", "snow", "soil", "star", "stem",
    "stone", "storm", "sun", "thorn", "tide", "trail", "vale", "vine",
    "wave", "well", "wind", "wood", "arch", "axe", "bell", "blade",
    "bolt", "bow", "card", "cart", "chip", "coin", "cord", "core",
    "cube", "dial", "disc", "dome", "drum", "flag", "fork", "gear",
    "grid", "helm", "hive", "hook", "horn", "hull", "iron", "key",
    "knob", "knot", "lamp", "lane", "lens", "link", "lock", "loom",
    "mark", "mast", "mill", "mint", "nail", "nest", "node", "note",
    "oar", "orb", "pad", "page", "path", "pier", "pin", "pipe",
    "pole", "port", "rail", "ring", "rod", "rope", "rune", "sash",
    "shard", "slab", "slot", "spool", "spur", "tank", "tile", "tool",
    "torch", "trap", "tray", "tube", "vault", "veil", "wand", "ward",
    "web", "wedge", "wick", "wing", "yard", "yoke", "zone", "frame",
    "prism", "plank", "ledge", "flask", "brush", "anvil", "crest", "drift",
]


def generate_session_id() -> str:
    """Generate a human-readable, date-prefixed session ID.

    Format: YYYYMMDD-adjective-noun-NNNN
    Example: 20260318-amber-fox-7291

    Returns:
        A unique-enough human-readable session identifier.
    """
    date_str = datetime.now(timezone.utc).strftime("%Y%m%d")
    adj = random.choice(ADJECTIVES)
    noun = random.choice(NOUNS)
    suffix = random.randint(1000, 9999)
    return f"{date_str}-{adj}-{noun}-{suffix}"
