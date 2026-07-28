#!/usr/bin/python3
"""Privileged helper for keyd config updates and physical input recording.

This file must be installed root-owned and must never be executed with elevated
privileges directly from a user-writable source checkout.
"""

from __future__ import annotations

import argparse
from contextlib import contextmanager
import fcntl
import json
import os
import re
import secrets
import select
import stat
import subprocess
import sys
import time


CONFIG_DIRECTORY = "/etc/keyd"
KEYD_COMMAND = "/usr/bin/keyd"
SYSTEMCTL_COMMAND = "/usr/bin/systemctl"
LOCK_PATH = "/run/lock/keyd-mapper.lock"
MAX_CONFIG_BYTES = 1024 * 1024
RECORDING_TIMEOUT_SECONDS = 30
# JSON escaping can make a valid UTF-8 config several times larger on the wire.
MAX_REQUEST_CHARACTERS = MAX_CONFIG_BYTES * 8
CONFIG_NAME = re.compile(
    r"[A-Za-z0-9][A-Za-z0-9_.-]{0,126}\.(?:conf|disabled)"
)
DEVICE_ID = re.compile(
    r"(?:(?:k|m):)?[0-9A-Fa-f]{4}:[0-9A-Fa-f]{4}"
    r"(?::[0-9A-Fa-f]{8})?"
)
MONITOR_EVENT = re.compile(
    r"^(?P<device>.*?)\t(?P<id>[^\t]+)\t"
    r"(?P<key>\S+) (?P<state>down|up)\s*$"
)
MODIFIER_PREFIXES = {
    "leftcontrol": "C",
    "rightcontrol": "C",
    "control": "C",
    "leftshift": "S",
    "rightshift": "S",
    "shift": "S",
    "leftalt": "A",
    "alt": "A",
    "rightalt": "G",
    "altgr": "G",
    "leftmeta": "M",
    "rightmeta": "M",
    "meta": "M",
}
MODIFIER_ORDER = ("C", "S", "A", "M", "G")


class ApplyError(Exception):
    """A safe, reader-facing error raised by the privileged transaction."""


def _validated_name(value: str) -> str:
    if len(value) > 128 or not CONFIG_NAME.fullmatch(value):
        raise argparse.ArgumentTypeError(
            "Config names may contain letters, numbers, '.', '_' and '-', "
            "must end in .conf or .disabled, and cannot exceed 128 characters."
        )
    return value


def _validate_rename_pair(name: str, old_name: str | None) -> None:
    """Allow old-name removal only for an enable/disable suffix change."""
    if old_name and name.rsplit(".", 1)[0] != old_name.rsplit(".", 1)[0]:
        raise ApplyError(
            "The previous config name must have the same base name."
        )


def _validated_source(source_text: str) -> bytes:
    if not isinstance(source_text, str):
        raise ApplyError("The configuration must be text.")
    source = source_text.encode("utf-8")
    if len(source) > MAX_CONFIG_BYTES:
        raise ApplyError("The configuration exceeds the 1 MiB safety limit.")
    if b"\0" in source:
        raise ApplyError("The configuration contains a NUL byte.")
    return source


def _check_system_paths() -> None:
    try:
        directory = os.lstat(CONFIG_DIRECTORY)
    except OSError as error:
        raise ApplyError(f"Cannot access {CONFIG_DIRECTORY}: {error}") from error
    if not stat.S_ISDIR(directory.st_mode) or stat.S_ISLNK(directory.st_mode):
        raise ApplyError(f"{CONFIG_DIRECTORY} must be a real directory.")
    if directory.st_uid != 0 or directory.st_mode & (
        stat.S_IWGRP | stat.S_IWOTH
    ):
        raise ApplyError(
            f"{CONFIG_DIRECTORY} must be root-owned and not group/world-writable."
        )
    for executable in (KEYD_COMMAND, SYSTEMCTL_COMMAND):
        if not os.path.isfile(executable) or not os.access(executable, os.X_OK):
            raise ApplyError(f"Required executable not found: {executable}")


def _assert_replaceable_file(path: str) -> None:
    """Refuse to move directories, devices, or symlinks in /etc/keyd."""
    try:
        metadata = os.lstat(path)
    except FileNotFoundError:
        return
    if not stat.S_ISREG(metadata.st_mode):
        raise ApplyError(f"Refusing to replace non-regular file: {path}")


