"""
Matrix Scripts

Global scripts for Matrix system maintenance and automation.

MatrixCleanupScript - Periodically removes empty ephemeral Matrix nodes
"""

from evennia.scripts.scripts import DefaultScript
from world.utils import get_containing_room


class MatrixCleanupScript(DefaultScript):
    """
    Global script that periodically cleans up empty ephemeral Matrix node clusters.

    Runs every 60 seconds and:
    1. Checks device connectivity for devices with ephemeral nodes
    2. Ejects avatars from devices that have lost network connectivity
    3. Deletes ephemeral node clusters where both nodes are empty

    This prevents ephemeral nodes (cameras, locks, simple devices) from
    accumulating in the database after users disconnect.
    """

    def at_script_creation(self):
        """Called when script is first created."""
        self.key = "matrix_cleanup"
        self.desc = "Cleans up empty ephemeral Matrix node clusters"
        self.interval = 60  # Run every 60 seconds
        self.repeats = 0  # Run forever
        self.persistent = True  # Survive server restarts
        self.start_delay = True  # Wait one interval before first run

    def at_repeat(self):
        """Called every interval. Checks device connectivity and cleans up empty clusters."""
        from typeclasses.matrix.rooms import MatrixNode, Room
        from typeclasses.matrix.avatars import MatrixAvatar

        # Get all MatrixNodes and filter for ephemeral ones in Python
        # (Can't filter on Attributes via SQL)
        all_nodes = MatrixNode.objects.all()
        ephemeral_nodes = [node for node in all_nodes if getattr(node.db, 'ephemeral', False)]

        deleted_count = 0
        ejected_count = 0
        processed_devices = set()  # Track devices we've already processed

        for node in ephemeral_nodes:
            # Get the parent device for this node
            parent_device = getattr(node.db, 'parent_object', None)
            if not parent_device:
                # Orphaned node with no parent - just delete it if empty
                has_avatars = any(isinstance(obj, MatrixAvatar) for obj in node.contents)
                if not has_avatars:
                    node.delete()
                    deleted_count += 1
                continue

            # Skip if we've already processed this device's cluster
            device_id = parent_device.pk
            if device_id in processed_devices:
                continue
            processed_devices.add(device_id)

            # Get both nodes in the cluster (checkpoint and interface)
            checkpoint_id = getattr(parent_device.db, 'checkpoint_node', None)
            interface_id = getattr(parent_device.db, 'interface_node', None)

            # Get the actual node objects
            checkpoint_node = None
            interface_node = None

            if checkpoint_id:
                try:
                    checkpoint_node = MatrixNode.objects.get(pk=checkpoint_id)
                except MatrixNode.DoesNotExist:
                    pass

            if interface_id:
                try:
                    interface_node = MatrixNode.objects.get(pk=interface_id)
                except MatrixNode.DoesNotExist:
                    pass
parent_device = cluster.db.parent_device

# Check if device is connected to network
device_connected = False
actual_room = get_containing_room(parent_device)

if actual_room:
    network_router = getattr(actual_room.db, 'network_router', None)
    if network_router:
        device_connected = True

            # If device lost connectivity, eject any avatars in the cluster
            if not device_connected:
                avatars_to_eject = []

                if checkpoint_node:
                    avatars_to_eject.extend([obj for obj in checkpoint_node.contents
                                            if isinstance(obj, MatrixAvatar)])
                if interface_node:
                    avatars_to_eject.extend([obj for obj in interface_node.contents
                                            if isinstance(obj, MatrixAvatar)])

                for avatar in avatars_to_eject:
                    rig = getattr(avatar.db, 'rig', None)
                    if rig and hasattr(rig, 'disconnect'):
                        from typeclasses.matrix.constants import JackoutSeverity
                        rig.disconnect(severity=JackoutSeverity.EMERGENCY)
                        ejected_count += 1

            # Check if the entire cluster is empty
            cluster_empty = True

            if checkpoint_node:
                has_avatars = any(isinstance(obj, MatrixAvatar) for obj in checkpoint_node.contents)
                if has_avatars:
                    cluster_empty = False

            if interface_node and cluster_empty:
                has_avatars = any(isinstance(obj, MatrixAvatar) for obj in interface_node.contents)
                if has_avatars:
                    cluster_empty = False

            # Only delete if the entire cluster is empty
            if cluster_empty:
                # Delete both nodes in the cluster
                if checkpoint_node:
                    checkpoint_node.delete()
                    deleted_count += 1
                if interface_node:
                    interface_node.delete()
                    deleted_count += 1

                # Clean up references in parent device
                parent_device.db.checkpoint_node = None
                parent_device.db.interface_node = None

        # Log cleanup activity
        if ejected_count > 0 or deleted_count > 0:
            from evennia.utils import logger
            logger.log_info(f"Matrix cleanup: ejected {ejected_count} avatar(s), deleted {deleted_count} empty ephemeral node(s)")

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
        proxy_disconnected = 0
        for rig in all_dive_rigs:
            # Only check rigs with active connections
            conn = getattr(rig.db, 'active_connection', None)
            if conn:
                # Validate rig connection
                if hasattr(rig, 'validate_connection') and not rig.validate_connection():
                    dive_disconnected += 1

                # Check avatar's proxy router if it has one
                avatar = conn.get('avatar')
                if avatar and hasattr(avatar.db, 'proxy_router') and avatar.db.proxy_router:
                    proxy_router_pk = avatar.db.proxy_router
                    try:
                        from typeclasses.matrix.objects import Router
                        proxy_router = Router.objects.get(pk=proxy_router_pk)
                        # Check if proxy router is offline
                        if not getattr(proxy_router.db, 'online', False):
                            if hasattr(avatar, 'handle_proxy_disconnect'):
                                avatar.handle_proxy_disconnect()
                                proxy_disconnected += 1
                    except Router.DoesNotExist:
                        # Proxy router was deleted - clear it and emergency jackout
                        if hasattr(avatar, 'handle_proxy_disconnect'):
                            avatar.handle_proxy_disconnect()
                            proxy_disconnected += 1

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
        if dive_disconnected > 0 or teleop_disconnected > 0 or proxy_disconnected > 0:
            from evennia.utils import logger
            logger.log_info(f"Connection check: disconnected {dive_disconnected} dive session(s), {teleop_disconnected} teleop session(s), {proxy_disconnected} proxy tunnel(s)")

    def at_start(self):
        """Called when script starts (including after server restart)."""
        from evennia.utils import logger
        logger.log_info("Matrix connection check script started")

    def at_stop(self):
        """Called when script stops."""
        from evennia.utils import logger
        logger.log_info("Matrix connection check script stopped")
