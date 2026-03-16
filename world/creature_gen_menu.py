"""
EvMenu for generating a custom PvE creature: name, stats (max_hp, armor_rating, base_attack),
room_pose, and a list of moves (instant or telegraph). Builder+.
"""
from evennia.utils.evmenu import EvMenuGotoAbortMessage


def _data(caller):
    return getattr(caller.ndb, "creature_gen", None) or {}


def node_start(caller, raw_string, **kwargs):
    data = _data(caller)
    text = (
        "|wC R E A T U R E   G E N E R A T O R|n\n\n"
        "Enter the creature's |wname (key)|n (e.g. |wGiant Rat|n):\n\n"
        "Current: |c%s|n" % data.get("key", "Custom Creature")
    )
    options = [{"key": "_default", "goto": "node_apply_name"}]
    return text, options


def node_apply_name(caller, raw_string, **kwargs):
    name = (raw_string or "").strip()
    if not name:
        raise EvMenuGotoAbortMessage("|rName cannot be empty.|n")
    data = _data(caller)
    data["key"] = name
    return node_stats(caller, raw_string, **kwargs)


def node_stats(caller, raw_string, **kwargs):
    data = _data(caller)
    text = (
        "|wStats|n\n\n"
        "  |wName|n: %s\n"
        "  |wMax HP|n: %s\n"
        "  |wArmor rating|n: %s\n"
        "  |wBase attack|n: %s\n"
        "  |wRoom pose|n: %s\n\n"
        "Choose an option to set a value, or continue to moves."
    ) % (
        data.get("key", "?"),
        data.get("max_hp", 100),
        data.get("armor_rating", 10),
        data.get("base_attack", 50),
        (data.get("room_pose") or "standing here")[:40],
    )
    options = [
        {"key": "1", "desc": "Set name (key)", "goto": ("node_start", kwargs)},
        {"key": "2", "desc": "Set max HP", "goto": ("node_input", {"field": "max_hp", "next": "node_stats", "prompt": "Enter max HP (integer):"})},
        {"key": "3", "desc": "Set armor rating", "goto": ("node_input", {"field": "armor_rating", "next": "node_stats", "prompt": "Enter armor rating (integer):"})},
        {"key": "4", "desc": "Set base attack", "goto": ("node_input", {"field": "base_attack", "next": "node_stats", "prompt": "Enter base attack (integer):"})},
        {"key": "5", "desc": "Set room pose", "goto": ("node_input", {"field": "room_pose", "next": "node_stats", "prompt": "Enter room pose (e.g. 'lumbering here'):"})},
        {"key": "6", "desc": "Next: Define moves", "goto": "node_moves"},
    ]
    return text, options


def node_input(caller, raw_string, **kwargs):
    """Generic text/number input; kwargs: field, next, prompt."""
    text = kwargs.get("prompt", "Enter value:")
    options = [{"key": "_default", "goto": ("node_apply_input", kwargs)}]
    return text, options


def node_apply_input(caller, raw_string, **kwargs):
    raw = (raw_string or "").strip()
    field = kwargs.get("field")
    next_node_name = kwargs.get("next", "node_stats")
    data = _data(caller)
    if field == "max_hp":
        try:
            data["max_hp"] = max(1, int(raw))
        except ValueError:
            raise EvMenuGotoAbortMessage("|rEnter a number.|n")
    elif field == "armor_rating":
        try:
            data["armor_rating"] = max(0, int(raw))
        except ValueError:
            raise EvMenuGotoAbortMessage("|rEnter a number.|n")
    elif field == "base_attack":
        try:
            data["base_attack"] = max(0, int(raw))
        except ValueError:
            raise EvMenuGotoAbortMessage("|rEnter a number.|n")
    elif field == "room_pose":
        data["room_pose"] = raw or "standing here"
    next_func = globals().get(next_node_name)
    if next_func:
        return next_func(caller, raw_string, **kwargs)
    return node_stats(caller, raw_string, **kwargs)


def node_moves(caller, raw_string, **kwargs):
    data = _data(caller)
    moves = data.get("moves") or {}
    lines = []
    for k, v in moves.items():
        dmg = v.get("damage", 0)
        typ = v.get("type", "instant")
        w = v.get("weight", 10)
        lines.append("  |w%s|n: %s, dmg %s, weight %s" % (k, typ, dmg, w))
    moves_text = "\n".join(lines) if lines else "  (none yet)"
    text = (
        "|wMoves|n\n\n"
        "%s\n\n"
        "Add moves (instant or telegraph). Each has: key, weight, type, damage, message(s)."
    ) % moves_text
    options = [
        {"key": "1", "desc": "Add move", "goto": "node_add_move_key"},
        {"key": "2", "desc": "Remove move", "goto": "node_remove_move"},
        {"key": "3", "desc": "Back to stats", "goto": "node_stats"},
        {"key": "4", "desc": "Done: Review and create", "goto": "node_confirm"},
    ]
    return text, options