def _run_checked(command: list[str], description: str) -> None:
    result = subprocess.run(
        command,
        capture_output=True,
        text=True,
        timeout=15,
        check=False,
        env={
            "PATH": "/usr/sbin:/usr/bin",
            "LANG": "C.UTF-8",
        },
    )
    if result.returncode != 0:
        details = (result.stderr or result.stdout or "").strip()
        raise ApplyError(f"{description} failed: {details or result.returncode}")


def _keyd_service_is_active() -> bool:
    """Return whether recording must restore a running keyd service."""
    result = subprocess.run(
        [SYSTEMCTL_COMMAND, "is-active", "--quiet", "keyd.service"],
        capture_output=True,
        text=True,
        timeout=15,
        check=False,
        env={
            "PATH": "/usr/sbin:/usr/bin",
            "LANG": "C.UTF-8",
        },
    )
    return result.returncode == 0


def _normalised_device_id(device_id: str | None) -> str | None:
    """Validate a monitor filter and remove keyd's optional type prefix."""
    if device_id in (None, "", "*"):
        return None
    if not isinstance(device_id, str) or not DEVICE_ID.fullmatch(device_id):
        raise ApplyError("The device id is invalid.")
    return device_id.removeprefix("k:").removeprefix("m:").lower()


def _read_cancel_request() -> bool | None:
    """Return True for cancel and None when the GUI session disappeared."""
    request = _read_request()
    if request is None:
        return None
    if request != {"operation": "cancel_record"}:
        raise ApplyError("Only recording cancellation is allowed while monitoring.")
    return True


def _record_original_input(
    device_id: str | None,
    capture_shortcut: bool,
) -> tuple[dict[str, object], bool]:
    """Pause keyd, capture one original event, and restore the service."""
    _check_system_paths()
    wanted_device = _normalised_device_id(device_id)
    service_was_active = _keyd_service_is_active()
    monitor: subprocess.Popen[str] | None = None
    parent_closed = False
    response: dict[str, object] = {"ok": True, "cancelled": True}

    if service_was_active:
        _run_checked(
            [SYSTEMCTL_COMMAND, "stop", "keyd.service"],
            "stopping keyd for physical input recording",
        )

    try:
        # pylint: disable-next=consider-using-with
        monitor = subprocess.Popen(
            [KEYD_COMMAND, "monitor"],
            stdin=subprocess.DEVNULL,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            encoding="utf-8",
            bufsize=1,
            env={
                "PATH": "/usr/sbin:/usr/bin",
                "LANG": "C.UTF-8",
            },
        )
        assert monitor.stdout is not None
        pressed_modifiers: dict[str, str] = {}
        pressed_keys: set[str] = set()
        captured_keys: set[str] = set()
        deadline = time.monotonic() + RECORDING_TIMEOUT_SECONDS

        while True:
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                raise ApplyError(
                    "Physical input recording timed out after 30 seconds."
                )
            ready, _, _ = select.select(
                [sys.stdin, monitor.stdout],
                [],
                [],
                remaining,
            )
            if not ready:
                continue

            if sys.stdin in ready:
                cancellation = _read_cancel_request()
                if cancellation is None:
                    parent_closed = True
                break

            line = monitor.stdout.readline()
            if not line:
                details = (
                    monitor.stderr.read().strip()
                    if monitor.stderr is not None
                    else ""
                )
                raise ApplyError(
                    details or "keyd monitor stopped before reporting a key."
                )

            event = MONITOR_EVENT.match(line)
            if event is None:
                continue
            event_device = event.group("id").lower()
            if wanted_device is not None and not (
                event_device == wanted_device
                or event_device.startswith(f"{wanted_device}:")
            ):
                continue

            key = event.group("key")
            state = event.group("state")
            if state == "down":
                pressed_keys.add(key)
            else:
                pressed_keys.discard(key)

            if "key" in response:
                if captured_keys.isdisjoint(pressed_keys):
                    break
                continue

            modifier = MODIFIER_PREFIXES.get(key)
            if not capture_shortcut:
                if state == "down":
                    response = {"ok": True, "key": key}
                    captured_keys = {key}
                continue

            if modifier is not None:
                if state == "down":
                    pressed_modifiers[key] = modifier
                    continue
                if key in pressed_modifiers:
                    pressed_modifiers.pop(key)
                    response = {"ok": True, "key": key}
                    captured_keys = {key}
                    if captured_keys.isdisjoint(pressed_keys):
                        break
                continue

            if state == "down":
                active = set(pressed_modifiers.values())
                prefixes = [
                    prefix for prefix in MODIFIER_ORDER if prefix in active
                ]
                response = {
                    "ok": True,
                    "key": "-".join((*prefixes, key)),
                }
                captured_keys = {*pressed_modifiers, key}
    finally:
        if monitor is not None and monitor.poll() is None:
            monitor.terminate()
            try:
                monitor.wait(timeout=2)
            except subprocess.TimeoutExpired:
                monitor.kill()
                monitor.wait(timeout=2)
        if service_was_active:
            _run_checked(
                [SYSTEMCTL_COMMAND, "start", "keyd.service"],
                "restoring keyd after physical input recording",
            )

    return response, parent_closed


