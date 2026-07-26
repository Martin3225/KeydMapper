"""Module for managing keyboard layouts."""

import json
import os
from dataclasses import asdict, dataclass, field

from constants import KEYD_CONFIG_PATH, LAYOUTS_PATH, RES_PATH


@dataclass
class LayoutButton:
    """Represents a single button in a layout."""

    name: str
    default: str
    x: float
    y: float
    width: float
    height: float


@dataclass
class Layout:
    """Represents a complete layout for a specific device."""

    device_id: str
    buttons: list[LayoutButton] = field(default_factory=list)


def _layout_path(device_id: str) -> str:
    """Returns the filesystem path for a layout file given a device ID."""
    filename = device_id.replace(":", "_") + ".layout"
    return os.path.join(LAYOUTS_PATH, filename)


def does_layout_exist(device_id: str) -> bool:
    """Checks if a layout file exists for the given device ID."""
    return os.path.isfile(_layout_path(device_id))


def load_layout(device_id: str) -> Layout:
    """Loads a layout for the given device ID, or returns an empty one if not found."""
    path = _layout_path(device_id)
    if not os.path.isfile(path):
        fallback_path = os.path.join(RES_PATH, "keyboard.layout")
        if os.path.isfile(fallback_path):
            return _load_from_path(fallback_path, device_id)
        return Layout(device_id=device_id)
    return _load_from_path(path, device_id)


def load_layout_from_path(path: str) -> Layout:
    """Loads a layout from a specific file path."""
    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)
    device_id = data.get("device_id", "")
    return _load_from_path(path, device_id)


def _load_from_path(path: str, device_id: str) -> Layout:
    """Helper to load layout data from a JSON file."""
    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)
    buttons = [LayoutButton(**b) for b in data.get("buttons", [])]
    return Layout(device_id=device_id, buttons=buttons)


def save_layout(layout: Layout) -> None:
    """Saves the given layout to its designated filesystem path."""
    os.makedirs(LAYOUTS_PATH, exist_ok=True)
    data = {
        "device_id": layout.device_id,
        "buttons": [asdict(b) for b in layout.buttons],
    }
    with open(_layout_path(layout.device_id), "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)


def get_device_id_from_config(config_name: str) -> str:
    """Returns the device ID from the start of a keyd config file."""
    path = os.path.join(KEYD_CONFIG_PATH, config_name)
    try:
        with open(path, "r", encoding="utf-8") as f:
            lines = f.readlines()
            for i, line in enumerate(lines):
                if line.strip() == "[ids]" and i + 1 < len(lines):
                    return lines[i + 1].strip()
    except OSError:
        pass
    return ""
