"""Shared catalogue, parser and formatter for keyd binding actions."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class ActionField:
    """One user-editable argument of a keyd action."""

    name: str
    label: str
    kind: str
    placeholder: str = ""


@dataclass(frozen=True)
class ActionSpec:
    """User-facing definition of a keyd action."""

    action_id: str
    label: str
    function: str
    fields: tuple[ActionField, ...]
    description: str
    macro_variant: str | None = None


@dataclass(frozen=True)
class ParsedAction:
    """A low-level keyd expression normalized to its user-facing action."""

    action_id: str
    arguments: tuple[str, ...]
    macro: str = ""
    held_key: str = ""

    def value(self, field_name: str) -> str:
        """Return the parsed value belonging to ``field_name``."""
        spec = ACTION_BY_ID[self.action_id]
        for index, field in enumerate(spec.fields):
            if field.name == field_name:
                return self.arguments[index]
        return ""


LAYER = ActionField("layer", "Layer", "layer", "nav")
LAYOUT = ActionField("layout", "Layout", "layer", "colemak")
ACTION = ActionField("action", "Action", "action", "esc or macro(C-c)")
SECOND_ACTION = ActionField(
    "second_action", "Fallback action", "action", "layer(nav)"
)
TIMEOUT = ActionField("timeout", "Timeout", "timeout", "200")
IDLE_TIMEOUT = ActionField("idle_timeout", "Idle timeout", "timeout", "1000")
HOLD_TIMEOUT = ActionField("hold_timeout", "Hold timeout", "timeout", "200")
REPEAT_TIMEOUT = ActionField(
    "repeat_timeout", "Repeat timeout", "timeout", "50"
)
KEY = ActionField("key", "Key", "key", "a")
MACRO_BODY = ActionField(
    "macro", "Sequence", "macro_body", "C-a C-c"
)
MACRO_EXPRESSION = ActionField(
    "macro", "Macro", "macro", "macro(C-a C-c)"
)
COMMAND = ActionField(
    "command", "Shell command", "command", "notify-send 'keyd'"
)


ACTION_SPECS: tuple[ActionSpec, ...] = (
    ActionSpec(
        "macro",
        "Macro",
        "macro",
        (MACRO_BODY,),
        "Press a sequence of keys.",
    ),
    ActionSpec(
        "layer",
        "Hold layer",
        "layer",
        (LAYER,),
        "Activate a layer while this key is held.",
        macro_variant="layerm",
    ),
    ActionSpec(
        "oneshot",
        "One-shot layer",
        "oneshot",
        (LAYER,),
        "Apply a layer to the next key press.",
        macro_variant="oneshotm",
    ),
    ActionSpec(
        "swap",
        "Swap layer",
        "swap",
        (LAYER,),
        "Replace the currently active layer.",
        macro_variant="swapm",
    ),
    ActionSpec(
        "toggle",
        "Toggle layer",
        "toggle",
        (LAYER,),
        "Toggle a layer on or off.",
        macro_variant="togglem",
    ),
    ActionSpec(
        "setlayout",
        "Set layout",
        "setlayout",
        (LAYOUT,),
        "Switch to a layout and clear the active layers.",
    ),
    ActionSpec(
        "clear",
        "Clear active layers",
        "clear",
        (),
        "Clear every active layer.",
        macro_variant="clearm",
    ),
    ActionSpec(
        "repeat",
        "Repeat last action",
        "repeat",
        (),
        "Repeat the last executed action.",
    ),
    ActionSpec(
        "overload",
        "Tap or hold",
        "overload",
        (LAYER, ACTION),
        "Use a layer while held and execute an action when tapped.",
    ),
    ActionSpec(
        "overloadt",
        "Tap or hold after timeout",
        "overloadt",
        (LAYER, ACTION, TIMEOUT),
        "Resolve a tap after a fixed timeout.",
    ),
    ActionSpec(
        "overloadt2",
        "Permissive tap or hold",
        "overloadt2",
        (LAYER, ACTION, TIMEOUT),
        "Prefer the hold action when another key is pressed.",
    ),
    ActionSpec(
        "overloadi",
        "Idle-sensitive action",
        "overloadi",
        (ACTION, SECOND_ACTION, IDLE_TIMEOUT),
        "Choose an action based on the time since the previous key press.",
    ),
    ActionSpec(
        "lettermod",
        "Letter modifier",
        "lettermod",
        (LAYER, KEY, IDLE_TIMEOUT, HOLD_TIMEOUT),
        "Use a layer on hold and a key on tap, optimized for typing.",
    ),
    ActionSpec(
        "timeout",
        "Timeout action",
        "timeout",
        (ACTION, TIMEOUT, SECOND_ACTION),
        "Choose an action based on how long the key is held.",
    ),
    ActionSpec(
        "macro2",
        "Timed macro",
        "macro2",
        (TIMEOUT, REPEAT_TIMEOUT, MACRO_EXPRESSION),
        "Run a macro with custom sequence and repeat timeouts.",
    ),
    ActionSpec(
        "command",
        "Run command",
        "command",
        (COMMAND,),
        "Execute a shell command asynchronously.",
    ),
    ActionSpec(
        "noop",
        "Do nothing",
        "noop",
        (),
        "Ignore the key.",
    ),
)

ACTION_BY_ID = {spec.action_id: spec for spec in ACTION_SPECS}
ACTION_BY_FUNCTION = {spec.function: spec for spec in ACTION_SPECS}
MACRO_VARIANTS = {
    spec.macro_variant: spec
    for spec in ACTION_SPECS
    if spec.macro_variant is not None
}
INTERNAL_ACTION_NAMES = frozenset(
    set(ACTION_BY_FUNCTION) | set(MACRO_VARIANTS) | {"oneshotk"}
)


def split_action_arguments(value: str) -> tuple[str, ...] | None:
    """Split function arguments while preserving nested action expressions."""
    if not value.strip():
        return ()

    arguments: list[str] = []
    start = 0
    depth = 0
    for index, character in enumerate(value):
        if character == "(":
            depth += 1
        elif character == ")":
            depth -= 1
            if depth < 0:
                return None
        elif character == "," and depth == 0:
            argument = value[start:index].strip()
            if not argument:
                return None
            arguments.append(argument)
            start = index + 1

    if depth != 0:
        return None
    final_argument = value[start:].strip()
    if not final_argument:
        return None
    arguments.append(final_argument)
    return tuple(arguments)


def _parse_call(value: str) -> tuple[str, str] | None:
    """Return a root function and its unparsed body if syntax is balanced."""
    value = value.strip()
    opening = value.find("(")
    if opening <= 0 or not value.endswith(")"):
        return None

    name = value[:opening].strip()
    if not name.isidentifier():
        return None

    depth = 0
    for index, character in enumerate(value[opening:], start=opening):
        if character == "(":
            depth += 1
        elif character == ")":
            depth -= 1
            if depth < 0 or (depth == 0 and index != len(value) - 1):
                return None
    if depth != 0:
        return None
    return name, value[opening + 1 : -1].strip()


def parse_action(value: str) -> ParsedAction | None:
    """Parse any supported keyd action into the normalized visual model."""
    stripped = value.strip()
    if stripped == "noop":
        return ParsedAction("noop", ())

    call = _parse_call(stripped)
    if call is None:
        return None
    function, body = call

    if function in MACRO_VARIANTS:
        return _parse_macro_variant(function, body)

    if function == "oneshotk":
        return _parse_oneshot_key(body)

    spec = ACTION_BY_FUNCTION.get(function)
    if spec is None or spec.function == "noop":
        return None
    return _parse_spec(spec, body)


def _parse_macro_variant(function: str, body: str) -> ParsedAction | None:
    """Normalize one of keyd's macro-capable internal functions."""
    spec = MACRO_VARIANTS[function]
    arguments = split_action_arguments(body)
    expected = len(spec.fields) + 1
    if arguments is None or len(arguments) != expected:
        return None
    return ParsedAction(spec.action_id, arguments[:-1], macro=arguments[-1])


