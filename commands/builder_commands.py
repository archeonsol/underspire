"""
Builder QoL commands: butag, buhere, budig, budesc, etc.
Prefixed with 'bu' to leave short names free. Locked to Builder only.
"""
from evennia import Command
from evennia.utils.create import create_object
from typeclasses.matrix.rooms import MatrixNode
from typeclasses.matrix.exits import MatrixExit


class CmdTag(Command):
    """
    Add, remove, or list tags on an object.
    Usage:
      butag [obj] = tagname[/remove]
      butag [obj]                    (list tags on obj)
      butag here = clone_spawn       (tag current room)
    If obj is omitted, 'here' (current room) is used.
    """
    key = "butag"
    locks = "cmd:perm(Builder)"
    help_category = "Building"

    def func(self):
        caller = self.caller
        args = (self.args or "").strip()
        if not args:
            caller.msg("Usage: |wbutag [obj] = tagname|n or |wbutag [obj] = tagname/remove|n or |wbutag [obj]|n to list.")
            return
        if "=" in args:
            left, right = args.split("=", 1)
            obj_spec = left.strip()
            tag_spec = right.strip()
            remove = tag_spec.endswith("/remove") or "/remove" in tag_spec
            if remove:
                tag_spec = tag_spec.replace("/remove", "").strip()
            if not tag_spec and not remove:
                caller.msg("Give a tag name after =.")
                return
        else:
            obj_spec = args.strip()
            tag_spec = None
            remove = False
        obj = None
        if not obj_spec or obj_spec.lower() in ("here", "room"):
            obj = caller.location
            if not obj:
                caller.msg("You are nowhere.")
                return
        else:
            obj = caller.search(obj_spec)
            if not obj:
                return
        if not hasattr(obj, "tags"):
            caller.msg("That object doesn't support tags.")
            return
        if tag_spec is None:
            tags = obj.tags.all()
            if not tags:
                caller.msg("|w%s|n has no tags." % obj.get_display_name(caller))
            else:
                caller.msg("|w%s|n tags: %s" % (obj.get_display_name(caller), ", ".join(tags)))
            return
        if remove:
            if obj.tags.has(tag_spec):
                obj.tags.remove(tag_spec)
                caller.msg("Removed tag |w%s|n from %s." % (tag_spec, obj.get_display_name(caller)))
            else:
                caller.msg("%s doesn't have that tag." % obj.get_display_name(caller))
        else:
            obj.tags.add(tag_spec)
            caller.msg("Added tag |w%s|n to %s." % (tag_spec, obj.get_display_name(caller)))


class CmdHere(Command):
    """
    Show current room info: name, #dbref, tags, exit count.
    Usage: buhere
    """
    key = "buhere"
    locks = "cmd:perm(Builder)"
    help_category = "Building"

    def func(self):
        caller = self.caller
        loc = caller.location
        if not loc:
            caller.msg("You are nowhere.")
            return
        name = loc.get_display_name(caller)
        dbref = "#%s" % loc.id
        tags = loc.tags.all() if hasattr(loc, "tags") else []
        tags_str = ", ".join(tags) if tags else "none"
        exits = [e for e in (loc.exits or []) if e]
        caller.msg(
            "|w%s|n  %s\n  Tags: %s  Exits: %d"
            % (name, dbref, tags_str, len(exits))
        )


class CmdListCmds(Command):
    """
    Debug: list all command keys in your current merged cmdset.
    Use to verify e.g. 'done' (leave pod) is available.
    Usage: bulistcmds [filter]
    """
    key = "bulistcmds"
    locks = "cmd:perm(Builder)"
    help_category = "Building"

    def func(self):
        self.cmdset.make_unique(self.caller)
        keys = sorted(set(cmd.key for cmd in self.cmdset if cmd))
        filter_arg = (self.args or "").strip().lower()
        if filter_arg:
            keys = [k for k in keys if filter_arg in k.lower()]
        self.caller.msg("Commands in set (%d): %s" % (len(keys), ", ".join(keys)))


class CmdCloneSpawn(Command):
    """
    Tag the current room as the clone spawn (where clones wake).
    Usage: buclone_spawn
    """
    key = "buclone_spawn"
    locks = "cmd:perm(Builder)"
    help_category = "Building"

    def func(self):
        caller = self.caller
        loc = caller.location
        if not loc:
            caller.msg("You are nowhere.")
            return
        if hasattr(loc, "tags"):
            loc.tags.add("clone_spawn")
            caller.msg("This room is now the |wclone spawn|n. Characters who use |wgo shard|n after death will awaken here.")
        else:
            caller.msg("This object doesn't support tags.")


