"""Module for lossless handling of keyd configuration files."""

from __future__ import annotations

import os
import re
import subprocess
import tempfile
from copy import deepcopy

from constants import CONFIGS_PATH, KEYD_CONFIG_PATH
from keyd.layout import get_device_id_from_config
from keyd.system_helper import SystemHelperError, apply_config


_SECTION_RE = re.compile(r"^\s*\[([^\]]+)\]\s*$")
_BINDING_RE = re.compile(
    r"^(?P<indent>\s*)(?P<key>[^#=\r\n][^=\r\n]*?)"
    r"(?P<separator>\s*=\s*)(?P<value>[^\r\n]*)(?P<newline>\r?\n)?$"
)
_SPECIAL_SECTIONS = frozenset({"ids", "global", "aliases"})
_LAYER_ACTIONS = (
    "layer",
    "oneshot",
    "swap",
    "toggle",
    "setlayout",
    "layerm",
    "oneshotm",
    "oneshotk",
    "swapm",
    "togglem",
    "overload",
    "overloadt",
    "overloadt2",
    "lettermod",
)


class ConfigSaveError(Exception):
    """Exception raised when saving the configuration fails."""


class Config:
    """Represents a keyd config while retaining its original source text."""

    def __init__(self, name: str, device_id: str | None = None) -> None:
        self.name = name
        self.device_id = (
            device_id if device_id else get_device_id_from_config(self.name)
        )
        self.keyd_path = os.path.join(KEYD_CONFIG_PATH, self.name)

        self.layers: dict[str, dict[str, str]] = {}
        self.special_sections: dict[str, list[str]] = {}
        self.layer_order: list[str] = []
        self.source_text = ""

        self.load()

    def load(self) -> None:
        """Load and parse the keyd configuration file."""
        if not os.path.exists(self.keyd_path):
            self._reset_model()
            self._ensure_main_layer()
            return

        with open(self.keyd_path, "r", encoding="utf-8") as file:
            self.update_from_text(file.read())

    def update_from_text(self, text: str) -> None:
        """Replace the live source and rebuild the visual-editor model from it."""
        layers, special_sections, layer_order = self._parse_text(text)
        self.source_text = text
        self.layers = layers
        self.special_sections = special_sections
        self.layer_order = layer_order
        self._ensure_main_layer()

    @staticmethod
    def _parse_text(
        text: str,
    ) -> tuple[
        dict[str, dict[str, str]],
        dict[str, list[str]],
        list[str],
    ]:
        """Parse source without normalising or modifying it."""
        layers: dict[str, dict[str, str]] = {}
        special_sections: dict[str, list[str]] = {}
        layer_order: list[str] = []
        current_section: str | None = None

        for line in text.splitlines(keepends=True):
            stripped = line.strip()
            section_match = _SECTION_RE.match(stripped)
            if section_match:
                current_section = section_match.group(1)
                if current_section in _SPECIAL_SECTIONS:
                    special_sections.setdefault(current_section, [])
                else:
                    if current_section not in layers:
                        layers[current_section] = {}
                        layer_order.append(current_section)
                continue

            if current_section in _SPECIAL_SECTIONS:
                special_sections[current_section].append(line)
            elif current_section is not None:
                binding_match = _BINDING_RE.match(line)
                if binding_match:
                    key = binding_match.group("key").strip()
                    layers[current_section][key] = binding_match.group("value").strip()

        return layers, special_sections, layer_order

    def _reset_model(self) -> None:
        self.layers = {}
        self.special_sections = {}
        self.layer_order = []

    def _ensure_main_layer(self) -> None:
        """Ensure that the visual editor always has a main layer."""
        if "main" not in self.layers:
            self.layers["main"] = {}
            if "main" not in self.layer_order:
                self.layer_order.insert(0, "main")

    def source(self) -> str:
        """Return source reflecting the current visual model."""
        self.source_text = self._render_model_into_source()
        return self.source_text

    def set_mapping(self, layer: str, key: str, value: str) -> None:
        """Update one binding and patch only that binding in the source."""
        self.layers.setdefault(layer, {})
        if layer not in self.layer_order:
            self.layer_order.append(layer)

        if value:
            self.layers[layer][key] = value
        else:
            self.layers[layer].pop(key, None)

        self.source_text = self._set_mapping_in_text(
            self._initial_source(), layer, key, value or None
        )

    def add_layer(self, name: str) -> None:
        """Add a layer to the model and source."""
        if name in self.layers:
            return
        self.layers[name] = {}
        self.layer_order.append(name)
        self.source_text = self._append_layer(self._initial_source(), name, {})

    def rename_layer(self, old_name: str, new_name: str) -> None:
        """Rename a layer and its action references without losing source context."""
        if old_name == new_name or old_name not in self.layers:
            return
        if old_name == "main":
            raise ValueError("The main layer cannot be renamed")
        if not new_name:
            raise ValueError("Layer name cannot be empty")
        if new_name in self.layers:
            raise ValueError(f"Layer '{new_name}' already exists")

        source = self._initial_source()
        lines = source.splitlines(keepends=True)
        for index, line in enumerate(lines):
            match = _SECTION_RE.match(line.strip())
            if match and match.group(1) == old_name:
                newline = "\n" if line.endswith("\n") else ""
                if line.endswith("\r\n"):
                    newline = "\r\n"
                indent = line[: len(line) - len(line.lstrip())]
                lines[index] = f"{indent}[{new_name}]{newline}"
        source = "".join(lines)

        old_reference = old_name.split(":", 1)[0]
        new_reference = new_name.split(":", 1)[0]
        action_names = "|".join(_LAYER_ACTIONS)
        reference_pattern = re.compile(
            rf"(?P<prefix>\b(?:{action_names})\(\s*)"
            rf"{re.escape(old_reference)}(?=\s*[,)])"
        )
        updated_lines: list[str] = []
        for line in source.splitlines(keepends=True):
            binding = _BINDING_RE.match(line)
            if binding is None:
                updated_lines.append(line)
                continue
            value = reference_pattern.sub(
                lambda match: f"{match.group('prefix')}{new_reference}",
                binding.group("value"),
            )
            updated_lines.append(
                f"{binding.group('indent')}{binding.group('key')}"
                f"{binding.group('separator')}{value}"
                f"{binding.group('newline') or ''}"
            )
        source = "".join(updated_lines)
        self.update_from_text(source)

    def delete_layer(self, name: str) -> None:
        """Delete a layer while retaining every comment in the file."""
        if name == "main":
            return
        self.layers.pop(name, None)
        if name in self.layer_order:
            self.layer_order.remove(name)
        self.source_text = self._delete_layer_from_text(self._initial_source(), name)

    def _initial_source(self) -> str:
        if self.source_text:
            return self.source_text
        device_line = f"{self.device_id}\n" if self.device_id else ""
        return f"[ids]\n{device_line}\n"

    def _render_model_into_source(self) -> str:
        """Patch model differences into source instead of regenerating the file."""
        text = self._initial_source()
        source_layers, _, source_order = self._parse_text(text)
        desired_layers = deepcopy(self.layers)

        for layer in source_order:
            if layer not in desired_layers:
                text = self._delete_layer_from_text(text, layer)

        for layer in self.layer_order:
            if layer not in source_layers:
                text = self._append_layer(text, layer, desired_layers.get(layer, {}))
                continue

            source_bindings = source_layers[layer]
            desired_bindings = desired_layers.get(layer, {})
            for key in source_bindings.keys() - desired_bindings.keys():
                text = self._set_mapping_in_text(text, layer, key, None)
            for key, value in desired_bindings.items():
                if source_bindings.get(key) != value:
                    text = self._set_mapping_in_text(text, layer, key, value)

        return text

    @staticmethod
    def _section_spans(lines: list[str], name: str) -> list[tuple[int, int]]:
        headers: list[tuple[int, str]] = []
        for index, line in enumerate(lines):
            match = _SECTION_RE.match(line.strip())
            if match:
                headers.append((index, match.group(1)))

        spans: list[tuple[int, int]] = []
        for header_index, (start, section_name) in enumerate(headers):
            end = (
                headers[header_index + 1][0]
                if header_index + 1 < len(headers)
                else len(lines)
            )
            if section_name == name:
                spans.append((start, end))
        return spans

    @classmethod
    def _set_mapping_in_text(
        cls, text: str, layer: str, key: str, value: str | None
    ) -> str:
        lines = text.splitlines(keepends=True)
        spans = cls._section_spans(lines, layer)
        matches: list[int] = []

        for start, end in spans:
            for index in range(start + 1, end):
                binding_match = _BINDING_RE.match(lines[index])
                if binding_match and binding_match.group("key").strip() == key:
                    matches.append(index)

        if value is None:
            for index in reversed(matches):
                del lines[index]
            return "".join(lines)

        if matches:
            index = matches[-1]
            binding_match = _BINDING_RE.match(lines[index])
            assert binding_match is not None
            newline = binding_match.group("newline") or ""
            lines[index] = (
                f"{binding_match.group('indent')}{binding_match.group('key')}"
                f"{binding_match.group('separator')}{value}{newline}"
            )
            return "".join(lines)

        if not spans:
            return cls._append_layer(text, layer, {key: value})

        _, insertion_index = spans[-1]
        if insertion_index and not lines[insertion_index - 1].endswith(("\n", "\r")):
            lines[insertion_index - 1] += "\n"
        lines.insert(insertion_index, f"{key} = {value}\n")
        return "".join(lines)

    @staticmethod
    def _append_layer(
        text: str, layer: str, bindings: dict[str, str]
    ) -> str:
        if text and not text.endswith("\n"):
            text += "\n"
        if text and not text.endswith("\n\n"):
            text += "\n"
        text += f"[{layer}]\n"
        for key, value in bindings.items():
            text += f"{key} = {value}\n"
        return text

    @classmethod
    def _delete_layer_from_text(cls, text: str, layer: str) -> str:
        """Remove layer semantics but deliberately retain its comment lines."""
        lines = text.splitlines(keepends=True)
        spans = cls._section_spans(lines, layer)
        remove_indices: set[int] = set()

        for start, end in spans:
            remove_indices.add(start)
            for index in range(start + 1, end):
                stripped = lines[index].lstrip()
                if stripped.startswith("#") or not stripped.strip():
                    continue
                remove_indices.add(index)

        return "".join(
            line for index, line in enumerate(lines) if index not in remove_indices
        )

    @staticmethod
    def diagnostics(text: str) -> list[str]:
        """Return lightweight diagnostics suitable for live editing."""
        significant_lines = [
            line.strip()
            for line in text.splitlines()
            if line.strip() and not line.lstrip().startswith("#")
        ]
        if not significant_lines:
            return ["Configuration is empty"]
        if significant_lines[0] != "[ids]":
            return ["The first section must be [ids]"]

        current_section: str | None = None
        for line_number, line in enumerate(text.splitlines(), start=1):
            stripped = line.strip()
            if not stripped or stripped.startswith("#"):
                continue
            section_match = _SECTION_RE.match(stripped)
            if section_match:
                current_section = section_match.group(1)
                continue
            if stripped.startswith("[") and not section_match:
                return [f"Malformed section header on line {line_number}"]
            if current_section is None:
                return [f"Content outside a section on line {line_number}"]
        return []

    @staticmethod
    def check_source_text(text: str) -> tuple[bool | None, str]:
        """Validate unsaved source with ``keyd check`` using a temporary config."""
        try:
            with tempfile.NamedTemporaryFile(
                mode="w",
                encoding="utf-8",
                suffix=".conf",
            ) as temporary_file:
                temporary_file.write(text)
                temporary_file.flush()
                result = subprocess.run(
                    ["keyd", "check", temporary_file.name],
                    capture_output=True,
                    text=True,
                    timeout=5,
                    check=False,
                )
        except FileNotFoundError:
            return None, "keyd check unavailable"
        except subprocess.TimeoutExpired:
            return False, "keyd syntax check timed out"

        output = ((result.stdout or "") + (result.stderr or "")).strip()
        if result.returncode == 0 and "No errors found." in output:
            return True, "keyd syntax valid"

        error_lines = [
            line.strip()
            for line in output.splitlines()
            if line.strip() and not line.startswith("Parsing ")
        ]
        return False, error_lines[-1] if error_lines else "Invalid keyd syntax"

    def save(self) -> None:
        """Save locally, validate, then copy the config to the system path."""
        os.makedirs(CONFIGS_PATH, exist_ok=True)
        local_path = os.path.join(CONFIGS_PATH, self.name)

        self._write_config_to_local(local_path)
        self._copy_to_system(local_path)

    def check(self) -> str | None:
        """Run ``keyd check`` and return its output when validation fails."""
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
        """Write the lossless live source and validate it."""
        try:
            with open(local_path, "w", encoding="utf-8") as file:
                file.write(self.source())
        except Exception as exc:
            raise ConfigSaveError(
                f"Error writing locally to {local_path}: {exc}"
            ) from exc

        warning = self.check()
        if warning:
            raise ConfigSaveError(f"Cannot save invalid configuration:\n\n{warning}")

    def _copy_to_system(self, local_path: str, old_name: str | None = None) -> None:
        """Apply through the installed root-owned helper without invoking a shell."""
        try:
            with open(local_path, "r", encoding="utf-8") as local_config:
                apply_config(
                    local_config.read(),
                    self.name,
                    old_name,
                )
        except (OSError, SystemHelperError) as exc:
            raise ConfigSaveError(
                f"Failed to apply config to system:\n{exc}"
            ) from exc

        if old_name:
            local_old = os.path.join(CONFIGS_PATH, old_name)
            if local_old != local_path and os.path.exists(local_old):
                os.remove(local_old)

    def set_config_enable(self, enable: bool) -> None:
        """Enable or disable the configuration by saving it under a new suffix."""
        old_name = self.name
        new_name = ".".join(self.name.split(".")[:-1]) + (
            ".conf" if enable else ".disabled"
        )
        if old_name == new_name:
            return

        self._update_name(new_name)
        local_new = os.path.join(CONFIGS_PATH, new_name)
        previous_local: bytes | None = None
        if os.path.isfile(local_new):
            with open(local_new, "rb") as previous_file:
                previous_local = previous_file.read()

        try:
            self._write_config_to_local(local_new)
            self._copy_to_system(local_new, old_name)
        except Exception:
            if previous_local is None:
                try:
                    os.remove(local_new)
                except FileNotFoundError:
                    pass
            else:
                with open(local_new, "wb") as previous_file:
                    previous_file.write(previous_local)
            self._update_name(old_name)
            raise

    def _update_name(self, name: str) -> None:
        """Update internal references to the configuration name and path."""
        self.name = name
        self.keyd_path = os.path.join(KEYD_CONFIG_PATH, name)
