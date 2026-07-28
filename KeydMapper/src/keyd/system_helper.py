"""Client for one installed, narrowly privileged KeydMapper session helper."""

from __future__ import annotations

import atexit
import json
import os
import re
import stat
import subprocess
import threading


HELPER_PATH = "/usr/lib/keyd-mapper/keyd-mapper-helper"
HELPER_PYTHON = "/usr/bin/python3"
POLICY_PATH = (
    "/usr/share/polkit-1/actions/"
    "io.github.keydmapper.apply-config.policy"
)
_CONFIG_NAME = re.compile(
    r"[A-Za-z0-9][A-Za-z0-9_.-]{0,126}\.(?:conf|disabled)"
)
_DEVICE_ID = re.compile(
    r"(?:(?:k|m):)?[0-9A-Fa-f]{4}:[0-9A-Fa-f]{4}"
    r"(?::[0-9A-Fa-f]{8})?"
)


class SystemHelperError(Exception):
    """Raised when a validated config cannot be applied system-wide."""


def _is_root_owned_regular_file(path: str) -> bool:
    """Return whether a privileged component has safe ownership and mode."""
    try:
        metadata = os.stat(path, follow_symlinks=False)
    except OSError:
        return False
    return (
        stat.S_ISREG(metadata.st_mode)
        and metadata.st_uid == 0
        and not metadata.st_mode & (stat.S_IWGRP | stat.S_IWOTH)
    )


def helper_installation_issue() -> str | None:
    """Explain why the privileged helper is unsafe or unavailable."""
    if not _is_root_owned_regular_file(HELPER_PATH):
        return (
            "The privileged KeydMapper helper is not installed securely. "
            "Run 'sudo ./scripts/install-system-helper.sh' from the project "
            "directory, then try again."
        )
    if not _is_root_owned_regular_file(POLICY_PATH):
        return (
            "The KeydMapper Polkit policy is missing or has unsafe permissions. "
            "Reinstall it with 'sudo ./scripts/install-system-helper.sh'."
        )
    if not os.path.isfile(HELPER_PYTHON):
        return f"The required interpreter '{HELPER_PYTHON}' was not found."
    return None


def _validate_names(name: str, old_name: str | None) -> None:
    for candidate in (name, old_name):
        if candidate and (
            len(candidate) > 128 or not _CONFIG_NAME.fullmatch(candidate)
        ):
            raise SystemHelperError(
                f"Unsafe or unsupported config name: {candidate!r}"
            )
    if old_name and name.rsplit(".", 1)[0] != old_name.rsplit(".", 1)[0]:
        raise SystemHelperError(
            "The previous config name must have the same base name."
        )