def _parse_exit_spec(spec):
    """Parse 'name' or 'name;alias1;alias2' into (key, aliases list)."""
    spec = (spec or "").strip()
    if not spec:
        return "out", []
    parts = [p.strip() for p in spec.split(";") if p.strip()]
    key = parts[0] if parts else "out"
    aliases = parts[1:] if len(parts) > 1 else []
    return key, aliases


class CmdDig(Command):
    """
    Create a new room and link it with exits. Uses game Room/Exit typeclasses.
    Usage: budig <room name> = <exit out>[, <exit back>]
    Exit format: name or name;alias1;alias2  (e.g. west;w  or south;s;down)
    Example: budig Testing = west;w, east;e
    Use /tel to teleport to the new room after creating.

    Note: Cannot create meatspace rooms from Matrix rooms. Use mdig for Matrix rooms.
    """
    key = "budig"
    switch_options = ("tel", "teleport")
    locks = "cmd:perm(Builder)"
    help_category = "Building"

    def func(self):
        caller = self.caller
        args = (self.args or "").strip()
        teleport = "tel" in getattr(self, "switches", []) or "teleport" in getattr(self, "switches", [])
        if "=" not in args:
            caller.msg("Usage: |wbudig <room name> = <exit out>[, <exit back>]|n  Exits: |wname;alias|n e.g. budig Kitchen = south;s, north;n")
            return
        room_spec, exit_spec = args.split("=", 1)
        room_name = room_spec.strip()
        exit_spec = exit_spec.strip()
        if not room_name:
            caller.msg("Give a room name.")
            return
        if not exit_spec:
            caller.msg("Give at least one exit name after =.")
            return
        parts = [p.strip() for p in exit_spec.split(",")]
        out_spec = parts[0] if parts else "out"
        back_spec = parts[1] if len(parts) > 1 else None
        exit_out, out_aliases = _parse_exit_spec(out_spec)
        exit_back, back_aliases = _parse_exit_spec(back_spec) if back_spec else (None, [])
        loc = caller.location
        if not loc:
            caller.msg("You are nowhere.")
            return

        # Verify current location is NOT a Matrix room
        if isinstance(loc, MatrixNode):
            caller.msg("You are in a Matrix room. Use mdig to create Matrix rooms.")
            return
        try:
            from typeclasses.rooms import Room
            from typeclasses.exits import Exit
        except ImportError:
            Room = "typeclasses.rooms.Room"
            Exit = "typeclasses.exits.Exit"
        new_room = create_object(Room, key=room_name, location=None)
        if not new_room:
            caller.msg("Could not create room.")
            return
        out_exit = create_object(Exit, key=exit_out, location=loc, destination=new_room)
        if not out_exit:
            caller.msg("Room created but could not create exit.")
            return
        for al in out_aliases:
            try:
                out_exit.aliases.add(al)
            except Exception:
                pass
        if exit_back:
            back_exit = create_object(Exit, key=exit_back, location=new_room, destination=loc)
            if back_exit:
                for al in back_aliases:
                    try:
                        back_exit.aliases.add(al)
                    except Exception:
                        pass
        msg = "Created room |w%s|n (#%s) with exit |w%s|n from here." % (room_name, new_room.id, exit_out)
        if out_aliases:
            msg += " (|w%s|n)" % ", ".join(out_aliases)
        if exit_back:
            msg += " Exit |w%s|n leads back." % exit_back
            if back_aliases:
                msg += " (|w%s|n)" % ", ".join(back_aliases)
        caller.msg(msg)
        if teleport:
            caller.move_to(new_room)
            caller.msg("You teleport to the new room.")


class CmdDesc(Command):
    """
    Set or view the description of an object or the current room.
    Usage: budesc [obj] = <text>   or   budesc [obj]   (view)
    Without obj, describes the current room.
    """
    key = "budesc"
    locks = "cmd:perm(Builder)"
    help_category = "Building"

    def func(self):
        caller = self.caller
        args = (self.args or "").strip()
        if "=" in args:
            left, right = args.split("=", 1)
            obj_spec = left.strip()
            text = right.strip()
        else:
            obj_spec = args.strip()
            text = None
        if not obj_spec or obj_spec.lower() in ("here", "room"):
            obj = caller.location
            if not obj:
                caller.msg("You are nowhere.")
                return
        else:
            obj = caller.search(obj_spec)
            if not obj:
                return
        if text is None:
            desc = getattr(obj.db, "desc", None) or "(no description set)"
            caller.msg("|w%s|n: %s" % (obj.get_display_name(caller), desc[:200] + ("..." if len(desc) > 200 else "")))
            return
        obj.db.desc = text
        caller.msg("Description set on %s." % obj.get_display_name(caller))


