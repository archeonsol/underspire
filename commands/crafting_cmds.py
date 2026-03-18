"""
Crafting commands: CmdTailor, CmdSurvey, CmdRepairArmor.
"""

from commands.base_cmds import Command


class CmdSurvey(Command):
    """
    Inspect armor to determine protection and mobility impact. Requires arms_tech skill.

    Usage:
      survey <armor>
    """
    key = "survey"
    aliases = ["armor survey", "inspect armor"]
    locks = "cmd:all()"
    help_category = "General"

    def func(self):
        caller = self.caller
        if not self.args:
            caller.msg("Survey what? Usage: survey <armor>")
            return
        from world.armor import _is_armor
        from world.skills import SKILL_STATS

        obj = caller.search(self.args.strip(), location=caller)
        if not obj:
            obj = caller.search(self.args.strip(), location=caller.location)
        if not obj:
            return
        if not _is_armor(obj):
            caller.msg(f"{obj.get_display_name(caller)} is not armor you can survey.")
            return

        stats = SKILL_STATS.get("arms_tech", ["intelligence", "perception"])
        level, roll_value = caller.roll_check(stats, "arms_tech")

        if level == "Failure":
            caller.msg("You can't tell much about its armor properties.")
            return

        # Basic: damage types protected, mobility yes/no
        from world.combat.damage_types import DAMAGE_TYPES
        prot = getattr(obj.db, "protection", None) or {}
        types_protected = [dt for dt in DAMAGE_TYPES if prot.get(dt, 0) > 0]
        mobility = obj.get_mobility_impact() if hasattr(obj, "get_mobility_impact") else (getattr(obj.db, "mobility_impact", 0) or 0)
        has_mobility = mobility != 0

        if level == "Critical Success" or (level == "Full Success" and roll_value > 75):
            # High success: exact protection per type, exact mobility
            lines = ["|wArmor survey (detailed):|n"]
            if types_protected:
                for dt in types_protected:
                    base = prot.get(dt, 0)
                    effective = obj.get_protection(dt) if hasattr(obj, "get_protection") else base
                    lines.append("  %s: %s (effective %s)" % (dt.capitalize(), base, effective))
            else:
                lines.append("  No damage protection.")
            lines.append("  Mobility impact: %s" % mobility)
            quality = max(0, min(100, int(getattr(obj.db, "quality", 100) or 100)))
            lines.append("  Quality (durability): %s" % quality)
            caller.msg("\n".join(lines))
        else:
            # Basic success: types and mobility yes/no
            if types_protected:
                caller.msg("It protects against: %s." % ", ".join(types_protected))
            else:
                caller.msg("It offers no significant damage protection.")
            if has_mobility:
                caller.msg("It impacts mobility.")
            else:
                caller.msg("It does not impact mobility.")


class CmdRepairArmor(Command):
    """
    Restore armor quality (durability) using arms_tech. Use on worn or held armor.

    Usage:
      repair <armor>
    """
    key = "repair"
    aliases = ["repair armor", "fix armor"]
    locks = "cmd:all()"
    help_category = "General"

    def func(self):
        caller = self.caller
        if not self.args:
            caller.msg("Repair what? Usage: repair <armor>")
            return
        from world.armor import _is_armor, repair_armor
        from world.skills import SKILL_STATS

        obj = caller.search(self.args.strip(), location=caller)
        if not obj:
            obj = caller.search(self.args.strip(), location=caller.location)
        if not obj:
            return
        if not _is_armor(obj):
            caller.msg(f"{obj.get_display_name(caller)} is not armor you can repair.")
            return

        quality_before = max(0, min(100, int(getattr(obj.db, "quality", 100) or 100)))
        if quality_before >= 100:
            caller.msg("It's already in peak condition.")
            return

        stats = SKILL_STATS.get("arms_tech", ["intelligence", "perception"])
        level, _ = caller.roll_check(stats, "arms_tech")

        if level == "Failure":
            caller.msg("You fail to improve its condition.")
            return
        amount = 15 if level == "Critical Success" else (10 if level == "Full Success" else 5)
        repair_armor(obj, amount)
        quality_after = max(0, min(100, int(getattr(obj.db, "quality", 100) or 100)))
        caller.msg("You restore some of its condition. Quality: %s -> %s." % (quality_before, quality_after))