def _unique_path(label: str) -> str:
    return os.path.join(
        CONFIG_DIRECTORY,
        f".keydmapper-{label}-{secrets.token_hex(8)}",
    )


def _write_staged_config(source: bytes) -> str:
    stage_path = _unique_path("stage")
    flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW
    descriptor = os.open(stage_path, flags, 0o600)
    try:
        with os.fdopen(descriptor, "wb", closefd=True) as stage:
            stage.write(source)
            stage.flush()
            os.fsync(stage.fileno())
        os.chmod(stage_path, 0o644, follow_symlinks=False)
        os.chown(stage_path, 0, 0, follow_symlinks=False)
    except Exception:
        try:
            os.unlink(stage_path)
        except OSError:
            pass
        raise
    return stage_path


def _restore(
    target_path: str,
    target_backup: str | None,
    old_path: str | None,
    old_backup: str | None,
    new_installed: bool,
) -> None:
    try:
        if new_installed and os.path.lexists(target_path):
            os.unlink(target_path)
        if target_backup:
            os.replace(target_backup, target_path)
        if old_path and old_backup:
            os.replace(old_backup, old_path)
        subprocess.run(
            [SYSTEMCTL_COMMAND, "restart", "keyd.service"],
            capture_output=True,
            timeout=15,
            check=False,
            env={"PATH": "/usr/sbin:/usr/bin", "LANG": "C.UTF-8"},
        )
    except OSError:
        # The original ApplyError is more useful; recovery is best-effort.
        pass


def apply(source: bytes, name: str, old_name: str | None) -> None:
    """Validate, atomically install, restart, and roll back on failure."""
    _validate_rename_pair(name, old_name)
    _check_system_paths()
    target_path = os.path.join(CONFIG_DIRECTORY, name)
    old_path = (
        os.path.join(CONFIG_DIRECTORY, old_name)
        if old_name and old_name != name
        else None
    )
    _assert_replaceable_file(target_path)
    if old_path:
        _assert_replaceable_file(old_path)

    stage_path = _write_staged_config(source)
    target_backup: str | None = None
    old_backup: str | None = None
    new_installed = False
    try:
        _run_checked(
            [KEYD_COMMAND, "check", stage_path],
            "keyd validation",
        )
        if os.path.lexists(target_path):
            target_backup = _unique_path("target-backup")
            os.replace(target_path, target_backup)
        if old_path and os.path.lexists(old_path):
            old_backup = _unique_path("old-backup")
            os.replace(old_path, old_backup)

        os.replace(stage_path, target_path)
        stage_path = ""
        new_installed = True
        _run_checked(
            [SYSTEMCTL_COMMAND, "restart", "keyd.service"],
            "keyd restart",
        )
    except Exception:
        if target_backup or old_backup or new_installed:
            _restore(
                target_path,
                target_backup,
                old_path,
                old_backup,
                new_installed,
            )
        raise
    finally:
        if stage_path and os.path.lexists(stage_path):
            os.unlink(stage_path)

    for backup in (target_backup, old_backup):
        if backup and os.path.lexists(backup):
            os.unlink(backup)


