"""
Combat messaging helpers and hit flavor.

Pulled out of `world.combat` so flavor text can be tuned without
modifying the combat engine or ticker handling code.
"""

import random


def hit_message(weapon_key, body_part, defender_name, attacker_name, is_critical):
    """
    Flavorful hit messages with hit location. No 'they go down' — combat isn't over.
    body_part is shown so the room knows where the blow landed.
    """
    loc = body_part or "them"
    if weapon_key == "knife":
        if is_critical:
            pool = [
                (f"|yCRITICAL.|n You drive the blade into {defender_name}'s {loc}. Steel goes deep; they buckle.", f"|R{attacker_name}|n sinks the knife into your {loc}. You double over, still standing."),
                (f"|yCRITICAL.|n One vicious thrust into {defender_name}'s {loc}. The blade comes back red.", f"|R{attacker_name}|n opens you at the {loc}. You reel but stay up."),
            ]
        else:
            pool = [
                (f"You slash at {defender_name}'s {loc}. The edge bites; they hiss and stagger.", f"The blade cuts your {loc}. It burns. You're still in the fight."),
                (f"Steel finds flesh at {defender_name}'s {loc}. A cut opens; red runs.", f"|R{attacker_name}|n opens a cut on your {loc}. You press a hand to it and hold your ground."),
            ]
    elif weapon_key == "long_blade":
        if is_critical:
            pool = [
                (f"|yCRITICAL.|n You slice through {defender_name}'s {loc} in one long stroke. The edge is red; they crumple to one knee.", f"|R{attacker_name}|n's blade shears across your {loc}. You drop to a knee, gasping."),
                (f"|yCRITICAL.|n A sweeping cut catches {defender_name}'s {loc}. Flesh parts; they stagger hard.", f"|R{attacker_name}|n cuts you deep across the {loc}. You're still standing — barely."),
            ]
        else:
            pool = [
                (f"You bring the edge down on {defender_name}'s {loc}. A clean cut; they reel back.", f"The blade finds your {loc}. You stagger but keep your feet."),
                (f"Your sword lashes across {defender_name}'s {loc}. Blood on the steel; they're still up.", f"|R{attacker_name}|n opens a gash on your {loc}. You taste blood and hold your stance."),
            ]
    elif weapon_key == "blunt":
        if is_critical:
            pool = [
                (f"|yCRITICAL.|n You put everything into a blow to {defender_name}'s {loc}. You feel the impact; they fold and catch themselves.", f"|R{attacker_name}|n crushes your {loc}. Something gives. You stay up through sheer will."),
                (f"|yCRITICAL.|n One heavy strike to {defender_name}'s {loc}. The crack is ugly. They stagger but don't fall.", f"|R{attacker_name}|n lands it on your {loc}. Your vision blurs. You're still standing."),
            ]
        else:
            pool = [
                (f"Your strike lands on {defender_name}'s {loc}. Solid impact; they grunt and reel.", f"The blow catches your {loc}. Your head rings. You stay in the fight."),
                (f"You hammer {defender_name}'s {loc}. They stagger, still up.", f"Something heavy finds your {loc}. You blink, taste blood, and hold your ground."),
            ]
    elif weapon_key in ("sidearm", "longarm", "automatic"):
        if is_critical:
            pool = [
                (f"|yCRITICAL.|n Your round punches through {defender_name}'s {loc}. They jerk and stagger, hand to the wound.", f"|R{attacker_name}|n shoots you. The bullet hits your {loc}. You're still on your feet."),
                (f"|yCRITICAL.|n The shot finds {defender_name}'s {loc}. They double over but don't drop.", f"|R{attacker_name}|n's round tears into your {loc}. You reel and stay standing."),
            ]
        else:
            pool = [
                (f"Your shot hits {defender_name}'s {loc}. They jerk; blood blooms. Still up.", f"You're hit in the {loc}. Shot. The pain is coming. You're still fighting."),
                (f"The round finds flesh at {defender_name}'s {loc}. They flinch and keep their feet.", f"|R{attacker_name}|n's bullet grazes your {loc}. Shock holds the worst at bay. You hold your ground."),
            ]
    else:
        if is_critical:
            pool = [
                (f"|yCRITICAL.|n Your fist connects with {defender_name}'s {loc}. You feel bone. They stagger badly but stay up.", f"|R{attacker_name}|n lands a brutal shot on your {loc}. Lights flash. You're still standing."),
                (f"|yCRITICAL.|n You put everything into a strike to {defender_name}'s {loc}. They reel and catch themselves.", f"|R{attacker_name}|n hits your {loc} hard. You taste blood. You don't go down."),
            ]
        else:
            pool = [
                (f"Your fist connects with {defender_name}'s {loc}. Solid. They stagger.", f"The punch catches your {loc}. You taste blood. Still up."),
                (f"You hit them in the {loc}. They reel but keep their feet.", f"|R{attacker_name}|n's blow finds your {loc}. You blink and stay in it."),
            ]
    atk, def_ = random.choice(pool)
    return atk, def_