class CmdTailor(Command):
    """
    Tailor clothing from a bolt of material: set name, coverage, descriptions, tease, then finalize into a wearable garment.

    Usage:
      @tailor [bolt]                        - show draft status
      @tailor [bolt] name <name>           - set clothing name (used in %t, sdesc)
      @tailor [bolt] aliases <a1> [a2...]  - set aliases for targeting
      @tailor [bolt] desc <text>           - item description (when you look at it)
      @tailor [bolt] worndesc <text>       - worn description (used on body; supports $N, $P, $S)
      @tailor [bolt] tease <text>          - tease message ($N/$P/$S, $T/$R/$U, $I; see help tease)
      @tailor [bolt] coverage <part...>    - body parts covered (head, larm, torso, lthigh, etc.)
      @tailor [bolt] seethru               - toggle see-through (body/clothes show through this layer)
      @tailor [bolt] finalize              - roll tailoring and turn bolt into wearable clothing

    Layering:
      Tailored clothing is automatically assigned a clothing layer (0-5) based on its name:
        Layer 0 (underwear):
          bikini, panties, underwear, bra, thong, boxers, g-string, gstring, sock, stockings
        Layer 1 (default):
          everything not matching another layer word
        Layer 2:
          blindfold, glasses, vest
        Layer 3:
          jacket, waistcoat
        Layer 4 (coats/robes):
          tailcoat, coat, labcoat, topcoat, overcoat, longcoat, greatcoat, browncoat,
          trenchcoat, watchcoat, trench, robe, habit, muumuu, hawaiian, bolero,
          apron, scrubs, bathrobe, armband, obi, duster
        Layer 5 (outer accessories/boots):
          tie, boots, cane, umbrella, blindfold, habit, shawl, scarf, armband, necktie,
          cummerbund, belt, veil, parka, balaclava, bandana, bandanna, sticker, badge

      You cannot wear lower-layer items over higher-layer ones on the same body parts
      (e.g. a bra over a trenchcoat), and you cannot stack multiple outer jackets/boots
      on the same layer covering the same body part. Tailored jackets/boots also conflict
      with armored jackets/boots on the same coverage.
    """
    key = "@tailor"
    aliases = []
    locks = "cmd:all()"
    help_category = "General"
    usage_typeclasses = ["typeclasses.bolt_of_cloth.BoltOfCloth"]
    usage_hint = "|w@tailor|n (to make clothing)"

    def func(self):
        caller = self.caller
        from world.rpg.tailoring import tailor_parse_args
        bolt_spec, subcmd, value = tailor_parse_args(self.args)

        if not bolt_spec and not subcmd:
            caller.msg("Usage: @tailor [bolt] [name|aliases|desc|worndesc|tease|coverage|seethru|finalize] ...")
            return

        if bolt_spec:
            bolt = caller.search(bolt_spec, location=caller)
            if not bolt:
                return
            if not getattr(bolt, "is_draft", lambda: False)():
                caller.msg(f"{bolt.get_display_name(caller)} is not a bolt of cloth.")
                return
        else:
            # Find a bolt in inventory
            from typeclasses.bolt_of_cloth import BoltOfCloth
            bolts = [o for o in caller.contents if isinstance(o, BoltOfCloth)]
            if not bolts:
                caller.msg("You aren't holding a bolt of cloth. Specify which bolt or get one.")
                return
            if len(bolts) > 1:
                caller.msg("You have more than one bolt; specify which: @tailor <bolt> ...")
                return
            bolt = bolts[0]

        if not subcmd:
            # Status
            st = bolt.get_draft_status()
            caller.msg("|wDraft status|n for %s:" % bolt.get_display_name(caller))
            caller.msg("  Material: %s" % st.get("material", "bolt of cloth"))
            caller.msg("  Name: %s" % st["name"])
            caller.msg("  Aliases: %s" % (st["aliases"] or "(none)"))
            caller.msg("  Desc: %s" % (st["desc"] or "(none)"))
            caller.msg("  Worn: %s" % (st["worn_desc"] or "(none)"))
            caller.msg("  Tease: %s" % (st["tease"] or "(none)"))
            caller.msg("  Coverage: %s" % (st["covered_parts"] or "(none)"))
            see = getattr(bolt.db, "draft_see_thru", False)
            caller.msg("  See-thru: %s" % ("yes" if see else "no"))
            return

        if subcmd == "name":
            if not value:
                caller.msg("Usage: @tailor [bolt] name <name>")
                return
            bolt.db.draft_name = value
            caller.msg("Draft name set to: %s" % value)
            return

        if subcmd == "aliases":
            aliases = value.split() if value else []
            bolt.db.draft_aliases = aliases
            caller.msg("Draft aliases set to: %s" % (aliases or "(none)"))
            return

        if subcmd == "desc":
            bolt.db.draft_desc = value or ""
            caller.msg("Draft description set.")
            return

        if subcmd in ("worndesc", "worn"):
            bolt.db.draft_worn_desc = value or ""
            caller.msg("Draft worn description set.")
            return

        if subcmd == "tease":
            if any(q in (value or "") for q in ('"', "'")):
                caller.msg("Tease messages cannot contain quotes. Avoid using \" or ' in the text.")
                return
            bolt.db.draft_tease = value or ""
            caller.msg("Draft tease message set.")
            return

        if subcmd == "coverage":
            from typeclasses.bolt_of_cloth import resolve_coverage_args
            from world.medical import BODY_PARTS_HEAD_TO_FEET
            parts = value.split() if value else []
            canonical, invalid = resolve_coverage_args(parts)
            if invalid:
                caller.msg("Unknown body parts: %s. Use: %s" % (", ".join(invalid), ", ".join(BODY_PARTS_HEAD_TO_FEET)))
                return
            bolt.db.draft_covered_parts = canonical
            caller.msg("Coverage set to: %s" % canonical)
            return

        if subcmd in ("seethru", "see-thru"):
            current = bool(getattr(bolt.db, "draft_see_thru", False))
            bolt.db.draft_see_thru = not current
            caller.msg("See-thru set to: %s" % ("yes" if bolt.db.draft_see_thru else "no"))
            return

        if subcmd == "finalize":
            from world.rpg.tailoring import finalize_bolt_to_clothing
            clothing, msg = finalize_bolt_to_clothing(bolt, caller)
            caller.msg(msg)
            return

        caller.msg("Unknown subcommand. Use: name, aliases, desc, worndesc, tease, coverage, seethru, finalize.")