def node_add_move_key(caller, raw_string, **kwargs):
    text = "Enter |wmove key|n (e.g. |wslash|n, |wbite|n):"
    options = [{"key": "_default", "goto": ("node_apply_move_key", kwargs)}]
    return text, options


def node_apply_move_key(caller, raw_string, **kwargs):
    key = (raw_string or "").strip().lower().replace(" ", "_")
    if not key:
        raise EvMenuGotoAbortMessage("|rKey cannot be empty.|n")
    data = _data(caller)
    data["_pending_move"] = {"key": key, "weight": 50, "type": "instant", "damage": 20, "msg": "{name} hits {target}!"}
    return node_add_move_weight(caller, raw_string, **kwargs)


def node_add_move_weight(caller, raw_string, **kwargs):
    data = _data(caller)
    p = data.get("_pending_move") or {}
    text = "Enter |wweight|n (chance to pick this move, e.g. 50):\nCurrent: %s" % p.get("weight", 50)
    options = [{"key": "_default", "goto": "node_apply_move_weight"}]
    return text, options


def node_apply_move_weight(caller, raw_string, **kwargs):
    try:
        w = max(1, min(100, int((raw_string or "50").strip())))
    except ValueError:
        raise EvMenuGotoAbortMessage("|rEnter a number 1-100.|n")
    data = _data(caller)
    if data.get("_pending_move"):
        data["_pending_move"]["weight"] = w
    return node_add_move_type(caller, raw_string, **kwargs)


def node_add_move_type(caller, raw_string, **kwargs):
    text = "Enter |wtype|n: |winstant|n or |wtelegraph|n:"
    options = [{"key": "_default", "goto": "node_apply_move_type"}]
    return text, options


def node_apply_move_type(caller, raw_string, **kwargs):
    t = (raw_string or "").strip().lower()
    if t not in ("instant", "telegraph"):
        t = "instant"
    data = _data(caller)
    if data.get("_pending_move"):
        data["_pending_move"]["type"] = t
    if t == "telegraph":
        data["_pending_move"]["telegraph_msg"] = "|r{name} winds up!|n"
        data["_pending_move"]["execute_msg"] = "|R{name} strikes {target}!|n"
        data["_pending_move"]["ticks"] = 1
    return node_add_move_damage(caller, raw_string, **kwargs)


def node_add_move_damage(caller, raw_string, **kwargs):
    text = "Enter |wdamage|n (integer):"
    options = [{"key": "_default", "goto": "node_apply_move_damage"}]
    return text, options


def node_apply_move_damage(caller, raw_string, **kwargs):
    try:
        d = max(0, int((raw_string or "20").strip()))
    except ValueError:
        raise EvMenuGotoAbortMessage("|rEnter a number.|n")
    data = _data(caller)
    if data.get("_pending_move"):
        data["_pending_move"]["damage"] = d
    return node_add_move_msg(caller, raw_string, **kwargs)


def node_add_move_msg(caller, raw_string, **kwargs):
    data = _data(caller)
    p = data.get("_pending_move") or {}
    text = (
        "Enter |wmessage|n for when the move hits (use |w{name}|n and |w{target}|n):\n"
        "Example: |w{name} slashes at {target}!|n\n\n"
        "Current: %s" % p.get("msg", "{name} hits {target}!")
    )
    options = [{"key": "_default", "goto": "node_apply_move_msg"}]
    return text, options


def node_apply_move_msg(caller, raw_string, **kwargs):
    msg = (raw_string or "").strip() or "{name} hits {target}!"
    data = _data(caller)
    if data.get("_pending_move"):
        data["_pending_move"]["msg"] = msg
    p = data["_pending_move"]
    if p.get("type") == "telegraph":
        return node_add_move_telegraph(caller, raw_string, **kwargs)
    # Save move and return to moves list
    key = p.get("key", "attack")
    moves = data.get("moves") or {}
    moves[key] = {"weight": p.get("weight", 50), "type": "instant", "damage": p.get("damage", 20), "msg": p.get("msg", msg)}
    data["moves"] = moves
    del data["_pending_move"]
    return node_moves(caller, raw_string, **kwargs)


