"""
Player XP commands: @xp to view and spend XP on stats, skills, and languages.
"""

from commands.base_cmds import Command


class CmdXp(Command):
    """
    View XP and spend it to advance stats, skills, or languages.

    Usage:
      @xp                             - show XP and next-raise costs for stats/skills/languages
      @xp advance stat <name> [N]     - spend XP to raise a stat by N levels (default 1)
      @xp advance skill <name> [N]    - spend XP to raise a skill by N levels (default 1)
      @xp advance language <name> [N] - spend 10 XP per raise to add % to a language (default 1 raise)
    Languages: 0-400% (basic/learning/fluent/native). % gained per 10 XP depends on Intelligence.
    Number of languages you can learn is limited by Intelligence (average = 1 other language).

    XP: 2 per 6h window, max 4 drops per 24h (8 XP/day).
    """

    key = "@xp"
    aliases = ["@advance", "@progress"]
    locks = "cmd:all()"
    help_category = "General"

    def func(self):
        from world.rpg.xp import (
            XP_CAP,
            get_xp_cost_stat,
            get_xp_cost_skill,
            xp_cost_for_stat_level,
            xp_cost_for_skill_level,
            _stat_level,
            _skill_level,
            _stat_cap_level,
            _skill_cap_level,
        )
        from world.levels import get_stat_grade, get_skill_grade, MAX_STAT_LEVEL, MAX_LEVEL
        from world.chargen import STAT_KEYS
        from world.skills import SKILL_KEYS, SKILL_DISPLAY_NAMES

        caller = self.caller
        xp = float(getattr(caller.db, "xp", 0) or 0)
        cap = int(getattr(caller.db, "xp_cap", XP_CAP) or XP_CAP)
        language_xp_spent = float(getattr(caller.db, "xp_spent_on_languages", 0) or 0)
        effective_cap = cap + language_xp_spent

        if not self.args or self.args.strip().lower() in ("show", ""):
            # Column widths for aligned display (match chargen)
            NAME_W, LETTER_W, ADJ_W = 24, 5, 20
            xp_display = int(xp) if xp == int(xp) else round(xp, 2)
            cap_display = int(effective_cap) if effective_cap == int(effective_cap) else round(effective_cap, 2)
            output = "|cXP|n: |w{}|n (cap |w{}|n)".format(xp_display, cap_display)
            if xp >= effective_cap:
                output += " |x(you are at your XP cap; you will not gain more time-based XP until this cap is raised)|n"
            output += "\n\n"
            output += "|cXP needed for next raise:|n\n\n"
            output += "|wStats|n:\n"
            for sk in STAT_KEYS:
                cost, _ = get_xp_cost_stat(caller, sk)
                letter = get_stat_grade(_stat_level(caller, sk))
                adj = caller.get_stat_grade_adjective(letter, sk)
                name_pad = sk.capitalize().ljust(NAME_W)
                letter_part = ("[" + letter + "] ").ljust(LETTER_W)
                adj_pad = adj.ljust(ADJ_W)
                if cost is None:
                    output += "  {} {} {} |x(at cap)|n\n".format(name_pad, letter_part, adj_pad)
                else:
                    cost_str = str(int(cost)) if cost == int(cost) else str(round(cost, 2))
                    output += "  {} {} {} next raise: |w{} XP|n\n".format(
                        name_pad, letter_part, adj_pad, cost_str
                    )
            output += "\n|wSkills|n:\n"
            for sk in SKILL_KEYS:
                cost, _ = get_xp_cost_skill(caller, sk)
                letter = get_skill_grade(_skill_level(caller, sk))
                adj = caller.get_skill_grade_adjective(letter)
                label = SKILL_DISPLAY_NAMES.get(sk, sk.replace("_", " ").title())
                name_pad = label.ljust(NAME_W)
                letter_part = ("[" + letter + "] ").ljust(LETTER_W)
                adj_pad = adj.ljust(ADJ_W)
                if cost is None:
                    output += "  {} {} {} |x(at cap)|n\n".format(name_pad, letter_part, adj_pad)
                else:
                    cost_str = str(int(cost)) if cost == int(cost) else str(round(cost, 2))
                    output += "  {} {} {} next raise: |w{} XP|n\n".format(
                        name_pad, letter_part, adj_pad, cost_str
                    )
            # Languages: 0-400% per language (basic/learning/fluent/native). Costs XP to improve; exact gains are hidden.
            from world.language import (
                LEARNABLE_LANGUAGE_KEYS,
                get_language_percent,
                get_language_level_name,
                max_other_languages,
                language_xp_percent_gain,
                LANGUAGE_MAX_PERCENT,
            )

            output += "\n|wLanguages|n (you can invest XP here; details are obscured in-world):\n"
            max_slots = max_other_languages(caller)
            learned = [k for k in LEARNABLE_LANGUAGE_KEYS if get_language_percent(caller, k) > 0]
            slots_used = len(learned)
            output += "  English (native). Slots: |w{}|n/|w{}|n other languages.\n".format(slots_used, max_slots)
            for lang_key in LEARNABLE_LANGUAGE_KEYS:
                pct = get_language_percent(caller, lang_key)
                level_name = get_language_level_name(pct)
                label = lang_key.replace("_", " ").title()
                if pct >= LANGUAGE_MAX_PERCENT:
                    output += "  {} {} (native) |x(at cap)|n\n".format(label.ljust(NAME_W), level_name)
                elif lang_key in learned or pct > 0:
                    output += "  {} {} |w(you have some grasp of this language)|n\n".format(
                        label.ljust(NAME_W), level_name
                    )
                else:
                    output += "  {} |x(not learned yet)|n\n".format(
                        label.ljust(NAME_W)
                    )
            output += (
                "\nUse |w@xp advance stat <name> [N]|n, |w@xp advance skill <name> [N]|n, "
                "or |w@xp advance language <name> [N]|n to spend XP. Confirm with |w@xp confirm|n."
            )
            caller.msg(output)
            return

        parts = self.args.strip().split()
        # Handle confirm/cancel for pending XP spend
        if parts and parts[0].lower() == "confirm":
            pending = getattr(caller.db, "pending_xp_advance", None)
            if not pending:
                caller.msg(
                    "You have no pending XP advance. Use |w@xp advance stat <name> [N]|n, "
                    "|w@xp advance skill <name> [N]|n, or |w@xp advance language <name> [N]|n."
                )
            else:
                from world.levels import get_stat_grade, get_skill_grade

                sub = pending["sub"]
                attr_key = pending["attr_key"]
                levels_gained = pending["levels_gained"]
                total_spent = pending["total_spent"]
                new_val = pending["new_val"]  # stored level for stats (0-300) or skill level (0-150)
                cur = pending["cur"]
                cap = pending["cap"]
                label = pending["label"]
                db_key = pending["db_key"]
                xp_now = float(getattr(caller.db, "xp", 0) or 0)
                if xp_now < total_spent:
                    caller.msg(
                        "You no longer have enough XP (need {}). Advance cancelled.".format(total_spent)
                    )
                    del caller.db.pending_xp_advance
                else:
                    if sub == "language":
                        # IMPORTANT: db attributes are proxies; mutate via copy → reassign so Evennia saves.
                        existing = getattr(caller.db, db_key, None) or {}
                        try:
                            langs = dict(existing)
                        except Exception:
                            langs = {}
                        langs[attr_key] = int(new_val)
                        setattr(caller.db, db_key, langs)
                        caller.db.xp = xp_now - total_spent
                        # Language XP does not count toward cap; track so they can earn it back
                        caller.db.xp_spent_on_languages = float(
                            getattr(caller.db, "xp_spent_on_languages", 0) or 0
                        ) + total_spent
                        from world.language import get_language_level_name

                        level_name = get_language_level_name(new_val)
                        spent_str = (
                            str(int(total_spent))
                            if total_spent == int(total_spent)
                            else str(round(total_spent, 2))
                        )
                        msg = "You spend {} XP. {} is now {} ({}%).".format(
                            spent_str, label, level_name, int(new_val)
                        )
                        if int(new_val) >= cap:
                            msg += " You've reached native level."
                        caller.msg(msg)
                        del caller.db.pending_xp_advance
                    else:
                        # Determine grade-letter helper
                        get_grade_fn = get_stat_grade if sub == "stat" else get_skill_grade

                        # SAFELY EXTRACT, MODIFY, AND FORCE-SAVE THE DICTIONARY
                        existing = getattr(caller.db, db_key, None) or {}
                        try:
                            db_dict = dict(existing)
                        except Exception:
                            db_dict = {}

                        # Stats: store raw 0-300 "stored_new" value; display = stored // 2 is derived.
                        # Skills: stored = display = 0-150.
                        stored_new = int(new_val)
                        db_dict[attr_key] = stored_new

                        # Force the database to save
                        setattr(caller.db, db_key, db_dict)

                        # Deduct XP
                        caller.db.xp = xp_now - total_spent
                        remainder = caller.db.xp

                        # Calculate display output
                        old_letter = get_grade_fn(cur)
                        new_letter = get_grade_fn(stored_new)
                        letter_changed = old_letter != new_letter
                        spent_str = (
                            str(int(total_spent))
                            if total_spent == int(total_spent)
                            else str(round(total_spent, 2))
                        )
                        if levels_gained == 1:
                            msg = "You spend {} XP.".format(spent_str)
                        else:
                            msg = "You spend {} XP and raise {} {} time{}.".format(
                                spent_str, label, levels_gained, "s" if levels_gained > 1 else ""
                            )
                        if letter_changed:
                            if sub == "stat":
                                adj = caller.get_stat_grade_adjective(new_letter, attr_key)
                            else:
                                adj = caller.get_skill_grade_adjective(new_letter)
                            msg += " {} is now [{}] {}.".format(label, new_letter, adj)
                        rem_str = (
                            str(int(remainder))
                            if remainder == int(remainder)
                            else str(round(remainder, 2))
                        )
                        if stored_new >= cap and remainder > 0:
                            msg += " You reached your cap; {} XP remains.".format(rem_str)
                        caller.msg(msg)
                        del caller.db.pending_xp_advance
            return

        if parts and parts[0].lower() == "cancel":
            if getattr(caller.db, "pending_xp_advance", None):
                del caller.db.pending_xp_advance
                caller.msg("Pending XP advance cancelled.")
            else:
                caller.msg("You have no pending XP advance to cancel.")
            return

        if len(parts) < 2 or parts[0].lower() != "advance":
            caller.msg(
                "Usage: @xp [show] | @xp advance stat <name> [N] | @xp advance skill <name> [N] | "
                "@xp advance language <name> [N] | @xp confirm | @xp cancel"
            )
            return

        sub = parts[1].lower()
        # Parse: advance stat <name> [N] | advance skill <name> [N] | advance language <name> [N]
        if sub not in ("stat", "skill", "language"):
            caller.msg(
                "Use |w@xp advance stat <name> [N]|n, |w@xp advance skill <name> [N]|n, "
                "or |w@xp advance language <name> [N]|n."
            )
            return
        if len(parts) < 3:
            caller.msg("Specify which stat, skill, or language to advance.")
            return

        target_name = parts[2].strip().lower()
        try:
            bulk_n = int(parts[3]) if len(parts) > 3 else 1
            if bulk_n < 1:
                bulk_n = 1
        except (ValueError, IndexError):
            bulk_n = 1
        if not target_name:
            caller.msg("Specify which stat, skill, or language to advance.")
            return

        def advance_loop(cur, cap, bulk_n, xp_available, get_cost_fn):
            """
            Bulk-buy loop: sum cost step-by-step until cap or XP runs out.

            Returns (levels_gained, total_spent, new_val).

            Important behavior:
            - If we hit the stat/skill cap before reaching bulk_n, we allow a
              partial raise up to the cap.
            - If we run out of XP *before* reaching bulk_n (and are not at cap),
              we treat this as "insufficient XP for that many raises" and
              return (0, 0.0, cur) so the caller can show an error instead of
              revealing how many raises you *could* afford.
            """

            total_spent = 0.0
            levels_gained = 0
            xp_limited = False
            while levels_gained < bulk_n and cur + levels_gained < cap:
                cost = get_cost_fn(cur + levels_gained)
                if cost is None:
                    break
                if xp_available - total_spent < cost:
                    xp_limited = True
                    break
                total_spent += cost
                levels_gained += 1
            new_val = min(cap, cur + levels_gained)
            # If this was a bulk request and we stopped early *due to XP* (not cap),
            # treat it as "not enough XP for that many raises".
            if bulk_n > 1 and xp_limited and levels_gained < bulk_n and new_val < cap:
                return 0, 0.0, cur
            return levels_gained, total_spent, new_val

        def format_insufficient_xp(get_cost_fn, cur, xp_available):
            """
            Inform the player that they don't have enough XP to perform the requested
            advance, without revealing the exact XP cost or how close they are.
            """

            caller.msg("You lack the XP required to raise that much right now.")

        if sub == "stat":
            stat_key = None
            for s in STAT_KEYS:
                if s.startswith(target_name) or target_name == s:
                    stat_key = s
                    break
            if not stat_key:
                caller.msg("Unknown stat. Use one of: {}.".format(", ".join(STAT_KEYS)))
                return
            cur = _stat_level(caller, stat_key)
            stat_cap = _stat_cap_level(caller, stat_key)
            if cur >= stat_cap:
                caller.msg("That stat is already at its cap.")
                return
            from world.rpg.xp import get_stat_cost

            levels_gained, total_spent, new_val = advance_loop(
                cur, stat_cap, bulk_n, xp, get_stat_cost
            )
            if levels_gained == 0:
                format_insufficient_xp(get_stat_cost, cur, xp)
                return
            spent_str = (
                str(int(total_spent))
                if total_spent == int(total_spent)
                else str(round(total_spent, 2))
            )
            caller.db.pending_xp_advance = {
                "sub": "stat",
                "attr_key": stat_key,
                "levels_gained": levels_gained,
                "total_spent": total_spent,
                "new_val": new_val,
                "cur": cur,
                "cap": stat_cap,
                "label": stat_key.capitalize(),
                "db_key": "stats",
            }
            raise_msg = "time" if levels_gained == 1 else "times"
            caller.msg(
                "Raise |w{}|n |w{}|n time(s)? This will spend |w{}|n XP. "
                "Type |w@xp confirm|n to confirm or |w@xp cancel|n to cancel.".format(
                    stat_key.capitalize(), levels_gained, spent_str, levels_gained, raise_msg
                )
            )
            return

        if sub == "skill":
            skill_key = None
            for s in SKILL_KEYS:
                if s.startswith(target_name) or target_name == s:
                    skill_key = s
                    break
            if not skill_key:
                caller.msg(
                    "Unknown skill. Use one of: {}.".format(
                        ", ".join(
                            SKILL_DISPLAY_NAMES.get(s, s.replace("_", " ").title())
                            for s in SKILL_KEYS
                        )
                    )
                )
                return
            cur = _skill_level(caller, skill_key)
            skill_cap = _skill_cap_level(caller, skill_key)
            if cur >= skill_cap:
                caller.msg("That skill is already at its cap.")
                return
            from world.rpg.xp import get_skill_cost

            levels_gained, total_spent, new_val = advance_loop(
                cur, skill_cap, bulk_n, xp, get_skill_cost
            )
            if levels_gained == 0:
                format_insufficient_xp(get_skill_cost, cur, xp)
                return
            label = SKILL_DISPLAY_NAMES.get(skill_key, skill_key.replace("_", " ").title())
            spent_str = (
                str(int(total_spent))
                if total_spent == int(total_spent)
                else str(round(total_spent, 2))
            )
            caller.db.pending_xp_advance = {
                "sub": "skill",
                "attr_key": skill_key,
                "levels_gained": levels_gained,
                "total_spent": total_spent,
                "new_val": new_val,
                "cur": cur,
                "cap": skill_cap,
                "label": label,
                "db_key": "skills",
            }
            raise_msg = "time" if levels_gained == 1 else "times"
            caller.msg(
                "Raise |w{}|n |w{}|n time(s)? This will spend |w{}|n XP. "
                "Type |w@xp confirm|n to confirm or |w@xp cancel|n to cancel.".format(
                    label, levels_gained, spent_str, levels_gained, raise_msg
                )
            )
            return

        if sub == "language":
            from world.language import (
                resolve_language_key,
                LEARNABLE_LANGUAGE_KEYS,
                get_language_percent,
                max_other_languages,
                language_xp_percent_gain,
                LANGUAGE_XP_COST,
                LANGUAGE_MAX_PERCENT,
            )

            lang_key = resolve_language_key(target_name)
            if not lang_key or lang_key == "english":
                caller.msg(
                    "You cannot spend XP on English (everyone has it). Choose: {}.".format(
                        ", ".join(LEARNABLE_LANGUAGE_KEYS)
                    )
                )
                return
            if lang_key not in LEARNABLE_LANGUAGE_KEYS:
                caller.msg("Unknown language. Choose: {}.".format(", ".join(LEARNABLE_LANGUAGE_KEYS)))
                return
            cur = get_language_percent(caller, lang_key)
            if cur >= LANGUAGE_MAX_PERCENT:
                caller.msg("You already speak that language at native level.")
                return
            # New language? Check slot limit (only count learnable languages they have started)
            learned = [k for k in LEARNABLE_LANGUAGE_KEYS if get_language_percent(caller, k) > 0]
            max_slots = max_other_languages(caller)
            if lang_key not in learned and len(learned) >= max_slots:
                caller.msg(
                    "You've reached your language slot limit ({} other language(s)); "
                    "raise Intelligence to learn more.".format(max_slots)
                )
                return
            percent_gain = language_xp_percent_gain(caller)
            # How many purchases can we do? Each adds percent_gain, cap 400; each purchase costs 10 XP (hidden from players).
            room = LANGUAGE_MAX_PERCENT - cur
            purchases_to_cap = max(0, (room + percent_gain - 1) // percent_gain)
            purchases_affordable = int(xp // LANGUAGE_XP_COST)
            max_purchases = min(bulk_n, purchases_to_cap, purchases_affordable)
            if max_purchases <= 0:
                if purchases_affordable == 0:
                    caller.msg(
                        "You need at least {} XP to raise a language (10 XP per raise).".format(
                            LANGUAGE_XP_COST
                        )
                    )
                else:
                    caller.msg("That language is already at native.")
                return
            total_xp_needed = LANGUAGE_XP_COST * max_purchases
            if xp < total_xp_needed:
                caller.msg(
                    "You need {} XP to buy {} language raise(s) ({} XP each). You have {} XP.".format(
                        total_xp_needed, max_purchases, LANGUAGE_XP_COST, int(xp)
                    )
                )
                return
            # Only commit the number we can afford and that fit in cap
            levels_gained = max_purchases
            total_spent = LANGUAGE_XP_COST * levels_gained
            new_val = min(LANGUAGE_MAX_PERCENT, cur + levels_gained * percent_gain)
            label = lang_key.replace("_", " ").title()
            caller.db.pending_xp_advance = {
                "sub": "language",
                "attr_key": lang_key,
                "levels_gained": levels_gained,
                "total_spent": total_spent,
                "new_val": int(new_val),
                "cur": cur,
                "cap": LANGUAGE_MAX_PERCENT,
                "label": label,
                "db_key": "languages",
            }
            caller.msg(
                "Invest XP to deepen your grasp of |w{}|n? This will cost |w{}|n XP. "
                "Type |w@xp confirm|n to confirm or |w@xp cancel|n to cancel.".format(
                    label, total_spent
                )
            )
            return

        caller.msg(
            "Use |w@xp advance stat <name> [N]|n, |w@xp advance skill <name> [N]|n, "
            "or |w@xp advance language <name> [N]|n."
        )