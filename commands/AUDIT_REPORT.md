# Commands Refactor Audit Report

**Scope:** `commands/` directory (all `*_cmds.py` modules) and `commands/default_cmdsets.py`  
**Date:** Post-refactor audit.

---

## 🚨 CRITICAL (Fix Immediately)

### 1. CmdLook does not inherit from base Command — flatline/dead bypass risk

- **File:** `commands/base_cmds.py`  
- **Line:** 61  
- **Issue:** `class CmdLook(DefaultCmdLook)` — CmdLook inherits from Evennia’s `DefaultCmdLook`, not from your `Command` class. Therefore it never runs `Command.at_pre_cmd()` and does not block flatlined or permanently dead characters. If the flatlined/unconscious cmdset is not active or is overridden, a dying/dead character could get a normal room look instead of the “You are dying…” message.
- **Recommendation:** Either make CmdLook inherit from `Command` and delegate to DefaultCmdLook behavior (e.g. mixin or explicit call), or override `at_pre_cmd` on CmdLook to perform the same flatline/dead check as in `Command.at_pre_cmd`.

---

### 2. multipuppet_cmds uses BaseCommand instead of Command

- **File:** `commands/multipuppet_cmds.py`  
- **Lines:** 5, 73, 128, 159  
- **Issue:** `from evennia.commands.command import Command as BaseCommand` and `class CmdAddPuppet(BaseCommand)` (and CmdPuppetList, CmdPuppetSlot). These are account-level commands (caller is Account), so they intentionally do not use the character `Command` that blocks flatline. This is **not a bug** — but it is an inconsistency: every other in-game command uses `commands.base_cmds.Command`. If you ever want account-level commands to go through a single base (e.g. for logging or permission hooks), consider a shared base; otherwise document that multipuppet uses Evennia’s base by design.

---

### 3. CmdSet imports still go through command.py (single point of failure)

- **File:** `commands/default_cmdsets.py`  
- **Lines:** 39–41, 52–54, 66–67, 80–81, 267–269, 296–301, 353–354  
- **Issue:** `SplinterPodCmdSet`, `CombatGrappleCmdSet`, `UnconsciousCmdSet`, `FlatlinedCmdSet`, `StaffOnlyPuppet`, `StaffOnlyUnpuppet`, and `AccountCmdSet` use `from commands.command import ...`. If `command.py` or any of its re-exported modules fails to load (e.g. missing name, circular import), all these cmdsets break.
- **Recommendation:** For resilience, consider importing directly from the specific modules (e.g. `from commands.death_cmds import CmdLeavePod`, `from commands.combat_cmds import CmdGrapple, CmdLetGo, CmdResist`) so a single broken module does not take down every cmdset that uses `command.py`.

---

## ⚠️ WARNING (Potential Bugs)

### 4. Silent failures — bare `except Exception: pass` (and similar)

The following swallow exceptions without logging; they can hide real bugs (e.g. missing imports, bad state):

