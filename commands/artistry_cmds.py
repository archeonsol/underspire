"""Artistry specialization: pick branch at E-tier or view current focus."""

from commands.base_cmds import Command


class CmdArtistry(Command):
    """
    View or set your Artistry specialization (at grade E or higher).

    Usage:
      artistry                 - show current specialization
      artistry specialize      - open the choice menu (if eligible)
      artistry specialize <tailoring|stage|visual>  - choose a branch
    """

    key = "artistry"
    locks = "cmd:all()"
    help_category = "General"

    def func(self):
        from world.rpg.artistry_specialization import (
            SPECIALIZATION_E_THRESHOLD,
            SPECIALIZATION_STAGE,
            SPECIALIZATION_TAILORING,
            SPECIALIZATION_VISUAL,
            get_artistry_specialization,
            needs_artistry_specialization_choice,
            open_artistry_specialization_menu,
            set_artistry_specialization,
        )

        caller = self.caller
        args = (self.args or "").strip().lower()

        if not args:
            cur = get_artistry_specialization(caller)
            if not cur:
                if needs_artistry_specialization_choice(caller):
                    caller.msg(
                        "|yArtistry|n specialization is available. Use |wartistry specialize|n to choose."
                    )
                else:
                    caller.msg("You have no Artistry specialization (requires grade E).")
            else:
                labels = {
                    SPECIALIZATION_TAILORING: "tailoring",
                    SPECIALIZATION_STAGE: "stage performance",
                    SPECIALIZATION_VISUAL: "visual arts",
                }
                caller.msg(
                    "|yArtistry specialization|n: |w%s|n."
                    % labels.get(cur, cur)
                )
            return

        parts = args.split()
        if parts[0] != "specialize":
            caller.msg("Use |wartistry|n, |wartistry specialize|n, or |wartistry specialize tailoring|stage|visual|n.")
            return

        if len(parts) == 1:
            if needs_artistry_specialization_choice(caller):
                open_artistry_specialization_menu(caller)
            elif get_artistry_specialization(caller):
                caller.msg("You already have an Artistry specialization.")
            else:
                caller.msg("You are not yet eligible (need Artistry grade E).")
            return

        branch = parts[1]
        key_map = {
            "tailoring": SPECIALIZATION_TAILORING,
            "stage": SPECIALIZATION_STAGE,
            "visual": SPECIALIZATION_VISUAL,
        }
        spec_key = key_map.get(branch)
        if not spec_key:
            caller.msg(
                "Use |wartistry specialize tailoring|n, |wstage|n, or |wvisual|n."
            )
            return

        if get_artistry_specialization(caller):
            caller.msg("You already have an Artistry specialization.")
            return

        if not hasattr(caller, "get_skill_level") or int(
            caller.get_skill_level("artistry") or 0
        ) < SPECIALIZATION_E_THRESHOLD:
            caller.msg("You are not yet eligible (need Artistry grade E).")
            return

        if set_artistry_specialization(caller, spec_key):
            labels = {
                SPECIALIZATION_TAILORING: "tailoring",
                SPECIALIZATION_STAGE: "stage performance",
                SPECIALIZATION_VISUAL: "visual arts",
            }
            caller.msg("|gYou specialize in %s.|n" % labels.get(spec_key, spec_key))
