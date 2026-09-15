"""Tests for shell command execution helpers."""

import subprocess
import sys

from net_install_manager.utilities.sh import CommandOutput, exec_command, exec_command_output, run_command


def test_run_command_capture_returns_stdout_and_stderr():
    """Captured commands should return both streams without printing them."""
    result = run_command(
        [
            sys.executable,
            "-c",
            "import sys; print('out'); print('err', file=sys.stderr)",
        ],
        output=CommandOutput.CAPTURE,
    )

    assert result.returncode == 0
    assert result.stdout == "out\n"
    assert result.stderr == "err\n"


def test_exec_command_output_returns_stdout_only():
    """The output wrapper should preserve the existing stdout-returning contract."""
    output = exec_command_output([sys.executable, "-c", "print('1.2.3')"])

    assert output == "1.2.3\n"


def test_exec_command_quiet_captures_failure_output():
    """Quiet commands should suppress normal streaming but keep failure details."""
    command = [
        sys.executable,
        "-c",
        "import sys; print('out'); print('err', file=sys.stderr); raise SystemExit(7)",
    ]

    try:
        exec_command(command, quiet=True)
    except subprocess.CalledProcessError as error:
        assert error.returncode == 7
        assert error.output == "out\n"
        assert error.stderr == "err\n"
    else:
        raise AssertionError("Expected command failure")