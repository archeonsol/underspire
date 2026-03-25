"""
EnterableMixin — base for objects that characters can enter.
"""


class EnterableMixin:
    """
    Mixin for any Object that characters can physically enter.
    Subclasses override at_enter(caller) with their specific logic.
    """

    def at_enter(self, caller):
        raise NotImplementedError(f"{type(self).__name__} must implement at_enter(caller)")