def node_add_move_telegraph(caller, raw_string, **kwargs):
    text = "Enter |wtelegraph message|n (wind-up; use {name}, {target}):\nExample: |r{name} charges energy!|n"
    options = [{"key": "_default", "goto": "node_apply_move_telegraph"}]
    return text, options


def node_apply_move_telegraph(caller, raw_string, **kwargs):
    msg = (raw_string or "").strip() or "|r{name} winds up!|n"
    data = _data(caller)
    if data.get("_pending_move"):
        data["_pending_move"]["telegraph_msg"] = msg
    return node_add_move_execute(caller, raw_string, **kwargs)


def node_add_move_execute(caller, raw_string, **kwargs):
    text = "Enter |wexecute message|n (when hit lands; use {name}, {target}):"
    options = [{"key": "_default", "goto": "node_apply_move_execute"}]
    return text, options


def node_apply_move_execute(caller, raw_string, **kwargs):
    msg = (raw_string or "").strip() or "|R{name} strikes {target}!|n"
    data = _data(caller)
    if data.get("_pending_move"):
        data["_pending_move"]["execute_msg"] = msg
    p = data["_pending_move"]
    key = p.get("key", "attack")
    moves = data.get("moves") or {}
    moves[key] = {
        "weight": p.get("weight", 50),
        "type": "telegraph",
        "ticks": p.get("ticks", 1),
        "telegraph_msg": p.get("telegraph_msg", "|r{name} winds up!|n"),
        "execute_msg": p.get("execute_msg", msg),
        "damage": p.get("damage", 20),
    }
    data["moves"] = moves
    del data["_pending_move"]
    return node_moves(caller, raw_string, **kwargs)


def node_remove_move(caller, raw_string, **kwargs):
    data = _data(caller)
    moves = data.get("moves") or {}
    if not moves:
        caller.msg("No moves to remove.")
        return node_moves(caller, raw_string, **kwargs)
    text = "Enter the |wmove key|n to remove: " + ", ".join(moves.keys())
    options = [{"key": "_default", "goto": "node_apply_remove_move"}]
    return text, options


def node_apply_remove_move(caller, raw_string, **kwargs):
    key = (raw_string or "").strip().lower().replace(" ", "_")
    data = _data(caller)
    moves = data.get("moves") or {}
    if key in moves:
        del moves[key]
        data["moves"] = moves
        caller.msg("Removed move '%s'." % key)
    else:
        caller.msg("No such move.")
    return node_moves(caller, raw_string, **kwargs)


def node_confirm(caller, raw_string, **kwargs):
    data = _data(caller)
    moves = data.get("moves") or {}
    lines = [
        "|wSummary|n",
        "  Name: %s" % data.get("key", "?"),
        "  Max HP: %s | Armor: %s | Base attack: %s" % (data.get("max_hp", 100), data.get("armor_rating", 10), data.get("base_attack", 50)),
        "  Room pose: %s" % (data.get("room_pose") or "standing here"),
        "  Moves: %s" % ", ".join(moves.keys()) if moves else "  (none)",
        "",
        "Create this creature in your current room?"
    ]
    text = "\n".join(lines)
    options = [
        {"key": "1", "desc": "Yes, create creature", "goto": "node_do_create"},
        {"key": "2", "desc": "Back to moves", "goto": "node_moves"},
    ]
    return text, options


def node_do_create(caller, raw_string, **kwargs):
    data = _data(caller)
    loc = caller.location
    if not loc:
        caller.msg("|rYou have no location. Creature not created.|n")
        if hasattr(caller.ndb, "creature_gen"):
            del caller.ndb.creature_gen
        return None, None
    from evennia.utils.create import create_object
    try:
        creature = create_object("typeclasses.creatures.Creature", key=data.get("key", "Custom Creature"), location=loc)
        creature.db.max_hp = int(data.get("max_hp", 100))
        creature.db.current_hp = creature.db.max_hp
        creature.db.armor_rating = int(data.get("armor_rating", 10))
        creature.db.base_attack = int(data.get("base_attack", 50))
        creature.db.room_pose = data.get("room_pose") or "standing here"
        creature.db.creature_moves = dict(data.get("moves") or {})
        caller.msg("|gCreature |w%s|n created here. Set |wcurrent_target|n and run creature AI to have it act.|n" % creature.key)
    except Exception as e:
        caller.msg("|rCould not create creature: %s|n" % e)
    if hasattr(caller.ndb, "creature_gen"):
        del caller.ndb.creature_gen
    return None, None
