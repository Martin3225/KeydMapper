"""Shared catalogue, parser and formatter for keyd binding actions."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


class ActionFieldKind(str, Enum):
    """Input semantics used by the visual action form."""

    LAYER_NAME = "layer_name"
    KEY_SEQUENCE = "key_sequence"
    ACTION_EXPRESSION = "action_expression"
    TIMEOUT_MS = "timeout_ms"
    MACRO_BODY = "macro_body"
    MACRO_EXPRESSION = "macro_expression"
    SHELL_COMMAND = "shell_command"


class ActionCategory(str, Enum):
    """Visual groups used by the single Binding action selector."""

    SEQUENCES = "Macros & repeat"
    LAYERS = "Layers"
    TAP_HOLD = "Tap & hold"
    SYSTEM = "System"


@dataclass(frozen=True)
class ActionField:
    """One documented argument of a keyd function.

    ``argument_id`` identifies the value inside the normalized model.
    ``input_kind`` tells the UI which control and completion rules to use.
    They are intentionally independent even when their words happen to match.
    """

    argument_id: str
    label: str
    input_kind: ActionFieldKind
    example: str = ""


@dataclass(frozen=True)
class ActionSpec:
    """User-facing definition of one normalized keyd action."""

    keyd_function: str
    label: str
    category: ActionCategory
    fields: tuple[ActionField, ...]
    help_text: str
    macro_function: str | None = None
    held_key_function: str | None = None


@dataclass(frozen=True)
class ParsedAction:
    """A low-level keyd expression normalized to its user-facing action."""

    action_name: str
    arguments: tuple[str, ...]
    macro: str = ""
    held_key: str = ""


LAYER_ARGUMENT = ActionField(
    argument_id="layer",
    label="Layer",
    input_kind=ActionFieldKind.LAYER_NAME,
    example="nav",
)
LAYOUT_ARGUMENT = ActionField(
    argument_id="layout",
    label="Layout",
    input_kind=ActionFieldKind.LAYER_NAME,
    example="colemak",
)
ACTION_ARGUMENT = ActionField(
    argument_id="action",
    label="Action",
    input_kind=ActionFieldKind.ACTION_EXPRESSION,
    example="esc or macro(C-c)",
)
FALLBACK_ACTION_ARGUMENT = ActionField(
    argument_id="second_action",
    label="Fallback action",
    input_kind=ActionFieldKind.ACTION_EXPRESSION,
    example="layer(nav)",
)
TIMEOUT_ARGUMENT = ActionField(
    argument_id="timeout",
    label="Timeout",
    input_kind=ActionFieldKind.TIMEOUT_MS,
    example="200",
)
IDLE_TIMEOUT_ARGUMENT = ActionField(
    argument_id="idle_timeout",
    label="Idle timeout",
    input_kind=ActionFieldKind.TIMEOUT_MS,
    example="1000",
)
HOLD_TIMEOUT_ARGUMENT = ActionField(
    argument_id="hold_timeout",
    label="Hold timeout",
    input_kind=ActionFieldKind.TIMEOUT_MS,
    example="200",
)
REPEAT_TIMEOUT_ARGUMENT = ActionField(
    argument_id="repeat_timeout",
    label="Repeat timeout",
    input_kind=ActionFieldKind.TIMEOUT_MS,
    example="50",
)
KEY_ARGUMENT = ActionField(
    argument_id="key",
    label="Key",
    input_kind=ActionFieldKind.KEY_SEQUENCE,
    example="a",
)
MACRO_BODY_ARGUMENT = ActionField(
    argument_id="macro",
    label="Sequence",
    input_kind=ActionFieldKind.MACRO_BODY,
    example="C-a C-c",
)
MACRO_EXPRESSION_ARGUMENT = ActionField(
    argument_id="macro",
    label="Macro",
    input_kind=ActionFieldKind.MACRO_EXPRESSION,
    example="macro(C-a C-c)",
)
SHELL_COMMAND_ARGUMENT = ActionField(
    argument_id="command",
    label="Shell command",
    input_kind=ActionFieldKind.SHELL_COMMAND,
    example="notify-send 'keyd'",
)


ACTION_SPECS: tuple[ActionSpec, ...] = (
    ActionSpec(
        keyd_function="macro",
        label="Macro",
        category=ActionCategory.SEQUENCES,
        fields=(MACRO_BODY_ARGUMENT,),
        help_text="Press a sequence of keys.",
    ),
    ActionSpec(
        keyd_function="layer",
        label="Hold layer",
        category=ActionCategory.LAYERS,
        fields=(LAYER_ARGUMENT,),
        help_text="Activate a layer while this key is held.",
        macro_function="layerm",
    ),
    ActionSpec(
        keyd_function="oneshot",
        label="One-shot layer",
        category=ActionCategory.LAYERS,
        fields=(LAYER_ARGUMENT,),
        help_text="Apply a layer to the next key press.",
        macro_function="oneshotm",
        held_key_function="oneshotk",
    ),
    ActionSpec(
        keyd_function="swap",
        label="Swap layer",
        category=ActionCategory.LAYERS,
        fields=(LAYER_ARGUMENT,),
        help_text="Replace the currently active layer.",
        macro_function="swapm",
    ),
    ActionSpec(
        keyd_function="toggle",
        label="Toggle layer",
        category=ActionCategory.LAYERS,
        fields=(LAYER_ARGUMENT,),
        help_text="Toggle a layer on or off.",
        macro_function="togglem",
    ),
    ActionSpec(
        keyd_function="setlayout",
        label="Set layout",
        category=ActionCategory.LAYERS,
        fields=(LAYOUT_ARGUMENT,),
        help_text="Switch to a layout and clear the active layers.",
    ),
    ActionSpec(
        keyd_function="clear",
        label="Clear active layers",
        category=ActionCategory.LAYERS,
        fields=(),
        help_text="Clear every active layer.",
        macro_function="clearm",
    ),
    ActionSpec(
        keyd_function="repeat",
        label="Repeat last action",
        category=ActionCategory.SEQUENCES,
        fields=(),
        help_text="Repeat the last executed action.",
    ),
    ActionSpec(
        keyd_function="overload",
        label="Tap or hold",
        category=ActionCategory.TAP_HOLD,
        fields=(LAYER_ARGUMENT, ACTION_ARGUMENT),
        help_text="Use a layer while held and execute an action when tapped.",
    ),
    ActionSpec(
        keyd_function="overloadt",
        label="Tap or hold after timeout",
        category=ActionCategory.TAP_HOLD,
        fields=(LAYER_ARGUMENT, ACTION_ARGUMENT, TIMEOUT_ARGUMENT),
        help_text="Resolve a tap after a fixed timeout.",
    ),
    ActionSpec(
        keyd_function="overloadt2",
        label="Permissive tap or hold",
        category=ActionCategory.TAP_HOLD,
        fields=(LAYER_ARGUMENT, ACTION_ARGUMENT, TIMEOUT_ARGUMENT),
        help_text="Prefer the hold action when another key is pressed.",
    ),
    ActionSpec(
        keyd_function="overloadi",
        label="Idle-sensitive action",
        category=ActionCategory.TAP_HOLD,
        fields=(
            ACTION_ARGUMENT,
            FALLBACK_ACTION_ARGUMENT,
            IDLE_TIMEOUT_ARGUMENT,
        ),
        help_text=(
            "Choose an action based on the time since the previous key press."
        ),
    ),
    ActionSpec(
        keyd_function="lettermod",
        label="Letter modifier",
        category=ActionCategory.TAP_HOLD,
        fields=(
            LAYER_ARGUMENT,
            KEY_ARGUMENT,
            IDLE_TIMEOUT_ARGUMENT,
            HOLD_TIMEOUT_ARGUMENT,
        ),
        help_text="Use a layer on hold and a key on tap, optimized for typing.",
    ),
    ActionSpec(
        keyd_function="timeout",
        label="Timeout action",
        category=ActionCategory.TAP_HOLD,
        fields=(
            ACTION_ARGUMENT,
            TIMEOUT_ARGUMENT,
            FALLBACK_ACTION_ARGUMENT,
        ),
        help_text="Choose an action based on how long the key is held.",
    ),
    ActionSpec(
        keyd_function="macro2",
        label="Timed macro",
        category=ActionCategory.SEQUENCES,
        fields=(
            TIMEOUT_ARGUMENT,
            REPEAT_TIMEOUT_ARGUMENT,
            MACRO_EXPRESSION_ARGUMENT,
        ),
        help_text="Run a macro with custom sequence and repeat timeouts.",
    ),
    ActionSpec(
        keyd_function="command",
        label="Run command",
        category=ActionCategory.SYSTEM,
        fields=(SHELL_COMMAND_ARGUMENT,),
        help_text="Execute a shell command asynchronously.",
    ),
    ActionSpec(
        keyd_function="noop",
        label="Do nothing",
        category=ActionCategory.SYSTEM,
        fields=(),
        help_text="Ignore the key.",
    ),
)

ACTION_BY_NAME = {spec.keyd_function: spec for spec in ACTION_SPECS}
MACRO_VARIANTS = {
    spec.macro_function: spec
    for spec in ACTION_SPECS
    if spec.macro_function is not None
}
HELD_KEY_VARIANTS = {
    spec.held_key_function: spec
    for spec in ACTION_SPECS
    if spec.held_key_function is not None
}
INTERNAL_ACTION_NAMES = frozenset(
    set(ACTION_BY_NAME) | set(MACRO_VARIANTS) | set(HELD_KEY_VARIANTS)
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

    if function in HELD_KEY_VARIANTS:
        return _parse_held_key_variant(function, body)

    spec = ACTION_BY_NAME.get(function)
    if spec is None or spec.keyd_function == "noop":
        return None
    return _parse_spec(spec, body)


def _parse_macro_variant(function: str, body: str) -> ParsedAction | None:
    """Normalize one of keyd's macro-capable internal functions."""
    spec = MACRO_VARIANTS[function]
    arguments = split_action_arguments(body)
    expected = len(spec.fields) + 1
    if arguments is None or len(arguments) != expected:
        return None
    return ParsedAction(
        spec.keyd_function,
        arguments[:-1],
        macro=arguments[-1],
    )


