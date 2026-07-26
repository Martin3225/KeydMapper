"""Tests for the configuration file management in KeydMapper."""

from unittest.mock import MagicMock, mock_open, patch

import pytest
from keyd.config import Config, ConfigSaveError


def test_config_initialization_with_no_file():
    """
    This test checks what happens when we create a Config object for a file
    that doesn't exist yet. It should automatically create a 'main' layer.
    """

    with (
        # Arrange
        patch("os.path.exists", return_value=False),
        patch("keyd.config.get_device_id_from_config", return_value="1234:5678"),
    ):
        # Act
        config = Config("new_test_config.conf")

        # Assert
        assert config.name == "new_test_config.conf"
        assert config.device_id == "1234:5678"

        assert "main" in config.layers
        assert config.layer_order == ["main"]


def test_config_loads_existing_file():
    """
    This test checks if the Config class can correctly read and understand
    an existing configuration file.
    """
    # Arrange (simple keyd config)
    sample_content = """[ids]
1234:5678

[main]
capslock = layer(control)
esc = capslock

[control]
h = left
j = down
"""

    with (
        patch("os.path.exists", return_value=True),
        patch("builtins.open", mock_open(read_data=sample_content)),
        patch("keyd.config.get_device_id_from_config", return_value="1234:5678"),
    ):
        # Act
        config = Config("existing_config.conf")

        # Assert
        # Check for layers we defined
        assert "main" in config.layers
        assert "control" in config.layers

        # Check if the keys and their values are correct
        assert config.layers["main"]["capslock"] == "layer(control)"
        assert config.layers["main"]["esc"] == "capslock"
        assert config.layers["control"]["h"] == "left"
        assert config.layers["control"]["j"] == "down"

        # Check if the order of layers was preserved
        assert config.layer_order == ["main", "control"]


def test_config_saves_correctly():
    """
    This test checks if calling .save() correctly writes to a file
    and tries to copy it to the system folder using 'pkexec'.
    """

    with (
        patch("os.path.exists", return_value=False),
        patch("keyd.config.get_device_id_from_config", return_value="1234:5678"),
    ):
        config = Config("save_test.conf")

    config.layers["main"]["a"] = "b"

    m = mock_open()
    with (
        patch("builtins.open", m),
        patch("os.makedirs"),
        patch("subprocess.Popen") as mock_popen,
    ):
        mock_process = MagicMock()
        mock_process.communicate.return_value = ("", "")
        mock_process.returncode = 0
        mock_popen.return_value.__enter__.return_value = mock_process

        # Act
        config.save()

        # Assert
        m.assert_called()

        # combine all calls into string
        handle = m()
        written_text = "".join(call.args[0] for call in handle.write.call_args_list)

        # Check the ID and shortcut
        assert "[ids]" in written_text.splitlines()[0]  # IDs should be at the top
        assert "[ids]\n1234:5678" in written_text
        assert "[main]\na = b" in written_text

        mock_popen.assert_called()
        args, _ = mock_popen.call_args
        cmd_str = " ".join(args[0])
        assert "pkexec" in cmd_str
        assert "cp" in cmd_str


def test_config_save_invalid_config():
    """Test that saving an invalid config raises ConfigSaveError."""
    with (
        patch("os.path.exists", return_value=False),
        patch("keyd.config.get_device_id_from_config", return_value="1234:5678"),
    ):
        config = Config("invalid_save_test.conf")

    m = mock_open()
    with (
        patch("builtins.open", m),
        patch("os.makedirs"),
        patch("keyd.config.Config.check", return_value="Error on line 1"),
        patch("subprocess.Popen") as mock_popen,
    ):
        with pytest.raises(ConfigSaveError) as excinfo:
            config.save()

        assert "Error on line 1" in str(excinfo.value)

        m.assert_called()
        mock_popen.assert_not_called()


def test_config_set_enable_invalid_config():
    """Test that enabling an invalid config raises ConfigSaveError."""
    with (
        patch("os.path.exists", return_value=False),
        patch("keyd.config.get_device_id_from_config", return_value="1234:5678"),
    ):
        config = Config("invalid_enable_test.disabled")

    with (
        patch("keyd.config.Config.check", return_value="Error on line 1"),
        patch("builtins.open", mock_open()),
        patch("os.makedirs")
    ):
        with pytest.raises(ConfigSaveError) as excinfo:
            config.set_config_enable(True)

        assert "Error on line 1" in str(excinfo.value)


def test_config_save_pkexec_missing():
    """Test that saving raises ConfigSaveError when pkexec is missing."""
    with (
        patch("os.path.exists", return_value=False),
        patch("keyd.config.get_device_id_from_config", return_value="1234:5678"),
    ):
        config = Config("pkexec_missing.conf")

    m = mock_open()
    with (
        patch("builtins.open", m),
        patch("os.makedirs"),
        patch("keyd.config.Config.check", return_value=None),
        patch("subprocess.Popen", side_effect=FileNotFoundError),
    ):
        with pytest.raises(ConfigSaveError) as excinfo:
            config.save()

        assert "pkexec" in str(excinfo.value)
        assert "command was not found" in str(excinfo.value)


