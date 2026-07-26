"""Module for validating key names against keyd's supported keys."""

import subprocess
from functools import cache

from keyd.actions import parse_action, starts_with_known_action


@cache
def get_valid_keys() -> frozenset[str]:
    """Retrieves the list of valid key names from keyd."""
    try:
        result = subprocess.run(
            ["keyd", "list-keys"],
            capture_output=True,
            text=True,
            timeout=5,
            check=False,
        )
        if result.returncode == 0:
            return frozenset(
                line.strip() for line in result.stdout.splitlines() if line.strip()
            )
    except (FileNotFoundError, subprocess.TimeoutExpired):
        pass
    return frozenset()


def is_valid_key(name: str) -> bool:
    """Checks if a given key name is valid according to keyd."""
    valid = get_valid_keys()
    if not valid:
        return True
    return name in valid


def is_valid_value(value: str) -> bool:
    """Checks if a mapped value string is valid according to keyd syntax."""
    if not value:
        return True  # Empty - clear the mapping

    if starts_with_known_action(value):
        return parse_action(value) is not None

    parts = value.split("-")
    base_key = parts[-1]
    modifiers = parts[:-1]

    valid_modifiers = {"C", "S", "M", "A", "G"}
    for mod in modifiers:
        if mod not in valid_modifiers:
            return False

    if not base_key and modifiers:
        return False

    return is_valid_key(base_key)
