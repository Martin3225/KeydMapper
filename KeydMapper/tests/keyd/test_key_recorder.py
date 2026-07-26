"""Tests for KeyRecorder class that listens to keyboard inputs."""
# pylint: disable=protected-access

from unittest.mock import MagicMock, patch

from keyd.key_recorder import KeyRecorder


def test_key_recorder_initialization():
    """Test that KeyRecorder initializes with correct default states."""
    recorder = KeyRecorder("1234:5678")
    assert recorder.is_recording is False
    assert recorder._device_id == "1234:5678"


def test_key_recorder_start_stop():
    """Test that KeyRecorder properly starts and stops the keyd monitor process."""
    # Arrange
    recorder = KeyRecorder()
    with patch("keyd.key_recorder.QProcess") as mock_qprocess:
        mock_process_instance = MagicMock()
        mock_qprocess.return_value = mock_process_instance

        # Act
        recorder.start()

        # Assert
        assert recorder.is_recording is True
        mock_qprocess.assert_called_once()
        mock_process_instance.start.assert_called_once_with("keyd", ["monitor"])
        mock_process_instance.readyReadStandardOutput.connect.assert_called_once()

        recorder.stop()

        assert recorder.is_recording is False
        mock_process_instance.kill.assert_called_once()
        mock_process_instance.waitForFinished.assert_called_once_with(200)


def test_key_recorder_toggle():
    """Test that toggle() switches the recording state."""
    recorder = KeyRecorder()
    with (
        patch.object(recorder, "start") as mock_start,
        patch.object(recorder, "stop") as mock_stop,
    ):
        recorder._process = None  # not recording
        recorder.toggle()
        mock_start.assert_called_once()
        mock_stop.assert_not_called()

        mock_start.reset_mock()
        recorder._process = MagicMock()  # recording
        recorder.toggle()
        mock_stop.assert_called_once()
        mock_start.assert_not_called()


def test_key_recorder_on_output():
    """Test that _on_output() parses matching device output and stops recording."""
    recorder = KeyRecorder("1111:2222")

    # Emulate QByteArray return from readAllStandardOutput()
    mock_byte_array = MagicMock()
    mock_byte_array.toStdString.return_value = "1111:2222:3333\tenter\tdown\n"
    mock_process = MagicMock()
    mock_process.readAllStandardOutput.return_value = mock_byte_array

    recorder._process = mock_process

    mock_slot = MagicMock()
    recorder.key_recorded.connect(mock_slot)

    with patch.object(recorder, "stop") as mock_stop:
        recorder._on_output()

        mock_slot.assert_called_once_with("enter")
        mock_stop.assert_called_once()


def test_key_recorder_on_output_wrong_device():
    """Test that _on_output() ignores output from unmonitored devices."""
    recorder = KeyRecorder("1111:2222")

    mock_process = MagicMock()
    mock_byte_array = MagicMock()
    mock_byte_array.toStdString.return_value = "3333:4444:5555\tspace\tdown\n"
    mock_process.readAllStandardOutput.return_value = mock_byte_array
    recorder._process = mock_process

    mock_slot = MagicMock()
    recorder.key_recorded.connect(mock_slot)

    with patch.object(recorder, "stop") as mock_stop:
        recorder._on_output()

        mock_slot.assert_not_called()
        mock_stop.assert_not_called()
