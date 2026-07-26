"""Global constants for the KeydMapper application."""

import os
from importlib.resources import files
from typing import Final

KEYD_CONFIG_PATH: Final = "/etc/keyd"
LAYOUTS_PATH: Final = os.path.expanduser("~/.config/keydmapper/layouts")
CONFIGS_PATH: Final = os.path.expanduser("~/.config/keydmapper/configs")
RES_PATH: Final = os.fspath(files("keyd").joinpath("resources"))
KEYD_MONITOR_TIMEOUT: Final = 0.1
