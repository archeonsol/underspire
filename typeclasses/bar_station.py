"""
Bar station typeclass.

A commercial bar or drinks counter. Serves alcoholic drinks only.
Has a register (takes payment), a menu, employee access, and recipes.

Attributes:
    db.station_type         str   "bar"
    db.social_tier          str   "gutter" | "slum" | "guild" | "bourgeois" | "elite"
    db.manager_id           int   dbref of the manager character (set by staff)
    db.employees            list  character ids with serve access
    db.recipes              list  recipe dicts
    db.register_balance     int   currency held in the register
    db.drink_price_default  int   default price for drinks
    db.recipe_prices        dict  {recipe_name_lower: price_int} per-recipe overrides
    db.station_name         str   display name ("The Marrow Bar")
    db.register_log         list  rolling log of sales (max 100 entries)
"""

from evennia.objects.objects import DefaultObject


class BarStation(DefaultObject):
    """
    A commercial bar or drinks counter.

    Serves alcoholic drinks only. Requires employee access to prepare drinks.
    Customers pay the menu price when served. Revenue goes to the register.

    Set up by builders:
        @create The Marrow Bar:typeclasses.bar_station.BarStation
        @set bar/social_tier = guild
        @barset bar name = The Marrow Bar
        @barset bar manager = <character>
    """

    def at_object_creation(self):
        super().at_object_creation()
        self.db.station_type = "bar"
        self.db.social_tier = "slum"
        self.db.manager_id = None
        self.db.employees = []
        self.db.recipes = []
        self.db.register_balance = 0
        self.db.drink_price_default = 10
        self.db.recipe_prices = {}
        self.db.station_name = self.key
        self.db.register_log = []
        self.db.room_pose = "is ready to serve"
        self.locks.add("get:perm(Builder) or perm(Admin);drop:perm(Builder) or perm(Admin);give:false()")

    def at_pre_get(self, getter, **kwargs):
        """Bars are fixed fixtures and cannot be picked up."""
        try:
            if getter and (getter.check_permstring("Builder") or getter.check_permstring("Admin")):
                return True
        except Exception:
            pass
        if getter:
            getter.msg("That fixture is bolted in place.")
        return False

    def at_pre_move(self, destination, **kwargs):
        """
        Prevent normal in-world movement of bar fixtures.
        Allow explicit builder/admin repositioning if needed.
        """
        if kwargs.get("move_type") == "teleport":
            return True
        mover = kwargs.get("caller") or kwargs.get("mover")
        if mover and (mover.check_permstring("Builder") or mover.check_permstring("Admin")):
            return True
        return False

    def get_room_appearance(self, looker, **kwargs):
        """
        Return the one-line room look entry for this fixture.
        Builders can customize with @set bar/room_pose = <text>.
        """
        from typeclasses.rooms import ROOM_DESC_OBJECT_NAME_COLOR
        name = self.get_display_name(looker, **kwargs)
        pose = (getattr(self.db, "room_pose", None) or "is ready to serve").strip().rstrip(".")
        return f"The {ROOM_DESC_OBJECT_NAME_COLOR}{name}|n {pose}."

    def return_appearance(self, looker, **kwargs):
        """Append a compact menu to the standard description."""
        base = super().return_appearance(looker, **kwargs)
        try:
            from world.food.recipes import format_compact_menu
            menu_text = format_compact_menu(self)
            if menu_text:
                tier = getattr(self.db, "social_tier", "slum").title()
                return (
                    f"{base}\n"
                    f"|x{'─' * 40}|n\n"
                    f"  |xMenu ({tier}):|n\n"
                    f"{menu_text}"
                )
        except Exception:
            pass
        return base

    def log_sale(self, amount: int, customer_name: str, employee_name: str, recipe_name: str):
        """Record a sale in the register log (capped at 100 entries)."""
        import time
        log = list(getattr(self.db, "register_log", None) or [])
        log.append({
            "time": time.time(),
            "amount": int(amount),
            "customer": str(customer_name),
            "employee": str(employee_name),
            "recipe": str(recipe_name),
        })
        if len(log) > 100:
            log = log[-100:]
        self.db.register_log = log
        self.db.register_balance = int(getattr(self.db, "register_balance", 0) or 0) + int(amount)
