"""Module for detecting input devices via keyd monitor."""

import re
import subprocess

from constants import KEYD_MONITOR_TIMEOUT


def get_devices() -> dict[str, str]:
    """Return unique (device_name, vendor:product) pairs from keyd monitor."""
    try:
        subprocess.run(
            ["keyd", "monitor"],
            capture_output=True,
            text=True,
            timeout=KEYD_MONITOR_TIMEOUT,
            check=False,
        )
        output = ""
    except subprocess.TimeoutExpired as exc:
        output = (exc.stdout or b"").decode("utf-8", errors="ignore")
    except FileNotFoundError:
        return {}

    pattern = re.compile(r"device added: (\w+:\w+):\w+ (.+?) \(/dev/input/event.*")

    # vendor:product, device name
    devices: dict[str, str] = {}

    for line in output.splitlines():
        match = pattern.search(line)
        if match:
            device_id, name = match.group(1), match.group(2).strip()
            devices[device_id] = name

    return devices
