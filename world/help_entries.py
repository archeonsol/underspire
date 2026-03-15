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
            the wearer's/target's pronouns. They work in |wtease|n messages, |wdescribe_bodypart|n
            text, |wlp|n/|wpose|n (room pose), and clothing |wworndesc|n.

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

            describe_bodypart head = $S has a scar across $p brow.
            lp leaning on the wall, $p arms crossed.
            tease message: $N .flash $p $I at $T and .grin.
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
]
