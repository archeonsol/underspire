"""
Combat messaging and flavor text.

All descriptive strings for combat hits live here so they can be edited without
touching the core combat engine.
"""

from __future__ import annotations

import random


def _slugify_template(name: str) -> str:
    """
    Turn a weapon template display name into a safe, lowercase key.
    Example: "Executioner's Blade" -> "executioners_blade".
    """
    if not name:
        return ""
    out = name.strip().lower()
    for ch in ("'", '"'):
        out = out.replace(ch, "")
    return out.replace(" ", "_")


def get_message_profile_id(weapon_key: str, weapon_obj=None) -> str:
    """
    Determine which message profile to use for this strike.

    If the weapon object has a db.weapon_template set (matching entries in
    world.combat.weapon_tiers), we use a profile id of
        "<weapon_key>::<slugified_template_name>"
    so that individual weapon items can override all combat text.

    Otherwise we fall back to a per-weapon-key profile like "knife" or
    "long_blade". Callers can also always define a "default" profile.
    """
    template = None
    if weapon_obj is not None and getattr(weapon_obj, "db", None):
        template = getattr(weapon_obj.db, "weapon_template", None)
    if template:
        slug = _slugify_template(str(template))
        if slug:
            return f"{weapon_key}::{slug}"
    return str(weapon_key or "fists")