def test_visual_mapping_change_preserves_comments_and_directives():
    """Patching a visual binding must leave authored source context untouched."""
    sample_content = """# Keyboard used at work
[ids]
1234:5678
# Keep this device note

[main]
# Home-row navigation
include common
a = b
# This stays below the binding

[global]
# Deliberately tuned
macro_timeout = 700
"""

    with (
        patch("os.path.exists", return_value=True),
        patch("builtins.open", mock_open(read_data=sample_content)),
        patch("keyd.config.get_device_id_from_config", return_value="1234:5678"),
    ):
        config = Config("comments.conf")

    config.set_mapping("main", "a", "left")
    config.set_mapping("main", "j", "down")
    rendered = config.source()

    assert "# Keyboard used at work" in rendered
    assert "# Keep this device note" in rendered
    assert "# Home-row navigation" in rendered
    assert "# This stays below the binding" in rendered
    assert "# Deliberately tuned" in rendered
    assert "include common" in rendered
    assert "a = left" in rendered
    assert "j = down" in rendered
    assert "macro_timeout = 700" in rendered


def test_rename_layer_preserves_comments_and_updates_action_references():
    """Renaming a layer patches headers and nested references losslessly."""
    sample_content = """# Keep the document heading
[ids]
1234:5678

[main]
capslock = layer(nav)
space = overload(nav, oneshot(nav))
x = layerm(nav, macro(C-a))
# Example remains literal: layer(nav)

[nav:C]
# Keep this layer note
h = left
"""
    with (
        patch("os.path.exists", return_value=True),
        patch("builtins.open", mock_open(read_data=sample_content)),
        patch("keyd.config.get_device_id_from_config", return_value="1234:5678"),
    ):
        config = Config("rename.conf")

    config.rename_layer("nav:C", "movement:C")
    rendered = config.source()

    assert "[movement:C]" in rendered
    assert "[nav:C]" not in rendered
    assert "layer(movement)" in rendered
    assert "overload(movement, oneshot(movement))" in rendered
    assert "layerm(movement, macro(C-a))" in rendered
    assert "# Keep the document heading" in rendered
    assert "# Keep this layer note" in rendered
    assert "# Example remains literal: layer(nav)" in rendered


def test_rename_layer_rejects_main_and_existing_name():
    """Layer identity remains unambiguous after a visual rename."""
    with (
        patch("os.path.exists", return_value=False),
        patch("keyd.config.get_device_id_from_config", return_value="1234:5678"),
    ):
        config = Config("rename-invalid.conf")
    config.add_layer("nav")

    with pytest.raises(ValueError, match="main"):
        config.rename_layer("main", "base")
    with pytest.raises(ValueError, match="already exists"):
        config.rename_layer("nav", "main")


def test_duplicate_binding_updates_only_effective_occurrence():
    """keyd uses the latest duplicate binding, so that is the one to patch."""
    sample_content = """[ids]
*

[main]
a = first
# Override kept for a reason
a    =    second
"""

    with (
        patch("os.path.exists", return_value=True),
        patch("builtins.open", mock_open(read_data=sample_content)),
        patch("keyd.config.get_device_id_from_config", return_value="*"),
    ):
        config = Config("duplicates.conf")

    config.set_mapping("main", "a", "third")
    rendered = config.source()

    assert "a = first" in rendered
    assert "a    =    third" in rendered
    assert "# Override kept for a reason" in rendered


def test_source_edit_rebuilds_visual_model_and_keeps_aliases_special():
    """Live source edits immediately become the semantic visual model."""
    with (
        patch("os.path.exists", return_value=False),
        patch("keyd.config.get_device_id_from_config", return_value="1234:5678"),
    ):
        config = Config("live.conf")

    config.update_from_text(
        """[ids]
1234:5678

[aliases]
rightmeta = alt

[main]
capslock = layer(nav)

[nav:C]
h = left
"""
    )

    assert config.layers["main"]["capslock"] == "layer(nav)"
    assert config.layers["nav:C"]["h"] == "left"
    assert "aliases" not in config.layers
    assert config.special_sections["aliases"] == ["rightmeta = alt\n", "\n"]
    assert config.layer_order == ["main", "nav:C"]


def test_deleting_layer_retains_its_comments():
    """Intentional layer deletion still honours the no-comment-loss guarantee."""
    sample_content = """[ids]
*

[main]
a = b

[nav]
# Explain why nav existed
h = left
"""

    with (
        patch("os.path.exists", return_value=True),
        patch("builtins.open", mock_open(read_data=sample_content)),
        patch("keyd.config.get_device_id_from_config", return_value="*"),
    ):
        config = Config("delete.conf")

    config.delete_layer("nav")
    rendered = config.source()

    assert "[nav]" not in rendered
    assert "h = left" not in rendered
    assert "# Explain why nav existed" in rendered


def test_check_source_text_reports_keyd_success():
    """Live validation uses keyd's parser rather than only the UI parser."""
    result = MagicMock(
        returncode=0,
        stdout="Parsing /tmp/config.conf\n\nNo errors found.\n",
        stderr="",
    )
    with patch("subprocess.run", return_value=result) as run:
        valid, message = Config.check_source_text("[ids]\n*\n")

    assert valid is True
    assert message == "keyd syntax valid"
    assert run.call_args.args[0][:2] == ["keyd", "check"]


def test_check_source_text_returns_keyd_error():
    """The generated-config panel receives a concise parser error."""
    result = MagicMock(
        returncode=1,
        stdout="Parsing /tmp/config.conf\n",
        stderr="ERROR: line 4: invalid action\n",
    )
    with patch("subprocess.run", return_value=result):
        valid, message = Config.check_source_text("[ids]\n*\n")

    assert valid is False
    assert message == "ERROR: line 4: invalid action"


def test_check_source_text_handles_missing_keyd():
    """Preview remains usable on systems where keyd validation is unavailable."""
    with patch("subprocess.run", side_effect=FileNotFoundError):
        valid, message = Config.check_source_text("[ids]\n*\n")

    assert valid is None
    assert message == "keyd check unavailable"
