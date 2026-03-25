"""
Performance commands: performance compose (EvEditor), performance play/stop.

Compose: 'performance compose <name>' opens EvEditor; on save, buffer is split by newlines
and stored as a list of pose lines (pose system supported). Only that character can use it.

Play: 'performance play <name> with <instrument>' requires an instrument item, rolls artistry
(ceiling) + charisma (strength), then runs each line as a pose every ~15s, followed by crowd reactions.
'performance stop' cancels the running performance.

Improvise: 'performance improvise with <instrument>' puts you in performance state: your poses and says
are shown in bright white and get audience reactions until you use 'performance stop'. Anyone can try.
"""

import random
import time
from commands.base_cmds import Command
from evennia.utils import delay
from evennia.utils.eveditor import EvEditor

from world.rpg.artistry_specialization import SPECIALIZATION_STAGE, get_specialization_roll_bonus

ARTISTRY_SKILL = "artistry"
PERFORMANCE_DELAY_SECONDS = 15  # minimum seconds between performance lines
COMPOSITION_SLOTS_MIN = 5
# Max compositions = COMPOSITION_SLOTS_MIN + 1 per 10 artistry skill (skill 0–150)
COMPOSITION_SLOTS_PER_SKILL = 10
# Max lines per composition: 25 at skill 0, up to 50 at higher Artistry skill
COMPOSITION_LINES_MIN = 25
COMPOSITION_LINES_MAX = 50
COMPOSITION_LINES_SKILL_DIVISOR = 6  # 25 + skill//6 -> 25 at 0, 50 at 150


