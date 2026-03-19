# EvMenu Implementation Guide

Evennia's `EvMenu` is the standard system for interactive menus in this codebase. This guide covers the patterns and conventions to follow when building new menus.

## Core Concepts

A menu is a collection of **nodes** — Python functions that each represent one screen. Evennia drives the flow between them based on player input.

Each node receives `(caller, raw_string, **kwargs)` and returns `(text, options)` to render a screen, or `None` to exit the menu.

There are two kinds of functions in a menu module:

| Kind | Naming | Returns | Purpose |
|------|--------|---------|---------|
| Display node | plain name | `(text, options)` | Renders UI to the player |
| Goto-callable | `_underscore` prefix | node name string or `None` | Performs logic, redirects |

Goto-callables are never rendered directly. They validate input, mutate state, and return the name of the next node to go to. The `_` prefix convention signals this clearly.

## Starting a Menu

Launch a menu from a command with:

```py /dev/null/example.py#L1-10
from evennia.utils.evmenu import EvMenu

EvMenu(
    caller,
    "commands.your_menu_module",
    startnode="your_main_menu",
    startnode_input=(raw_string, {"your_object": obj})
)
```

Pass any objects the menu needs as kwargs into `startnode_input`. These flow into the first node's `**kwargs`.

## Passing State Between Nodes

All inter-node state travels through kwargs on the `"goto"` tuple:

```py /dev/null/example.py#L1-5
{
    "key": ("a", "action"),
    "desc": "Do something",
    "goto": ("next_node", {"your_object": obj})
}
```

At the top of every node that needs a persistent object, add a fallback read from `caller.ndb._evmenu` in case the node is entered without kwargs:

```py /dev/null/example.py#L1-5
obj = kwargs.get("your_object")
if not obj:
    obj = getattr(caller.ndb._evmenu, 'your_object', None)
if not obj:
    caller.msg("|rError: context lost.|n")
    return None
```

Store it on `ndb._evmenu` in your main menu node so the fallback is always populated:

```py /dev/null/example.py#L1-3
if hasattr(caller.ndb, '_evmenu'):
    caller.ndb._evmenu.your_object = obj
```

This dual-source pattern keeps nodes resilient without coupling them to globals.

## Free-Text Input

Use `_default` to capture a line of raw player input:

```py /dev/null/example.py#L1-10
options = (
    {
        "key": "_default",
        "desc": None,
        "goto": (_process_input, {"your_object": obj})
    },
    {
        "key": ("q", "back"),
        "desc": "Go back",
        "goto": ("previous_node", {"your_object": obj})
    }
)
```

The `_default` option fires on any input that doesn't match a named key. Always pair it with a goto-callable that:

1. Validates the input
2. Returns the appropriate next node on success
3. Loops back to the same prompt node on failure with an error message

```py /dev/null/example.py#L1-15
def _process_input(caller, raw_string, **kwargs):
    obj = kwargs.get("your_object")
    value = raw_string.strip()

    if not value:
        return ("prompt_node", kwargs)  # loop back

    if not valid(value):
        caller.msg("|rInvalid input.|n")
        return ("prompt_node", kwargs)  # loop back

    # success
    return ("result_node", {"your_object": obj, "value": value})
```

Never put validation logic inside the display node body. Keep display nodes dumb.

## Dynamic Options

Compute option labels and goto targets inside the node body based on current state:

```py /dev/null/example.py#L1-10
is_active = bool(caller.db.some_flag)

options = (
    {
        "key": ("t", "toggle"),
        "desc": "Deactivate" if is_active else "Activate",
        "goto": (_deactivate, kwargs) if is_active else (_activate, kwargs)
    },
)
```

Keep the number of options consistent rather than conditionally including/excluding them. Changing labels on a fixed set of options is less disorienting than options appearing and disappearing.

## Async Actions with `delay()`

When an action needs to play out over time (movement, connection sequences, etc.), exit the menu immediately with `return None` and use chained closures with `delay()`:

```py /dev/null/example.py#L1-20
from evennia.utils import delay

def some_action_node(caller, raw_string, **kwargs):
    target = kwargs.get("target")

    caller.msg("|cInitializing...|n")

    def _step_two():
        caller.msg("|cConnecting...|n")
        delay(1.0, _step_three)

    def _step_three():
        caller.move_to(target)
        target.msg_contents(f"{caller.key} arrives.", exclude=[caller])

    delay(1.0, _step_two)
    return None  # exit menu before delays fire
```

The closures capture `caller` and any other locals from scope. The menu is gone by the time they execute — that's fine and intended. Don't try to hold the menu open across async gaps.

## Error Handling

- Return early with a message on any missing context. Never silently continue with `None` objects.
- Wrap operations that can fail (e.g. cluster creation, DB lookups) in try/except and log with `logger.log_trace()`:

```py /dev/null/example.py#L1-8
from evennia.utils import logger

try:
    result = obj.some_operation()
except Exception as e:
    logger.log_trace(f"menu_module.node_name: {e}")
    caller.msg("|rOperation failed. Try again later.|n")
    return ("main_menu", kwargs)
```

- Bare `except` is only acceptable in display-only paths where degraded output is better than an error (e.g. showing stale status info). Never use it in action paths.

## Type Guards

If a node or goto-callable is only valid for a specific caller type, check at the top and redirect:

```py /dev/null/example.py#L1-6
from typeclasses.matrix.avatars import MatrixAvatar

if not isinstance(caller, MatrixAvatar):
    caller.msg("|rThis action requires a Matrix avatar.|n")
    return "main_menu"
```

Do this in the goto-callable closest to the action, not in the command that launches the menu.

## Imports

Do all typeclass imports inside node functions, not at the module level. Menu modules are imported early and circular import errors are easy to hit:

```py /dev/null/example.py#L1-5
def some_node(caller, raw_string, **kwargs):
    from typeclasses.matrix.objects import Router  # inside the function
    ...
```

## Conventions Summary

- Goto-callables for all logic. Display nodes only build text and options.
- Always pass context objects in kwargs. Use `ndb._evmenu` only as a fallback.
- `return None` exits the menu. Use it deliberately after async operations.
- `_default` + goto-callable for all free-text input. Loop back on failure.
- Type-check in goto-callables, not in the launching command.
- Late imports inside functions to avoid circular imports.
- Bare `except` only in display paths, never in action paths.