# Central registry of combat text. Each profile key maps to per-result templates
# that use {attacker} and {defender} placeholders. Room lines see names from the
# perspective of an arbitrary third-party viewer.
#
# You can add new entries here for individual weapon templates, for example:
#   "long_blade::executioners_blade": { ... custom text ... }
#
# Any missing profile/result falls back to the base weapon_key profile, then
# finally to the "fists" profile.
WEAPON_MESSAGE_PROFILES = {
    "fists": {
        "MISS": {
            "attacker": "Your punch finds air. |r{defender}|n slipped it. You're off balance.",
            "defender": "{attacker} throws. You move. They |rmiss.|n",
            "room": "{attacker} attacks {defender} but |rmisses.|n",
        },
        "PARRIED": {
            "attacker": "Your punch goes in. |c{defender}|n blocks. No contact. |cParried.|n",
            "defender": "{attacker} throws. Your guard is up. The punch is turned. |cParried.|n",
            "room": "{attacker} attacks {defender}, but {defender} |cparries the blow.|n",
        },
        "DODGED": {
            "attacker": "You commit. |y{defender} slips the punch.|n You're open.",
            "defender": "The punch comes. You |yroll.|n {attacker}'s fist misses.",
            "room": "{attacker} attacks {defender}, but {defender} |ydodges aside.|n",
        },
    },
    "knife": {
        "MISS": {
            "attacker": "You lunge. |r{defender}|n is gone. The blade cuts air. You're open.",
            "defender": "{attacker} thrusts. You're already moving. The knife misses. They |rmiss.|n",
            "room": "{attacker} attacks {defender} but |rmisses.|n",
        },
        "PARRIED": {
            "attacker": "You thrust. |c{defender}|n meets it. Steel on steel. Your blade is turned. |cParried.|n",
            "defender": "The knife comes in. You block. The blade goes wide. |cParried.|n",
            "room": "{attacker} attacks {defender}, but {defender} |cparries the blow.|n",
        },
        "DODGED": {
            "attacker": "You go for the gut. |y{defender} rolls.|n The blade misses. You're exposed.",
            "defender": "You see the lunge. You |yroll.|n The knife passes. You're still up.",
            "room": "{attacker} attacks {defender}, but {defender} |ydodges aside.|n",
        },
    },
    "long_blade": {
        "MISS": {
            "attacker": "You swing. |r{defender}|n steps clear. Your edge finds nothing. You're exposed.",
            "defender": "The blade comes. You're not there. It passes. {attacker} |rmiss.|n",
            "room": "{attacker} attacks {defender} but |rmisses.|n",
        },
        "PARRIED": {
            "attacker": "Your blade comes down. |c{defender}|n catches it. Impact. They shove it aside. |cParried.|n",
            "defender": "The edge falls. You meet it. You turn the blow. |cParried.|n",
            "room": "{attacker} attacks {defender}, but {defender} |cparries the blow.|n",
        },
        "DODGED": {
            "attacker": "Downstroke. |y{defender} slips it.|n Your edge hits nothing. You're open.",
            "defender": "The blade drops. You |yroll clear.|n It misses. You're still standing.",
            "room": "{attacker} attacks {defender}, but {defender} |ydodges aside.|n",
        },
    },
    "long_blade::executioners_blade": {
        "MISS": {
            "attacker": "You swing the headsman's steel. |r{defender}|n steps away; the stroke takes stone instead.",
            "defender": "{attacker} swings an executioner's blade where you were a heartbeat ago. The edge |rmisses.|n",
            "room": "{attacker} swings an executioner's blade at {defender}, but the killing stroke |rmisses.|n",
        },
        "PARRIED": {
            "attacker": "You drop the verdict toward {defender}. Their guard meets it; the judgment glances off. |cParried.|n",
            "defender": "You meet the fall of the executioner's blade and |cturn it aside|n with a jolt up your arms.",
            "room": "{attacker}'s executioner's blade crashes toward {defender}, but {defender} |cparries the stroke.|n",
        },
        "DODGED": {
            "attacker": "You commit the full weight of the blade. |y{defender} isn't there anymore.|n",
            "defender": "You move before the headsman's steel finishes its arc, |yslipping|n under the killing line.",
            "room": "{attacker} hews at {defender} with an executioner's blade, but {defender} |ydodges clear.|n",
        },
        "moves": {
            "executioners_slash": {
                "MISS": {
                    "attacker": "You loose an executioner's slash. |r{defender}|n ducks the verdict; steel whistles past.",
                    "defender": "{attacker}'s executioner's slash carves the air where your neck was. They |rmiss.|n",
                    "room": "{attacker}'s executioner's slash scythes for {defender}, but the stroke |rmisses.|n",
                },
                "PARRIED": {
                    "attacker": "You drive an executioner's slash at {defender}. Their guard jars your wrists. |cParried.|n",
                    "defender": "You catch the executioner's slash on your guard and feel the weight as you |cturn it away.|n",
                    "room": "{attacker}'s executioner's slash crashes toward {defender}, but {defender} |cparries the blow.|n",
                },
                "DODGED": {
                    "attacker": "You commit to an executioner's slash. |y{defender} is already outside the arc.|n",
                    "defender": "You see the executioner's slash coming and |yslip off the line|n before it lands.",
                    "room": "{attacker} whips an executioner's slash at {defender}, but {defender} |ydodges aside.|n",
                },
            },
            "forward-weight_cleave": {
                "MISS": {
                    "attacker": "You swing a forward-weight cleave. |r{defender}|n shifts; the heavy edge bites nothing.",
                    "defender": "{attacker}'s forward-weight cleave tears through space where you stood. They |rmiss.|n",
                    "room": "{attacker} throws a forward-weight cleave at {defender}, but the blow |rmisses.|n",
                },
                "PARRIED": {
                    "attacker": "You drop a forward-weight cleave at {defender}. Their guard catches and bleeds the force. |cParried.|n",
                    "defender": "You brace as the forward-weight cleave falls and |cturn the mass aside|n at the last moment.",
                    "room": "{attacker}'s forward-weight cleave crashes into {defender}'s guard; the stroke is |cparried.|n",
                },
                "DODGED": {
                    "attacker": "You let the weight do the work. |y{defender} has already slipped the kill-line.|n",
                    "defender": "You feel the rush of air as the forward-weight cleave passes where you were. You |ydodge.|n",
                    "room": "{attacker} commits to a forward-weight cleave, but {defender} |ydodges clear.|n",
                },
            },
            "spine_strike": {
                "MISS": {
                    "attacker": "You angle for a spine strike. |r{defender}|n twists away; the blade cuts only cloth.",
                    "defender": "{attacker} reaches for your spine. You shift aside and the spine strike |rmisses.|n",
                    "room": "{attacker} darts in for a spine strike on {defender}, but the attempt |rmisses.|n",
                },
                "PARRIED": {
                    "attacker": "You slip the blade toward their spine. Their guard snaps back and spoils the spine strike. |cParried.|n",
                    "defender": "You feel the intent on your back and bring steel back in time to |cparry the spine strike.|n",
                    "room": "{attacker} hunts for {defender}'s spine, but {defender} |cparries the attempt.|n",
                },
                "DODGED": {
                    "attacker": "You cut for the spine. |y{defender} rolls off the line|n before the edge arrives.",
                    "defender": "You move as the spine strike comes, |yrolling|n so the blade passes over you.",
                    "room": "{attacker} slashes for {defender}'s spine, but {defender} |ydodges aside.|n",
                },
            },
            "half-blade_rend": {
                "MISS": {
                    "attacker": "You choke up and drive a half-blade rend. |r{defender}|n isn't there when it lands.",
                    "defender": "{attacker} closes in for a half-blade rend, but you slip out of reach. They |rmiss.|n",
                    "room": "{attacker} crowds in on {defender} with a half-blade rend, but the attempt |rmisses.|n",
                },
                "PARRIED": {
                    "attacker": "You wrench the half-blade in close. {defender}'s defense shoves the steel off its line. |cParried.|n",
                    "defender": "You meet the half-blade rend at grappling distance and |cjam the blade aside.|n",
                    "room": "{attacker} tries to tear into {defender} with a half-blade rend, but {defender} |cparries it in close.|n",
                },
                "DODGED": {
                    "attacker": "You step in, half-blade ready. |y{defender} slides back out of the clinch.|n",
                    "defender": "You refuse the clinch, stepping off before the half-blade rend can land. You |ydodge.|n",
                    "room": "{attacker} closes for a half-blade rend, but {defender} |yslips out of range.|n",
                },
            },
            "sweeping_behead": {
                "MISS": {
                    "attacker": "You commit to a sweeping behead. |r{defender}|n drops low; the arc takes only air.",
                    "defender": "{attacker}'s sweeping behead scythes overhead as you duck. The blade |rmisses.|n",
                    "room": "{attacker} unleashes a sweeping behead at {defender}, but the killing arc |rmisses.|n",
                },
                "PARRIED": {
                    "attacker": "You hurl a sweeping behead at {defender}. Their weapon crashes up and spoils the cut. |cParried.|n",
                    "defender": "You bring steel up under the sweeping behead and |cmeet the edge|n before it finds your neck.",
                    "room": "{attacker}'s sweeping behead smashes into {defender}'s guard; the stroke is |cparried.|n",
                },
                "DODGED": {
                    "attacker": "You throw the sweeping behead. |y{defender} throws themselves out of the line.|n",
                    "defender": "You see the beheading line and hurl yourself clear; the sweeping behead |ymisses.|n",
                    "room": "{attacker} whips a sweeping behead toward {defender}, but {defender} |ydodges clear.|n",
                },
            },
            "final_verdict": {
                "MISS": {
                    "attacker": "You swing the Final Verdict. |r{defender}|n cheats fate by inches; the blade bites only stone.",
                    "defender": "{attacker}'s Final Verdict roars past you. For a moment you feel the wind of your death. They |rmiss.|n",
                    "room": "{attacker} brings the Final Verdict down on {defender}, but the execution stroke |rmisses.|n",
                },
                "PARRIED": {
                    "attacker": "You raise the Final Verdict. {defender}'s guard screams and holds. The judgment glances off. |cParried.|n",
                    "defender": "You meet the Final Verdict with everything you have and |cjust barely turn it aside.|n",
                    "room": "{attacker}'s Final Verdict crashes into {defender}'s defense, but {defender} |cparries the killing blow.|n",
                },
                "DODGED": {
                    "attacker": "You swing the Final Verdict as if the fight is already decided. |y{defender} refuses the sentence.|n",
                    "defender": "You move before the Final Verdict can fall, |yslipping|n out from under the headsman's line.",
                    "room": "{attacker} swings the Final Verdict at {defender}, but {defender} |ydodges aside.|n",
                },
            },
        },
    },
    "blunt": {
        "MISS": {
            "attacker": "You swing. |r{defender}|n reads it and moves. Your weapon hits empty. You're open.",
            "defender": "{attacker} winds up. You're gone before it lands. They |rmiss.|n",
            "room": "{attacker} attacks {defender} but |rmisses.|n",
        },
        "PARRIED": {
            "attacker": "You swing. |c{defender}|n blocks. Your strike slides off. |cParried.|n",
            "defender": "{attacker} swings. You block. The blow goes wide. |cParried.|n",
            "room": "{attacker} attacks {defender}, but {defender} |cparries the blow.|n",
        },
        "DODGED": {
            "attacker": "You put your weight into it. |y{defender} is gone.|n The blow finds air. You're exposed.",
            "defender": "You see it coming. You |yroll.|n The weapon misses. That would have broken you.",
            "room": "{attacker} attacks {defender}, but {defender} |ydodges aside.|n",
        },
    },
    "sidearm": {
        "MISS": {
            "attacker": "You fire. |r{defender}|n isn't there. The round goes wide. Miss.",
            "defender": "The shot cracks past. You moved. They |rmiss.|n",
            "room": "{attacker} attacks {defender} but |rmisses.|n",
        },
        "PARRIED": {
            # Kept generic; parrying bullets is handled via dodge/evasion mechanically.
            "attacker": "You fire, but |c{defender}'s cover eats the rounds.|n",
            "defender": "Shots spark off your cover. {attacker} doesn't connect. |cParried.|n",
            "room": "{attacker}'s shots spark off {defender}'s cover. |cNo clean hit.|n",
        },
        "DODGED": {
            "attacker": "You squeeze. |y{defender} is already moving.|n The round goes where they were. Miss.",
            "defender": "Muzzle flash. You |ydive.|n The shot goes past. You're still breathing.",
            "room": "{attacker} attacks {defender}, but {defender} |ydodges aside.|n",
        },
    },
    "longarm": {
        "MISS": {
            "attacker": "You fire. |r{defender}|n isn't there. The round goes wide. Miss.",
            "defender": "The shot cracks past. You moved. They |rmiss.|n",
            "room": "{attacker} attacks {defender} but |rmisses.|n",
        },
        "PARRIED": {
            "attacker": "You send a round in, but |c{defender}'s cover drinks it.|n",
            "defender": "You feel the impact through cover. {attacker} doesn't get through. |cParried.|n",
            "room": "{attacker}'s shot punches {defender}'s cover but |cdoesn't get through.|n",
        },
        "DODGED": {
            "attacker": "You line it up. |y{defender} is already moving.|n The round takes stone instead.",
            "defender": "You break line-of-fire as the shot comes. You |yduck behind cover.|n",
            "room": "{attacker} fires at {defender}, but {defender} |yslips out of the firing line.|n",
        },
    },
    "automatic": {
        "MISS": {
            "attacker": "You rake the space where |r{defender}|n was. Rounds chew stone. They're not there.",
            "defender": "Automatic fire rips past. You moved before it walked onto you. They |rmiss.|n",
            "room": "{attacker}'s burst tears up the air around {defender} but |rdoesn't connect.|n",
        },
        "PARRIED": {
            "attacker": "Your burst chews into |c{defender}'s cover.|n No clean shot.",
            "defender": "Automatic fire hammers your cover. {attacker} can't quite walk it onto you. |cParried.|n",
            "room": "{attacker}'s burst hammers {defender}'s cover, |cthrowing up chips instead of blood.|n",
        },
        "DODGED": {
            "attacker": "You walk a burst through the space. |y{defender} dives clear.|n",
            "defender": "You see the burst coming and |ydive out of its path.|n Rounds tear where you were.",
            "room": "{attacker} sweeps a burst at {defender}, but {defender} |ydodges aside.|n",
        },
    },
}


