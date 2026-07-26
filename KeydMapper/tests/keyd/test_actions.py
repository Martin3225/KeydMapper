"""Tests for the shared keyd action catalogue and round-trip parser."""

import shutil

import pytest

from keyd.actions import (
    ACTION_BY_ID,
    ACTION_SPECS,
    action_completions,
    format_action,
    parse_action,
    split_action_arguments,
)
from keyd.config import Config


ACTION_CASES = (
    ("macro", ("C-a C-c",), "macro(C-a C-c)"),
    ("layer", ("nav",), "layer(nav)"),
    ("oneshot", ("shift",), "oneshot(shift)"),
    ("swap", ("main",), "swap(main)"),
    ("toggle", ("symbols",), "toggle(symbols)"),
    ("setlayout", ("colemak",), "setlayout(colemak)"),
    ("clear", (), "clear()"),
    ("repeat", (), "repeat()"),
    ("overload", ("control", "esc"), "overload(control, esc)"),
    (
        "overloadt",
        ("control", "esc", "200"),
        "overloadt(control, esc, 200)",
    ),
    (
        "overloadt2",
        ("control", "esc", "200"),
        "overloadt2(control, esc, 200)",
    ),
    (
        "overloadi",
        ("left", "layer(nav)", "1000"),
        "overloadi(left, layer(nav), 1000)",
    ),
    (
        "lettermod",
        ("shift", "a", "1000", "200"),
        "lettermod(shift, a, 1000, 200)",
    ),
    (
        "timeout",
        ("layer(nav)", "200", "esc"),
        "timeout(layer(nav), 200, esc)",
    ),
    (
        "macro2",
        ("20", "50", "macro(C-a C-c)"),
        "macro2(20, 50, macro(C-a C-c))",
    ),
    (
        "command",
        ("notify-send 'hello, keyd'",),
        "command(notify-send 'hello, keyd')",
    ),
    ("noop", (), "noop"),
)


@pytest.mark.parametrize(("action_id", "arguments", "expected"), ACTION_CASES)
def test_all_visual_actions_format_and_round_trip(action_id, arguments, expected):
    """Every catalogue entry has stable generated and parsed syntax."""
    generated = format_action(action_id, arguments)

    assert generated == expected
    parsed = parse_action(generated)
    assert parsed is not None
    assert parsed.action_id == action_id
    assert parsed.arguments == arguments
    assert format_action(parsed.action_id, parsed.arguments) == expected


@pytest.mark.parametrize(
    ("action_id", "function"),
    (
        ("layer", "layerm"),
        ("oneshot", "oneshotm"),
        ("swap", "swapm"),
        ("toggle", "togglem"),
        ("clear", "clearm"),
    ),
)
def test_parallel_macro_is_a_property_of_the_base_action(action_id, function):
    """Internal macro spellings never become separate visual action types."""
    spec = ACTION_BY_ID[action_id]
    arguments = ("nav",) if spec.fields else ()
    generated = format_action(
        action_id,
        arguments,
        macro="macro(C-a C-c)",
    )

    assert generated == (
        f"{function}({', '.join(arguments + ('macro(C-a C-c)',))})"
    )
    parsed = parse_action(generated)
    assert parsed is not None
    assert parsed.action_id == action_id
    assert parsed.arguments == arguments
    assert parsed.macro == "macro(C-a C-c)"


def test_oneshot_held_key_is_a_property_of_oneshot():
    """``oneshotk`` is represented by the normal one-shot action form."""
    generated = format_action("oneshot", ("nav",), held_key="a")

    assert generated == "oneshotk(nav, a)"
    parsed = parse_action(generated)
    assert parsed is not None
    assert parsed.action_id == "oneshot"
    assert parsed.arguments == ("nav",)
    assert parsed.held_key == "a"


def test_oneshot_rejects_conflicting_additional_behaviours():
    """The visual model cannot express a nonexistent combined keyd variant."""
    with pytest.raises(ValueError, match="mutually exclusive"):
        format_action(
            "oneshot",
            ("nav",),
            macro="macro(a)",
            held_key="a",
        )


def test_nested_arguments_split_only_at_the_root():
    """Nested commas remain part of their child action or macro."""
    assert split_action_arguments(
        "control, timeout(layer(nav), 200, macro(C-a, C-c)), 250"
    ) == (
        "control",
        "timeout(layer(nav), 200, macro(C-a, C-c))",
        "250",
    )


@pytest.mark.parametrize(
    "value",
    (
        "layer()",
        "layer(nav",
        "layer(nav, shift)",
        "overload(control)",
        "overload(control, esc, 200)",
        "oneshotk(nav)",
        "layerm(nav)",
        "overloadt(nav, esc, later)",
        "lettermod(nav, a, 1000, soon)",
        "noop()",
    ),
)
def test_malformed_known_actions_are_not_parsed(value):
    """Known action names require their exact documented arity and form."""
    assert parse_action(value) is None


def test_catalogue_and_completions_cover_every_low_level_action():
    """The source editor still suggests real keyd spellings when edited by hand."""
    completions = set(action_completions())
    for spec in ACTION_SPECS:
        spelling = spec.function if spec.function == "noop" else f"{spec.function}()"
        assert spelling in completions
        if spec.macro_variant:
            assert f"{spec.macro_variant}()" in completions
    assert "oneshotk()" in completions


@pytest.mark.skipif(shutil.which("keyd") is None, reason="keyd is not installed")
def test_complete_generated_action_config_is_accepted_by_keyd():
    """Exercise all generated action forms against keyd's real parser."""
    source = """[ids]
*

[main]
a = macro(C-a C-c)
b = layerm(nav, macro(C-a))
c = oneshotm(nav, macro(C-a))
d = oneshotk(nav, a)
e = swapm(nav, macro(C-a))
f = togglem(nav, macro(C-a))
g = clearm(macro(C-a))
h = repeat()
i = overload(nav, esc)
j = overloadt(nav, esc, 200)
k = overloadt2(nav, esc, 200)
l = overloadi(left, layer(nav), 1000)
m = lettermod(nav, a, 1000, 200)
n = timeout(layer(nav), 200, esc)
o = macro2(20, 50, macro(C-a C-c))
p = command(true)
q = noop
r = setlayout(colemak)

[nav]

[colemak:layout]
"""

    valid, message = Config.check_source_text(source)

    assert valid is True, message
