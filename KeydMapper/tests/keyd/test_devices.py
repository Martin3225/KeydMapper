"""Tests for the device discovery functionality in KeydMapper."""

import subprocess
from unittest.mock import patch

from keyd.devices import get_devices


def test_get_devices_success():
    """Test get_devices successfully parses output from keyd monitor."""

    mock_output = b"""device added: 0fac:1ade:d2b36ae6 keyd virtual pointer (/dev/input/event28)
    device added: 0fac:0ade:bea394c0 keyd virtual keyboard (/dev/input/event27)
    device added: 0000:0000:8358108e Eee PC WMI hotkeys (/dev/input/event15)
    device added: 1532:0228:89318789 Razer Razer BlackWidow Elite (/dev/input/event13)
    device added: 1532:0228:e98f6c9f Razer Razer BlackWidow Elite Keyboard (/dev/input/event11)
    device added: 1532:0228:6855fe24 Razer Razer BlackWidow Elite (/dev/input/event10)
    device added: 1532:0099:fbd4d445 Razer Razer Basilisk V3 (/dev/input/event9)
    device added: 1532:0099:481eb9a0 Razer Razer Basilisk V3 Keyboard (/dev/input/event7)
    device added: 1532:0099:0b8462ca Razer Razer Basilisk V3 (/dev/input/event6)
    device added: 1532:0c04:30cd2f9e RAZER Razer Firefly V2 Keyboard (/dev/input/event4)
    device added: 1532:0c04:2ac57f68 RAZER Razer Firefly V2 (/dev/input/event3)
    device added: 0000:0001:48a093aa Power Button (/dev/input/event2)
    device added: 0000:0001:48a093aa Power Button (/dev/input/event1)
    device added: 0000:0003:86db4035 Sleep Button (/dev/input/event0)
    Razer Razer BlackWidow Elite    1532:0228:6855fe24      enter up
    Razer Razer BlackWidow Elite    1532:0228:6855fe24      f down
    Razer Razer BlackWidow Elite    1532:0228:6855fe24      f up
    Razer Razer BlackWidow Elite    1532:0228:6855fe24      a down
    Razer Razer BlackWidow Elite    1532:0228:6855fe24      d down
    Razer Razer BlackWidow Elite    1532:0228:6855fe24      s down
    Razer Razer BlackWidow Elite    1532:0228:6855fe24      f down
    Razer Razer BlackWidow Elite    1532:0228:6855fe24      s up
    Razer Razer BlackWidow Elite    1532:0228:6855fe24      a up
    Razer Razer BlackWidow Elite    1532:0228:6855fe24      d up
    Razer Razer BlackWidow Elite    1532:0228:6855fe24      f up
    Razer Razer BlackWidow Elite    1532:0228:6855fe24      leftcontrol down
    Razer Razer BlackWidow Elite    1532:0228:6855fe24      c down
"""
    with patch("subprocess.run") as mock_run:
        mock_exc = subprocess.TimeoutExpired(
            cmd=["keyd", "monitor"], timeout=1, output=mock_output
        )
        mock_run.side_effect = mock_exc

        devices = get_devices()

        assert devices == {
            "0fac:1ade": "keyd virtual pointer",
            "0fac:0ade": "keyd virtual keyboard",
            "0000:0000": "Eee PC WMI hotkeys",
            "1532:0228": "Razer Razer BlackWidow Elite",
            "1532:0099": "Razer Razer Basilisk V3",
            "1532:0c04": "RAZER Razer Firefly V2",
            "0000:0001": "Power Button",
            "0000:0003": "Sleep Button",
        }
        mock_run.assert_called_once()


def test_get_devices_timeout():
    """Test get_devices handles timeout and captures initial device list."""

    with patch("subprocess.run") as mock_run:
        mock_exc = subprocess.TimeoutExpired(
            cmd=["keyd", "monitor"],
            timeout=1,
            output=b"device added: 0000:0001:48a093aa Power Button (/dev/input/event2)\n",
        )
        mock_run.side_effect = mock_exc

        devices = get_devices()

        assert devices == {"0000:0001": "Power Button"}


def test_get_devices_file_not_found():
    """Test get_devices returns empty dict if keyd monitor is not found."""

    with patch("subprocess.run") as mock_run:
        mock_run.side_effect = FileNotFoundError()

        devices = get_devices()
        assert not devices
