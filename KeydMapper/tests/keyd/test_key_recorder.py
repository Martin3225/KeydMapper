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
    """An unprivileged app asks Polkit to run only keyd monitor as root."""
    # Arrange
    recorder = KeyRecorder()
    with (
        patch("keyd.key_recorder.QProcess") as mock_qprocess,
        patch(
            "keyd.key_recorder.shutil.which",
            side_effect=lambda command: f"/usr/bin/{command}",
        ),
        patch("keyd.key_recorder.os.geteuid", return_value=1000),
    ):
        mock_process_instance = MagicMock()
        mock_qprocess.return_value = mock_process_instance

        # Act
        recorder.start()

        # Assert
        assert recorder.is_recording is True
        mock_qprocess.assert_called_once()
        mock_process_instance.start.assert_called_once_with(
            "/usr/bin/pkexec",
            ["/usr/bin/keyd", "monitor"],
        )
        mock_process_instance.readyReadStandardOutput.connect.assert_called_once()
        mock_process_instance.readyReadStandardError.connect.assert_called_once()
        mock_process_instance.finished.connect.assert_called_once()

        recorder.stop()

        assert recorder.is_recording is False
        mock_process_instance.kill.assert_called_once()
        mock_process_instance.waitForFinished.assert_called_once_with(200)


def test_key_recorder_root_process_does_not_use_pkexec():
    """A process that already has access starts keyd directly."""
    recorder = KeyRecorder()
    with (
        patch("keyd.key_recorder.QProcess") as mock_qprocess,
        patch("keyd.key_recorder.shutil.which", return_value="/usr/bin/keyd"),
        patch("keyd.key_recorder.os.geteuid", return_value=0),
    ):
        recorder.start()

    mock_qprocess.return_value.start.assert_called_once_with(
        "/usr/bin/keyd",
        ["monitor"],
    )


def test_key_recorder_reports_missing_polkit_without_starting():
    """A missing authentication helper produces a useful UI error."""
    recorder = KeyRecorder()
    errors = MagicMock()
    recorder.error_occurred.connect(errors)

    with (
        patch(
            "keyd.key_recorder.shutil.which",
            side_effect=lambda command: (
                "/usr/bin/keyd" if command == "keyd" else None
            ),
        ),
        patch("keyd.key_recorder.os.geteuid", return_value=1000),
        patch("keyd.key_recorder.QProcess") as mock_qprocess,
    ):
        recorder.start()

    assert recorder.is_recording is False
    mock_qprocess.assert_not_called()
    assert "pkexec" in errors.call_args.args[0]


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


def test_key_recorder_matches_output_split_between_process_chunks():
    """Partial QProcess reads do not lose the physical key event."""
    recorder = KeyRecorder("1111:2222")
    first = MagicMock()
    first.toStdString.return_value = "1111:2222:3333\tspa"
    second = MagicMock()
    second.toStdString.return_value = "ce\tdown\n"
    mock_process = MagicMock()
    mock_process.readAllStandardOutput.side_effect = [first, second]
    recorder._process = mock_process
    recorded = MagicMock()
    recorder.key_recorded.connect(recorded)

    with patch.object(recorder, "stop"):
        recorder._on_output()
        recorded.assert_not_called()
        recorder._on_output()

    recorded.assert_called_once_with("space")


def test_key_recorder_explains_cancelled_polkit_authentication():
    """Cancelling the system password dialog is not shown as an unknown error."""
    recorder = KeyRecorder()
    recorder._process = MagicMock()
    recorder._uses_polkit = True
    stderr = MagicMock()
    stderr.toStdString.return_value = ""
    recorder._process.readAllStandardError.return_value = stderr
    errors = MagicMock()
    recorder.error_occurred.connect(errors)

    recorder._on_finished(126, MagicMock())

    assert recorder.is_recording is False
    assert "denied" in errors.call_args.args[0]
