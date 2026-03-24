"""
Base ingredient catalog for the food/drink crafting system.

Every recipe starts with a base ingredient. The base determines mechanical
properties (hunger/thirst restore, alcohol strength, nutritious flag).
Players customize everything else: name, description, taste message, and
optional cosmetic flavor notes.

Station type restrictions:
  - Bars: ALCOHOL_BASES only
  - Kitchenettes: FOOD_BASES + NON_ALCOHOLIC_BASES only
"""

from world.food import SOCIAL_TIERS, get_tier_level

# ══════════════════════════════════════════════════════════════════════════════
#  FOOD BASES
# ══════════════════════════════════════════════════════════════════════════════

FOOD_BASES = {
    # ── GUTTER TIER (level 0) ─────────────────────────────────────────────────
    "scrap_pile": {
        "key": "scrap_pile",
        "name": "Scrap Pile",
        "category": "food",
        "tier": "gutter",
        "hunger_restore": 8,
        "is_nutritious": False,
        "base_desc": "Unidentifiable scraps scraped together into something technically edible.",
        "base_taste": "Your stomach accepts it. Your tongue files a complaint.",
    },
    "sewer_fungus": {
        "key": "sewer_fungus",
        "name": "Sewer Fungus",
        "category": "food",
        "tier": "gutter",
        "hunger_restore": 10,
        "is_nutritious": False,
        "base_desc": "Grey-brown fungal matter peeled from a drainage pipe.",
        "base_taste": "Earthy, damp, and faintly chemical. You try not to think about the source.",
    },
    "tunnel_rat": {
        "key": "tunnel_rat",
        "name": "Tunnel Rat",
        "category": "food",
        "tier": "gutter",
        "hunger_restore": 15,
        "is_nutritious": True,
        "base_desc": "A skinned tunnel rat, charred over an open flame.",
        "base_taste": "Gamey, oily, and stringy. Protein is protein.",
    },
    "expired_ration": {
        "key": "expired_ration",
        "name": "Expired Ration Pack",
        "category": "food",
        "tier": "gutter",
        "hunger_restore": 12,
        "is_nutritious": False,
        "base_desc": "A ration pack well past its date. The packaging is bloated.",
        "base_taste": "Stale, mealy, with an aftertaste of preservative and regret.",
    },

    # ── SLUM TIER (level 1) ───────────────────────────────────────────────────
    "ration_brick": {
        "key": "ration_brick",
        "name": "Ration Brick",
        "category": "food",
        "tier": "slum",
        "hunger_restore": 25,
        "is_nutritious": True,
        "base_desc": "A dense block of compressed calories.",
        "base_taste": "Dry, flavorless, and clings to your teeth. It does the job.",
    },
    "dried_meat": {
        "key": "dried_meat",
        "name": "Dried Meat Strip",
        "category": "food",
        "tier": "slum",
        "hunger_restore": 20,
        "is_nutritious": True,
        "base_desc": "Tough, salt-cured meat dried hard against spoilage.",
        "base_taste": "Salt and smoke flood your mouth. The meat fights every bite.",
    },
    "canned_stew": {
        "key": "canned_stew",
        "name": "Canned Stew",
        "category": "food",
        "tier": "slum",
        "hunger_restore": 35,
        "is_nutritious": True,
        "base_desc": "A battered tin of thick stew. The label is half-gone.",
        "base_taste": "Grease and peppery broth spread warmth through your throat.",
    },
    "protein_bar": {
        "key": "protein_bar",
        "name": "Protein Bar",
        "category": "food",
        "tier": "slum",
        "hunger_restore": 18,
        "is_nutritious": True,
        "base_desc": "A compact bar of pressed nuts, seeds, and synthetic binders.",
        "base_taste": "Sugary oil and crushed nuts coat your teeth in a sticky film.",
    },
    "gruel": {
        "key": "gruel",
        "name": "Gruel",
        "category": "food",
        "tier": "slum",
        "hunger_restore": 22,
        "is_nutritious": True,
        "base_desc": "A bowl of grey grain porridge. Warm. Bland. Filling.",
        "base_taste": "Like chewing wet cardboard that someone once showed a spice to.",
    },
    "tube_paste": {
        "key": "tube_paste",
        "name": "Tube Paste",
        "category": "food",
        "tier": "slum",
        "hunger_restore": 15,
        "is_nutritious": True,
        "base_desc": "A squeeze tube of nutrient paste. The label says 'chicken flavour.' It lies.",
        "base_taste": "Salty, vaguely savoury, with the consistency of wet cement.",
    },
    "moldy_bread": {
        "key": "moldy_bread",
        "name": "Stale Bread Loaf",
        "category": "food",
        "tier": "slum",
        "hunger_restore": 12,
        "is_nutritious": False,
        "base_desc": "A stale loaf with grey-green spots. It'll quiet your stomach.",
        "base_taste": "Mold and damp rot on your tongue. You swallow fast.",
    },
    "soy_cake": {
        "key": "soy_cake",
        "name": "Soy Cake",
        "category": "food",
        "tier": "slum",
        "hunger_restore": 20,
        "is_nutritious": True,
        "base_desc": "A flat, dense cake made from processed soy protein.",
        "base_taste": "Beany, chalky, faintly sweet. Edible. That's the best word.",
    },

    # ── GUILD TIER (level 2) ──────────────────────────────────────────────────
    "canteen_rice": {
        "key": "canteen_rice",
        "name": "Canteen Rice Bowl",
        "category": "food",
        "tier": "guild",
        "hunger_restore": 30,
        "is_nutritious": True,
        "base_desc": "A bowl of steamed rice with a ladle of brown sauce.",
        "base_taste": "Starchy, salty, with a hint of soy. Institutional but honest.",
    },
    "noodle_bowl": {
        "key": "noodle_bowl",
        "name": "Noodle Bowl",
        "category": "food",
        "tier": "guild",
        "hunger_restore": 32,
        "is_nutritious": True,
        "base_desc": "A bowl of wheat noodles in broth with synthetic protein strips.",
        "base_taste": "The broth is hot and salty. The noodles are soft. This is comfort.",
    },
    "meat_pie": {
        "key": "meat_pie",
        "name": "Meat Pie",
        "category": "food",
        "tier": "guild",
        "hunger_restore": 38,
        "is_nutritious": True,
        "base_desc": "A hand-sized pie with a flaky crust and dense meat filling.",
        "base_taste": "Pastry crumbles. The filling is peppery and rich. Don't ask what the meat is.",
    },
    "bean_stew": {
        "key": "bean_stew",
        "name": "Bean and Sausage Stew",
        "category": "food",
        "tier": "guild",
        "hunger_restore": 40,
        "is_nutritious": True,
        "base_desc": "A heavy bowl of beans, sausage chunks, and root vegetables in thick gravy.",
        "base_taste": "Smoky, filling, with a slow heat. This is guild-canteen at its best.",
    },
    "dumpling_plate": {
        "key": "dumpling_plate",
        "name": "Dumpling Plate",
        "category": "food",
        "tier": "guild",
        "hunger_restore": 35,
        "is_nutritious": True,
        "base_desc": "A plate of steamed dumplings with a dipping sauce.",
        "base_taste": "The wrapper is soft. The filling bursts with ginger and pork.",
    },
    "flatbread_wrap": {
        "key": "flatbread_wrap",
        "name": "Flatbread Wrap",
        "category": "food",
        "tier": "guild",
        "hunger_restore": 28,
        "is_nutritious": True,
        "base_desc": "Grilled flatbread wrapped around shredded meat and pickled vegetables.",
        "base_taste": "Smoky bread, tangy pickles, and tender shredded meat. Portable and good.",
    },
    "synth_egg_plate": {
        "key": "synth_egg_plate",
        "name": "Synthetic Egg Plate",
        "category": "food",
        "tier": "guild",
        "hunger_restore": 26,
        "is_nutritious": True,
        "base_desc": "Scrambled synthetic eggs with toast and a smear of fat.",
        "base_taste": "Close enough to real eggs that you don't mind. Rich and yellow.",
    },

    # ── BOURGEOIS TIER (level 3) ──────────────────────────────────────────────
    "roast_fowl": {
        "key": "roast_fowl",
        "name": "Roast Fowl",
        "category": "food",
        "tier": "bourgeois",
        "hunger_restore": 50,
        "is_nutritious": True,
        "base_desc": "A quarter of roasted bird, skin crisped and golden, on a bed of greens.",
        "base_taste": "Crisp skin, tender meat, and rendered fat. This is actual food.",
    },
    "grilled_fish": {
        "key": "grilled_fish",
        "name": "Grilled Fish Fillet",
        "category": "food",
        "tier": "bourgeois",
        "hunger_restore": 42,
        "is_nutritious": True,
        "base_desc": "A fillet of vat-grown fish, char-grilled and dressed with oil and herbs.",
        "base_taste": "Flaky, delicate, with a hint of char and something green and bright.",
    },
    "braised_meat": {
        "key": "braised_meat",
        "name": "Braised Meat",
        "category": "food",
        "tier": "bourgeois",
        "hunger_restore": 55,
        "is_nutritious": True,
        "base_desc": "Slow-braised meat in a deep sauce, falling apart at the touch of a fork.",
        "base_taste": "The meat dissolves on your tongue. The sauce is dark, rich, complex.",
    },
    "fresh_salad": {
        "key": "fresh_salad",
        "name": "Fresh Green Salad",
        "category": "food",
        "tier": "bourgeois",
        "hunger_restore": 20,
        "is_nutritious": True,
        "base_desc": "Actual green leaves. Hydroponic, but green and crisp and real.",
        "base_taste": "Crisp, cool, with a dressing that's sharp and bright. This is luxury.",
    },
    "pasta_plate": {
        "key": "pasta_plate",
        "name": "Pasta Plate",
        "category": "food",
        "tier": "bourgeois",
        "hunger_restore": 45,
        "is_nutritious": True,
        "base_desc": "Fresh pasta in a cream sauce with herbs and shaved hard cheese.",
        "base_taste": "The pasta is soft and yielding. The sauce coats your mouth in cream and salt.",
    },
    "cheese_board": {
        "key": "cheese_board",
        "name": "Cheese Board",
        "category": "food",
        "tier": "bourgeois",
        "hunger_restore": 30,
        "is_nutritious": True,
        "base_desc": "A wooden board with three types of cheese, dried fruit, and crackers.",
        "base_taste": "Sharp, creamy, and nutty in turns. Each bite is different.",
    },
    "soup_du_jour": {
        "key": "soup_du_jour",
        "name": "Chef's Soup",
        "category": "food",
        "tier": "bourgeois",
        "hunger_restore": 35,
        "is_nutritious": True,
        "base_desc": "A bowl of the day's soup — whatever the kitchen had that was fresh.",
        "base_taste": "Warm, layered, with depth. Someone cared about this.",
    },

    # ── ELITE TIER (level 4) ──────────────────────────────────────────────────
    "wagyu_steak": {
        "key": "wagyu_steak",
        "name": "Vat-Grown Wagyu",
        "category": "food",
        "tier": "elite",
        "hunger_restore": 60,
        "is_nutritious": True,
        "base_desc": "A thick-cut steak, marbled white and red, seared and resting in its own juices.",
        "base_taste": "The fat melts. The meat is butter. You understand why wars are fought over cattle genes.",
    },
    "truffle_risotto": {
        "key": "truffle_risotto",
        "name": "Truffle Risotto",
        "category": "food",
        "tier": "elite",
        "hunger_restore": 50,
        "is_nutritious": True,
        "base_desc": "Creamy rice studded with shaved truffle. The aroma fills the room.",
        "base_taste": "Earthy, umami, impossibly rich. Every grain of rice is perfect.",
    },
    "sashimi_plate": {
        "key": "sashimi_plate",
        "name": "Sashimi Plate",
        "category": "food",
        "tier": "elite",
        "hunger_restore": 40,
        "is_nutritious": True,
        "base_desc": "Paper-thin slices of raw fish on a lacquered plate. Each piece is a different colour.",
        "base_taste": "Clean, cold, ocean-bright. The wasabi blooms in your sinuses.",
    },
    "molecular_course": {
        "key": "molecular_course",
        "name": "Molecular Gastronomy Course",
        "category": "food",
        "tier": "elite",
        "hunger_restore": 35,
        "is_nutritious": True,
        "base_desc": "A tiny plate of spherified liquids, foams, and gels that look like art.",
        "base_taste": "Flavours that shouldn't exist together but do. The texture shifts mid-bite.",
    },
    "garden_tasting": {
        "key": "garden_tasting",
        "name": "Garden Tasting Menu",
        "category": "food",
        "tier": "elite",
        "hunger_restore": 45,
        "is_nutritious": True,
        "base_desc": "Five courses of vegetables from the Apex's private gardens. Each one is a different green.",
        "base_taste": "You forgot vegetables could taste like this. Sweet, bitter, alive.",
    },
}