def get_result_messages(result: str, weapon_key: str, weapon_obj=None, move_name: str | None = None):
    """
    Return the appropriate message templates for a MISS/PARRIED/DODGED result.

    The return value is a dict with keys:
      attacker, defender, room

    Callers are responsible for formatting these with {attacker} and {defender}
    using their own combat_display_name() lookups for each viewer.
    """
    result = str(result or "").upper()
    base_key = str(weapon_key or "fists")
    profile_id = get_message_profile_id(base_key, weapon_obj)

    profile = WEAPON_MESSAGE_PROFILES.get(profile_id)
    if not profile:
        profile = WEAPON_MESSAGE_PROFILES.get(base_key) or WEAPON_MESSAGE_PROFILES["fists"]

    # Optional per-attack overrides for this profile.
    if move_name:
        move_slug = _slugify_template(str(move_name))
        moves = profile.get("moves") or {}
        move_profile = moves.get(move_slug)
        if move_profile:
            messages = move_profile.get(result)
            if messages:
                return messages

    messages = profile.get(result)
    if not messages:
        # Final fallback: use fists profile for the requested result.
        messages = WEAPON_MESSAGE_PROFILES["fists"].get(result, {})
    return messages or {}


def hit_message(
    weapon_key,
    body_part,
    defender_name,
    attacker_name,
    is_critical,
    weapon_obj=None,
    move_name: str | None = None,
):
    """
    Flavorful hit messages with hit location. No 'they go down' — combat isn't over.
    body_part is shown so the room knows where the blow landed.

    Returns (attacker_line, defender_line).

    This function supports per-template overrides via the same profile id
    scheme used for MISS/PARRIED/DODGED. To define custom hit text for a
    specific weapon item, add a 'hit_critical' and/or 'hit_normal' pool under
    that profile key in HIT_POOLS below.
    """
    loc = body_part or "them"

    # Optional per-template / per-move overrides.
    profile_id = get_message_profile_id(weapon_key, weapon_obj)
    pool_key = "hit_critical" if is_critical else "hit_normal"
    profile_pools = HIT_POOLS.get(profile_id, {}) or {}

    # First, check for per-move pools under this profile.
    custom_pool = None
    if move_name:
        move_slug = _slugify_template(str(move_name))
        move_pools = profile_pools.get("moves") or {}
        move_profile = move_pools.get(move_slug) or {}
        custom_pool = move_profile.get(pool_key)

    # If no move-specific pool, fall back to profile-wide pool.
    if not custom_pool:
        custom_pool = profile_pools.get(pool_key)

    if custom_pool:
        atk, def_ = random.choice(custom_pool)
        return atk.format(defender=defender_name, attacker=attacker_name, loc=loc), def_.format(
            defender=defender_name, attacker=attacker_name, loc=loc
        )

    # Fallback to weapon_key-based text.
    if weapon_key == "knife":
        if is_critical:
            pool = [
                (
                    "|yCRITICAL.|n You drive the blade into {defender}'s {loc}. Steel goes deep; they buckle.",
                    "|R{attacker}|n sinks the knife into your {loc}. You double over, still standing.",
                ),
                (
                    "|yCRITICAL.|n One vicious thrust into {defender}'s {loc}. The blade comes back red.",
                    "|R{attacker}|n opens you at the {loc}. You reel but stay up.",
                ),
            ]
        else:
            pool = [
                (
                    "You slash at {defender}'s {loc}. The edge bites; they hiss and stagger.",
                    "The blade cuts your {loc}. It burns. You're still in the fight.",
                ),
                (
                    "Steel finds flesh at {defender}'s {loc}. A cut opens; red runs.",
                    "|R{attacker}|n opens a cut on your {loc}. You press a hand to it and hold your ground.",
                ),
            ]
    elif weapon_key == "long_blade":
        if is_critical:
            pool = [
                (
                    "|yCRITICAL.|n You slice through {defender}'s {loc} in one long stroke. "
                    "The edge is red; they crumple to one knee.",
                    "|R{attacker}|n's blade shears across your {loc}. You drop to a knee, gasping.",
                ),
                (
                    "|yCRITICAL.|n A sweeping cut catches {defender}'s {loc}. Flesh parts; they stagger hard.",
                    "|R{attacker}|n cuts you deep across the {loc}. You're still standing — barely.",
                ),
            ]
        else:
            pool = [
                (
                    "You bring the edge down on {defender}'s {loc}. A clean cut; they reel back.",
                    "The blade finds your {loc}. You stagger but keep your feet.",
                ),
                (
                    "Your sword lashes across {defender}'s {loc}. Blood on the steel; they're still up.",
                    "|R{attacker}|n opens a gash on your {loc}. You taste blood and hold your stance.",
                ),
            ]
    elif weapon_key == "blunt":
        if is_critical:
            pool = [
                (
                    "|yCRITICAL.|n You put everything into a blow to {defender}'s {loc}. "
                    "You feel the impact; they fold and catch themselves.",
                    "|R{attacker}|n crushes your {loc}. Something gives. You stay up through sheer will.",
                ),
                (
                    "|yCRITICAL.|n One heavy strike to {defender}'s {loc}. The crack is ugly. They stagger but don't fall.",
                    "|R{attacker}|n lands it on your {loc}. Your vision blurs. You're still standing.",
                ),
            ]
        else:
            pool = [
                (
                    "Your strike lands on {defender}'s {loc}. Solid impact; they grunt and reel.",
                    "The blow catches your {loc}. Your head rings. You stay in the fight.",
                ),
                (
                    "You hammer {defender}'s {loc}. They stagger, still up.",
                    "Something heavy finds your {loc}. You blink, taste blood, and hold your ground.",
                ),
            ]
    elif weapon_key in ("sidearm", "longarm", "automatic"):
        if is_critical:
            pool = [
                (
                    "|yCRITICAL.|n Your round punches through {defender}'s {loc}. "
                    "They jerk and stagger, hand to the wound.",
                    "|R{attacker}|n shoots you. The bullet hits your {loc}. You're still on your feet.",
                ),
                (
                    "|yCRITICAL.|n The shot finds {defender}'s {loc}. They double over but don't drop.",
                    "|R{attacker}|n's round tears into your {loc}. You reel and stay standing.",
                ),
            ]
        else:
            pool = [
                (
                    "Your shot hits {defender}'s {loc}. They jerk; blood blooms. Still up.",
                    "You're hit in the {loc}. Shot. The pain is coming. You're still fighting.",
                ),
                (
                    "The round finds flesh at {defender}'s {loc}. They flinch and keep their feet.",
                    "|R{attacker}|n's bullet grazes your {loc}. Shock holds the worst at bay. You hold your ground.",
                ),
            ]
    else:
        if is_critical:
            pool = [
                (
                    "|yCRITICAL.|n Your fist connects with {defender}'s {loc}. "
                    "You feel bone. They stagger badly but stay up.",
                    "|R{attacker}|n lands a brutal shot on your {loc}. Lights flash. You're still standing.",
                ),
                (
                    "|yCRITICAL.|n You put everything into a strike to {defender}'s {loc}. "
                    "They reel and catch themselves.",
                    "|R{attacker}|n hits your {loc} hard. You taste blood. You don't go down.",
                ),
            ]
        else:
            pool = [
                (
                    "Your fist connects with {defender}'s {loc}. Solid. They stagger.",
                    "The punch catches your {loc}. You taste blood. Still up.",
                ),
                (
                    "You hit them in the {loc}. They reel but keep their feet.",
                    "|R{attacker}|n's blow finds your {loc}. You blink and stay in it.",
                ),
            ]

    atk_tpl, def_tpl = random.choice(pool)
    return atk_tpl.format(defender=defender_name, attacker=attacker_name, loc=loc), def_tpl.format(
        defender=defender_name, attacker=attacker_name, loc=loc
    )