| File | Line(s) | Context |
|------|--------|--------|
| `combat_cmds.py` | 17–18 | `_combat_caller`: Builder/Admin check |
| `combat_cmds.py` | 71–72, 84–85, 93–94 | CmdAttack: corpse/death/stamina imports |
| `combat_cmds.py` | 119–120 | CmdAttack: creature_combat import |
| `staff_cmds.py` | 33–34, 55–56 | CmdStats: puppet/caller resolution |
| `staff_cmds.py` | 385–386 | CmdStaffSheet: target stats fallback |
| `staff_cmds.py` | 456–457 | CmdStaffSetStat |
| `staff_cmds.py` | 989–990 | CmdTypeclasses: DefaultScript import |
| `staff_cmds.py` | 1008–1009 | CmdTypeclasses: typeclass discovery loop |
| `staff_cmds.py` | 1254–1255 | CmdSpawnOR |
| `roleplay_cmds.py` | 103–104, 125–126, 137–138, 164–165 | _run_emote / CmdDescribeBodypart |
| `roleplay_cmds.py` | 618–619 | CmdSdesc: original_name fallback |
| `multipuppet_cmds.py` | 18–19, 23–24 | _clear_multi_puppet_links_for_account |
| `death_cmds.py` | 29–30, 37–38, 53–54 | _can_use_ooc_room / _spirit_account / _get_pod_from_caller |
| `death_cmds.py` | 110–111, 152–153, 219–220 | CmdGoOOC, CmdSplinterMe, CmdReturnIC |
| `death_cmds.py` | 299–300, 304–305, 333–334, 340–341, 346–347, 354–355, 358–359, 363–364, 369–370, 379–380 | CmdGoLight: cleanup / disconnect loops |
| `scavenge_cmds.py` | 90–91, 115–116, 211–212, 340–341, 349–350, 384–385, 578–579 | Skin/butcher/sever/loot callbacks |
| `scavenge_cmds.py` | 21–22 | _loot_finish: generic Exception |
| `inventory_cmds.py` | 91–92, 133–134 | _obj_in_hands, _update_primary_wielded |
| `inventory_cmds.py` | 246–247 | CmdInventory: worn_set fallback |
| `inventory_cmds.py` | 626–627 | CmdStrip: Clothing import |
| `medical_cmds.py` | 196–197, 294–295 | CmdApply, CmdSurgery |
| `base_cmds.py` | 42–43, 52–53 | Command.at_pre_cmd |
| `base_cmds.py` | 103–104, 121–122 | CmdLook: aliases / chars fallback |
| `base_cmds.py` | 200–201, 210–211 | CmdGet.at_pre_cmd |

**Recommendation:** At minimum, log the exception (e.g. `evennia.utils.logger.log_trace()` or `logger.log_err`) before `pass` or re-raise in development so failures are visible.

---

### 5. _loot_finish and scavenge delay callbacks — silent return on exception

- **File:** `commands/scavenge_cmds.py`  
- **Lines:** 16–22 (`_loot_finish`), 134–136 (scavenge delay)  
- **Issue:** On `ImportError` or `Exception`, `_loot_finish` returns without notifying the player or logging. Scavenge delay failure calls `_finish_scavenge()` immediately but the player may not see an error. If world.death or world.grapple is missing, loot/scavenge can fail silently.
- **Recommendation:** Log the exception and, where possible, send a short message to the caller (e.g. “Something went wrong.”) so players and builders know the action did not complete.

---

### 6. death_cmds._get_pod_from_caller — broad `except Exception: pass`

- **File:** `commands/death_cmds.py`  
- **Line:** 53–54  
- **Issue:** `_get_pod_from_caller` returns `None` on any exception when searching for a pod by interior. Failures (e.g. search_typeclass or attribute errors) are invisible.
- **Recommendation:** Log the exception; optionally re-raise or return a sentinel so callers can distinguish “no pod” from “error while looking”.

---

### 7. Duplicate flatline/dead/unconscious checks across commands

- **Files / lines:**  
  - `base_cmds.py`: 45–56 (Command), 203–215 (CmdGet)  
  - `combat_cmds.py`: 74–86 (CmdAttack), 360–367 (CmdExecute)  
  - `death_cmds.py`: 17–39 (_can_use_ooc_room), 215–216 (CmdReturnIC)  
  - `scavenge_cmds.py`: 422–424, 487–490 (CmdSever)  
  - `medical_cmds.py`: 192–193, 290–291 (CmdApply, CmdSurgery)  
  - `staff_cmds.py`: 874–875, 903–915 (CmdRestore, CmdDebugKill)  
- **Issue:** The same logical checks (`is_flatlined`, `is_permanently_dead`, `is_unconscious`, `is_character_logged_off`) are repeated in many places. If the rules or API change (e.g. new death state), multiple files must be updated and can drift.
- **Recommendation:** Add a small helper (e.g. in `world.death` or `world.medical`) such as `can_act(character)` or `block_if_incapacitated(character, caller)` that centralizes these checks and returns a (bool, msg) or raises a small custom exception, then use it from each command.

---

## 💡 OPTIMIZATION (Code Smells)

### 8. Database access in loops (potential DB spam)

