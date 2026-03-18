"""
Combat messaging and flavor text.

Canonical location: `world.combat.combat_messages`

Moved from `world/combat_messages.py` so combat text lives with the combat system.
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

    # If the stored template doesn't resolve in weapon_tiers for this weapon_key,
    # fall back to matching against the object's key. This helps legacy/spawned
    # items that were renamed but never had weapon_template set correctly.
    if template:
        try:
            from world.combat.weapon_tiers import find_weapon_template

            entry, _tier = find_weapon_template(str(weapon_key or ""), str(template))
            if not entry and weapon_obj is not None:
                entry2, _tier2 = find_weapon_template(
                    str(weapon_key or ""), str(getattr(weapon_obj, "key", "") or "")
                )
                if entry2:
                    template = entry2.get("name") or template
        except Exception:
            pass
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
#
# Unified structure:
# - Defensive outcomes (MISS/PARRIED/DODGED) live under result keys.
# - Hit outcomes (HIT pools for normal/critical) live under "HIT":
#     "HIT": { "normal": [(atk, def), ...], "critical": [(atk, def), ...] }
# - Optional per-move overrides live under "moves" and can include both result
#   dicts and "HIT" pools:
#     "moves": { "move_slug": { "MISS": {...}, "HIT": {...} } }
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
        "SOAK": {
            "attacker": "|cYour blow lands on {defender}'s {loc}, but their armor absorbs it.|n",
            "defender": "|c{attacker}'s strike hits your {loc}; your armor takes it.|n",
            "room": "{attacker}'s blow lands on {defender}'s {loc}, but their armor |cabsorbs the hit.|n",
        },
        "SOAK_SHIELD": {
            "attacker": "|cYour blow lands on {effective_defender}'s {loc} — {defender} pulled them in the way — but their armor absorbs it.|n",
            "defender": "|cYou pull {effective_defender} in the way. {attacker}'s strike hits them but armor takes it.|n",
            "effective_defender": "|c{defender} uses you as a shield. {attacker}'s blow hits your {loc}; your armor takes it.|n",
            "room": "{defender} pulls {effective_defender} into the line of fire. {attacker}'s blow hits {effective_defender}'s {loc}, but their armor |csoaks the impact.|n",
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
            "attacker": "You hurl the headsman's weight in a killing arc. |r{defender}|n wrenches clear and the slab of steel hammers sparks off stone.",
            "defender": "{attacker} swings the executioner's blade — a blur of black iron that displaces the air where your throat was. The edge |rmisses|n by a finger's width and you taste the draft of your own near-death.",
            "room": "{attacker} heaves an executioner's blade at {defender} in a stroke meant to end it. The massive edge |rmisses,|n gouging stone where flesh should have been.",
        },
        "PARRIED": {
            "attacker": "You bring the full sentence down on {defender}. Their guard catches the headsman's edge with a shriek of tortured metal; the impact jars your teeth loose. |cParried.|n",
            "defender": "The executioner's blade falls on you like a dropped guillotine. You get steel under it — barely — and |cdeflect the blow|n with a shock that numbs both arms to the elbows.",
            "room": "{attacker}'s executioner's blade crashes into {defender}'s guard with a sound like a church bell breaking. {defender} |cparries,|n staggering under the sheer mass of the stroke.",
        },
        "DODGED": {
            "attacker": "You give the blade everything — shoulders, hips, murder. |y{defender} is already gone,|n and the momentum nearly takes you off your feet.",
            "defender": "You read the headsman's intent and move before the steel commits. The executioner's blade carves a trench where you stood. You |ydodge,|n heart slamming.",
            "room": "{attacker} buries the full weight of an executioner's blade into empty ground as {defender} |ydodges clear,|n the impact sending up a shower of grit.",
        },
        "moves": {
            "executioners_slash": {
                "MISS": {
                    "attacker": "You rip an executioner's slash at neck height. |r{defender}|n drops under the killing line and the blade shears air, trailing a whistle like a last breath.",
                    "defender": "{attacker} uncorks a flat executioner's slash aimed to open your throat from ear to ear. You duck and feel steel part your hair. They |rmiss.|n",
                    "room": "{attacker}'s executioner's slash screams at throat-height toward {defender}, but the killing stroke |rmisses,|n the massive blade burying its momentum into a wall.",
                },
                "PARRIED": {
                    "attacker": "You drive an executioner's slash into {defender}'s guard. Metal screams. Their weapon bows but holds, bleeding the force sideways. |cParried.|n",
                    "defender": "You brace for the executioner's slash and catch it — God help you, you catch it — and |cturn the edge|n aside with a wrench that nearly dislocates your shoulder.",
                    "room": "{attacker}'s executioner's slash slams into {defender}'s guard hard enough to throw sparks. {defender} |cparries|n with a grunt of raw effort.",
                },
                "DODGED": {
                    "attacker": "You put your whole body behind the executioner's slash. |y{defender} reads it and vanishes outside the arc|n before the blade reaches the kill zone.",
                    "defender": "The executioner's slash is already in motion when you move, |yslipping off-line|n and feeling the displaced air yank at your clothes.",
                    "room": "{attacker} unleashes an executioner's slash at {defender}, but {defender} |ydodges|n under the singing arc of black steel.",
                },
                "HIT": {
                    "normal": [
                        (
                            "You drag an executioner's slash through {defender}'s {loc}. The heavy edge splits cloth, then skin, then the wet layers underneath — the blade so massive it barely slows down.",
                            "|R{attacker}|n's executioner's slash cleaves into your {loc}. You don't feel pain yet — just the weight, the impossible weight of the blade settling into you like it belongs there.",
                        ),
                    ],
                    "critical": [
                        (
                            "|yCRITICAL.|n The executioner's slash catches {defender}'s {loc} dead-on and keeps going. Meat parts. Something underneath gives with a sound you'll hear in your sleep.",
                            "|yCRITICAL.|n |R{attacker}|n's executioner's slash buries itself in your {loc}. There's a moment of nothing — then heat, then wet, then the understanding that you are coming apart.",
                        ),
                    ],
                },
            },
            "forward-weight_cleave": {
                "MISS": {
                    "attacker": "You drop a forward-weight cleave straight from the sky. |r{defender}|n shifts and the blade hammers the ground hard enough to numb your palms.",
                    "defender": "{attacker}'s forward-weight cleave falls like a meat-cutter's chop — all mass, no mercy. You jerk sideways and the edge |rmisses,|n cracking the floor where you stood.",
                    "room": "{attacker} drops a forward-weight cleave at {defender} that could split a man crown to crotch. The blow |rmisses,|n cratering the ground.",
                },
                "PARRIED": {
                    "attacker": "You feed the blade's weight into a forward cleave. {defender}'s guard buckles under it but holds, and the force bleeds off in a screech of metal. |cParried.|n",
                    "defender": "The forward-weight cleave comes down on you like a felled tree. You jam steel overhead and |cdeflect the blow|n — but the shock drives you to one knee.",
                    "room": "{attacker}'s forward-weight cleave smashes into {defender}'s guard with bone-rattling force. {defender} |cparries,|n knees buckling under the impact.",
                },
                "DODGED": {
                    "attacker": "You let gravity pull the blade through. |y{defender} steps off the line|n and the cleave buries itself in nothing, dragging you forward.",
                    "defender": "You feel the air compress as the forward-weight cleave falls and |ythrow yourself clear.|n The edge hits where your collarbone was.",
                    "room": "{attacker} commits fully to a forward-weight cleave, but {defender} |ydodges|n and the massive blade hammers empty ground.",
                },
                "HIT": {
                    "normal": [
                        (
                            "You drop the forward-weight cleave into {defender}'s {loc} and let gravity finish the argument. The blade sinks in with a butcher-shop thud and sticks.",
                            "The forward-weight cleave from |R{attacker}|n hammers into your {loc}. Something cracks under the mass — not a clean sound, a splintering one. Your vision whites at the edges.",
                        ),
                    ],
                    "critical": [
                        (
                            "|yCRITICAL.|n The forward-weight cleave hits {defender}'s {loc} with the finality of a dropped anvil. The blade doesn't bounce — it sinks, and what's underneath deforms around it.",
                            "|yCRITICAL.|n |R{attacker}|n's forward-weight cleave demolishes your {loc}. You feel your body rearrange itself around the impact — bones bending, tissue compressing, something deep rupturing with a wet pop.",
                        ),
                    ],
                },
            },
            "spine_strike": {
                "MISS": {
                    "attacker": "You angle the headsman's edge for the spine. |r{defender}|n rotates at the last instant and the blade skims past, taking a strip of cloth with it.",
                    "defender": "{attacker} hunts for your spine with the executioner's blade. You wrench sideways and the edge |rmisses,|n so close you feel the flat drag across your ribs.",
                    "room": "{attacker} lunges at {defender}'s back with a vicious spine strike. The blade |rmisses,|n but only just.",
                },
                "PARRIED": {
                    "attacker": "You thread the blade toward their spine. {defender} gets steel behind their back at the last second and jams the edge off course. |cParried.|n",
                    "defender": "You feel death reaching for your spine and whip your guard behind you. Steel meets steel and you |cparry the spine strike|n blind, by feel alone.",
                    "room": "{attacker} drives the executioner's blade at {defender}'s spine, but {defender} somehow gets a guard up behind them and |cparries the attempt.|n",
                },
                "DODGED": {
                    "attacker": "You aim for the spine — one clean stroke to sever the cord. |y{defender} torques away|n and the edge draws a line through empty air.",
                    "defender": "You feel the intent on your back like a cold hand and |ytwist off the line|n as the spine strike cuts where your vertebrae were.",
                    "room": "{attacker} drives for {defender}'s spine, but {defender} |ydodges,|n rotating out of the blade's path at the last breath.",
                },
                "HIT": {
                    "normal": [
                        (
                            "You thread the blade in for a spine strike at {defender}'s {loc}. The edge finds the channel between muscle and bone and digs in — their whole frame shudders and lists.",
                            "|R{attacker}|n drives a spine strike into your {loc}. Something structural shifts. Your legs feel like they belong to someone else and your balance goes sideways.",
                        ),
                    ],
                    "critical": [
                        (
                            "|yCRITICAL.|n Your spine strike bites into {defender}'s {loc} and you feel the blade grate against something fundamental. Their body locks rigid for a heartbeat, then goes loose in all the wrong places.",
                            "|yCRITICAL.|n |R{attacker}|n's spine strike connects with your {loc} and the world goes electric. Everything below the cut turns to static — signals misfiring, muscles clenching on their own, your body no longer fully yours.",
                        ),
                    ],
                },
            },
            "half-blade_rend": {
                "MISS": {
                    "attacker": "You choke up on the blade and drive it forward in a close-range rend. |r{defender}|n jerks back and the edge chews air where their belly was.",
                    "defender": "{attacker} crowds in and tries to gut you with a half-blade rend. You suck your stomach in and stagger back. They |rmiss|n — barely.",
                    "room": "{attacker} closes to grappling distance and drives a half-blade rend at {defender}'s midsection. The ugly stroke |rmisses.|n",
                },
                "PARRIED": {
                    "attacker": "You wrench the half-blade in close, going for the rend. {defender} jams their weapon against yours at bad-breath distance and shoves you off. |cParried.|n",
                    "defender": "The half-blade rend comes in close and filthy. You clamp steel against the executioner's edge and |cforce it aside|n with an ugly, grinding shove.",
                    "room": "{attacker} tries to rip into {defender} at close range with a half-blade rend. {defender} |cparries in the clinch,|n metal grinding against metal.",
                },
                "DODGED": {
                    "attacker": "You step into the clinch, half-blade leading. |y{defender} peels out of grappling range|n before you can put the edge to work.",
                    "defender": "You refuse the close range and |yback out of the clinch|n as the half-blade rend chews through the space you just occupied.",
                    "room": "{attacker} crowds in for a half-blade rend, but {defender} |yslips out of the clinch|n before the edge can bite.",
                },
                "HIT": {
                    "normal": [
                        (
                            "You choke up on the steel and drive a half-blade rend through {defender}'s {loc} at bad-breath distance. The edge catches and tears — not a clean cut but a ragged one, all leverage and malice.",
                            "The half-blade rend from |R{attacker}|n gouges into your {loc}. They're close enough that you can smell them — sweat, steel, intent — and the blade tears through you like a jagged promise.",
                        ),
                    ],
                    "critical": [
                        (
                            "|yCRITICAL.|n You wrench the half-blade rend across {defender}'s {loc} and something gives — not just skin but the stuff underneath, peeling apart in layers. The wound is ugly, ragged, deep.",
                            "|yCRITICAL.|n |R{attacker}|n's half-blade rend rips through your {loc} at close range. You feel it catch on something inside and pull — a tearing, unzipping wrongness that sends your vision dark around the edges.",
                        ),
                    ],
                },
            },
            "sweeping_behead": {
                "MISS": {
                    "attacker": "You throw the sweeping behead — a flat, screaming arc at neck height. |r{defender}|n drops under it and you feel the blade's hunger go unsatisfied.",
                    "defender": "{attacker}'s sweeping behead hisses over your head as you flatten yourself. The edge |rmisses|n your scalp by an inch and takes a chunk out of the wall behind you.",
                    "room": "{attacker} uncorks a sweeping behead at {defender} — a full-rotation killing stroke. The massive blade |rmisses,|n carving a groove in the scenery.",
                },
                "PARRIED": {
                    "attacker": "You hurl the sweeping behead at their neck. {defender}'s guard smashes up into the blade's path and the impact kicks through both your arms. |cParried.|n",
                    "defender": "You drive your weapon up into the sweeping behead's path and |cmeet the edge|n with a crash that drops your vision to a white flash.",
                    "room": "{attacker}'s sweeping behead smashes into {defender}'s raised guard with a sound like a forge hammer. {defender} |cparries,|n visibly shaken by the blow.",
                },
                "DODGED": {
                    "attacker": "You loose the sweeping behead — all hip, all shoulder, all intent. |y{defender} throws themselves under the arc|n and the blade decapitates nothing.",
                    "defender": "You see the beheading arc begin and |yhurl yourself flat.|n The executioner's blade passes where your head was, singing.",
                    "room": "{attacker} whips a sweeping behead at {defender}'s neck in a killing arc. {defender} |ydodges,|n barely clearing the headsman's edge.",
                },
                "HIT": {
                    "normal": [
                        (
                            "Your sweeping behead catches {defender} across the {loc} — not the clean decapitation it promised but something worse: a deep, ragged bite that leaves the blade stuck in meat and sinew.",
                            "|R{attacker}|n's sweeping behead slams into your {loc}. You feel how close that was to taking everything. The blade bites deep enough that you feel cold air inside the wound.",
                        ),
                    ],
                    "critical": [
                        (
                            "|yCRITICAL.|n The sweeping behead connects with {defender}'s {loc} with the full arc's momentum. The blade goes through whatever's in the way — cloth, skin, muscle — with a sound like wet canvas tearing.",
                            "|yCRITICAL.|n |R{attacker}|n's sweeping behead crunches through your {loc}. The rotation carries the blade so deep you feel it scrape bone. Something inside you lets go — quietly, finally, like it was waiting for permission.",
                        ),
                    ],
                },
            },
            "final_verdict": {
                "MISS": {
                    "attacker": "You bring the Final Verdict down with everything — this is the killing stroke, the last word. |r{defender}|n cheats it by inches and the blade splits stone, throwing fragments.",
                    "defender": "{attacker} swings the Final Verdict and for a frozen instant you see your own death in the arc. Then you |rmove|n and the world's heaviest blade smashes the ground where you stood, hard enough to crack foundations.",
                    "room": "{attacker} swings the Final Verdict at {defender} — the headsman's masterwork, meant to end everything. The execution stroke |rmisses|n and hammers a crater into the ground.",
                },
                "PARRIED": {
                    "attacker": "You swing the Final Verdict with killing weight. {defender}'s guard catches it and for a moment holds — metal screaming, arms shaking. The judgment doesn't land. |cParried.|n",
                    "defender": "The Final Verdict falls on you like the world ending. You get steel under it and |chold|n — barely, screaming through your teeth, arms threatening to buckle — and somehow turn the blade aside.",
                    "room": "{attacker}'s Final Verdict crashes into {defender}'s guard with catastrophic force. {defender} |cparries|n through what looks like sheer refusal to die, staggering under the impact.",
                },
                "DODGED": {
                    "attacker": "You bring the Final Verdict — the headsman's last word. |y{defender} is already gone.|n The blade buries itself in the ground and you're left staring at nothing.",
                    "defender": "The Final Verdict begins its descent and you |ymove before it can finish.|n Behind you, the blade hits the ground hard enough to send cracks through stone. You don't look back.",
                    "room": "{attacker} brings the Final Verdict down on {defender} with absolute, terminal commitment. {defender} |ydodges|n and the execution stroke obliterates the ground, sending up a spray of broken stone.",
                },
                "HIT": {
                    "normal": [
                        (
                            "You deliver the Final Verdict to {defender}'s {loc}. The blade lands with the weight of a pronouncement — heavy, deliberate, absolute. The wound opens and stays open, too deep and too wide to close on its own.",
                            "The Final Verdict from |R{attacker}|n crashes into your {loc}. It doesn't feel like being cut. It feels like being divided — the blade so heavy and the stroke so committed that your body just accepts the separation.",
                        ),
                    ],
                    "critical": [
                        (
                            "|yCRITICAL.|n The Final Verdict finds {defender}'s {loc} and the headsman's steel delivers everything it promised. The wound is catastrophic — deep, structural, the kind that changes what a body is.",
                            "|yCRITICAL.|n |R{attacker}|n's Final Verdict connects with your {loc} and the world reduces to a single fact: you have been opened. The blade goes deeper than muscle, deeper than bone — it hits something foundational and breaks it.",
                        ),
                    ],
                },
            },
        },
        "HIT": {"normal": [], "critical": []},
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
    """
    result = str(result or "").upper()
    base_key = str(weapon_key or "fists")
    profile_id = get_message_profile_id(base_key, weapon_obj)

    profile = WEAPON_MESSAGE_PROFILES.get(profile_id)
    if not profile:
        profile = WEAPON_MESSAGE_PROFILES.get(base_key) or WEAPON_MESSAGE_PROFILES["fists"]

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
        messages = WEAPON_MESSAGE_PROFILES["fists"].get(result, {})
    return messages or {}


