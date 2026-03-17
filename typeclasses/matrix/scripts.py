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
    Global script that periodically checks Matrix connections.

    Runs every few seconds and validates active connections on dive rigs and
    teleop rigs. Disconnects any connections that have become invalid.
    """

    def at_script_creation(self):
        """Called when script is first created."""
        self.key = "matrix_connection_check"
        self.desc = "Checks Matrix dive and teleop connections periodically"
        self.interval = 10  # Run every 10 seconds
        self.repeats = 0  # Run forever
        self.persistent = True  # Survive server restarts
        self.start_delay = True  # Wait one interval before first run

    def at_repeat(self):
        """Called every interval. Checks all active dive and teleop connections."""
        from evennia.objects.models import ObjectDB

        # Check dive rig connections
        # Can't filter by attribute, so get all DiveRigs and check for active_connection
        from typeclasses.matrix.devices.dive_rig import DiveRig
        all_dive_rigs = DiveRig.objects.all()
        dive_disconnected = 0
        for rig in all_dive_rigs:
            # Only check rigs with active connections
            if getattr(rig.db, 'active_connection', None):
                if hasattr(rig, 'validate_connection') and not rig.validate_connection():
                    dive_disconnected += 1

        # Check teleop connections - iterate all objects and check for controlled_by attribute
        # (Can't filter by attribute directly)
        from typeclasses.matrix.devices.teleop_rig import TeleopRig
        all_teleop_rigs = TeleopRig.objects.all()
        teleop_disconnected = 0
        for rig in all_teleop_rigs:
            # Check if this rig has an active control session
            if not getattr(rig.db, 'controlled_target', None):
                continue

            # Validate the connection
            if hasattr(rig, 'validate_connection') and not rig.validate_connection():
                teleop_disconnected += 1

        # Optional: log disconnection activity
        if dive_disconnected > 0 or teleop_disconnected > 0:
            from evennia.utils import logger
            logger.log_info(f"Connection check: disconnected {dive_disconnected} dive session(s), {teleop_disconnected} teleop session(s)")

    def at_start(self):
        """Called when script starts (including after server restart)."""
        from evennia.utils import logger
        logger.log_info("Matrix connection check script started")

    def at_stop(self):
        """Called when script stops."""
        from evennia.utils import logger
        logger.log_info("Matrix connection check script stopped")
