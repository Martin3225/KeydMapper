"""Security and transaction tests for the privileged apply boundary."""
# pylint: disable=protected-access,no-member,redefined-outer-name

import argparse
from collections.abc import Iterator
import importlib.util
import json
from pathlib import Path
from types import ModuleType
from unittest.mock import MagicMock, patch
from xml.etree import ElementTree

import pytest
from keyd import system_helper


def _load_privileged_helper() -> ModuleType:
    helper_path = (
        _project_root()
        / "system"
        / "keyd-mapper-helper.py"
    )
    spec = importlib.util.spec_from_file_location(
        "keyd_mapper_privileged_helper",
        helper_path,
    )
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _project_root() -> Path:
    return Path(__file__).resolve().parents[3]


@pytest.fixture
def privileged_helper() -> Iterator[ModuleType]:
    """Load the installed-helper source without elevating the test process."""
    module = _load_privileged_helper()
    with patch.object(module.os, "chown"):
        yield module


def _fake_session_process(*responses: str) -> MagicMock:
    process = MagicMock()
    process.poll.return_value = None
    process.wait.return_value = 0
    process.stdout.readline.side_effect = responses
    return process


def test_client_reuses_pinned_helper_and_sends_json_over_stdin():
    """Two operations use one authenticated process and never invoke a shell."""
    process = _fake_session_process(
        '{"ready":true}\n',
        '{"ok":true}\n',
        '{"ok":true}\n',
    )
    session = system_helper._SystemHelperSession()
    with (
        patch("keyd.system_helper.helper_installation_issue", return_value=None),
        patch("keyd.system_helper.os.geteuid", return_value=1000),
        patch(
            "keyd.system_helper.subprocess.Popen",
            return_value=process,
        ) as popen,
        patch.object(system_helper, "_SESSION", session),
    ):
        system_helper.apply_config(
            "[ids]\n*\n",
            "keyboard.conf",
            "keyboard.disabled",
        )
        system_helper.apply_config(
            "[ids]\n1234:5678\n",
            "keyboard.conf",
        )
        session.close()

    popen.assert_called_once_with(
        [
            "pkexec",
            "/usr/bin/python3",
            "/usr/libexec/keyd-mapper-helper",
            "session",
        ],
        stdin=system_helper.subprocess.PIPE,
        stdout=system_helper.subprocess.PIPE,
        stderr=system_helper.subprocess.PIPE,
        text=True,
        encoding="utf-8",
        bufsize=1,
    )
    requests = [
        json.loads(call.args[0])
        for call in process.stdin.write.call_args_list
    ]
    assert requests == [
        {
            "operation": "apply",
            "name": "keyboard.conf",
            "old_name": "keyboard.disabled",
            "source": "[ids]\n*\n",
        },
        {
            "operation": "apply",
            "name": "keyboard.conf",
            "old_name": None,
            "source": "[ids]\n1234:5678\n",
        },
    ]
    process.stdin.close.assert_called_once()


def test_client_refuses_uninstalled_or_user_writable_helper():
    """The application never elevates code directly from the source checkout."""
    session = system_helper._SystemHelperSession()
    with (
        patch(
            "keyd.system_helper.helper_installation_issue",
            return_value="unsafe helper",
        ),
        patch("keyd.system_helper.subprocess.Popen") as popen,
        patch.object(system_helper, "_SESSION", session),
        pytest.raises(system_helper.SystemHelperError, match="unsafe helper"),
    ):
        system_helper.apply_config("[ids]\n*\n", "keyboard.conf")

    popen.assert_not_called()


def test_polkit_policy_pins_helper_without_global_authorization_cache():
    """The session, not a reusable Polkit cache, avoids repeated prompts."""
    policy = ElementTree.parse(  # nosec: trusted repository test fixture
        _project_root()
        / "system"
        / "io.github.keydmapper.apply-config.policy"
    ).getroot()
    action = policy.find("./action")

    assert action is not None
    assert action.attrib["id"] == "io.github.keydmapper.apply-config"
    assert action.findtext("./defaults/allow_active") == "auth_admin"
    annotations = {
        element.attrib["key"]: element.text
        for element in action.findall("./annotate")
    }
    assert annotations["org.freedesktop.policykit.exec.path"] == "/usr/bin/python3"
    assert (
        annotations["org.freedesktop.policykit.exec.argv1"]
        == "/usr/libexec/keyd-mapper-helper"
    )


@pytest.mark.parametrize("return_code", [126, 127])
def test_client_explains_cancelled_or_denied_authorization(return_code: int):
    """Standard pkexec authorization outcomes become concise errors."""
    process = _fake_session_process("")
    process.wait.return_value = return_code
    session = system_helper._SystemHelperSession()
    with (
        patch("keyd.system_helper.helper_installation_issue", return_value=None),
        patch("keyd.system_helper.os.geteuid", return_value=1000),
        patch(
            "keyd.system_helper.subprocess.Popen",
            return_value=process,
        ),
        patch.object(system_helper, "_SESSION", session),
        pytest.raises(system_helper.SystemHelperError, match="authorization"),
    ):
        system_helper.apply_config("[ids]\n*\n", "keyboard.conf")