def _get_max_compositions(caller):
    """Return max number of compositions this character can have (min 5, scales with Artistry skill)."""
    if not hasattr(caller, "get_skill_level"):
        return COMPOSITION_SLOTS_MIN
    skill = caller.get_skill_level(ARTISTRY_SKILL) or 0
    return max(COMPOSITION_SLOTS_MIN, COMPOSITION_SLOTS_MIN + int(skill) // COMPOSITION_SLOTS_PER_SKILL)


def _get_max_composition_lines(caller):
    """Return max lines allowed per composition (25 at low skill, up to 50)."""
    if not hasattr(caller, "get_skill_level"):
        return COMPOSITION_LINES_MIN
    skill = caller.get_skill_level(ARTISTRY_SKILL) or 0
    return min(COMPOSITION_LINES_MAX, COMPOSITION_LINES_MIN + int(skill) // COMPOSITION_LINES_SKILL_DIVISOR)


# Short audience reactions for each pose/say during improvise (bold white).
AUDIENCE_IMPROV_ONGOING = [
    "The crowd watches.",
    "A few people nod.",
    "Someone taps a foot.",
    "Heads turn your way.",
    "The room is listening.",
    "Someone passes a drink.",
    "A scattered murmur runs through the crowd.",
]

# Audience reaction echoes (bold white) keyed by roll outcome. One chosen at random per tier.
AUDIENCE_FAILURE = [
    "The crowd erupts in boos and jeers. Someone hurls an empty can at the stage; another voice shouts, \"Get off!\"",
    "Heckles cut through the room: \"You call that music?\" A bottle flies past. The audience turns away in disgust.",
    "Scattered hisses and booing. A guard by the door folds his arms; someone throws a crumpled cup. The room has turned against you.",
    "The crowd doesn't wait. \"Next!\" someone yells. Empty cans and catcalls rain down; people are already heading for the exits.",
    "Loud jeers and mocking laughter. \"Save it for the recyclers!\" A can bounces off the wall. The audience is hostile.",
    "Someone lobs a bottle; it shatters near the stage. \"We came for a show, not a funeral!\" The room is turning ugly.",
    "Boos roll from the back. A mercenary spits and walks out; others fold their arms. You've lost them.",
    "\"Off the stage!\" The crowd starts chanting. A scavenger flings a wad of something; the room smells of rage and cheap liquor.",
    "Catcalls and whistles, the cruel kind. \"My ears are bleeding!\" Someone else throws a cup. Nobody's on your side.",
    "The room erupts in derision. \"Next act!\" \"Get a real job!\" Empty cans and jeers drive you toward the wings.",
]

AUDIENCE_MARGINAL = [
    "A few scattered claps, then silence. Some nod; others turn back to their drinks. Lukewarm at best.",
    "Mixed reception: one drunk cheers, a couple of heads turn your way, but most carry on talking. You've got a foot in the door.",
    "Polite, half-hearted applause. A soldier taps his boot once; a scavenger shrugs and goes back to their meal. Could be worse.",
    "Nobody boos, but nobody moves closer either. A few people nod along. The room is indifferent but not unkind.",
    "Scattered approval. Someone raises a glass; another mutters something that might be praise. You're not drowning, at least.",
    "A couple of people actually listen. The rest keep chatting, but you've caught an ear or two. Small victory.",
    "One or two nod in time. A guard by the door doesn't leave. The room hasn't turned on you; that's something.",
    "Tepid claps from the corner. Someone passes a drink; another shrugs and goes back to their argument. You're background noise, but not unwelcome.",
    "A few heads turn. No boos, no bottles. The room is busy ignoring you more than hating you. Room to grow.",
    "Scattered acknowledgment: a raised glass, a half-nod. The crowd is lukewarm but not hostile. You're in the door.",
]

AUDIENCE_FULL_SUCCESS = [
    "Heads turn. Feet tap. Someone passes a drink to a neighbour; the room warms. People are listening.",
    "The crowd settles into the sound. Nodding heads, swaying shoulders. A couple leans in; a mercenary puts down his rifle and listens.",
    "The room stills. People stop mid-sentence. A guard by the door relaxes; a scavenger closes their eyes. You've got them.",
    "Cheers and raised glasses. The floor fills with swaying bodies; someone passes around a shared chem. The room is alive.",
    "Soldiers and civvies alike nod along. A rich coat and a patched jacket stand side by side, both tapping time. You've crossed the room.",
    "The crowd is with you. Feet tap, shoulders sway; someone hums along. A scavenger passes a vial; the room feels warmer.",
    "Heads bob. A guard stops checking the door and just listens. Couples lean in; the room has one pulse.",
    "You've got the room. Nodding heads, tapping boots, someone raising a glass your way. The air is easy.",
    "The floor stirs. People sway; a merc puts his weapon down and listens. Someone passes a chem; the crowd is yours.",
    "Cheers and movement. The room is nodding, swaying, passing drinks. You've crossed the line from background to show.",
]

AUDIENCE_CRITICAL = [
    "The room holds its breath. Soldiers and guards forget their posts; mercenaries set down their drinks. Rich and poor, scavengers and suits: everyone is here, in the sound. Someone passes a vial; feet find the beat. The whole place is dancing.",
    "For a moment the sector doesn't exist. Guards tap their boots. A scavenger stops haggling and just listens. Someone in fine cloth sways next to someone in rags. Chems go round; the crowd surges. You've turned the room into one pulse.",
    "The crowd erupts, not in jeers but in movement. Soldiers and civilians, mercs and miners, the well-dressed and the threadbare, all drawn in. Glasses rise; someone dances on a table. The air is thick with sweat and shared chemicals. You own the room.",
    "Every face is turned. A guard hums along; a scavenger's eyes are closed. Mercenaries put down weapons. The rich and the poor stand shoulder to shoulder. Someone passes a drink; someone else is already swaying. The room is one living thing, and you're the heart.",
    "Booze and chems flow. The floor is a sea of nodding heads and tapping boots: soldiers, guards, scavengers, merchants, the desperate and the comfortable, all caught in the same moment. Someone shouts your name. The walls seem to bend with the sound.",
    "The room becomes one body. Guards and scavengers, suits and rags, everyone moving. Someone dances on a crate; vials and drinks pass hand to hand. You've stopped time.",
    "Every soul in the room is yours. Soldiers put down rifles; merchants forget their deals. The floor is swaying; someone shouts your name. The walls pulse.",
    "The crowd surges, not away but in. Rich and poor, armed and not, all in the same beat. Glasses rise; someone is crying and smiling. You've made the sector disappear.",
    "Guards hum. Scavengers close their eyes. Mercenaries set their weapons down. The room is one heartbeat; someone passes a vial and the whole place is dancing. You own it.",
    "The air crackles. Every face is turned, every foot tapping. Soldiers and civvies, the broken and the whole, all one. Someone dances on the bar; the room shouts your name. You've remade the moment.",
    "Nobody is leaving. The crowd is a single wave: guards, scavengers, the well-dressed and the ragged. Chems and booze pass; feet stamp; someone is weeping with joy. For this moment, you are the only thing that exists.",
]


def _audience_echo(room, outcome, result):
    """Send a bold white audience-reaction echo to the room based on roll outcome and result."""
    if not room:
        return
    if outcome == "Failure":
        msg = random.choice(AUDIENCE_FAILURE)
    elif outcome == "Marginal Success":
        msg = random.choice(AUDIENCE_MARGINAL)
    elif outcome == "Full Success":
        msg = random.choice(AUDIENCE_FULL_SUCCESS)
    else:  # Critical Success
        msg = random.choice(AUDIENCE_CRITICAL)
    room.msg_contents("|w%s|n" % msg)


def _audience_echo_improvise(room):
    """Send a short bold white audience reaction (used after each pose/say during improvise)."""
    if not room:
        return
    msg = random.choice(AUDIENCE_IMPROV_ONGOING)
    room.msg_contents("|w%s|n" % msg)


def _normalize_title(title):
    """Normalize composition title for storage lookup (lowercase, strip)."""
    return (title or "").strip().lower()


def _run_emote(caller, text):
    """Run one pose line through the emote system (same as .pose)."""
    from commands.roleplay_cmds import _run_emote as _run
    _run(caller, text)


def stop_performance_if_active(character):
    """Stop any running performance or improvise (e.g. on logoff). Call from at_post_unpuppet."""
    if not character or not hasattr(character, "ndb"):
        return
    character.ndb.performance_lines = None
    if hasattr(character.ndb, "performance_cooldown_until"):
        character.ndb.performance_cooldown_until = None
    if hasattr(character.ndb, "performance_room_id"):
        character.ndb.performance_room_id = None
    if hasattr(character.ndb, "performance_outcome"):
        character.ndb.performance_outcome = None
        character.ndb.performance_result = None
    character.ndb.performance_improvising = False


def _performance_next_line(character):
    """
    Manually trigger the next line of an ongoing performance.
    Enforces cooldown between lines and stops if the character left the starting room
    or is unconscious/flatlined.
    """
    if not character or not hasattr(character, "ndb"):
        return
    lines = getattr(character.ndb, "performance_lines", None)
    
    if not lines:
        if hasattr(character.ndb, "performance_lines"):
            character.ndb.performance_lines = None
        if hasattr(character.ndb, "performance_cooldown_until"):
            character.ndb.performance_cooldown_until = None
        if hasattr(character.ndb, "performance_outcome"):
            character.ndb.performance_outcome = None
            character.ndb.performance_result = None
        character.msg("|cYou have no more lines to perform.|n")
        return
        
    # Safety: stop if they left the room or are no longer conscious
    start_room_id = getattr(character.ndb, "performance_room_id", None)
    if start_room_id is not None:
        try:
            from world.death import is_flatlined
            from world.medical import is_unconscious
            if not character.location or character.location.id != start_room_id:
                character.ndb.performance_lines = None
                character.ndb.performance_room_id = None
                if hasattr(character.ndb, "performance_cooldown_until"):
                    character.ndb.performance_cooldown_until = None
                if hasattr(character.ndb, "performance_outcome"):
                    character.ndb.performance_outcome = None
                    character.ndb.performance_result = None
                character.msg("|cYour performance is interrupted; you're no longer in the same place.|n")
                return
            if is_flatlined(character) or is_unconscious(character):
                character.ndb.performance_lines = None
                character.ndb.performance_room_id = None
                if hasattr(character.ndb, "performance_cooldown_until"):
                    character.ndb.performance_cooldown_until = None
                if hasattr(character.ndb, "performance_outcome"):
                    character.ndb.performance_outcome = None
                    character.ndb.performance_result = None
                character.msg("|cYour performance is interrupted.|n")
                return
        except Exception:
            pass

    # Enforce cooldown between lines
    now = time.time()
    cooldown_until = getattr(character.ndb, "performance_cooldown_until", 0) or 0
    if now < cooldown_until:
        remaining = int(round(cooldown_until - now))
        if remaining <= 0:
            remaining = 1
        character.msg("|cYou need to wait %d more second%s before the next line.|n" % (remaining, "" if remaining == 1 else "s"))
        return

    line = lines.pop(0)
    line = (line or "").strip()
    if line:
        try:
            _run_emote(character, line)
        except Exception:
            pass

    # Set next cooldown window
    character.ndb.performance_cooldown_until = now + PERFORMANCE_DELAY_SECONDS
    # Crowd reacts 2 seconds AFTER the line is sung
    outcome = getattr(character.ndb, "performance_outcome", "Marginal Success")
    result = getattr(character.ndb, "performance_result", 0)
    if character.location:
        delay(2, _audience_echo, character.location, outcome, result)

    if not lines:
        character.ndb.performance_lines = None
        if hasattr(character.ndb, "performance_room_id"):
            character.ndb.performance_room_id = None
        if hasattr(character.ndb, "performance_cooldown_until"):
            character.ndb.performance_cooldown_until = None
        if hasattr(character.ndb, "performance_outcome"):
            character.ndb.performance_outcome = None
            character.ndb.performance_result = None
        character.msg("|cYour performance ends.|n")


def _character_has_instrument(caller, instrument_spec):
    """
    Return (True, instrument_obj) if caller has access to an instrument matching instrument_spec
    that has any tag in the performance_instrument category. Accepts e.g. "guitar", "acoustic guitar",
    "battered guitar" for items tagged in that category.
    """
    spec = (instrument_spec or "").strip().lower()
    if not spec:
        return False, None
    candidates = list(caller.contents) if hasattr(caller, "contents") else []
    if caller.location:
        candidates.extend(caller.location.contents or [])
    for obj in candidates:
        if obj == caller:
            continue
        key = (getattr(obj, "key", None) or "").lower()
        alias_list = list(obj.aliases.all()) if hasattr(obj, "aliases") and obj.aliases else []
        name_matches = (
            spec in key or key in spec
            or any(spec in (a or "").lower() or (a or "").lower() in spec for a in alias_list)
        )
        if not name_matches:
            continue
        # Any tag in category "performance_instrument" makes it a valid instrument
        if hasattr(obj, "tags"):
            try:
                result = obj.tags.has(category="performance_instrument")
                has_tag = result if isinstance(result, bool) else any(result)
                if has_tag:
                    return True, obj
            except (ValueError, Exception):
                pass
    return False, None


def _open_compose_editor(caller, title):
    """Open EvEditor for composing a performance named title. Stores lines in caller.db.compositions."""
    normalized = _normalize_title(title)
    compositions = getattr(caller.db, "compositions", None) or {}
    max_slots = _get_max_compositions(caller)
    if normalized not in compositions and len(compositions) >= max_slots:
        caller.msg("You can only store %s composition(s) (based on your Artistry skill). Use |wperformance list|n to see yours." % max_slots)
        return

    def loadfunc(caller):
        """Re-read from db so we always get the right composition for this editor session."""
        comps = getattr(caller.db, "compositions", None) or {}
        existing = comps.get(normalized)
        if not existing:
            return ""
        return "\n".join(existing) if isinstance(existing, list) else str(existing)

    def savefunc(caller, buffer):
        comps = dict(getattr(caller.db, "compositions", None) or {})
        is_new = normalized not in comps
        if is_new and len(comps) >= _get_max_compositions(caller):
            caller.msg("You've reached your composition limit. Raise your Artistry skill to store more.")
            return False
        raw_lines = (buffer or "").replace("\r\n", "\n").replace("\r", "\n").split("\n")
        lines = [ln.strip() for ln in raw_lines if ln.strip()]
        max_lines = _get_max_composition_lines(caller)
        if len(lines) > max_lines:
            caller.msg("That would be %d lines; you can only store up to %d per composition (based on your Performance skill)." % (len(lines), max_lines))
            return False
        comps[normalized] = lines
        caller.db.compositions = comps
        caller.msg("|gSaved performance \"%s\" with %d line(s). Use |wperformance play %s with <instrument>|n to perform it.|n" % (title, len(lines), title))
        return True

    def quitfunc(caller):
        caller.msg("Exited the performance editor.")

    EvEditor(caller, loadfunc=loadfunc, savefunc=savefunc, quitfunc=quitfunc, key="compose_%s" % normalized, persistent=False)


class CmdPerformance(Command):
    """
    Compose a set piece, play it with a guitar, or improvise live.

    Usage:
      performance list                   - show your stored compositions (limit based on Artistry skill)
      performance compose <name>         - write a new performance in the editor (one pose per line)
      performance edit <name>            - edit an existing stored performance
      performance delete <name>          - remove a stored composition
      performance play <name> with <instrument>   - begin performing it; use |wperformance next|n for each line
      performance next                  - manually trigger the next line of your current performance
      performance improvise with <instrument>     - your poses and says light up and draw reactions until you stop
      performance stop                  - end a performance or improvise
    """
    key = "performance"
    aliases = ["pf"]
    locks = "cmd:all()"
    help_category = "Roleplay"

    def func(self):
        caller = self.caller
        args = (self.args or "").strip()
        if not args:
            caller.msg("Usage: |wperformance list|n, |wperformance compose <name>|n, |wperformance delete <name>|n, |wperformance play <name> with <instrument>|n, |wperformance improvise with <instrument>|n, or |wperformance stop|n")
            return

        # --- performance list ---
        if args.strip().lower() == "list":
            compositions = dict(getattr(caller.db, "compositions", None) or {})
            max_slots = _get_max_compositions(caller)
            if not compositions:
                caller.msg("You have no compositions. Use |wperformance compose <name>|n to create one.")
                return
            caller.msg("|wYour compositions (%s/%s):|n" % (len(compositions), max_slots))
            for norm_title in sorted(compositions.keys()):
                lines = compositions[norm_title]
                display = norm_title.replace("_", " ").title() if norm_title else "(unnamed)"
                count = len(lines) if lines else 0
                caller.msg("  |w%s|n (%s line%s)" % (display, count, "s" if count != 1 else ""))
            return

        # --- performance delete <name> ---
        if args.lower().startswith("delete "):
            title = args[7:].strip()
            if not title:
                caller.msg("Usage: |wperformance delete <name>|n (e.g. performance delete The Ballad of the Wastes)")
                return
            normalized = _normalize_title(title)
            comps = dict(getattr(caller.db, "compositions", None) or {})
            if normalized not in comps:
                caller.msg("You have no composition named \"%s\". Use |wperformance list|n to see yours." % title)
                return
            del comps[normalized]
            caller.db.compositions = comps
            display = normalized.replace("_", " ").title()
            caller.msg("|gDeleted composition \"%s\".|n" % display)
            return

        # --- performance edit <name> ---
        if args.lower().startswith("edit "):
            title = args[5:].strip()
            if not title:
                caller.msg("Usage: |wperformance edit <name>|n (e.g. performance edit The Ballad of the Wastes)")
                return
            normalized = _normalize_title(title)
            compositions = getattr(caller.db, "compositions", None) or {}
            if normalized not in compositions:
                caller.msg("You have no composition named \"%s\". Use |wperformance list|n to see yours, or |wperformance compose %s|n to create it." % (title, title))
                return
            _open_compose_editor(caller, title)
            return

        # --- performance compose <name> ---
        if args.lower().startswith("compose "):
            title = args[8:].strip()
            if not title:
                caller.msg("Give a name for the performance (e.g. |wperformance compose The Ballad of the Wastes|n).")
                return
            _open_compose_editor(caller, title)
            return

        # --- performance stop ---
        if args.strip().lower() == "stop":
            caller.ndb.performance_lines = None
            if hasattr(caller.ndb, "performance_room_id"):
                caller.ndb.performance_room_id = None
            if hasattr(caller.ndb, "performance_outcome"):
                caller.ndb.performance_outcome = None
                caller.ndb.performance_result = None
            if hasattr(caller.ndb, "performance_cooldown_until"):
                caller.ndb.performance_cooldown_until = None
            was_improvising = getattr(caller.ndb, "performance_improvising", False)
            caller.ndb.performance_improvising = False
            if was_improvising:
                caller.msg("|cYou stop improvising.|n")
            else:
                caller.msg("|cYou stop your performance.|n")
            return

        # --- performance next ---
        if args.strip().lower() in ("next", "continue"):
            lines = getattr(caller.ndb, "performance_lines", None)
            if not lines:
                caller.msg("You are not currently performing a stored piece. Use |wperformance play <name> with <instrument>|n to begin.")
                return
            _performance_next_line(caller)
            return

        # --- performance improvise with <instrument> ---
        if args.lower().startswith("improvise with "):
            instrument_spec = args[15:].strip()
            if not instrument_spec:
                caller.msg("Usage: |wperformance improvise with <instrument>|n (e.g. performance improvise with guitar)")
                return
            has_instrument, instrument_obj = _character_has_instrument(caller, instrument_spec)
            if not has_instrument:
                caller.msg("You need an instrument matching \"%s\" to improvise. Get or hold one first." % instrument_spec)
                return
            if getattr(caller.ndb, "performance_task", None) or getattr(caller.ndb, "performance_improvising", False):
                caller.msg("You're already performing or improvising. Use |wperformance stop|n first.")
                return
            # Improvise is harder than a rehearsed performance: apply a hidden penalty to the roll
            # and do not fire a big success/failure audience echo before the first pose.
            if hasattr(caller, "roll_check"):
                spec_mod = get_specialization_roll_bonus(caller, SPECIALIZATION_STAGE)
                outcome, result = caller.roll_check(
                    ["charisma"], ARTISTRY_SKILL, modifier=-10 + spec_mod
                )
                caller.ndb.performance_outcome = outcome
                caller.ndb.performance_result = result
            caller.ndb.performance_improvising = True
            caller.msg("|gYou start improvising with %s. Your poses and says will appear in |wbright white|n and draw audience reactions. Use |wperformance stop|n to stop.|n" % (instrument_obj.get_display_name(caller) if instrument_obj else instrument_spec))
            return

        # --- performance play <name> with <instrument> ---
        if not args.lower().startswith("play ") or " with " not in args.lower():
            caller.msg("Usage: |wperformance list|n, |wperformance play <name> with <instrument>|n, |wperformance improvise with <instrument>|n, or |wperformance stop|n")
            return
        rest = args[5:].strip()
        part, _, instrument = rest.partition(" with ")
        title = part.strip()
        instrument_spec = (instrument or "").strip()
        if not title:
            caller.msg("Give the name of the performance (e.g. |wperformance play The Ballad of the Wastes with guitar|n).")
            return
        if not instrument_spec:
            caller.msg("Specify an instrument (e.g. |wperformance play %s with guitar|n)." % title)
            return

        has_instrument, instrument_obj = _character_has_instrument(caller, instrument_spec)
        if not has_instrument:
            caller.msg("You need an instrument matching \"%s\" to perform. Get or hold one first." % instrument_spec)
            return

        normalized = _normalize_title(title)
        compositions = getattr(caller.db, "compositions", None) or {}
        lines = compositions.get(normalized)
        if not lines:
            caller.msg("You have no performance named \"%s\". Use |wperformance compose %s|n to create it." % (title, title))
            return

        if getattr(caller.ndb, "performance_lines", None):
            caller.msg("You're already performing. Use |wperformance stop|n first.")
            return

        if not hasattr(caller, "roll_check"):
            caller.msg("You cannot perform right now.")
            return

        spec_mod = get_specialization_roll_bonus(caller, SPECIALIZATION_STAGE)
        outcome, result = caller.roll_check(["charisma"], ARTISTRY_SKILL, modifier=spec_mod)
        caller.ndb.performance_outcome = outcome
        caller.ndb.performance_result = result

        caller.ndb.performance_lines = list(lines)
        caller.ndb.performance_room_id = caller.location.id if caller.location else None
        caller.ndb.performance_cooldown_until = 0

        inst_name = instrument_obj.get_display_name(caller) if instrument_obj else instrument_spec
        caller.msg("|gYou begin your performance of \"%s\" with %s. Use |wperformance next|n to play each line (at least %s seconds apart). Use |wperformance stop|n to stop.|n" % (title, inst_name, PERFORMANCE_DELAY_SECONDS))