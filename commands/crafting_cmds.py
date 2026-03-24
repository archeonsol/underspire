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
    Tailor clothing from a bolt of material: set name, coverage, descriptions, tease, optional alt-state, then finalize into a wearable garment.

    Usage:
      @tailor [bolt]                        - show draft status
      @tailor [bolt] name <name>           - set clothing name (used in %t, sdesc)
      @tailor [bolt] aliases <a1> [a2...]  - set aliases for targeting
      @tailor [bolt] desc <text>           - item description (when you look at it)
      @tailor [bolt] worndesc <text>       - worn description (used on body; supports $N, $P, $S)
      @tailor [bolt] tease <text>          - tease message ($N/$P/$S, $T/$R/$U, $I; see help tease)
      @tailor [bolt] coverage <part...>    - body parts covered (head, larm, torso, lthigh, etc.)
      @tailor [bolt] seethru               - toggle see-through (body/clothes show through this layer)
      @tailor [bolt] altstate              - switch tailoring edits between primary (A) and alternate (B) state
      @tailor [bolt] finalize              - roll artistry and turn bolt into wearable clothing
      @tailor modify <garment> tail        - add tail accommodation (coverage + desc note)
      @tailor modify <garment> no-tail     - remove tail accommodation

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
        from typeclasses.clothing import Clothing

        bolt_spec, subcmd, value = tailor_parse_args(self.args)

        if subcmd == "modify":
            if not (value or "").strip():
                caller.msg("Usage: @tailor modify <garment> tail|no-tail")
                return
            bits = value.split()
            if len(bits) < 2:
                caller.msg("Usage: @tailor modify <garment> tail|no-tail")
                return
            mode = bits[-1].lower()
            if mode not in ("tail", "no-tail"):
                caller.msg("Usage: @tailor modify <garment> tail|no-tail")
                return
            garment_spec = " ".join(bits[:-1])
            garment = caller.search(garment_spec, location=caller)
            if not garment:
                return
            if not isinstance(garment, Clothing):
                caller.msg("That isn't a tailored garment.")
                return
            TAIL_NOTE = "A tail slit has been cut in the back."
            parts = list(getattr(garment.db, "covered_parts", None) or [])
            if mode == "tail":
                if "tail" not in parts:
                    parts.append("tail")
                    garment.db.covered_parts = parts
                desc = (getattr(garment.db, "desc", None) or "").strip()
                if TAIL_NOTE not in desc:
                    garment.db.desc = (desc + "\n\n" + TAIL_NOTE).strip() if desc else TAIL_NOTE
                caller.msg("You add tail accommodation to %s." % garment.get_display_name(caller))
            else:
                garment.db.covered_parts = [p for p in parts if p != "tail"]
                desc = (getattr(garment.db, "desc", None) or "")
                if TAIL_NOTE in desc:
                    garment.db.desc = desc.replace(TAIL_NOTE, "").replace("\n\n\n", "\n\n").strip()
                caller.msg("You remove tail accommodation from %s." % garment.get_display_name(caller))
            return

        if not bolt_spec and not subcmd:
            caller.msg("Usage: @tailor [bolt] [name|aliases|desc|worndesc|tease|coverage|seethru|altstate|finalize] ...")
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
            active = getattr(bolt.db, "draft_active_state", "a") or "a"

            caller.msg("|wDraft status|n for %s:" % bolt.get_display_name(caller))
            caller.msg("  Material: %s" % st.get("material", "bolt of cloth"))

            # Name and aliases are primary (A) properties; hide them when viewing B.
            if active == "a":
                caller.msg("  Name: %s" % st["name"])
                caller.msg("  Aliases: %s" % (st["aliases"] or "(none)"))

            caller.msg("  Desc: %s" % (st["desc"] or "(none)"))
            caller.msg("  Worn: %s" % (st["worn_desc"] or "(none)"))
            caller.msg("  Tease: %s" % (st["tease"] or "(none)"))
            caller.msg("  Coverage: %s" % (st["covered_parts"] or "(none)"))
            see = getattr(bolt.db, "draft_see_thru", False)
            caller.msg("  See-thru: %s" % ("yes" if see else "no"))

            # Show toggleemote-you for the currently active alt-state (A/B) so tailors
            # can see, at a glance, what will fire on toggle without leaving this menu.
            if active == "b":
                cfg = getattr(bolt.db, "draft_state_b", None) or {}
                label = "B"
            else:
                cfg = getattr(bolt.db, "draft_state_a", None) or {}
                label = "A"
            t_you = cfg.get("toggle_emote_you") if cfg else None
            caller.msg("  %s toggleemote-you: %s" % (label, t_you or "(none)"))
            return

        if subcmd == "name":
            # Name is a primary (A) property; prevent editing while in alt/B view
            # to avoid confusion. Use altstate to swap back to A first.
            active = getattr(bolt.db, "draft_active_state", "a") or "a"
            if active == "b":
                caller.msg("You can only change the garment's name while in primary (A) state. Use @tailor [bolt] altstate to switch back.")
                return
            if not value:
                caller.msg("Usage: @tailor [bolt] name <name>")
                return
            bolt.db.draft_name = value
            caller.msg("Draft name set to: %s" % value)
            return

        if subcmd == "aliases":
            # Aliases are also shared; only editable in primary (A) view.
            active = getattr(bolt.db, "draft_active_state", "a") or "a"
            if active == "b":
                caller.msg("You can only change aliases while in primary (A) state. Use @tailor [bolt] altstate to switch back.")
                return
            aliases = value.split() if value else []
            bolt.db.draft_aliases = aliases
            caller.msg("Draft aliases set to: %s" % (aliases or "(none)"))
            return

        if subcmd == "desc":
            bolt.db.draft_desc = value or ""
            caller.msg("Draft description set.")
            return

        if subcmd in ("worndesc", "worn"):
            active = getattr(bolt.db, "draft_active_state", "a") or "a"
            if active == "b":
                cfg = getattr(bolt.db, "draft_state_b", None) or {}
                cfg["worn_desc"] = value or ""
                bolt.db.draft_state_b = cfg
                caller.msg("Draft alternate (state B) worn description set.")
            else:
                bolt.db.draft_worn_desc = value or ""
                caller.msg("Draft worn description set.")
            return

        if subcmd == "tease":
            if any(q in (value or "") for q in ('"', "'")):
                caller.msg("Tease messages cannot contain quotes. Avoid using \" or ' in the text.")
                return
            active = getattr(bolt.db, "draft_active_state", "a") or "a"
            if active == "b":
                cfg = getattr(bolt.db, "draft_state_b", None) or {}
                cfg["tease"] = value or ""
                bolt.db.draft_state_b = cfg
                caller.msg("Draft alternate (state B) tease message set.")
            else:
                bolt.db.draft_tease = value or ""
                caller.msg("Draft tease message set.")
            return

        if subcmd == "coverage":
            from typeclasses.bolt_of_cloth import resolve_coverage_args
            from world.medical import BODY_PARTS_HEAD_TO_FEET
            parts = value.split() if value else []
            canonical, invalid = resolve_coverage_args(parts)
            if invalid:
                cov_hint = ", ".join(BODY_PARTS_HEAD_TO_FEET) + ", tail"
                caller.msg("Unknown body parts: %s. Use: %s" % (", ".join(invalid), cov_hint))
                return
            active = getattr(bolt.db, "draft_active_state", "a") or "a"
            if active == "b":
                cfg = getattr(bolt.db, "draft_state_b", None) or {}
                cfg["covered_parts"] = canonical
                bolt.db.draft_state_b = cfg
                caller.msg("Alternate (state B) coverage set to: %s" % canonical)
            else:
                bolt.db.draft_covered_parts = canonical
                caller.msg("Coverage set to: %s" % canonical)
            return

        if subcmd in ("seethru", "see-thru"):
            active = getattr(bolt.db, "draft_active_state", "a") or "a"
            if active == "b":
                cfg = getattr(bolt.db, "draft_state_b", None) or {}
                current = bool(cfg.get("see_thru", False))
                cfg["see_thru"] = not current
                bolt.db.draft_state_b = cfg
                caller.msg(
                    "Alternate (state B) see-thru set to: %s"
                    % ("yes" if cfg["see_thru"] else "no")
                )
            else:
                current = bool(getattr(bolt.db, "draft_see_thru", False))
                bolt.db.draft_see_thru = not current
                caller.msg("See-thru set to: %s" % ("yes" if bolt.db.draft_see_thru else "no"))
            return

        if subcmd in ("statea", "stateb"):
            # Configure optional two-state behavior for the finished garment.
            # Usage examples:
            #   @tailor <bolt> statea coverage torso head
            #   @tailor <bolt> statea worndesc <text>
            #   @tailor <bolt> statea seethru
            #   @tailor <bolt> statea toggleemote-you <text>
            #   @tailor <bolt> statea clear
            attr_name = "draft_state_a" if subcmd == "statea" else "draft_state_b"
            cfg = getattr(bolt.db, attr_name, None) or {}

            # If called without further args, show the per-state menu/status only for
            # that state, including toggleemote-* values.
            if not value:
                cov = cfg.get("covered_parts") if cfg else None
                worn = cfg.get("worn_desc") if cfg else None
                see_flag = None
                if cfg and "see_thru" in cfg:
                    see_flag = "yes" if cfg.get("see_thru") else "no"
                t_you = cfg.get("toggle_emote_you") if cfg else None
                t_room = cfg.get("toggle_emote_room") if cfg else None

                label = "A" if subcmd == "statea" else "B"
                caller.msg(f"|wState {label} config|n for {bolt.get_display_name(caller)}:")
                caller.msg("  Coverage: %s" % (cov or "(none)"))
                caller.msg("  Worn: %s" % (worn or "(none)"))
                caller.msg("  See-thru: %s" % (see_flag if see_flag is not None else "(none)"))
                caller.msg("  toggleemote-you (when leaving state %s): %s" % (label, t_you or "(none)"))
                caller.msg(
                    "  Use: @tailor [bolt] %s <coverage|worndesc|seethru|toggleemote-you|clear> ..."
                    % subcmd
                )
                return

            parts = value.split(None, 1)
            field = parts[0].lower()
            rest = parts[1] if len(parts) > 1 else ""

            if field == "clear":
                setattr(bolt.db, attr_name, None)
                caller.msg("Draft %s configuration cleared." % ("state A" if subcmd == "statea" else "state B"))
                return

            if field == "coverage":
                from typeclasses.bolt_of_cloth import resolve_coverage_args
                from world.medical import BODY_PARTS_HEAD_TO_FEET

                cov_parts = rest.split() if rest else []
                canonical, invalid = resolve_coverage_args(cov_parts)
                if invalid:
                    cov_hint = ", ".join(BODY_PARTS_HEAD_TO_FEET) + ", tail"
                    caller.msg(
                        "Unknown body parts: %s. Use: %s"
                        % (", ".join(invalid), cov_hint)
                    )
                    return
                cfg["covered_parts"] = canonical
                setattr(bolt.db, attr_name, cfg)
                caller.msg(
                    "Draft %s coverage set to: %s"
                    % (subcmd, canonical or "(none)")
                )
                return

            if field in ("worndesc", "worn"):
                cfg["worn_desc"] = rest or ""
                setattr(bolt.db, attr_name, cfg)
                caller.msg("Draft %s worn description set." % subcmd)
                return

            if field in ("seethru", "see-thru", "see"):
                current = bool(cfg.get("see_thru", False))
                cfg["see_thru"] = not current
                setattr(bolt.db, attr_name, cfg)
                caller.msg(
                    "Draft %s see-thru set to: %s"
                    % (subcmd, "yes" if cfg["see_thru"] else "no")
                )
                return

            if field in ("toggleemote-you", "toggleemoteyou", "toggleemote_you"):
                cfg["toggle_emote_you"] = rest or ""
                setattr(bolt.db, attr_name, cfg)
                caller.msg("Draft %s toggleemote-you text set." % subcmd)
                return

            caller.msg(
                "Unknown %s option. Use: coverage, worndesc, seethru, toggleemote-you, clear."
                % subcmd
            )
            return

        if subcmd == "altstate":
            # Toggle which state @tailor edits/views: primary (A) or alternate (B).
            current = getattr(bolt.db, "draft_active_state", "a") or "a"
            new_state = "b" if current == "a" else "a"
            bolt.db.draft_active_state = new_state
            # Ensure a draft_state_b dict exists when switching into B, so later edits have a place to live.
            if new_state == "b" and not getattr(bolt.db, "draft_state_b", None):
                bolt.db.draft_state_b = {}
            label = "alternate (state B)" if new_state == "b" else "primary (state A)"
            caller.msg(f"@tailor now editing the {label} configuration.")
            return

        if subcmd == "finalize":
            from world.rpg.tailoring import finalize_bolt_to_clothing
            clothing, msg = finalize_bolt_to_clothing(bolt, caller)
            caller.msg(msg)
            return

        caller.msg(
            "Unknown subcommand. Use: name, aliases, desc, worndesc, tease, coverage, seethru, statea, stateb, finalize."
        )