# ══════════════════════════════════════════════════════════════════════════════
#  NON-ALCOHOLIC DRINK BASES
# ══════════════════════════════════════════════════════════════════════════════

NON_ALCOHOLIC_BASES = {
    # ── GUTTER ────────────────────────────────────────────────────────────────
    "puddle_water": {
        "key": "puddle_water",
        "name": "Puddle Water",
        "category": "drink",
        "tier": "gutter",
        "thirst_restore": 15,
        "is_nutritious": False,
        "base_desc": "Water scooped from a low point in the tunnel floor. Brownish.",
        "base_taste": "Gritty, metallic, and warm. You try not to look at what's floating in it.",
    },
    "pipe_drip": {
        "key": "pipe_drip",
        "name": "Pipe Drip",
        "category": "drink",
        "tier": "gutter",
        "thirst_restore": 20,
        "is_nutritious": False,
        "base_desc": "Condensation collected from an overhead pipe into a jar.",
        "base_taste": "Cool, faintly chemical, cleaner than it has any right to be.",
    },

    # ── SLUM ──────────────────────────────────────────────────────────────────
    "recycled_water": {
        "key": "recycled_water",
        "name": "Recycled Water",
        "category": "drink",
        "tier": "slum",
        "thirst_restore": 30,
        "is_nutritious": False,
        "base_desc": "A cup of recycled water. Clear, mostly. A faint chlorine smell.",
        "base_taste": "Clean enough. The chlorine aftertaste reminds you it's been through the system.",
    },
    "synth_juice": {
        "key": "synth_juice",
        "name": "Synthetic Juice",
        "category": "drink",
        "tier": "slum",
        "thirst_restore": 25,
        "is_nutritious": True,
        "base_desc": "A pouch of bright orange liquid. The colour is aggressive.",
        "base_taste": "Aggressively sweet, vaguely citrus. The aftertaste is chemical.",
    },
    "stim_tea": {
        "key": "stim_tea",
        "name": "Stim Tea",
        "category": "drink",
        "tier": "slum",
        "thirst_restore": 20,
        "is_nutritious": False,
        "base_desc": "Hot water steeped with dried fungal shavings and caffeine tablets.",
        "base_taste": "Bitter, earthy, with a caffeine kick that hits behind the eyes.",
    },
    "broth_cup": {
        "key": "broth_cup",
        "name": "Cup of Broth",
        "category": "drink",
        "tier": "slum",
        "thirst_restore": 20,
        "hunger_restore": 10,
        "is_nutritious": True,
        "base_desc": "A tin cup of hot broth made from boiled bones and salt.",
        "base_taste": "Salty, savoury, and warm. It fills the empty spaces.",
    },

    # ── GUILD ─────────────────────────────────────────────────────────────────
    "filtered_water": {
        "key": "filtered_water",
        "name": "Filtered Water",
        "category": "drink",
        "tier": "guild",
        "thirst_restore": 35,
        "is_nutritious": False,
        "base_desc": "Clean filtered water in a glass. No taste, no smell. That IS the luxury.",
        "base_taste": "Clean. Just clean. You notice the absence of everything wrong.",
    },
    "canteen_coffee": {
        "key": "canteen_coffee",
        "name": "Canteen Coffee",
        "category": "drink",
        "tier": "guild",
        "thirst_restore": 25,
        "is_nutritious": False,
        "base_desc": "A mug of black coffee from the guild canteen's machine. Strong and burnt.",
        "base_taste": "Bitter, dark, and hot. The caffeine is the point. The flavour is a side effect.",
    },
    "herb_tea": {
        "key": "herb_tea",
        "name": "Herbal Tea",
        "category": "drink",
        "tier": "guild",
        "thirst_restore": 30,
        "is_nutritious": False,
        "base_desc": "A cup of dried-herb tea in a ceramic mug.",
        "base_taste": "Floral, light, with a warmth that settles your stomach.",
    },
    "soy_milk": {
        "key": "soy_milk",
        "name": "Soy Milk",
        "category": "drink",
        "tier": "guild",
        "thirst_restore": 25,
        "hunger_restore": 8,
        "is_nutritious": True,
        "base_desc": "A glass of warm soy milk. Creamy and pale.",
        "base_taste": "Beany, mild, with a slight sweetness. Comforting.",
    },

    # ── BOURGEOIS ─────────────────────────────────────────────────────────────
    "sparkling_water": {
        "key": "sparkling_water",
        "name": "Sparkling Water",
        "category": "drink",
        "tier": "bourgeois",
        "thirst_restore": 35,
        "is_nutritious": False,
        "base_desc": "Carbonated water in a glass with a slice of something green.",
        "base_taste": "Crisp, cold, fizzing. The garnish adds a whisper of citrus.",
    },
    "pressed_juice": {
        "key": "pressed_juice",
        "name": "Pressed Fruit Juice",
        "category": "drink",
        "tier": "bourgeois",
        "thirst_restore": 30,
        "is_nutritious": True,
        "base_desc": "Actual fruit, actually pressed. The colour is natural.",
        "base_taste": "Bright, sweet, with a tartness that means the fruit was real.",
    },
    "artisan_coffee": {
        "key": "artisan_coffee",
        "name": "Artisan Coffee",
        "category": "drink",
        "tier": "bourgeois",
        "thirst_restore": 25,
        "is_nutritious": False,
        "base_desc": "A small cup of dark coffee with a crema on top. It smells extraordinary.",
        "base_taste": "Chocolate, cherry, a hint of smoke. This is coffee that means something.",
    },
    "hot_chocolate": {
        "key": "hot_chocolate",
        "name": "Hot Chocolate",
        "category": "drink",
        "tier": "bourgeois",
        "thirst_restore": 25,
        "hunger_restore": 10,
        "is_nutritious": True,
        "base_desc": "Thick, dark drinking chocolate in a ceramic cup.",
        "base_taste": "Rich, bittersweet, coating your mouth in velvet. Warmth from the inside.",
    },

    # ── ELITE ─────────────────────────────────────────────────────────────────
    "mineral_spring": {
        "key": "mineral_spring",
        "name": "Mineral Spring Water",
        "category": "drink",
        "tier": "elite",
        "thirst_restore": 40,
        "is_nutritious": False,
        "base_desc": "Water from a deep mineral spring beneath the Apex. Served in crystal.",
        "base_taste": "Silky, mineral-bright, and impossibly pure. You taste the stone it came through.",
    },
    "garden_tea": {
        "key": "garden_tea",
        "name": "Garden Leaf Tea",
        "category": "drink",
        "tier": "elite",
        "thirst_restore": 30,
        "is_nutritious": False,
        "base_desc": "Tea leaves grown in the Apex gardens. Served in a porcelain cup.",
        "base_taste": "Delicate, layered. Each sip reveals something new — grass, flowers, stone.",
    },
}

