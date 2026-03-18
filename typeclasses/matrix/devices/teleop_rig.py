"""
Teleop Rig

Physical rig for remote operation of robots and other controllable devices.

TeleopRig - Chair that allows puppeting into a remote robot/object
"""

from evennia.utils.create import create_object
from typeclasses.seats import Seat
from typeclasses.matrix.objects import NetworkedObject
from typeclasses.matrix.mixins import PuppetRigMixin


class TeleopRig(PuppetRigMixin, Seat, NetworkedObject):
    """
    Telepresence rig for remote operation of robots and controllable devices.

    Unlike DiveRig which creates a virtual avatar in the Matrix, TeleopRig
    allows direct puppeting of a physical robot or other controllable object.
    The connection is registered on the target object.

    The character's consciousness is transferred to the remote body, experiencing
    the world through its sensors and controlling it directly.

    Attributes:
        target_object_dbref (int): dbref of the robot/object this rig controls
        jack_in_message (str): Custom message shown when engaging telepresence
        jack_out_message (str): Custom message shown when disengaging
    """

    def at_object_creation(self):
        """Called when the rig is first created."""
        super().at_object_creation()
        self.setup_networked_attrs()

        # TeleopRig specific attributes
        self.db.device_type = "teleop_rig"
        self.db.target_object_dbref = None  # The robot/object this rig controls
        self.db.jack_in_message = "engages telepresence link"
        self.db.jack_out_message = "disengages from remote control"
        self.db.jack_in_transition_msg = "|cYour senses blur as your consciousness shifts into the remote body...|n"
        self.db.normal_jackout_msg = "|cYour awareness flows back from the remote body into your own.|n"
        self.db.emergency_jackout_msg = "|yThe telepresence link destabilizes, yanking you back!|n"
        self.db.forced_jackout_msg = "|rThe connection is severed violently, tearing your consciousness back!|n"

    def engage(self, character):
        """
        Engage telepresence control of the target object.

        Args:
            character (Character): The character engaging telepresence

        Returns:
            bool: True if successful, False otherwise
        """
        return self.puppet_in(character)

    def disengage(self, character, severity=0, reason="Disengaging"):
        """
        Disengage from telepresence control.

        Args:
            character (Character): The character in the rig
            severity (int): Disconnect severity (0=normal, 1=emergency, 2=forced)
            reason (str): Reason for disconnect
        """
        self.puppet_out(character, severity=severity, reason=reason)

    # PuppetRigMixin required methods

    def validate_connection(self, character):
        """
        Validate that the target object exists and is accessible.

        Requires Matrix connectivity to transmit the telepresence signal.

        Returns:
            bool: True if connection is valid, False otherwise
        """
        # Check Matrix connection
        if not self.has_network_coverage():
            if hasattr(character, 'msg'):
                character.msg("No Matrix connection available. Cannot establish telepresence link.")
            return False

        if not self.db.target_object_dbref:
            if hasattr(character, 'msg'):
                character.msg("This rig is not configured with a target object.")
            return False

        # Try to get the target object
        target = self._get_target_object()
        if not target:
            if hasattr(character, 'msg'):
                character.msg("Target object not found or has been destroyed.")
            return False

        # Check if target is already being controlled by someone else
        if target.db.controlled_by and target.db.controlled_by != character:
            if hasattr(character, 'msg'):
                character.msg("Target is already under remote control by someone else.")
            return False

        return True

    def get_puppet_target(self, character):
        """
        Get the target object to puppet into.

        Returns:
            Object: The target object, or None if not available
        """
        target = self._get_target_object()
        if not target:
            return None

        # Mark target as controlled
        target.db.controlled_by = character
        target.db.control_rig = self
        target.db.real_character = character

        return target

    def get_current_puppet(self, character):
        """
        Get the currently puppeted object for this character.

        Returns:
            Object: The target object if puppeted, or None
        """
        target = self._get_target_object()
        if target and target.db.controlled_by == character:
            return target
        return None

    def cleanup_on_disconnect(self, character):
        """
        Clean up when connection is forcibly broken.

        Clears control flags on the target object.
        """
        target = self._get_target_object()
        if target:
            target.db.controlled_by = None
            target.db.control_rig = None
            target.db.real_character = None

    # Helper methods

    def _get_target_object(self):
        """
        Get the target object by dbref.

        Returns:
            Object: The target object, or None if not found
        """
        if not self.db.target_object_dbref:
            return None

        try:
            from evennia.objects.models import ObjectDB
            return ObjectDB.objects.get(pk=self.db.target_object_dbref)
        except ObjectDB.DoesNotExist:
            # Target was deleted
            self.db.target_object_dbref = None
            return None

    def set_target(self, target_object):
        """
        Set the target object this rig controls.

        Args:
            target_object (Object): The object to control

        Returns:
            bool: True if successful
        """
        if not target_object:
            self.db.target_object_dbref = None
            return False

        self.db.target_object_dbref = target_object.pk

        # Register this rig on the target object
        target_object.db.teleop_rig_dbref = self.pk

        return True

    def clear_target(self):
        """
        Clear the target object registration.
        """
        target = self._get_target_object()
        if target:
            target.db.teleop_rig_dbref = None
        self.db.target_object_dbref = None

    # Rig lifecycle methods

    def at_object_delete(self):
        """Clean up when rig is destroyed."""
        # Force disconnect anyone using the rig
        sitter = self.get_sitter()
        if sitter:
            target = self.get_current_puppet(sitter)
            if target:
                self.disengage(sitter, severity=2, reason="Telepresence rig destroyed")

        # Unregister from target object
        self.clear_target()

        return super().at_object_delete()

    def handle_disconnect(self):
        """
        Called when the rig loses connectivity.

        Emergency disconnects anyone currently using it.
        """
        sitter = self.get_sitter()
        if sitter:
            target = self.get_current_puppet(sitter)
            if target:
                self.disengage(
                    sitter,
                    severity=1,
                    reason="Connection lost"
                )

    def handle_forced_removal(self, character):
        """
        Called when someone is forcibly removed from the rig.

        Forces violent disconnect with consequences.

        Args:
            character (Character): Character being removed
        """
        target = self.get_current_puppet(character)
        if target:
            self.disengage(
                character,
                severity=2,
                reason="Forcibly disconnected!"
            )