- **File:** `commands/staff_cmds.py`  
- **Lines:** 71–74, 79–82, 128–131, 141–144, 398–408  
- **Issue:** In CmdStats and CmdStaffSheet, loops over `STAT_KEYS` / `SKILL_KEYS` call `caller.get_stat_level(key)`, `caller.get_skill_level(key)`, `caller.get_stat_grade_adjective(...)`, etc. If those methods hit `caller.db.stats` / `caller.db.skills` every time, that’s repeated DB access inside the loop. Same for `target.get_stat_level` / `get_skill_level` in the staff sheet loop.
- **Recommendation:** Cache `caller.db.stats`, `caller.db.skills`, and `target.db.stats` / `target.db.skills` (or the result of a single “get all stats” helper) in local variables before the loop and use them inside.

---

### 9. death_cmds CmdGoLight — many nested try/except with `pass`

- **File:** `commands/death_cmds.py`  
- **Lines:** 330–380  
- **Issue:** Long block with multiple `for session in ...` and `try: ... except Exception: pass` branches. Hard to see which path ran and whether any failure is intentional.
- **Recommendation:** Extract small helpers (e.g. `_disconnect_sessions(account, reason)`, `_clear_death_attrs(account)`), use early returns, and log exceptions instead of bare `pass` so behavior is clear and debuggable.

---

### 10. Cyclomatic complexity — staff_cmds CmdTypeclasses

- **File:** `commands/staff_cmds.py`  
- **Lines:** ~974–1034  
- **Issue:** CmdTypeclasses walks packages, imports modules, filters by base class, and builds a list with several nested loops and conditionals. High branching and nesting.
- **Recommendation:** Extract “discover typeclasses in package” into a function that returns the list of paths; keep the command’s `func()` to parsing args, calling that function, and messaging. Same idea for other large staff commands (e.g. CmdXp advance loop).

---

### 11. Unused or redundant imports

- **File:** `commands/roleplay_cmds.py` — **Line:** 7  
  - `CMD_NOMATCH` is used (CmdNoMatch.key). No change needed.

- **File:** `commands/death_cmds.py` — **Line:** 7  
  - `CMD_NOMATCH` is used (CmdNoMatchFlatlined, CmdNoMatchUnconscious). No change needed.

No other obviously unused imports were found in the scanned `*_cmds.py` files.

---

### 12. CmdSet documentation and import style

- **File:** `commands/default_cmdsets.py`  
- **Line:** 9–10  
- **Issue:** Docstring says “To create new commands to populate the cmdset, see `commands/command.py`.” After the refactor, new commands live in the appropriate `*_cmds.py` module; `command.py` is only a re-export hub.
- **Recommendation:** Update the docstring to point to the relevant `commands/*_cmds.py` modules (and optionally to `command.py` for the re-export list).

---

## Summary Table

| Category   | Count |
|-----------|-------|
| Critical  | 3     |
| Warning   | 4     |
| Optimization | 5  |

---

## Dependency Graph (No Circular Loops Found)

- `base_cmds`: evennia only.  
- `combat_cmds` → base_cmds, world.combat.  
- `medical_cmds` → base_cmds, inventory_cmds.  
- `scavenge_cmds` → base_cmds, inventory_cmds.  
- `inventory_cmds` → base_cmds.  
- `survival_cmds` → base_cmds, inventory_cmds.  
- `death_cmds` → base_cmds, combat_cmds.  
- `staff_cmds` → base_cmds, roleplay_cmds.  
- `multipuppet_cmds` → evennia BaseCommand, media_cmds.  
- `media_cmds` → base_cmds.  

No circular imports detected between the new modules.

---

## CmdSet Coverage (CharacterCmdSet)

All commands imported in `CharacterCmdSet.at_cmdset_creation()` have a matching `self.add(...)` call. No missing adds were found. SplinterPodCmdSet adds CmdLeavePod; CombatGrappleCmdSet adds CmdGrapple, CmdLetGo, CmdResist; UnconsciousCmdSet and FlatlinedCmdSet add their look/no-match commands. AccountCmdSet imports and adds the expected account-level commands.

---

*End of audit report. Fix critical and warning items first; then tackle optimizations as needed.*