class _SystemHelperSession:
    """Own one authenticated helper process for the GUI process lifetime."""

    def __init__(self) -> None:
        self._process: subprocess.Popen[str] | None = None
        self._lock = threading.Lock()
        self._write_lock = threading.Lock()
        self._record_active = False

    def apply(
        self,
        source: str,
        name: str,
        old_name: str | None,
    ) -> None:
        """Send one serialized transaction through the authenticated pipe."""
        with self._lock:
            process = self._ensure_started()
            request = json.dumps(
                {
                    "operation": "apply",
                    "name": name,
                    "old_name": old_name,
                    "source": source,
                },
                ensure_ascii=False,
                separators=(",", ":"),
            )
            try:
                self._write_line(process, request)
                response = self._read_json_line(process)
            except (BrokenPipeError, OSError, SystemHelperError) as error:
                self._discard_process()
                if isinstance(error, SystemHelperError):
                    raise
                raise SystemHelperError(
                    "The privileged helper connection was lost."
                ) from error

            if response.get("ok") is not True:
                message = response.get("error")
                raise SystemHelperError(
                    str(message) if message else "The system transaction failed."
                )

    def record_key(
        self,
        device_id: str | None,
        capture_shortcut: bool,
        cancel_event: threading.Event,
    ) -> str | None:
        """Capture one original input event while serializing helper operations."""
        with self._lock:
            if cancel_event.is_set():
                return None
            process = self._ensure_started()
            request = json.dumps(
                {
                    "operation": "record",
                    "device_id": device_id,
                    "capture_shortcut": capture_shortcut,
                },
                ensure_ascii=False,
                separators=(",", ":"),
            )
            try:
                self._write_line(process, request)
                acknowledgement = self._read_json_line(process)
                if acknowledgement.get("recording") is not True:
                    message = acknowledgement.get("error")
                    raise SystemHelperError(
                        str(message)
                        if message
                        else "The helper could not start physical input recording."
                    )
                self._record_active = True
                if cancel_event.is_set():
                    self.cancel_recording()
                response = self._read_json_line(process)
            except (BrokenPipeError, OSError, SystemHelperError) as error:
                self._discard_process()
                if isinstance(error, SystemHelperError):
                    raise
                raise SystemHelperError(
                    "The privileged helper connection was lost."
                ) from error
            finally:
                self._record_active = False

            if response.get("ok") is not True:
                message = response.get("error")
                raise SystemHelperError(
                    str(message) if message else "Physical input recording failed."
                )
            if response.get("cancelled") is True:
                return None
            key = response.get("key")
            if not isinstance(key, str) or not key:
                raise SystemHelperError(
                    "The privileged helper returned an invalid key."
                )
            return key

    def cancel_recording(self) -> None:
        """Ask an in-flight record operation to restore keyd and finish."""
        process = self._process
        if (
            not self._record_active
            or process is None
            or process.poll() is not None
        ):
            return
        request = json.dumps(
            {"operation": "cancel_record"},
            separators=(",", ":"),
        )
        try:
            self._write_line(process, request)
        except (BrokenPipeError, OSError):
            self._discard_process()

    def _write_line(
        self,
        process: subprocess.Popen[str],
        line: str,
    ) -> None:
        """Write one complete protocol frame without interleaving threads."""
        with self._write_lock:
            assert process.stdin is not None
            process.stdin.write(line + "\n")
            process.stdin.flush()

    def _ensure_started(self) -> subprocess.Popen[str]:
        process = self._process
        if process is not None and process.poll() is None:
            return process
        self._discard_process()

        installation_issue = helper_installation_issue()
        if installation_issue:
            raise SystemHelperError(installation_issue)

        arguments = [
            HELPER_PYTHON,
            HELPER_PATH,
            "session",
        ]
        if os.geteuid() != 0:
            arguments.insert(0, "pkexec")

        try:
            # The process intentionally outlives this method and is closed by
            # QApplication.aboutToQuit (with atexit as a crash-safe fallback).
            # pylint: disable-next=consider-using-with
            process = subprocess.Popen(
                arguments,
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                encoding="utf-8",
                bufsize=1,
            )
        except FileNotFoundError as error:
            command = "pkexec" if os.geteuid() != 0 else HELPER_PYTHON
            raise SystemHelperError(
                f"The required command '{command}' was not found."
            ) from error

        self._process = process
        try:
            response = self._read_json_line(process)
        except SystemHelperError:
            try:
                return_code = process.wait(timeout=0.5)
            except subprocess.TimeoutExpired:
                process.terminate()
                try:
                    return_code = process.wait(timeout=1)
                except subprocess.TimeoutExpired:
                    process.kill()
                    return_code = process.wait(timeout=1)
            details = (
                process.stderr.read().strip()
                if process.stderr is not None
                else ""
            )
            self._process = None
            if return_code == 126:
                raise SystemHelperError(
                    "System authorization was cancelled."
                ) from None
            if return_code == 127:
                raise SystemHelperError(
                    "System authorization was denied."
                ) from None
            raise SystemHelperError(
                details or "The privileged helper failed to start."
            ) from None

        if response.get("ready") is not True:
            self._discard_process()
            raise SystemHelperError(
                "The privileged helper sent an invalid handshake."
            )
        return process

    @staticmethod
    def _read_json_line(process: subprocess.Popen[str]) -> dict[str, object]:
        assert process.stdout is not None
        line = process.stdout.readline()
        if not line:
            raise SystemHelperError("The privileged helper closed unexpectedly.")
        try:
            response = json.loads(line)
        except json.JSONDecodeError as error:
            raise SystemHelperError(
                "The privileged helper returned an invalid response."
            ) from error
        if not isinstance(response, dict):
            raise SystemHelperError(
                "The privileged helper returned an invalid response."
            )
        return response

    def close(self) -> None:
        """Close stdin so the root helper exits even during interpreter shutdown."""
        self.cancel_recording()
        with self._lock:
            process = self._process
            self._process = None
            if process is None:
                return
            try:
                if process.stdin is not None:
                    process.stdin.close()
                process.wait(timeout=1)
            except (OSError, subprocess.TimeoutExpired):
                process.terminate()
                try:
                    process.wait(timeout=1)
                except subprocess.TimeoutExpired:
                    process.kill()
                    process.wait(timeout=1)

    def _discard_process(self) -> None:
        process = self._process
        self._process = None
        if process is not None and process.poll() is None:
            process.terminate()
            try:
                process.wait(timeout=1)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait(timeout=1)


_SESSION = _SystemHelperSession()


def apply_config(
    source: str,
    name: str,
    old_name: str | None = None,
) -> None:
    """Apply one config through the helper authorized for this app session."""
    _validate_names(name, old_name)
    _SESSION.apply(source, name, old_name)


def record_key(
    device_id: str | None,
    *,
    capture_shortcut: bool,
    cancel_event: threading.Event,
) -> str | None:
    """Record physical input through the authenticated helper session."""
    if device_id not in (None, "", "*") and (
        len(device_id) > 20 or not _DEVICE_ID.fullmatch(device_id)
    ):
        raise SystemHelperError(f"Unsupported device id: {device_id!r}")
    return _SESSION.record_key(
        device_id,
        capture_shortcut,
        cancel_event,
    )


def cancel_key_recording() -> None:
    """Cancel the active physical-input transaction, if any."""
    _SESSION.cancel_recording()


def close_system_helper() -> None:
    """Stop the privileged helper when KeydMapper exits."""
    _SESSION.close()


atexit.register(close_system_helper)
