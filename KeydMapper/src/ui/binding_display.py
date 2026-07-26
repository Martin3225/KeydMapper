"""Compact, semantic labels for bindings and small physical keys."""

from __future__ import annotations

from dataclasses import dataclass

from keyd.actions import ParsedAction, parse_action


@dataclass(frozen=True)
class KeyDisplay:
    """Presentation content rendered inside one visual key."""

    title: str
    detail: str = ""
    badge: str = ""
    tooltip: str = ""


PHYSICAL_KEY_LABELS = {
    "scrollup": KeyDisplay("WHEEL", "↑"),
    "scrolldown": KeyDisplay("WHEEL", "↓"),
    "middlemouse": KeyDisplay("MIDDLE"),
    "leftmouse": KeyDisplay("LEFT", "mouse"),
    "rightmouse": KeyDisplay("RIGHT", "mouse"),
    "mouse1": KeyDisplay("MOUSE", "1"),
    "mouse2": KeyDisplay("MOUSE", "2"),
}

MOUSE_ACTION_LABELS = {
    "leftmouse": "Left click",
    "rightmouse": "Right click",
    "middlemouse": "Middle click",
    "scrollup": "Wheel ↑",
    "scrolldown": "Wheel ↓",
}

ACTION_TITLES = {
    "macro": "MACRO",
    "layer": "HOLD",
    "oneshot": "ONESHOT",
    "swap": "SWAP",
    "toggle": "TOGGLE",
    "setlayout": "LAYOUT",
    "clear": "CLEAR",
    "repeat": "REPEAT",
    "overload": "TAP / HOLD",
    "overloadt": "TAP / HOLD",
    "overloadt2": "TAP / HOLD",
    "overloadi": "IDLE",
    "lettermod": "LETTER MOD",
    "timeout": "TIMEOUT",
    "macro2": "MACRO",
    "command": "COMMAND",
    "noop": "NOOP",
}


def display_for_key(key_name: str, binding: str) -> KeyDisplay:
    """Return a compact label and lossless tooltip for one visual key."""
    if not binding:
        physical = PHYSICAL_KEY_LABELS.get(key_name.lower())
        if physical is not None:
            return KeyDisplay(
                title=physical.title,
                detail=physical.detail,
                tooltip=key_name,
            )
        return KeyDisplay(title=key_name, tooltip=key_name)

    parsed = parse_action(binding)
    if parsed is None:
        physical = PHYSICAL_KEY_LABELS.get(binding.lower())
        if physical is not None:
            return KeyDisplay(
                title=physical.title,
                detail=physical.detail,
                tooltip=f"{key_name} = {binding}",
            )
        return KeyDisplay(
            title=binding,
            tooltip=f"{key_name} = {binding}",
        )

    presentation = _display_for_action(parsed)
    return KeyDisplay(
        title=presentation.title,
        detail=presentation.detail,
        badge=presentation.badge,
        tooltip=f"{key_name} = {binding}",
    )


def _display_for_action(action: ParsedAction) -> KeyDisplay:
    """Build a two-line semantic summary of a normalized keyd action."""
    name = action.action_name
    arguments = action.arguments
    title = ACTION_TITLES[name]
    badge = "+M" if action.macro else ("+K" if action.held_key else "")

    if name in {"layer", "oneshot", "swap", "toggle", "setlayout"}:
        display = KeyDisplay(title, arguments[0], badge)
    elif name in {"clear", "repeat", "noop"}:
        display = KeyDisplay(title, badge=badge)
    elif name == "macro":
        display = KeyDisplay(title, _compact_macro(arguments[0]))
    elif name in {"overload", "overloadt", "overloadt2"}:
        layer, tap_action = arguments[:2]
        display = KeyDisplay(
            f"TAP · {_compact_expression(tap_action)}",
            f"HOLD · {_compact_expression(layer)}",
        )
    elif name == "overloadi":
        first, second = arguments[:2]
        display = KeyDisplay(
            title,
            f"{_compact_expression(first)} · {_compact_expression(second)}",
        )
    elif name == "lettermod":
        layer, key = arguments[:2]
        display = KeyDisplay(title, f"{key} · {layer}")
    elif name == "timeout":
        first, _, second = arguments
        display = KeyDisplay(
            title,
            f"{_compact_expression(first)} · {_compact_expression(second)}",
        )
    elif name == "macro2":
        display = KeyDisplay(title, _compact_expression(arguments[2]))
    elif name == "command":
        display = KeyDisplay(title, arguments[0])
    else:
        display = KeyDisplay(title)
    return display


def _compact_expression(value: str) -> str:
    """Reduce a nested action to the information useful on a small key."""
    nested = parse_action(value)
    if nested is None:
        physical = PHYSICAL_KEY_LABELS.get(value.lower())
        if physical is None:
            return value
        return " ".join(
            part for part in (physical.title.title(), physical.detail) if part
        )
    if nested.action_name == "macro":
        return _compact_macro(nested.arguments[0])
    if nested.arguments:
        return f"{ACTION_TITLES[nested.action_name]} {nested.arguments[0]}"
    return ACTION_TITLES[nested.action_name]


def _compact_macro(value: str) -> str:
    """Summarize repeated clicks or a longer key sequence without raw syntax."""
    tokens = value.split()
    if not tokens:
        return "Empty macro"

    first = tokens[0]
    first_label = MOUSE_ACTION_LABELS.get(first.lower(), first)
    if all(token == first for token in tokens):
        if len(tokens) == 1:
            return first_label
        return f"{len(tokens)}× {first_label}"
    return f"{len(tokens)}-step macro"
