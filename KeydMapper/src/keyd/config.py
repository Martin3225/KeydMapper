"""Module for handling keyd configuration files."""

import os
import subprocess

from constants import CONFIGS_PATH, KEYD_CONFIG_PATH
from keyd.layout import get_device_id_from_config


class ConfigSaveError(Exception):
    """Exception raised when saving the configuration fails."""


class Config:
    """Represents a keyd configuration file, parsing its layers and properties."""

    def __init__(self, name: str, device_id: str | None = None) -> None:
        self.name = name
        self.device_id = (
            device_id if device_id else get_device_id_from_config(self.name)
        )
        self.keyd_path = os.path.join(KEYD_CONFIG_PATH, self.name)

        self.layers: dict[str, dict[str, str]] = {}
        self.special_sections: dict[str, list[str]] = {}
        self.layer_order: list[str] = []

        self.load()

    def load(self) -> None:
        """Loads and parses the keyd configuration file."""
        if not os.path.exists(self.keyd_path):
            self._ensure_main_layer()
            return

        current_layer = None
        with open(self.keyd_path, "r", encoding="utf-8") as file:
            for line in file:
                current_layer = self._parse_line(line, current_layer)

        self._ensure_main_layer()

    def _parse_line(self, line: str, current_layer: str | None) -> str | None:
        """Parses a single line from the config file and updates state."""
        stripped = line.strip()

        if stripped.startswith("[") and stripped.endswith("]"):
            return self._handle_section_header(stripped)

        if current_layer in ["ids", "global"]:
            self.special_sections[current_layer].append(line)
        elif current_layer is not None:
            self._handle_key_value(current_layer, stripped)

        return current_layer

    def _handle_section_header(self, stripped_line: str) -> str:
        """Handles a section header (e.g., [ids], [main]) and returns the section name."""
        section_name = stripped_line[1:-1]

        if section_name in ["ids", "global"]:
            if section_name not in self.special_sections:
                self.special_sections[section_name] = []
        else:
            if section_name not in self.layers:
                self.layers[section_name] = {}
                self.layer_order.append(section_name)

        return section_name

    def _handle_key_value(self, current_layer: str, stripped_line: str) -> None:
        """Handles a key-value assignment in a standard layer."""
        if "=" in stripped_line and not stripped_line.startswith("#"):
            k, v = stripped_line.split("=", 1)
            self.layers[current_layer][k.strip()] = v.strip()

    def _ensure_main_layer(self) -> None:
        """Ensures that the 'main' layer exists in the configuration."""
        if "main" not in self.layers:
            self.layers["main"] = {}
            if "main" not in self.layer_order:
                self.layer_order.insert(0, "main")

    def save(self) -> None:
        """Saves the configuration locally, validates it, and copies it to the system path."""
        os.makedirs(CONFIGS_PATH, exist_ok=True)
        local_path = os.path.join(CONFIGS_PATH, self.name)

        self._write_config_to_local(local_path)
        self._copy_to_system(local_path)

    def check(self) -> str | None:
        """Runs keyd check on the local config file and returns its output if there are errors."""
        local_path = os.path.join(CONFIGS_PATH, self.name)
        if not os.path.exists(local_path):
            return None
        try:
            result = subprocess.run(
                ["keyd", "check", local_path],
                capture_output=True,
                text=True,
                check=False,
            )
            output = (result.stdout or "") + (result.stderr or "")
            if "No errors found." not in output:
                return output.strip()
        except FileNotFoundError:
            pass
        return None

    def _write_config_to_local(self, local_path: str) -> None:
        """Writes the current configuration state to a local file and validates it."""
        try:
            with open(local_path, "w", encoding="utf-8") as file:
                self._write_ids_section(file)
                self._write_global_section(file)
                self._write_layers(file)
        except Exception as e:
            raise ConfigSaveError(f"Error writing locally to {local_path}: {e}") from e

        warning = self.check()
        if warning:
            raise ConfigSaveError(f"Cannot save invalid configuration:\n\n{warning}")

    def _write_ids_section(self, file_obj) -> None:
        """Writes the [ids] section to the configuration file."""
        if "ids" in self.special_sections:
            file_obj.write("[ids]\n")
            for line in self.special_sections["ids"]:
                file_obj.write(line)
        else:
            file_obj.write("[ids]\n")
            if self.device_id:
                file_obj.write(f"{self.device_id}\n")
        file_obj.write("\n")

    def _write_global_section(self, file_obj) -> None:
        """Writes the [global] section to the configuration file."""
        if "global" in self.special_sections:
            file_obj.write("[global]\n")
            for line in self.special_sections["global"]:
                file_obj.write(line)
            file_obj.write("\n")

    def _write_layers(self, file_obj) -> None:
        """Writes the custom layers to the configuration file."""
        for layer in self.layer_order:
            file_obj.write(f"[{layer}]\n")
            for k, v in self.layers[layer].items():
                file_obj.write(f"{k} = {v}\n")
            file_obj.write("\n")

    def _copy_to_system(self, local_path: str, old_name: str | None = None) -> None:
        """Copies the local configuration to the system path, optionally cleaning up old files, and restarts keyd."""
        cmd = ["pkexec", "sh", "-c", f"cp '{local_path}' '{self.keyd_path}'"]

        if old_name:
            local_old = os.path.join(CONFIGS_PATH, old_name)
            system_old = os.path.join(KEYD_CONFIG_PATH, old_name)

            if os.path.exists(local_old):
                os.remove(local_old)

            if os.path.exists(system_old):
                cmd[3] += f" && rm -f '{system_old}'"

        cmd[3] += " && systemctl restart keyd"

        try:
            with subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
            ) as process:
                _, stderr = process.communicate()

                if process.returncode != 0:
                    raise ConfigSaveError(
                        f"Failed to apply config to system:\n{stderr}"
                    )
        except FileNotFoundError as exc:
            raise ConfigSaveError(
                "The 'pkexec' command was not found. Cannot apply configuration on this system."
            ) from exc

    def set_config_enable(self, enable: bool) -> None:
        """Enables or disables the configuration by saving current state and renaming."""
        old_name = self.name
        new_name = ".".join(self.name.split(".")[:-1]) + (
            ".conf" if enable else ".disabled"
        )
        if old_name == new_name:
            return

        self._update_name(new_name)

        try:
            local_new = os.path.join(CONFIGS_PATH, new_name)
            self._write_config_to_local(local_new)
            self._copy_to_system(local_new, old_name)
        except Exception:
            self._update_name(old_name)
            raise

    def _update_name(self, name: str) -> None:
        """Updates internal references to the configuration name and path."""
        self.name = name
        self.keyd_path = os.path.join(KEYD_CONFIG_PATH, name)
