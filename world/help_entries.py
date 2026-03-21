"""
File-based help entries. These complements command-based help and help entries
added in the database using the `sethelp` command in-game.

Control where Evennia reads these entries with `settings.FILE_HELP_ENTRY_MODULES`,
which is a list of python-paths to modules to read.

A module like this should hold a global `HELP_ENTRY_DICTS` list, containing
dicts that each represent a help entry. If no `HELP_ENTRY_DICTS` variable is
given, all top-level variables that are dicts in the module are read as help
entries.

Each dict is on the form
::

    {'key': <str>,
     'text': <str>}``     # the actual help text. Can contain # subtopic sections
     'category': <str>,   # optional, otherwise settings.DEFAULT_HELP_CATEGORY
     'aliases': <list>,   # optional
     'locks': <str>       # optional, 'view' controls seeing in help index, 'read'
                          #           if the entry can be read. If 'view' is unset,
                          #           'read' is used for the index. If unset, everyone
                          #           can read/view the entry.

"""

HELP_ENTRY_DICTS = [
    {
        "key": "tokens",
        "aliases": ["tease tokens", "pronoun tokens", "targeting tokens"],
        "category": "General",
        "text": """
            Pronoun and name tokens let you write one message that adapts to who sees it and to
            the wearer's/target's pronouns. They work in |wtease|n messages, |w@body|n
            part lines, |wlp|n/|wpose|n (room pose), and clothing |wworndesc|n.

            # Wearer / first person (doer)

            These refer to the character who is wearing the item, posing, or being looked at:

            |w$N|n / |w$n|n
                Name (capitalized / lowercase). E.g. "TS" or "ts".

            |w$P|n / |w$p|n
                Possessive (his, her, their). Capitalized for $P: "His", "Her", "Their".

            |w$S|n / |w$s|n
                Subject pronoun (he, she, they). Capitalized for $S: "He", "She", "They".

            # Target (tease only)

            When using |wtease <item> at <target>|n, these refer to the target:

            |w$T|n / |w$t|n
                Target's name (capitalized / lowercase).

            |w$R|n / |w$r|n
                Target's possessive (his, her, their). $R capitalized.

            |w$U|n / |w$u|n
                Target's subject pronoun (he, she, they). $U capitalized.

            # Item (tease only)

            |w$I|n / |w$i|n
                The clothing item's name (e.g. "t-shirt"). $I capitalized, $i lowercase.

            # Examples

            @body head = $S has a scar across $p brow.
            lp leaning on the wall, $p arms crossed.
            tease message: $N .flash $p $I at $T and .grin.
        """,
    },
    {
        "key": "performance",
        "aliases": ["perform", "compose", "improvise", "performance play", "performance stop"],
        "category": "Roleplay",
        "text": """
            Compose set pieces, play them with a guitar, or improvise live. The crowd reacts—good or bad—and anyone can try.
            You can store a limited number of compositions (minimum 5); the limit goes up with your Performance skill.

            # performance list

            Shows your stored compositions and how many slots you have. Use this to see what you can play or to check your limit before composing.

            # performance delete <name>

            Permanently remove one of your stored compositions. Use |wperformance list|n to see names.

            # performance compose <name>

            Opens the editor so you can write a performance. Each line becomes one pose when you play it.
            Use the usual pose tricks: |w.verb|n, leading |w,|n for scene-setting. Save with |w:wq|n.

            # performance play <name> with guitar

            Perform something you've composed. You need a guitar (in hand or in the room). The crowd reacts
            and your lines play out automatically until the piece ends or you stop.

            # performance improvise with guitar

            Go live with a guitar. Your poses and says show up in bright white and get audience reactions.
            Use |wperformance stop|n when you're done.

            # performance stop

            Ends a performance or improvise.

            # Getting a guitar

            Staff can spawn one with |wspawnitem GUITAR_WASTES|n. Otherwise find or buy one in the game.
        """,
    },
    {
        "key": "evennia",
        "aliases": ["ev"],
        "category": "General",
        "locks": "read:perm(Developer)",
        "text": """
            Evennia is a MU-game server and framework written in Python. You can read more
            on https://www.evennia.com.

            # subtopics

            ## Installation

            You'll find installation instructions on https://www.evennia.com.

            ## Community

            There are many ways to get help and communicate with other devs!

            ### Discussions

            The Discussions forum is found at https://github.com/evennia/evennia/discussions.

            ### Discord

            There is also a discord channel for chatting - connect using the
            following link: https://discord.gg/AJJpcRUhtF

        """,
    },
    # -------------------------------------------------------------------------
    # Staff-only: Creature system (PvE)
    # -------------------------------------------------------------------------
    {
        "key": "creatures",
        "aliases": ["creature system", "creature help", "pve", "spawn creature", "creatureset"],
        "category": "Admin",
        "locks": "read:perm(Builder)",
        "text": """
            # Creature system (PvE) — staff reference

            The creature framework provides PvE monsters and bosses that use raw combat stats
            (max_hp, armor_rating, base_attack) and a moveset (instant or telegraph attacks)
            instead of the human stat/skill curves. Only Builder+ can read this help.

            ## Overview

            - |wCreature|n is a typeclass (inherits Character) with |wis_creature|n set. It uses
              |wdb.max_hp|n, |wdb.armor_rating|n, |wdb.base_attack|n for combat math when players
              attack it; it does not use the 0–300 stat ladder.
            - Creatures have a |wmoveset|n: a dict of move keys to move specs. Each move has
              |wweight|n (chance to pick), |wtype|n (instant or telegraph), |wdamage|n, and
              message strings. Telegraph moves have a wind-up message, then after a delay they
              execute (execute_msg + damage).
            - When a creature has a |wcurrent_target|n, an AI ticker runs every ~8 seconds
              (CREATURE_AI_INTERVAL). Each tick it picks a move by weight and either executes
              it (instant) or starts a telegraph (then executes after CREATURE_TICK_INTERVAL
              seconds per tick).
            - Creatures do not flatline; at 0 HP they die and the AI ticker stops.

            ## Commands (Builder+)

            ### spawncreature

            |wspawncreature list|n
                Lists available creature types.

            |wspawncreature <type> [= name]|n
                Spawns a creature of that type in your room. Optional |w= Custom Name|n
                overrides the default key.

            Types: |wgutter hulk|n, |wspore runner|n, |wrust stalker|n, |wcreature|n (base Creature
            with no moves). Aliases: spawncreature, spawn creature, spawnc.

            # generatecreature

            |wgeneratecreature|n (aliases: gencreature, create creature, creature menu)
                Opens an EvMenu to build a custom creature: name, max_hp, armor_rating,
                base_attack, room_pose, and a list of moves. Each move has key, weight,
                type (instant/telegraph), damage, and message(s). Telegraph moves also
                ask for telegraph_msg and execute_msg. The result is a |wCreature|n with
                |wdb.creature_moves|n                 set so it uses your moveset.

            ### creatureset

            |wcreatureset <creature> target <player>|n
                Sets the creature's |wcurrent_target|n to that player and starts its AI
                ticker. The creature will pick moves and attack that player every ~8 seconds
                until the target dies, leaves the room, or you clear the target. Aliases:
                cset, creature target.

            |wcreatureset <creature> notarget|n
                Clears the creature's target and stops its AI ticker.

            ## Automatic targeting

            When a |wplayer|n uses |wattack <creature>|n, the creature automatically sets
            |wcurrent_target|n to the attacker and starts its AI ticker, so it fights back
            without staff having to run creatureset.

            ## Typeclasses and moves

            - |wtypeclasses.creatures.Creature|n — base class. |wget_moves()|n returns
              |wdb.creature_moves|n (used by generatecreature output).
            - |wGutterHulk|n, |wSporeRunner|n, |wRustStalker|n — subclasses with fixed
              key, stats, and |wget_moves()|n returning a class-level moves dict (swipe,
              rad_beam, crush / bite, spore_burst, lunge / slash, saw_charge, gouge).
            - Move spec keys: |wweight|n (int), |wtype|n "instant" or "telegraph",
              |wdamage|n (int), |wmsg|n (instant) or |wtelegraph_msg|n + |wexecute_msg|n
              (telegraph), |wticks|n (telegraph delay in ticks), optional |wunblockable|n,
              |wstamina_drain|n. Use |w{name}|n and |w{target}|n in messages.

            ## Implementation

            - |wworld.creature_combat|n: get_creature_moves, pick_creature_move,
              execute_creature_move, start_telegraph, creature_ai_tick,
              start_creature_ai_ticker, stop_creature_ai_ticker. CREATURE_AI_INTERVAL = 8s,
              CREATURE_TICK_INTERVAL = 3s per telegraph tick.
            - When a creature dies (at_damage, hp <= 0), |wstop_creature_ai_ticker|n is
              called so the ticker does not keep running.
        """,
    },
]
