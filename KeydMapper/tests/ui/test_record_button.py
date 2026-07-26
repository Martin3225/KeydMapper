"""Tests for the RecordButton UI component."""
# pylint: disable=protected-access, redefined-outer-name

from unittest.mock import MagicMock

from ui.record_button import RecordButton


def test_record_button_initialization() -> None:
    """Test that RecordButton initializes with the correct state."""
    recorder = MagicMock()
    recorder.is_recording = False

    btn = RecordButton(recorder)
    assert btn.text() == "Record"
    assert btn.isCheckable() is True
    assert btn.isChecked() is False
    assert btn.isEnabled() is False


def test_record_button_on_clicked() -> None:
    """Test that clicking the button toggles the recorder and updates UI."""
    recorder = MagicMock()
    recorder.is_recording = False

    def fake_toggle() -> None:
        recorder.is_recording = not recorder.is_recording

    recorder.toggle.side_effect = fake_toggle

    btn = RecordButton(recorder)
    btn.setEnabled(True)

    # start recording
    btn.click()
    recorder.toggle.assert_called_once()
    assert btn.isChecked() is True

    # stop recording
    btn.click()
    assert recorder.toggle.call_count == 2
    assert btn.isChecked() is False


def test_record_button_reset() -> None:
    """Test that reset() stops the recorder and updates UI."""
    recorder = MagicMock()
    recorder.is_recording = True

    def fake_stop() -> None:
        recorder.is_recording = False

    recorder.stop.side_effect = fake_stop

    btn = RecordButton(recorder)
    btn.reset()

    recorder.stop.assert_called_once()
    assert btn.isChecked() is False
