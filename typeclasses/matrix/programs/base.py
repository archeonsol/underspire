"""
Base Program Class

Executable programs that can be run in Matrix interface rooms.
"""

from typeclasses.matrix.items import MatrixItem


class Program(MatrixItem):
    """
    Executable program that can be run in Matrix nodes.

    Programs are carried by avatars and executed via 'exec <program> [args]'.
    They interact with networked devices to perform operations like file
    manipulation, device control, information gathering, etc.

    Programs can degrade with use and eventually become unusable.

    Attributes:
        program_type (str): Type of program (utility, exploit, combat, etc.)
        max_uses (int): Maximum uses before degradation (None = unlimited)
        uses_remaining (int): Current remaining uses (None = unlimited)
        quality (int): Quality level 0-10 (affects capabilities)
        execute_handler (str): Name of method to call when executed
        requires_device (bool): Whether program needs a device interface to run
    """

    def at_object_creation(self):
        """Called when the program is first created."""
        super().at_object_creation()
        self.db.data_type = "program"
        self.db.program_type = "utility"
        self.db.max_uses = None  # None = unlimited uses
        self.db.uses_remaining = None
        self.db.quality = 1  # 0-10 scale
        self.db.execute_handler = None  # Method name to call
        self.db.requires_device = False  # Programs can run anywhere, but may check room type

    def can_execute(self):
        """
        Check if this program can be executed.

        Returns:
            bool: True if program is usable, False if degraded/broken
        """
        if self.db.uses_remaining is not None and self.db.uses_remaining <= 0:
            return False
        return True

    def degrade(self):
        """
        Degrade the program by one use.

        Returns:
            bool: True if program is still usable, False if now broken
        """
        if self.db.uses_remaining is not None:
            self.db.uses_remaining -= 1
            return self.db.uses_remaining > 0
        return True

    def execute(self, caller, device, *args):
        """
        Execute this program.

        This is the base implementation. Subclasses or handler methods
        should override this to provide specific functionality.

        Args:
            caller (MatrixAvatar): The avatar executing the program
            device (NetworkedObject): The device being targeted
            *args: Additional arguments passed to the program

        Returns:
            bool: True if execution succeeded, False otherwise
        """
        if not self.can_execute():
            caller.msg(f"|r{self.key} is corrupted and unusable.|n")
            return False

        # If a handler method is defined, call it
        if self.db.execute_handler:
            handler = getattr(self, self.db.execute_handler, None)
            if handler and callable(handler):
                result = handler(caller, device, *args)
                if result:
                    self.degrade()
                return result

        # Default behavior - show usage
        caller.msg(f"Program: {self.key}")
        if self.db.desc:
            caller.msg(self.db.desc)
        if self.db.uses_remaining is not None:
            caller.msg(f"Uses remaining: {self.db.uses_remaining}/{self.db.max_uses}")
        return True

    def get_display_name(self, looker, **kwargs):
        """Add use count to display name if applicable."""
        name = super().get_display_name(looker, **kwargs)
        if self.db.uses_remaining is not None:
            if self.db.uses_remaining <= 0:
                return f"{name} |r[CORRUPTED]|n"
            elif self.db.uses_remaining <= 2:
                return f"{name} |y[{self.db.uses_remaining} uses]|n"
        return name
