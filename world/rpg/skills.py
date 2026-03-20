"""
Canonical skill list and which 2 SPECIAL stats govern each skill's roll strength.
Skill = roll ceiling; the two stats are averaged for roll strength (equal weight).
"""
# Full skill list (display order by category)
SKILL_KEYS = [
    "unarmed",
    "short_blades",
    "long_blades",
    "blunt_weaponry",
    "sidearms",
    "longarms",
    "automatics",
    "evasion",
    "footwork",
    "stealth",
    "cyberdecking",
    "systems_security",
    "piloting",
    "driving",
    "mechanical_engineering",
    "arms_tech",
    "electrical_engineering",
    "medicine",
    "cyber_surgery",
    "alchemy",
    "tailoring",
    "performance",
    "diplomacy",
    "scavenging",
]

# Two stats per skill (equal weight for roll strength). Must be valid SPECIAL keys.
SKILL_STATS = {
    "unarmed": ["strength", "agility"],
    "short_blades": ["agility", "strength"],
    "long_blades": ["strength", "agility"],
    "blunt_weaponry": ["strength", "endurance"],
    "sidearms": ["perception", "agility"],
    "longarms": ["perception", "strength"],
    "automatics": ["agility", "perception"],
    "evasion": ["agility", "perception"],
    "footwork": ["agility"],
    "stealth": ["agility", "perception"],
    "cyberdecking": ["intelligence", "agility"],
    "systems_security": ["intelligence", "perception"],
    "piloting": ["perception", "agility"],
    "driving": ["perception", "agility"],
    "mechanical_engineering": ["intelligence", "strength"],
    "arms_tech": ["intelligence", "perception"],
    "electrical_engineering": ["intelligence", "perception"],
    "medicine": ["intelligence", "perception"],
    "cyber_surgery": ["intelligence", "agility"],
    "alchemy": ["intelligence", "perception"],
    "tailoring": ["intelligence", "charisma"],
    "performance": ["charisma", "agility"],
    "diplomacy": ["charisma", "intelligence"],
    "scavenging": ["intelligence", "perception"],
}

# Weapon key (combat) -> skill key for attack roll
WEAPON_KEY_TO_SKILL = {
    "fists": "unarmed",
    "claws": "unarmed",
    "knife": "short_blades",
    "short_blade": "short_blades",
    "long_blade": "long_blades",
    "blunt": "blunt_weaponry",
    "sidearm": "sidearms",
    "longarm": "longarms",
    "automatic": "automatics",
    "unarmed": "unarmed",
}

# Defense roll always uses this skill
DEFENSE_SKILL = "evasion"

# Display names for UI / chargen
SKILL_DISPLAY_NAMES = {
    "unarmed": "Unarmed",
    "short_blades": "Short Blades",
    "long_blades": "Long Blades",
    "blunt_weaponry": "Blunt Weaponry",
    "sidearms": "Sidearms",
    "longarms": "Longarms",
    "automatics": "Automatics",
    "evasion": "Evasion",
    "footwork": "Footwork",
    "stealth": "Stealth",
    "cyberdecking": "Cyberdecking",
    "systems_security": "Systems Security",
    "piloting": "Piloting",
    "driving": "Driving",
    "mechanical_engineering": "Mechanical Engineering",
    "arms_tech": "Arms & Armor Tech",
    "electrical_engineering": "Electrical Engineering",
    "medicine": "Medicine",
    "cyber_surgery": "Cyber-surgery",
    "alchemy": "Alchemy",
    "tailoring": "Tailoring",
    "performance": "Performance",
    "diplomacy": "Diplomacy",
    "scavenging": "Scavenging",
}