def _parse_oneshot_key(body: str) -> ParsedAction | None:
    """Normalize ``oneshotk`` to the visual one-shot action."""
    arguments = split_action_arguments(body)
    if arguments is None or len(arguments) != 2:
        return None
    return ParsedAction("oneshot", arguments[:1], held_key=arguments[1])


def _parse_spec(spec: ActionSpec, body: str) -> ParsedAction | None:
    """Parse a regular catalogue entry with its documented arity."""
    if spec.function in {"macro", "command"}:
        arguments = (body,) if body else ()
    else:
        arguments = split_action_arguments(body)
        if arguments is None:
            return None
    if len(arguments) != len(spec.fields):
        return None
    if any(
        not argument
        or (field.kind == "timeout" and not argument.isdigit())
        for field, argument in zip(spec.fields, arguments)
    ):
        return None
    return ParsedAction(spec.action_id, arguments)


def format_action(
    action_id: str,
    arguments: tuple[str, ...],
    *,
    macro: str = "",
    held_key: str = "",
) -> str:
    """Generate low-level keyd syntax from a normalized visual action."""
    spec = ACTION_BY_ID[action_id]
    cleaned_arguments = tuple(argument.strip() for argument in arguments)
    if len(cleaned_arguments) != len(spec.fields):
        raise ValueError(f"{action_id} expects {len(spec.fields)} arguments")
    if any(not argument for argument in cleaned_arguments):
        raise ValueError(f"{action_id} has an empty required argument")
    if any(
        field.kind == "timeout" and not argument.isdigit()
        for field, argument in zip(spec.fields, cleaned_arguments)
    ):
        raise ValueError(f"{action_id} has a non-numeric timeout")

    macro = macro.strip()
    held_key = held_key.strip()
    if macro and held_key:
        raise ValueError("parallel macro and held key are mutually exclusive")
    if held_key:
        if spec.action_id != "oneshot":
            raise ValueError(f"{action_id} does not support a held key")
        return f"oneshotk({', '.join(cleaned_arguments + (held_key,))})"
    if macro:
        if spec.macro_variant is None:
            raise ValueError(f"{action_id} does not support a parallel macro")
        return (
            f"{spec.macro_variant}("
            f"{', '.join(cleaned_arguments + (macro,))})"
        )
    if spec.function == "noop":
        return "noop"
    return f"{spec.function}({', '.join(cleaned_arguments)})"


def action_completions() -> tuple[str, ...]:
    """Return all low-level action spellings accepted by keyd."""
    ordered_names = [spec.function for spec in ACTION_SPECS]
    ordered_names.extend(
        spec.macro_variant
        for spec in ACTION_SPECS
        if spec.macro_variant is not None
    )
    ordered_names.append("oneshotk")
    return tuple(
        name if name == "noop" else f"{name}()" for name in ordered_names
    )


def starts_with_known_action(value: str) -> bool:
    """Whether a value appears intended to be one of the supported actions."""
    stripped = value.strip()
    if stripped == "noop":
        return True
    return any(
        stripped.startswith(f"{function}(")
        for function in INTERNAL_ACTION_NAMES
    )
