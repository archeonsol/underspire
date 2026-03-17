"""
Matrix Scripts

Global scripts for Matrix system maintenance and automation.

MatrixCleanupScript - Periodically removes empty ephemeral Matrix nodes
"""

from evennia.scripts.scripts import DefaultScript


class MatrixCleanupScript(DefaultScript):
    """
    Global script that periodically cleans up empty ephemeral Matrix nodes.

    Runs every CLEANUP_INTERVAL seconds and deletes any MatrixNode where:
    - db.ephemeral is True
    - No avatars are present in the node

    This prevents ephemeral nodes (cameras, locks, simple devices) from
    accumulating in the database after users disconnect.
    """

    def at_script_creation(self):
        """Called when script is first created."""
        self.key = "matrix_cleanup"
        self.desc = "Cleans up empty ephemeral Matrix nodes"
        self.interval = 60  # Run every 60 seconds
        self.repeats = 0  # Run forever
        self.persistent = True  # Survive server restarts
        self.start_delay = True  # Wait one interval before first run

    def at_repeat(self):
        """Called every interval. Scans for and deletes empty ephemeral nodes."""
        from typeclasses.matrix.rooms import MatrixNode

        # Find all ephemeral Matrix nodes
        ephemeral_nodes = MatrixNode.objects.filter(db_ephemeral=True)

        deleted_count = 0
        for node in ephemeral_nodes:
            # Check if any avatars are in the node
            # Import here to avoid circular imports
            from typeclasses.matrix.avatars import MatrixAvatar

            has_avatars = any(
                isinstance(obj, MatrixAvatar)
                for obj in node.contents
            )

            if not has_avatars:
                # Clean up reference in parent device
                if node.db.parent_object:
                    node.db.parent_object.db.matrix_node = None

                # Delete the node
                node.delete()
                deleted_count += 1

        # Optional: log cleanup activity (only if nodes were deleted)
        if deleted_count > 0:
            from evennia.utils import logger
            logger.log_info(f"Matrix cleanup: deleted {deleted_count} empty ephemeral node(s)")

    def at_start(self):
        """Called when script starts (including after server restart)."""
        from evennia.utils import logger
        logger.log_info("Matrix cleanup script started")

    def at_stop(self):
        """Called when script stops."""
        from evennia.utils import logger
        logger.log_info("Matrix cleanup script stopped")


class MatrixConnectionScript(DefaultScript):
    """
    Global script that periodically checks Matrix avatar connections.

    Runs every few seconds and verifies that each active avatar still has
    a valid connection to meatspace (character in rig, rig connected, etc.).
    Disconnects avatars whose physical connection has been severed.
    """

    def at_script_creation(self):
        """Called when script is first created."""
        self.key = "matrix_connection_check"
        self.desc = "Checks Matrix avatar and teleop connections periodically"
        self.interval = 10  # Run every 10 seconds
        self.repeats = 0  # Run forever
        self.persistent = True  # Survive server restarts
        self.start_delay = True  # Wait one interval before first run

    def at_repeat(self):
        """Called every interval. Checks all active avatar and teleop connections."""
        from typeclasses.matrix.avatars import MatrixAvatar
        from typeclasses.matrix.devices import TeleopRig
        from evennia.objects.models import ObjectDB

        # Check Matrix avatar connections
        avatars = MatrixAvatar.objects.filter(db_idle=False)
        avatar_disconnected = 0
        for avatar in avatars:
            if not avatar.check_connection():
                avatar_disconnected += 1

        # Check teleop rig connections
        teleop_rigs = ObjectDB.objects.filter(db_typeclass_path__contains="TeleopRig")
        teleop_disconnected = 0
        for rig in teleop_rigs:
            # Check if someone is sitting in the rig
            sitter = rig.get_sitter() if hasattr(rig, 'get_sitter') else None
            if not sitter:
                continue

            # Check if they're currently puppeted into a target
            target = rig.get_current_puppet(sitter) if hasattr(rig, 'get_current_puppet') else None
            if not target:
                continue

            # Verify Matrix connection is still valid
            if hasattr(rig, 'is_connected') and not rig.is_connected():
                # Lost Matrix connection - emergency disconnect
                if hasattr(rig, 'disengage'):
                    rig.disengage(sitter, severity=1, reason="Network connection lost")
                    teleop_disconnected += 1

        # Optional: log disconnection activity
        if avatar_disconnected > 0 or teleop_disconnected > 0:
            from evennia.utils import logger
            logger.log_info(f"Connection check: disconnected {avatar_disconnected} avatar(s), {teleop_disconnected} teleop session(s)")

    def at_start(self):
        """Called when script starts (including after server restart)."""
        from evennia.utils import logger
        logger.log_info("Matrix connection check script started")

    def at_stop(self):
        """Called when script stops."""
        from evennia.utils import logger
        logger.log_info("Matrix connection check script stopped")