def get_soak_messages(
    weapon_key: str,
    weapon_obj=None,
    move_name: str | None = None,
    *,
    shielded: bool = False,
):
    """
    Return armor soak message templates when armor absorbs the hit.

    Returns a dict of templates using placeholders:
    - Always: {attacker}, {defender}, {loc}
    - If shielded=True: also {effective_defender}; and may include an "effective_defender" key.
    """
    key = "SOAK_SHIELD" if shielded else "SOAK"
    base_key = str(weapon_key or "fists")
    profile_id = get_message_profile_id(base_key, weapon_obj)

    profile = WEAPON_MESSAGE_PROFILES.get(profile_id)
    if not profile:
        profile = WEAPON_MESSAGE_PROFILES.get(base_key) or WEAPON_MESSAGE_PROFILES["fists"]

    if move_name:
        move_slug = _slugify_template(str(move_name))
        move_profile = (profile.get("moves") or {}).get(move_slug) or {}
        msgs = move_profile.get(key)
        if msgs:
            return msgs

    msgs = profile.get(key)
    if not msgs:
        msgs = WEAPON_MESSAGE_PROFILES["fists"].get(key, {})
    return msgs or {}


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
    Flavorful hit messages with hit location.
    Returns (attacker_line, defender_line).
    """
    loc = body_part or "them"
    profile_id = get_message_profile_id(weapon_key, weapon_obj)
    want = "critical" if is_critical else "normal"

    base_key = str(weapon_key or "fists")
    profile = WEAPON_MESSAGE_PROFILES.get(profile_id) or WEAPON_MESSAGE_PROFILES.get(base_key) or WEAPON_MESSAGE_PROFILES["fists"]

    def _get_hit_pool(p):
        if not p:
            return None
        hit = p.get("HIT") or {}
        pool = hit.get(want)
        return pool if pool else None

    if move_name and profile:
        move_slug = _slugify_template(str(move_name))
        move_profile = (profile.get("moves") or {}).get(move_slug) or {}
        pool = _get_hit_pool(move_profile)
        if pool:
            atk, def_ = random.choice(pool)
            return atk.format(defender=defender_name, attacker=attacker_name, loc=loc), def_.format(
                defender=defender_name, attacker=attacker_name, loc=loc
            )

    pool = _get_hit_pool(profile)
    if pool:
        atk, def_ = random.choice(pool)
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


# Legacy: kept for any external imports.
HIT_POOLS: dict = {}