@contextmanager
def _transaction_lock():
    """Serialize only active transactions, not the whole GUI session."""
    lock_descriptor = os.open(
        LOCK_PATH,
        os.O_RDWR | os.O_CREAT | os.O_NOFOLLOW,
        0o600,
    )
    try:
        lock_metadata = os.fstat(lock_descriptor)
        if (
            not stat.S_ISREG(lock_metadata.st_mode)
            or lock_metadata.st_uid != 0
        ):
            raise ApplyError(
                "The transaction lock has unsafe ownership or type."
            )
        with os.fdopen(lock_descriptor, "a", encoding="ascii") as lock:
            lock_descriptor = -1
            os.fchmod(lock.fileno(), 0o600)
            fcntl.flock(lock, fcntl.LOCK_EX)
            yield
    finally:
        if lock_descriptor >= 0:
            os.close(lock_descriptor)


def _write_response(response: dict[str, object]) -> None:
    sys.stdout.write(
        json.dumps(response, ensure_ascii=False, separators=(",", ":")) + "\n"
    )
    sys.stdout.flush()


def _read_request() -> dict[str, object] | None:
    """Read one bounded JSON request; EOF means the owning GUI has exited."""
    line = sys.stdin.readline(MAX_REQUEST_CHARACTERS + 1)
    if not line:
        return None
    if len(line) > MAX_REQUEST_CHARACTERS or not line.endswith("\n"):
        raise ApplyError("The helper request exceeds the safety limit.")
    try:
        request = json.loads(line)
    except json.JSONDecodeError as error:
        raise ApplyError("The helper request is not valid JSON.") from error
    if not isinstance(request, dict):
        raise ApplyError("The helper request must be an object.")
    return request


def _apply_request(request: dict[str, object]) -> None:
    expected_fields = {"operation", "name", "old_name", "source"}
    if set(request) != expected_fields or request.get("operation") != "apply":
        raise ApplyError("The helper request has unsupported fields.")

    name = request.get("name")
    old_name = request.get("old_name")
    source = request.get("source")
    if not isinstance(name, str):
        raise ApplyError("The config name must be text.")
    if old_name is not None and not isinstance(old_name, str):
        raise ApplyError("The previous config name must be text or null.")
    try:
        name = _validated_name(name)
        if old_name is not None:
            old_name = _validated_name(old_name)
    except argparse.ArgumentTypeError as error:
        raise ApplyError(str(error)) from error

    with _transaction_lock():
        apply(_validated_source(source), name, old_name)


def _record_request(
    request: dict[str, object],
) -> tuple[dict[str, object], bool]:
    """Validate and execute one bounded keyd monitor transaction."""
    expected_fields = {"operation", "device_id", "capture_shortcut"}
    if set(request) != expected_fields or request.get("operation") != "record":
        raise ApplyError("The recording request has unsupported fields.")
    device_id = request.get("device_id")
    capture_shortcut = request.get("capture_shortcut")
    if device_id is not None and not isinstance(device_id, str):
        raise ApplyError("The device id must be text or null.")
    if not isinstance(capture_shortcut, bool):
        raise ApplyError("The shortcut option must be true or false.")
    _write_response({"recording": True})
    with _transaction_lock():
        return _record_original_input(device_id, capture_shortcut)


def _run_session() -> int:
    """Serve validated transactions until the unprivileged parent closes stdin."""
    _write_response({"ready": True})
    while True:
        try:
            request = _read_request()
            if request is None:
                return 0
            operation = request.get("operation")
            if operation == "apply":
                _apply_request(request)
                response = {"ok": True}
                parent_closed = False
            elif operation == "record":
                response, parent_closed = _record_request(request)
            else:
                raise ApplyError("The helper request has an unsupported operation.")
            if parent_closed:
                return 0
        except (ApplyError, OSError, subprocess.SubprocessError) as error:
            try:
                _write_response({"ok": False, "error": str(error)})
            except (BrokenPipeError, OSError):
                return 0
        else:
            try:
                _write_response(response)
            except (BrokenPipeError, OSError):
                return 0


def _parse_arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    subcommands = parser.add_subparsers(dest="operation", required=True)
    subcommands.add_parser("session")
    return parser.parse_args()


def main() -> int:
    """Run one authorized, GUI-owned helper session."""
    if os.geteuid() != 0:
        print("This helper must run as root through Polkit.", file=sys.stderr)
        return 1
    arguments = _parse_arguments()
    if arguments.operation == "session":
        return _run_session()
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