def test_client_keeps_session_after_a_rejected_transaction():
    """A config validation error does not cause another authorization prompt."""
    process = _fake_session_process(
        '{"ready":true}\n',
        '{"ok":false,"error":"invalid config"}\n',
        '{"ok":true}\n',
    )
    session = system_helper._SystemHelperSession()
    with (
        patch("keyd.system_helper.helper_installation_issue", return_value=None),
        patch("keyd.system_helper.os.geteuid", return_value=1000),
        patch(
            "keyd.system_helper.subprocess.Popen",
            return_value=process,
        ) as popen,
        patch.object(system_helper, "_SESSION", session),
        pytest.raises(system_helper.SystemHelperError, match="invalid config"),
    ):
        system_helper.apply_config("invalid", "keyboard.conf")

    with (
        patch.object(system_helper, "_SESSION", session),
        patch("keyd.system_helper.subprocess.Popen") as second_popen,
    ):
        system_helper.apply_config("[ids]\n*\n", "keyboard.conf")

    popen.assert_called_once()
    second_popen.assert_not_called()
    session.close()


@pytest.mark.parametrize(
    "name",
    [
        "../evil.conf",
        "/tmp/evil.conf",
        "evil.conf;id",
        "evil",
        ".hidden.conf",
        "evil.conf/other",
    ],
)
def test_privileged_helper_rejects_unsafe_names(
    privileged_helper: ModuleType,
    name: str,
):
    """Every destination remains a plain filename directly under /etc/keyd."""
    with pytest.raises(argparse.ArgumentTypeError):
        privileged_helper._validated_name(name)


def test_privileged_helper_cannot_delete_an_unrelated_config(
    privileged_helper: ModuleType,
):
    """old-name is restricted to the matching enable/disable counterpart."""
    with pytest.raises(privileged_helper.ApplyError, match="same base"):
        privileged_helper._validate_rename_pair(
            "keyboard.conf",
            "unrelated.disabled",
        )


def test_privileged_session_validates_each_request(
    privileged_helper: ModuleType,
):
    """The long-lived root process exposes only the narrow apply operation."""
    privileged_helper.apply = MagicMock()
    privileged_helper._transaction_lock = MagicMock()

    with pytest.raises(privileged_helper.ApplyError, match="unsupported"):
        privileged_helper._apply_request(
            {
                "operation": "command",
                "name": "keyboard.conf",
                "old_name": None,
                "source": "id",
            }
        )

    privileged_helper.apply.assert_not_called()


def test_privileged_session_bounds_config_bytes(
    privileged_helper: ModuleType,
):
    """The limit applies to UTF-8 bytes, including multi-byte characters."""
    oversized = "ž" * (privileged_helper.MAX_CONFIG_BYTES // 2 + 1)

    with pytest.raises(privileged_helper.ApplyError, match="1 MiB"):
        privileged_helper._validated_source(oversized)


def test_privileged_apply_is_atomic_and_uses_fixed_commands(
    privileged_helper: ModuleType,
    tmp_path: Path,
):
    """A successful transaction validates, replaces, and restarts keyd."""
    privileged_helper.CONFIG_DIRECTORY = str(tmp_path)
    privileged_helper._check_system_paths = MagicMock()
    privileged_helper._run_checked = MagicMock()

    privileged_helper.apply(
        b"[ids]\n*\n",
        "keyboard.conf",
        None,
    )

    target = tmp_path / "keyboard.conf"
    assert target.read_bytes() == b"[ids]\n*\n"
    assert privileged_helper._run_checked.call_args_list[0].args[0][0:2] == [
        "/usr/bin/keyd",
        "check",
    ]
    assert privileged_helper._run_checked.call_args_list[1].args[0] == [
        "/usr/bin/systemctl",
        "restart",
        "keyd.service",
    ]


def test_validation_failure_preserves_existing_system_config(
    privileged_helper: ModuleType,
    tmp_path: Path,
):
    """Invalid staged content cannot remove or replace the active config."""
    target = tmp_path / "keyboard.conf"
    target.write_bytes(b"original")
    privileged_helper.CONFIG_DIRECTORY = str(tmp_path)
    privileged_helper._check_system_paths = MagicMock()
    privileged_helper._run_checked = MagicMock(
        side_effect=privileged_helper.ApplyError("invalid")
    )

    with pytest.raises(privileged_helper.ApplyError):
        privileged_helper.apply(b"invalid", "keyboard.conf", None)

    assert target.read_bytes() == b"original"


def test_restart_failure_rolls_back_enable_rename(
    privileged_helper: ModuleType,
    tmp_path: Path,
):
    """Both names and contents are restored if keyd cannot restart."""
    target = tmp_path / "keyboard.conf"
    old_target = tmp_path / "keyboard.disabled"
    target.write_bytes(b"previous enabled")
    old_target.write_bytes(b"previous disabled")
    privileged_helper.CONFIG_DIRECTORY = str(tmp_path)
    privileged_helper._check_system_paths = MagicMock()
    privileged_helper._run_checked = MagicMock(
        side_effect=[
            None,
            privileged_helper.ApplyError("restart failed"),
        ]
    )

    with (
        patch.object(privileged_helper.subprocess, "run"),
        pytest.raises(privileged_helper.ApplyError),
    ):
        privileged_helper.apply(
            b"new config",
            "keyboard.conf",
            "keyboard.disabled",
        )

    assert target.read_bytes() == b"previous enabled"
    assert old_target.read_bytes() == b"previous disabled"


def test_privileged_helper_refuses_symlink_target(
    privileged_helper: ModuleType,
    tmp_path: Path,
):
    """An existing symlink can never redirect the root write outside /etc/keyd."""
    outside = tmp_path / "outside"
    outside.write_text("do not touch", encoding="utf-8")
    (tmp_path / "keyboard.conf").symlink_to(outside)
    privileged_helper.CONFIG_DIRECTORY = str(tmp_path)
    privileged_helper._check_system_paths = MagicMock()

    with pytest.raises(privileged_helper.ApplyError, match="non-regular"):
        privileged_helper.apply(
            b"[ids]\n*\n",
            "keyboard.conf",
            None,
        )

    assert outside.read_text(encoding="utf-8") == "do not touch"