class CmdSetAttr(Command):
    """
    Set or view a db attribute on an object.
    Usage: busetattr <obj> <attr> [= value]   or   busetattr <obj> <attr> =   (clear)
    Without = value, shows current value. Use quotes for values with spaces.
    """
    key = "busetattr"
    locks = "cmd:perm(Builder)"
    help_category = "Building"

    def func(self):
        caller = self.caller
        args = (self.args or "").strip()
        if not args:
            caller.msg("Usage: |wbusetattr <obj> <attr> [= value]|n")
            return
        if "=" in args:
            left, right = args.split("=", 1)
            parts = left.strip().split(None, 1)
            right = right.strip()
        else:
            parts = args.strip().split(None, 1)
            right = None
        if len(parts) < 2 and right is None:
            caller.msg("Usage: |wbusetattr <obj> <attr> [= value]|n")
            return
        obj_spec = parts[0]
        attr = parts[1] if len(parts) > 1 else None
        if not attr and right is None:
            caller.msg("Give an attribute name.")
            return
        obj = caller.search(obj_spec)
        if not obj:
            return
        if not hasattr(obj, "db"):
            caller.msg("That object has no attributes.")
            return
        if right is None:
            val = getattr(obj.db, attr, None)
            caller.msg("%s.%s = %s" % (obj.get_display_name(caller), attr, repr(val)))
            return
        if right == "" or right == "#":
            try:
                del obj.db[attr]
                caller.msg("Cleared %s on %s." % (attr, obj.get_display_name(caller)))
            except Exception as e:
                caller.msg("Could not clear: %s" % e)
            return
        if right.isdigit():
            obj.db[attr] = int(right)
        elif right.lower() in ("true", "false"):
            obj.db[attr] = right.lower() == "true"
        else:
            if (right.startswith('"') and right.endswith('"')) or (right.startswith("'") and right.endswith("'")):
                right = right[1:-1]
            obj.db[attr] = right
        caller.msg("Set %s.%s = %s" % (obj.get_display_name(caller), attr, repr(obj.db[attr])))


class CmdName(Command):
    """
    Rename an object.
    Usage: buname <obj> = <new name>
    """
    key = "buname"
    locks = "cmd:perm(Builder)"
    help_category = "Building"

    def func(self):
        caller = self.caller
        args = (self.args or "").strip()
        if "=" not in args:
            caller.msg("Usage: |wbuname <obj> = <new name>|n")
            return
        left, new_name = args.split("=", 1)
        obj_spec = left.strip()
        new_name = new_name.strip()
        if not new_name:
            caller.msg("Give a new name.")
            return
        obj = caller.search(obj_spec)
        if not obj:
            return
        old = obj.key
        obj.key = new_name
        obj.save()

        # Check if key was auto-corrected (validation happens in save())
        if obj.key != new_name:
            caller.msg("Renamed %s to |w%s|n (auto-corrected from '%s')." % (old, obj.key, new_name))
        else:
            caller.msg("Renamed %s to |w%s|n." % (old, new_name))


