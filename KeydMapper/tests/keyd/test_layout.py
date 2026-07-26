"""Tests for layout configuration and button management."""

import json
from unittest.mock import mock_open, patch

from keyd.layout import (
    Layout,
    LayoutButton,
    does_layout_exist,
    get_device_id_from_config,
    load_layout,
    load_layout_from_path,
    save_layout,
)


def test_does_layout_exist():
    """Test does_layout_exist correctly checks filesystem for layout files."""
    with patch("os.path.isfile") as mock_isfile:
        mock_isfile.return_value = True
        assert does_layout_exist("1234:5678") is True
        mock_isfile.assert_called_once()
        args, _ = mock_isfile.call_args
        assert "1234_5678.layout" in args[0]


def test_load_layout_not_exists():
    """Test load_layout returns an empty layout when the file is missing."""
    with patch("os.path.isfile", return_value=False):
        layout = load_layout("1111:2222")
        assert layout.device_id == "1111:2222"
        assert len(layout.buttons) == 0


def test_load_layout_exists():
    """Test load_layout successfully loads a layout from a JSON file."""
    mock_json = json.dumps(
        {
            "device_id": "4242:7667",
            "buttons": [
                {
                    "name": "B",
                    "default": "B",
                    "x": 1.0,
                    "y": 2.0,
                    "width": 3.0,
                    "height": 4.0,
                }
            ],
        }
    )
    with (
        patch("os.path.isfile", return_value=True),
        patch("builtins.open", mock_open(read_data=mock_json)),
    ):
        layout = load_layout("4242:7667")
        assert layout.device_id == "4242:7667"
        assert len(layout.buttons) == 1
        assert layout.buttons[0].name == "B"


def test_load_layout_from_path():
    """Test load_layout_from_path successfully loads layout data from a specific path."""
    mock_json = '{"device_id": "1111:2222", "buttons": []}'
    with patch("builtins.open", mock_open(read_data=mock_json)):
        layout = load_layout_from_path("/some/path/file.layout")
        assert layout.device_id == "1111:2222"


def test_save_layout():
    """Test save_layout writes layout data to the correct file path."""
    layout = Layout(
        device_id="1111:2222", buttons=[LayoutButton("A", "A", 0.0, 0.0, 1.0, 1.0)]
    )
    with (
        patch("builtins.open", mock_open()) as mock_file,
        patch("os.makedirs") as mock_makedirs,
    ):
        save_layout(layout)

        mock_makedirs.assert_called_once()
        mock_file.assert_called_once()
        handle = mock_file()
        written = "".join(call.args[0] for call in handle.write.call_args_list)
        assert '"device_id": "1111:2222"' in written
        assert '"name": "A"' in written


def test_get_device_id_from_config():
    """Test get_device_id_from_config correctly parses the device ID from a config."""
    config_content = """[ids]
    1111:2222
    [main]
    a = b
    """
    with patch("builtins.open", mock_open(read_data=config_content)):
        device_id = get_device_id_from_config("test.conf")
        assert device_id == "1111:2222"


def test_get_device_id_from_config_fail():
    """Test get_device_id_from_config returns an empty string on read failure."""
    with patch("builtins.open") as mock_file:
        mock_file.side_effect = OSError()
        device_id = get_device_id_from_config("test.conf")
        assert device_id == ""