# Optional per-weapon / per-template hit overrides. See docstring on hit_message.
HIT_POOLS = {
    "long_blade::executioners_blade": {
        "moves": {
            "executioners_slash": {
                "hit_normal": [
                    (
                        "You bring an executioner's slash across {defender}'s {loc}. The headsman's edge bites deep.",
                        "|R{attacker}|n's executioner's slash hacks into your {loc}. You feel the whole weight of the blade.",
                    ),
                ],
                "hit_critical": [
                    (
                        "|yCRITICAL.|n The executioner's slash falls true on {defender}'s {loc}. For a moment, everything is very still.",
                        "|yCRITICAL.|n |R{attacker}|n's executioner's slash smashes through your {loc}. The world narrows to the edge.",
                    ),
                ],
            },
            "forward-weight_cleave": {
                "hit_normal": [
                    (
                        "You drive a forward-weight cleave into {defender}'s {loc}. The mass of the blade does the rest.",
                        "The forward-weight cleave from |R{attacker}|n crashes into your {loc}. You feel bone protest.",
                    ),
                ],
                "hit_critical": [
                    (
                        "|yCRITICAL.|n The forward-weight cleave slams into {defender}'s {loc} with execution-ground force.",
                        "|yCRITICAL.|n |R{attacker}|n's forward-weight cleave detonates through your {loc}. You taste iron and verdict.",
                    ),
                ],
            },
            "spine_strike": {
                "hit_normal": [
                    (
                        "You angle the blade in for a spine strike at {defender}'s {loc}. Their stance buckles.",
                        "|R{attacker}|n threads a spine strike into your {loc}. Your balance goes with it.",
                    ),
                ],
                "hit_critical": [
                    (
                        "|yCRITICAL.|n Your spine strike lands at {defender}'s {loc}. Everything in their posture comes undone.",
                        "|yCRITICAL.|n |R{attacker}|n's spine strike finds your {loc}. Your limbs stop agreeing with you.",
                    ),
                ],
            },
            "half-blade_rend": {
                "hit_normal": [
                    (
                        "You choke up on the steel and rend through {defender}'s {loc} with half-blade control.",
                        "The half-blade rend from |R{attacker}|n tears through your {loc}. It's all leverage and intention.",
                    ),
                ],
                "hit_critical": [
                    (
                        "|yCRITICAL.|n You wrench a half-blade rend across {defender}'s {loc}. Flesh and balance both go.",
                        "|yCRITICAL.|n |R{attacker}|n's half-blade rend opens your {loc} in a way surgeons curse.",
                    ),
                ],
            },
            "sweeping_behead": {
                "hit_normal": [
                    (
                        "Your sweeping behead takes {defender} across the {loc}. Not a clean head, but close enough for fear.",
                        "|R{attacker}|n's sweeping behead slams into your {loc}. You feel just how close that was to ending you.",
                    ),
                ],
                "hit_critical": [
                    (
                        "|yCRITICAL.|n The sweeping behead bites into {defender}'s {loc} with headsman's promise.",
                        "|yCRITICAL.|n |R{attacker}|n's sweeping behead crashes through your {loc}. The world tilts on the cut.",
                    ),
                ],
            },
            "final_verdict": {
                "hit_normal": [
                    (
                        "You deliver the Final Verdict to {defender}'s {loc}. The blade lands like a gavel.",
                        "The Final Verdict from |R{attacker}|n smashes into your {loc}. You feel the judgment in bone.",
                    ),
                ],
                "hit_critical": [
                    (
                        "|yCRITICAL.|n Final Verdict: {defender}'s {loc} takes the full weight of the headsman's steel.",
                        "|yCRITICAL.|n |R{attacker}|n's Final Verdict finds your {loc}. Everything after this is appeal.",
                    ),
                ],
            },
        },
    },
}