# ══════════════════════════════════════════════════════════════════════════════
#  ALCOHOL BASES
# ══════════════════════════════════════════════════════════════════════════════

ALCOHOL_BASES = {
    # ── GUTTER ────────────────────────────────────────────────────────────────
    "sewer_wine": {
        "key": "sewer_wine",
        "name": "Sewer Wine",
        "category": "alcohol",
        "tier": "gutter",
        "alcohol_strength": 8.0,
        "thirst_restore": 0,
        "base_desc": "A jar of cloudy liquid fermented from fruit scraps and desperation.",
        "base_taste": "Vinegar, rot-sweetness, and a burning finish. You wince.",
    },
    "gutter_moonshine": {
        "key": "gutter_moonshine",
        "name": "Gutter Moonshine",
        "category": "alcohol",
        "tier": "gutter",
        "alcohol_strength": 25.0,
        "thirst_restore": 0,
        "base_desc": "A cloudy jar of bootleg shine. The fumes alone make your eyes water.",
        "base_taste": "Liquid fire. Your throat closes. Your eyes stream. You're drunk.",
    },

    # ── SLUM ──────────────────────────────────────────────────────────────────
    "tunnel_beer": {
        "key": "tunnel_beer",
        "name": "Tunnel-Brewed Beer",
        "category": "alcohol",
        "tier": "slum",
        "alcohol_strength": 6.0,
        "thirst_restore": 5,
        "base_desc": "A brown glass bottle of flat, tunnel-brewed beer.",
        "base_taste": "Bitter, sour, and deceptively strong. It's cold. That's the best thing.",
    },
    "rot_whiskey": {
        "key": "rot_whiskey",
        "name": "Rot Whiskey",
        "category": "alcohol",
        "tier": "slum",
        "alcohol_strength": 15.0,
        "thirst_restore": 0,
        "base_desc": "A small metal flask of distilled grain spirits. Industrial-grade.",
        "base_taste": "It burns going down. It burns sitting in your stomach. You feel warmer.",
    },
    "fungal_wine": {
        "key": "fungal_wine",
        "name": "Fungal Wine",
        "category": "alcohol",
        "tier": "slum",
        "alcohol_strength": 10.0,
        "thirst_restore": 0,
        "base_desc": "A dark, slightly luminescent liquid fermented from the Sink's mushroom crops.",
        "base_taste": "Earthy, sweet, and mushroomy. The glow fades as it hits your tongue.",
    },
    "engine_cleaner": {
        "key": "engine_cleaner",
        "name": "Engine Cleaner",
        "category": "alcohol",
        "tier": "slum",
        "alcohol_strength": 20.0,
        "thirst_restore": 0,
        "base_desc": "Nobody knows what this was before it was alcohol. It's translucent and blue.",
        "base_taste": "Sweet, chemical, with a delayed kick that hits your temples like a hammer.",
    },

    # ── GUILD ─────────────────────────────────────────────────────────────────
    "guild_lager": {
        "key": "guild_lager",
        "name": "Guild Lager",
        "category": "alcohol",
        "tier": "guild",
        "alcohol_strength": 5.0,
        "thirst_restore": 10,
        "base_desc": "A pint of pale lager from the guild brewery. Clean, cold, golden.",
        "base_taste": "Crisp, light, malty. This is beer that's actually been brewed on purpose.",
    },
    "guild_stout": {
        "key": "guild_stout",
        "name": "Guild Stout",
        "category": "alcohol",
        "tier": "guild",
        "alcohol_strength": 7.0,
        "thirst_restore": 5,
        "base_desc": "A pint of dark stout with a cream head. It smells of roasted grain.",
        "base_taste": "Coffee, chocolate, and a bitter finish. Heavy and satisfying.",
    },
    "rye_whiskey": {
        "key": "rye_whiskey",
        "name": "Rye Whiskey",
        "category": "alcohol",
        "tier": "guild",
        "alcohol_strength": 14.0,
        "thirst_restore": 0,
        "base_desc": "A measured pour of rye whiskey in a tumbler. Amber and still.",
        "base_taste": "Spicy, warm, with a caramel sweetness that lingers. This is whiskey.",
    },
    "rice_wine": {
        "key": "rice_wine",
        "name": "Rice Wine",
        "category": "alcohol",
        "tier": "guild",
        "alcohol_strength": 12.0,
        "thirst_restore": 0,
        "base_desc": "A small ceramic cup of warm rice wine.",
        "base_taste": "Smooth, faintly sweet, with a warmth that spreads from your chest.",
    },
    "vodka": {
        "key": "vodka",
        "name": "Grain Vodka",
        "category": "alcohol",
        "tier": "guild",
        "alcohol_strength": 16.0,
        "thirst_restore": 0,
        "base_desc": "A shot glass of clear vodka. No adornment. No pretence.",
        "base_taste": "Clean, sharp, with a burn that's honest about what it is.",
    },

    # ── BOURGEOIS ─────────────────────────────────────────────────────────────
    "red_wine": {
        "key": "red_wine",
        "name": "Red Wine",
        "category": "alcohol",
        "tier": "bourgeois",
        "alcohol_strength": 12.0,
        "thirst_restore": 0,
        "base_desc": "A glass of deep red wine. The colour is jewel-bright against the light.",
        "base_taste": "Dark fruit, tannin, and a long finish. This was grown, not manufactured.",
    },
    "white_wine": {
        "key": "white_wine",
        "name": "White Wine",
        "category": "alcohol",
        "tier": "bourgeois",
        "alcohol_strength": 11.0,
        "thirst_restore": 0,
        "base_desc": "A glass of pale gold wine. It catches the light like liquid topaz.",
        "base_taste": "Citrus, stone fruit, and a mineral finish. Crisp and precise.",
    },
    "aged_whiskey": {
        "key": "aged_whiskey",
        "name": "Aged Whiskey",
        "category": "alcohol",
        "tier": "bourgeois",
        "alcohol_strength": 16.0,
        "thirst_restore": 0,
        "base_desc": "A measure of whiskey aged in actual wood. The colour is deep amber.",
        "base_taste": "Vanilla, oak, smoke, and a warmth that glows. Someone waited years for this.",
    },
    "gin": {
        "key": "gin",
        "name": "Botanical Gin",
        "category": "alcohol",
        "tier": "bourgeois",
        "alcohol_strength": 14.0,
        "thirst_restore": 0,
        "base_desc": "A measure of juniper-forward gin. The botanicals are real.",
        "base_taste": "Pine, citrus, a hint of spice. The juniper blooms on your palate.",
    },
    "champagne": {
        "key": "champagne",
        "name": "Sparkling Wine",
        "category": "alcohol",
        "tier": "bourgeois",
        "alcohol_strength": 11.0,
        "thirst_restore": 0,
        "base_desc": "A flute of golden, fizzing wine. Tiny bubbles race upward.",
        "base_taste": "Toast, green apple, and a persistent fizz. Celebration in a glass.",
    },

    # ── ELITE ─────────────────────────────────────────────────────────────────
    "single_malt": {
        "key": "single_malt",
        "name": "Single Malt",
        "category": "alcohol",
        "tier": "elite",
        "alcohol_strength": 18.0,
        "thirst_restore": 0,
        "base_desc": "A dram of single malt whisky from a pre-collapse bottle. Priceless.",
        "base_taste": "Peat, honey, salt air, and a finish that lasts for minutes. History in a glass.",
    },
    "cognac": {
        "key": "cognac",
        "name": "Cognac",
        "category": "alcohol",
        "tier": "elite",
        "alcohol_strength": 16.0,
        "thirst_restore": 0,
        "base_desc": "Amber spirit in a snifter. The aroma alone is worth the price.",
        "base_taste": "Dried fruit, spice, oak, and a warmth that wraps around you. Extraordinary.",
    },
    "absinthe": {
        "key": "absinthe",
        "name": "Absinthe",
        "category": "alcohol",
        "tier": "elite",
        "alcohol_strength": 22.0,
        "thirst_restore": 0,
        "base_desc": "Green-tinted spirit served over a sugar cube. The louche clouds the glass.",
        "base_taste": "Anise, fennel, and something herbal and ancient. The world softens at the edges.",
    },
    "void_spirit": {
        "key": "void_spirit",
        "name": "Void Spirit",
        "category": "alcohol",
        "tier": "elite",
        "alcohol_strength": 30.0,
        "thirst_restore": 0,
        "base_desc": "A black liquid that absorbs the light around it. It doesn't slosh — it moves.",
        "base_taste": "There is no taste. There is an absence. Then everything floods back at once.",
    },
}

