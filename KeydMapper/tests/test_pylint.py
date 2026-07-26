"""Test to ensure the codebase complies with pylint rules."""

import importlib.util
import os
import subprocess
import sys

import pytest


def test_pylint():
    """Run pylint on the src and tests directories and assert it passes."""
    # Resolve the root directory of the project (KeydMapper directory)
    root_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    workspace_dir = os.path.dirname(root_dir)

    if importlib.util.find_spec("pylint") is None:
        pytest.skip("Pylint is not installed in the current environment.")

    try:
        result = subprocess.run(
            [
                sys.executable,
                "-m",
                "pylint",
                "--disable=C0301,C0103,R0914,R0913,E0611",
                "KeydMapper",
            ],
            cwd=workspace_dir,
            capture_output=True,
            text=True,
            check=False,
        )

        assert result.returncode == 0, f"Pylint found errors:\n{result.stdout}"
    except FileNotFoundError:
        pytest.skip("Pylint or Python executable not found in the environment.")
