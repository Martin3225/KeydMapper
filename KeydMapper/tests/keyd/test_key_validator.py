"""Tests for valid key detection using keyd list-keys."""

from unittest.mock import MagicMock, patch

from keyd.key_validator import get_valid_keys, is_valid_key, is_valid_value


def test_get_valid_keys_success():
    """Test get_valid_keys successfully parses keyd list-keys output."""
    get_valid_keys.cache_clear()
    with patch("subprocess.run") as mock_run:
        mock_result = MagicMock()
        mock_result.stdout = "enter\nspace\n\nbackspace\n"
        mock_result.returncode = 0
        mock_run.return_value = mock_result

        keys = get_valid_keys()
        assert keys == frozenset(["enter", "space", "backspace"])


def test_get_valid_keys_failure():
    """Test get_valid_keys handles missing keyd command by returning empty set."""
    get_valid_keys.cache_clear()
    with patch("subprocess.run") as mock_run:
        mock_run.side_effect = FileNotFoundError()

        keys = get_valid_keys()
        assert keys == frozenset()


def test_is_valid_key_empty():
    """Test is_valid_key returns True as a fallback when no valid keys are found."""
    get_valid_keys.cache_clear()
    with patch("keyd.key_validator.get_valid_keys") as mock_get_valid_keys:
        mock_get_valid_keys.return_value = frozenset()

        assert is_valid_key("bober") is True


def test_is_valid_value_empty():
    """Test that empty string is valid."""
    assert is_valid_value("") is True


def test_is_valid_value_functions():
    """Test that known functions with balanced parentheses are valid."""
    assert is_valid_value("layer(nav)") is True
    assert is_valid_value("macro(C-c)") is True
    assert is_valid_value("toggle(main)") is True
    assert is_valid_value("macro(layer(nav))") is True

    # Missing closing parenthesis
    assert is_valid_value("layer(nav") is False
    # Unbalanced parentheses
    assert is_valid_value("macro(layer(nav)") is False


def test_is_valid_value_modifiers():
    """Test that key mappings with valid modifiers are handled correctly."""
    with patch("keyd.key_validator.is_valid_key") as mock_is_valid_key:
        mock_is_valid_key.return_value = True

        assert is_valid_value("C-a") is True
        assert is_valid_value("C-S-A-M-G-delete") is True

        # Invalid modifiers
        assert is_valid_value("X-a") is False
        assert is_valid_value("Ctrl-a") is False # keyd uses 'C' for control modifier

        # Modifier without a base key
        assert is_valid_value("C-") is False