class CmdMatrixDig(Command):
    """
    Create a new Matrix room and link it with exits. Creates MatrixNode/MatrixExit.
    Usage: mdig <room name> = <exit out>[, <exit back>]
    Exit format: name or name;alias1;alias2  (e.g. west;w  or south;s;down)
    Example: mdig The Cortex = entrance;in, exit;out
    Use /tel to teleport to the new room after creating.
    Use /force to create a Matrix room without exits (for bootstrapping or isolated rooms).
    """
    key = "mdig"
    switch_options = ("tel", "teleport", "force")
    locks = "cmd:perm(Builder)"
    help_category = "Building"

    def func(self):
        caller = self.caller
        args = (self.args or "").strip()

        # Check switches
        switches = getattr(self, 'switches', [])
        teleport = "tel" in switches or "teleport" in switches
        force = "force" in switches

        # With /force, exit spec is optional
        if "=" not in args:
            if force:
                room_name = args
                exit_spec = None
            else:
                caller.msg("Usage: |wmdig <room name> = <exit out>[, <exit back>]|n  Exits: |wname;alias|n e.g. mdig The Cortex = entrance;in, exit;out")
                caller.msg("Use |wmdig/force <room name>|n to create a Matrix room without exits.")
                return
        else:
            room_spec, exit_spec = args.split("=", 1)
            room_name = room_spec.strip()
            exit_spec = exit_spec.strip()

        if not room_name:
            caller.msg("Give a room name.")
            return

        # Parse exit spec if provided
        if exit_spec:
            parts = [p.strip() for p in exit_spec.split(",")]
            out_spec = parts[0] if parts else "out"
            back_spec = parts[1] if len(parts) > 1 else None
            exit_out, out_aliases = _parse_exit_spec(out_spec)
            exit_back, back_aliases = _parse_exit_spec(back_spec) if back_spec else (None, [])
        else:
            exit_out, out_aliases = None, []
            exit_back, back_aliases = None, []
        loc = caller.location
        if not loc:
            caller.msg("You are nowhere.")
            return

        # Check if we're in a Matrix room
        loc_is_matrix = isinstance(loc, MatrixNode)

        # Require /force flag to create Matrix rooms from meatspace
        if not loc_is_matrix and not force:
            caller.msg("You must be in a Matrix room to use mdig.")
            caller.msg("Use |wmdig/force|n to create the first Matrix room from meatspace.")
            return

        new_room = create_object(MatrixNode, key=room_name, location=None)
        if not new_room:
            caller.msg("Could not create Matrix room.")
            return

        # If /force flag is set or no exit spec provided, skip exit creation
        if force or not exit_spec:
            caller.msg("Created Matrix room |m%s|n (#%s) with no exits." % (room_name, new_room.id))
            if teleport:
                caller.move_to(new_room)
                caller.msg("You teleport to the new Matrix room.")
            return

        # If not in Matrix (shouldn't happen due to check above, but safety)
        if not loc_is_matrix:
            caller.msg("Error: Cannot create exits from meatspace.")
            return

        out_exit = create_object(MatrixExit, key=exit_out, location=loc, destination=new_room)
        if not out_exit:
            caller.msg("Matrix room created but could not create exit.")
            return
        for al in out_aliases:
            try:
                out_exit.aliases.add(al)
            except Exception:
                pass

        if exit_back:
            back_exit = create_object(MatrixExit, key=exit_back, location=new_room, destination=loc)
            if back_exit:
                for al in back_aliases:
                    try:
                        back_exit.aliases.add(al)
                    except Exception:
                        pass

        msg = "Created Matrix room |m%s|n (#%s) with exit |w%s|n from here." % (room_name, new_room.id, exit_out)
        if out_aliases:
            msg += " (|w%s|n)" % ", ".join(out_aliases)
        if exit_back:
            msg += " Exit |w%s|n leads back." % exit_back
            if back_aliases:
                msg += " (|w%s|n)" % ", ".join(back_aliases)
        caller.msg(msg)
        if teleport:
            caller.move_to(new_room)
            caller.msg("You teleport to the new Matrix room.")


class CmdOpen(Command):
    """
    Create an exit from the current room to a destination.
    Usage: buopen <exit name> = <destination>
    Destination can be room name, #dbref, or "here" for current room (one-way).

    Note: Cannot create exits between Matrix and meatspace rooms.
    """
    key = "buopen"
    locks = "cmd:perm(Builder)"
    help_category = "Building"

    def func(self):
        caller = self.caller
        args = (self.args or "").strip()
        if "=" not in args:
            caller.msg("Usage: |wbuopen <exit name> = <destination>|n")
            return
        exit_name, dest_spec = args.split("=", 1)
        exit_name = exit_name.strip()
        dest_spec = dest_spec.strip()
        if not exit_name:
            caller.msg("Give an exit name.")
            return
        loc = caller.location
        if not loc:
            caller.msg("You are nowhere.")
            return
        if not dest_spec or dest_spec.lower() == "none":
            dest = None
        else:
            dest = caller.search(dest_spec, global_search=True)
            if not dest:
                return

        # Prevent cross-realm exits
        loc_is_matrix = isinstance(loc, MatrixNode)
        dest_is_matrix = isinstance(dest, MatrixNode) if dest else loc_is_matrix

        if loc_is_matrix != dest_is_matrix:
            caller.msg("Cannot create exits between Matrix and meatspace rooms.")
            return

        try:
            if loc_is_matrix:
                ex = create_object(MatrixExit, key=exit_name, location=loc, destination=dest)
            else:
                from typeclasses.exits import Exit
                ex = create_object(Exit, key=exit_name, location=loc, destination=dest)

            if ex:
                caller.msg("Created exit |w%s|n from here to %s." % (exit_name, dest.get_display_name(caller) if dest else "nowhere (unlinked)"))
            else:
                caller.msg("Could not create exit.")
        except Exception as e:
            caller.msg("Error: %s" % e)