# ══════════════════════════════════════════════════════════════════════════════
#  Lookup helpers
# ══════════════════════════════════════════════════════════════════════════════

_ALL_BASES = {}
_ALL_BASES.update(FOOD_BASES)
_ALL_BASES.update(NON_ALCOHOLIC_BASES)
_ALL_BASES.update(ALCOHOL_BASES)


def get_base(key: str) -> dict | None:
    """Return the base ingredient dict for a key, or None if not found."""
    return _ALL_BASES.get(key)


def get_base_tier_level(key: str) -> int:
    """Return the numeric tier level for a base ingredient key."""
    base = get_base(key)
    if not base:
        return 0
    return get_tier_level(base.get("tier", "gutter"))


def get_bases_for_station(station) -> list:
    """
    Return a list of base ingredient dicts available for this station,
    filtered by the station's social tier and type.

    Bar stations: alcohol only, up to station tier.
    Kitchenette stations: food + non-alcoholic drinks, up to station tier.
    """
    station_tier = getattr(station.db, "social_tier", "slum")
    station_level = get_tier_level(station_tier)
    station_type = getattr(station.db, "station_type", "kitchenette")

    if station_type == "bar":
        pool = ALCOHOL_BASES
    else:
        pool = {}
        pool.update(FOOD_BASES)
        pool.update(NON_ALCOHOLIC_BASES)

    return [b for b in pool.values() if get_tier_level(b.get("tier", "gutter")) <= station_level]