def _parse_held_key_variant(
    function: str, body: str
) -> ParsedAction | None:
    """Normalize a low-level held-key variant to its base action."""
    spec = HELD_KEY_VARIANTS[function]
    arguments = split_action_arguments(body)
    expected = len(spec.fields) + 1
    if arguments is None or len(arguments) != expected:
        return None
    return ParsedAction(
        spec.keyd_function,
        arguments[:-1],
        held_key=arguments[-1],
    )


def _parse_spec(spec: ActionSpec, body: str) -> ParsedAction | None:
    """Parse a regular catalogue entry with its documented arity."""
    opaque_kinds = {
        ActionFieldKind.MACRO_BODY,
        ActionFieldKind.SHELL_COMMAND,
    }
    if len(spec.fields) == 1 and spec.fields[0].input_kind in opaque_kinds:
        arguments = (body,) if body else ()
    else:
        arguments = split_action_arguments(body)
        if arguments is None:
            return None
    if len(arguments) != len(spec.fields):
        return None
    if any(
        not argument
        or (
            field.input_kind is ActionFieldKind.TIMEOUT_MS
            and not argument.isdigit()
        )
        for field, argument in zip(spec.fields, arguments)
    ):
        return None
    return ParsedAction(spec.keyd_function, arguments)


def format_action(
    action_name: str,
    arguments: tuple[str, ...],
    *,
    macro: str = "",
    held_key: str = "",
) -> str:
    """Generate low-level keyd syntax from a normalized visual action."""
    spec = ACTION_BY_NAME[action_name]
    cleaned_arguments = tuple(argument.strip() for argument in arguments)
    if len(cleaned_arguments) != len(spec.fields):
        raise ValueError(
            f"{action_name} expects {len(spec.fields)} arguments"
        )
    if any(not argument for argument in cleaned_arguments):
        raise ValueError(f"{action_name} has an empty required argument")
    if any(
        field.input_kind is ActionFieldKind.TIMEOUT_MS
        and not argument.isdigit()
        for field, argument in zip(spec.fields, cleaned_arguments)
    ):
        raise ValueError(f"{action_name} has a non-numeric timeout")

    macro = macro.strip()
    held_key = held_key.strip()
    if macro and held_key:
        raise ValueError("parallel macro and held key are mutually exclusive")
    if held_key:
        if spec.held_key_function is None:
            raise ValueError(f"{action_name} does not support a held key")
        return (
            f"{spec.held_key_function}("
            f"{', '.join(cleaned_arguments + (held_key,))})"
        )
    if macro:
        if spec.macro_function is None:
            raise ValueError(
                f"{action_name} does not support a parallel macro"
            )
        return (
            f"{spec.macro_function}("
            f"{', '.join(cleaned_arguments + (macro,))})"
        )
    if spec.keyd_function == "noop":
        return "noop"
    return f"{spec.keyd_function}({', '.join(cleaned_arguments)})"


def action_completions() -> tuple[str, ...]:
    """Return all low-level action spellings accepted by keyd."""
    ordered_names = [spec.keyd_function for spec in ACTION_SPECS]
    ordered_names.extend(
        spec.macro_function
        for spec in ACTION_SPECS
        if spec.macro_function is not None
    )
    ordered_names.extend(
        spec.held_key_function
        for spec in ACTION_SPECS
        if spec.held_key_function is not None
    )
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
