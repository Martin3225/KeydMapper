"""Global constants for the KeydMapper application."""

import os
from typing import Final

KEYD_CONFIG_PATH: Final = "/etc/keyd"
LAYOUTS_PATH: Final = os.path.expanduser("~/.config/keydmapper/layouts")
CONFIGS_PATH: Final = os.path.expanduser("~/.config/keydmapper/configs")
RES_PATH: Final = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "res"
)
KEYD_MONITOR_TIMEOUT: Final = 0.1
