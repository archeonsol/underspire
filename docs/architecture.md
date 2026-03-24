# Architecture Overview

Cyberpunk MUD built on [Evennia](https://www.evennia.com/) (Python game engine, Django ORM). This document maps the systems and their connections — not an API reference.

---

## Foundation

| Layer | Technology |
|---|---|
| Game engine | Evennia (Twisted + Django) |
| Database | SQLite (`server/evennia.db3`) via Django ORM |
| Web client | Django + Evennia webclient |
| Config | `server/conf/settings.py` |

**Persistence model:**
- `object.db.key = value` — persisted to DB; survives server reloads
- `object.ndb.key = value` — in-memory only; cleared on reload

Server lifecycle hooks live in `server/conf/at_server_startstop.py`. On startup it creates all persistent scripts and OOC channels.

---

## Object Model

```
DefaultObject (Evennia)
└── ObjectParent mixin  ← key validation (blocks ^ and # prefixes)
    ├── Object           typeclasses/objects.py
    │   ├── NetworkedObject   (physical device with Matrix interface)
    │   └── MatrixObject      (virtual-only; Router, Programs)
    ├── Room             typeclasses/rooms.py
    │   └── MatrixNode        (virtual location in cyberspace)
    ├── Exit             typeclasses/exits.py
    └── DefaultCharacter
        ├── Character    typeclasses/characters.py  ← main player character
        ├── Creature     typeclasses/creatures.py   ← PvE monsters
        └── MatrixAvatar typeclasses/matrix/avatars.py  ← virtual presence when jacked in
```

**Character is assembled from five mixins** (stacked via multiple inheritance):

| Mixin | File | Adds |
|---|---|---|
| `MatrixIdMixin` | `typeclasses/mixins/` | Matrix ID chip, virtual identity |
| `RoleplayMixin` | `typeclasses/mixins/roleplay_mixin.py` | Emotes, recognition, display names, movement flavor |
| `MedicalMixin` | `typeclasses/mixins/` | HP, injuries, bleeding, organ damage |
| `RPGCharacterMixin` | `typeclasses/mixins/rpg_character_mixin.py` | Stats (0–300), skills (0–150), grade letters, roll system, buffs |
| `FurnitureMixin` | `typeclasses/mixins/furniture_mixin.py` | Sit/lie on objects, vehicle seats |

**Account model** (`typeclasses/accounts.py`): OOC entity, not in-game. Puppets one Character at a time. Max 1 character per account.

---

## Systems

### Combat
`world/combat/` · `commands/combat_cmds.py` · `commands/range_cmds.py` · `commands/cover_commands.py`

- One `CombatInstance` per active fight (UUID-keyed, tracks participants, rounds, initiative)
- `engine.py` resolves each attack: roll → S-curve probability (`rolls.py`) → damage → armor soak → hit location → apply injury
- Combat ticker in `tickers.py` drives the round loop automatically
- Sub-systems: grapple (`grapple.py`), range bands (`range_system.py`), cover bonuses (`cover.py`), armor degradation (`armor.py`), damage types (`damage_types.py`)
- State is enforced via cmdset priority (see Command System)

### Medical
`world/medical/` · `commands/medical_cmds.py`

- Injuries occupy HP capacity (a 30-HP wound takes 30 capacity out of max)
- Treatment quality ladder: untreated → field-dressed → clinical → surgical
- Separate tracking for: bleeding (time-based HP drain), infection (spreads untreated), organ damage (applies stat penalties), fractures (body part penalties)
- Surgery and cybersurgery via interactive menu (`medical_menu.py`, `medical_surgery.py`, `cybersurgery.py`)
- Salvage system: harvest organs/cyberware from corpses (`salvage.py`)
- Medical scanner tool gives diagnostic output

### Matrix / Cyberspace
`typeclasses/matrix/` · `commands/matrix_cmds.py`

**Physical layer:**
- `DiveRig` — reclined jack-in chair; `JackInMixin` manages connection state
- `Handset` — portable device for basic Matrix access and Network comms
- `Hub` — creates a private Matrix node
- `NetworkedObject` — any physical device with a Matrix interface (camera, terminal, lock, console)

**Virtual layer:**
- `MatrixNode` — virtual location; can be persistent or ephemeral (auto-cleaned when empty)
- `MatrixAvatar` — player's virtual presence when jacked in
- `Router` — virtual relay; meatspace rooms link to routers for network coverage
- Programs (carried by avatars): `SysInfoProgram`, `CmdExeProgram`, `CRUDProgram`, `ExfilProgram`, `InfilProgram`, `SkeletonKeyProgram` (ACL manipulation), `ICEpickProgram` (ICE combat)
- ICE behavior driven by `matrix/scripts.py`

**Jack-in flow:**
1. Character sits in DiveRig
2. `jack in` → `DiveRig.jack_in()` creates `MatrixAvatar` in linked `MatrixNode`
3. Puppet switches: Character → MatrixAvatar (physical body stays in meatspace, vulnerable)
4. `jack out` destroys avatar, returns puppet to Character
5. Connection state stored in `DiveRig.db.active_connection`

### Network / Communications
`world/matrix_ids.py` · `world/matrix_accounts.py` · `world/matrix_groups.py` · `commands/handset_cmds.py` · `commands/network_cmds.py`

- **Handset**: calls, texts, photos, Matrix ID management, jailbroken identities
- **Network** (meatspace-only): global chat gated by room signal coverage
- **Matrix groups**: org/faction encrypted channels (`matrix_groups.py`)
- Matrix IDs registered globally; alias validation: 2–10 alphanumeric chars

### RPG Progression
`world/rpg/xp.py` · `world/rpg/skills.py` · `commands/player_cmds.py` · `commands/sheet_cmds.py`

- 7 stats: strength, perception, endurance, charisma, intelligence, agility, luck (0–300, display halved)
- 23 skills (0–150); each governed by a stat pair
- Grade letter display: U–A (21 tiers)
- XP: 2 per 6h window, cap 3050; costs scale nonlinearly
- Cyberware buffs applied through Evennia's `BuffHandler` (`character.buffs`)

### Character Generation
`world/rpg/chargen.py` · `world/main_menu.py`

Multi-step menu at login: stat allocation → skill distribution → descriptions → pronoun → background. Characters flagged `db.needs_chargen = True` until complete.

### Cyberware
`typeclasses/cyberware.py` · `world/cyberware_buffs.py` · `commands/cyberware_cmds.py`

- Installed on character (not inventory); persisted in `character.db.cyberware`
- Provides stat/skill buffs via `BuffHandler`; can conflict by body part or uniqueness
- Activation commands: `surge` (burst mode), `claws`, `skinweave`
- Installation/removal via cybersurgery system

### Crafting & Survival
`world/rpg/crafting.py` · `world/rpg/tailoring.py` · `world/rpg/scavenging.py` · `world/rpg/survival.py`

- Tailoring: custom armor creation from cloth bolts
- Salvage/scavenge: resource gathering from environment and corpses
- Repair armor: restore armor protection
- Hunger/thirst tracked on character; food/drink items in world

### Death & Revival
`world/death.py` · `world/rpg/cloning.py` · `commands/death_cmds.py`

- **Flatline** (0 HP): `FlatlinedCmdSet` loads — character can only look and receive help
- **Unconscious** (0 stamina from grapple): similar restrictions
- **Permanent death**: leaves corpse; player can go OOC as spirit in limbo
- **Splinter pod**: cloning respawn system; `splinterme` command

### Vehicles
`typeclasses/vehicles.py` · `commands/vehicle_cmds.py`

- Vehicles are mobile containers; passengers ride inside
- Engine states: off/running; fuel, speed, part system
- `drive` moves vehicle + all passengers; exits place character at vehicle location

### Broadcast / Media
`typeclasses/broadcast.py` · `commands/media_cmds.py`

- `Camera`: records room messages, feeds live to connected `Television`
- `Television`: displays live feed or plays back a `Cassette`
- `Cassette`: stores timestamped recordings persistently

### Roleplay
`typeclasses/mixins/roleplay_mixin.py` · `world/rpg/emote.py` · `commands/roleplay_cmds.py`

- Short description (`sdesc`): what others see at a glance
- Emotes and poses with pronoun substitution
- Recognition and memory system (per-character relationship tracking)
- Body part descriptions, voice/accent, scent (`perfume.py`), languages

---

## Command System

**Base `Command` class** (`commands/base_cmds.py`):
- Blocks all commands when character is flatlined/dead (checked in `at_pre_cmd()`)
- Parses `/switch` syntax; extracts `self.switches` and `self.args`
- Records profiling timestamps in `at_pre_cmd()` / `at_post_cmd()`

**Cmdset merging** (`commands/default_cmdsets.py`):

Higher priority wins when cmdsets conflict.

| CmdSet | Priority | Active when |
|---|---|---|
| `CharacterCmdSet` | default | Always (base player commands) |
| `CombatGrappleCmdSet` | 120 | Always merged in (grapple/letgo available during combat) |
| `GrappledCmdSet` | 180 | Character is grappled — restricts to look + resist |
| `UnconsciousCmdSet` | 200 | Knocked out — look only |
| `FlatlinedCmdSet` | 200 | At 0 HP — look only |
| `SplinterPodCmdSet` | 110 | Inside a splinter pod |

**Staff commands**: locked with `perm(Builder)`; live in `commands/staff_cmds.py`. Includes spawning, setstat/setskill, goto/summon, npc tools, debug-kill, etc.

---

## Server Scripts

All created by `at_server_startstop.py` on startup:

| Script key | Purpose |
|---|---|
| `stamina_regen` | Periodic stamina recovery for all characters |
| `bleeding_tick` | Bleeding damage over time |
| `staff_pending` | Staff approval review queue |
| `matrix_cleanup` | Purge empty ephemeral MatrixNodes |
| `matrix_connection_check` | Health-check active jack-in connections |
| `handset_message_cleanup` | Clear stale handset text buffers |
| `profiling` | Aggregate command performance monitoring |

Combat instances have their own per-fight tickers (managed by `world/combat/tickers.py`).

---

## System Interconnections

| From | To | How |
|---|---|---|
| Combat damage | Medical | `engine.py` calls `character.add_injury()` |
| Grapple (0 stamina) | Death | `grapple.py` calls `set_unconscious()` → loads UnconsciousCmdSet |
| Cyberware | Stats/Skills | Buffs via `character.buffs` (BuffHandler); `get_display_stat()` / `get_skill_level()` apply mods |
| Matrix jack-in | Puppet system | DiveRig switches puppet from Character to MatrixAvatar |
| Handset | Matrix IDs | Reads/spoofs Matrix ID registry |
| Camera | Room messages | `room.msg_contents()` hooks feed into `feed_cameras_in_location()` |
| Vehicle drive | Room/exits | Moves vehicle object; passengers travel with it |
| Profiling | All commands | `at_pre_cmd()` / `at_post_cmd()` hooks on base Command class |
| Death state | Command access | `make_flatlined()` swaps in FlatlinedCmdSet (priority 200) |

---

## Key File Index

| Domain | Path |
|---|---|
| **Characters** | `typeclasses/characters.py` |
| Character mixins | `typeclasses/mixins/` |
| Accounts | `typeclasses/accounts.py` |
| Rooms | `typeclasses/rooms.py` |
| Objects | `typeclasses/objects.py` |
| Creatures | `typeclasses/creatures.py` |
| **Matrix (virtual)** | `typeclasses/matrix/avatars.py`, `rooms.py`, `objects.py` |
| Matrix devices | `typeclasses/matrix/devices/` |
| Matrix programs | `typeclasses/matrix/programs/` |
| **Combat engine** | `world/combat/engine.py`, `rolls.py`, `instance.py` |
| Grapple | `world/combat/grapple.py` |
| **Medical core** | `world/medical/__init__.py`, `injuries.py`, `cybersurgery.py` |
| **RPG systems** | `world/rpg/xp.py`, `skills.py`, `chargen.py`, `emote.py` |
| Death & revival | `world/death.py`, `world/rpg/cloning.py` |
| Cyberware | `typeclasses/cyberware.py`, `world/cyberware_buffs.py` |
| Vehicles | `typeclasses/vehicles.py` |
| Broadcast | `typeclasses/broadcast.py` |
| **Commands (all)** | `commands/` |
| Cmdset structure | `commands/default_cmdsets.py` |
| Staff commands | `commands/staff_cmds.py` |
| **Server config** | `server/conf/settings.py` |
| Server lifecycle | `server/conf/at_server_startstop.py` |
| Prototypes | `world/prototypes/` |
| Constants/grades | `world/constants.py`, `world/levels.py`, `world/grades.py` |
| Profiling | `world/profiling.py` |
| UI utilities | `world/ui_utils.py` |