class CmdDestroy(Command):
    """
    Permanently delete an object. Asks for confirmation unless /force.
    Usage: budestroy <obj> [/force]
    """
    key = "budestroy"
    switch_options = ("force",)
    locks = "cmd:perm(Builder)"
    help_category = "Building"

    def func(self):
        caller = self.caller
        args = (self.args or "").strip()
        force = "force" in getattr(self, "switches", [])
        if not args:
            caller.msg("Usage: |wbudestroy <obj>|n or |wbudestroy/force <obj>|n")
            return
        obj = caller.search(args)
        if not obj:
            return
        if not force:
            caller.msg("To permanently delete |w%s|n (#%s), type |wbudestroy/force %s|n." % (obj.get_display_name(caller), obj.id, args))
            return
        name = obj.get_display_name(caller)
        try:
            obj.delete()
            caller.msg("Destroyed %s." % name)
        except Exception as e:
            caller.msg("Could not destroy: %s" % e)


class CmdMatrixLink(Command):
    """
    Link the current room to a network router.

    Usage:
        mlink <router_key>
        mlink              (view current router)
        mlink/clear        (remove router link)

    Sets the network_router attribute (dbref) on the current room, which determines
    whether networked devices in this room can connect to the Matrix.

    Example:
        mlink downtown_router
    """
    key = "mlink"
    locks = "cmd:perm(Builder)"
    help_category = "Building"
    switch_options = ("clear",)

    def func(self):
        caller = self.caller
        args = (self.args or "").strip()
        clear = "clear" in self.switches

        loc = caller.location
        if not loc:
            caller.msg("You are nowhere.")
            return

        # Prevent mlinking MatrixNodes
        from typeclasses.matrix.rooms import MatrixNode
        if isinstance(loc, MatrixNode):
            caller.msg("|rCannot mlink MatrixNodes.|n Matrix nodes don't need access point IDs - they are destinations, not entry points.")
            return

        # View current router
        if not args and not clear:
            current_dbref = getattr(loc.db, 'network_router', None)
            if current_dbref:
                from evennia.objects.models import ObjectDB
                try:
                    router = ObjectDB.objects.get(pk=current_dbref)
                    online = getattr(router.db, 'online', False)
                    status = "|g[ONLINE]|n" if online else "|r[OFFLINE]|n"
                    caller.msg(f"This room is linked to router: |w{router.key}|n (#{router.id}) {status}")

                    # Show AP Matrix ID if available
                    matrix_id = loc.get_matrix_id() if hasattr(loc, 'get_matrix_id') else None
                    if matrix_id:
                        caller.msg(f"Access Point ID: |m{matrix_id}|n")
                    else:
                        caller.msg("Access Point ID: |x(not yet assigned)|n")
                except ObjectDB.DoesNotExist:
                    caller.msg(f"This room is linked to a router that no longer exists (#{current_dbref}).")
                    caller.msg("Use |wmlink/clear|n to remove the broken link.")
            else:
                caller.msg("This room has no network router link.")
            return

        # Clear router
        if clear:
            loc.db.network_router = None
            caller.msg("Network router link cleared from this room.")
            return

        # Set router - search for it and store dbref
        from evennia.utils.search import search_object
        from typeclasses.matrix.objects import Router

        results = search_object(args, typeclass=Router)

        if not results:
            caller.msg(f"Could not find router '{args}'.")
            return

        if len(results) > 1:
            caller.msg(f"Multiple routers found matching '{args}':")
            for i, router in enumerate(results, 1):
                online = getattr(router.db, 'online', False)
                status = "|g[ONLINE]|n" if online else "|r[OFFLINE]|n"
                caller.msg(f"  {i}. {router.key} (#{router.id}) {status} in {router.location.key if router.location else 'nowhere'}")
            caller.msg("Please be more specific or use the dbref.")
            return

        router = results[0]
        loc.db.network_router = router.pk  # Store dbref, not name

        # Force Matrix ID assignment for this access point
        matrix_id = loc.get_matrix_id() if hasattr(loc, 'get_matrix_id') else None

        online = getattr(router.db, 'online', False)
        status = "|g[ONLINE]|n" if online else "|r[OFFLINE]|n"
        caller.msg(f"Room linked to router |w{router.key}|n (#{router.id}) {status}. Networked devices here will use this router.")

        if matrix_id:
            caller.msg(f"Access Point ID assigned: |m{matrix_id}|n")
