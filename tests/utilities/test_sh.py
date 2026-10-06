import subprocess
from types import SimpleNamespace

import pytest

from net_install_manager.utilities import sh
from net_install_manager.utilities.sh import CommandOutput, CommandResult


@pytest.mark.parametrize(
    ("output", "captures"),
    [
        (CommandOutput.STREAM, False),
        (CommandOutput.CAPTURE, True),
        (CommandOutput.QUIET, True),
    ],
)
def test_run_command_configures_capture_and_normalizes_result(monkeypatch, output, captures):
    calls = []

    def fake_run(command, **kwargs):
        calls.append((command, kwargs))
        return SimpleNamespace(returncode=0, stdout=None, stderr=None)

    monkeypatch.setattr(sh.subprocess, "run", fake_run)

    result = sh.run_command(["tool", "--version"], cwd="/tmp", output=output)

    assert calls == [
        (
            ["tool", "--version"],
            {
                "cwd": "/tmp",
                "stdout": subprocess.PIPE if captures else None,
                "stderr": subprocess.PIPE if captures else None,
                "text": True,
                "check": False,
            },
        )
    ]
    assert result == CommandResult(["tool", "--version"], 0, "", "")


def test_run_command_raises_called_process_error_with_captured_output(monkeypatch):
    monkeypatch.setattr(
        sh.subprocess,
        "run",
        lambda *_args, **_kwargs: SimpleNamespace(returncode=7, stdout="out", stderr="failure"),
    )

    with pytest.raises(subprocess.CalledProcessError) as error:
        sh.run_command(["tool"], output=CommandOutput.CAPTURE)

    assert error.value.returncode == 7
    assert error.value.output == "out"
    assert error.value.stderr == "failure"


def test_exec_command_uses_default_stream_mode(monkeypatch):
    calls = []
    monkeypatch.setattr(sh, "run_command", lambda *args, **kwargs: calls.append((args, kwargs)))

    sh.exec_command(["tool"], cwd="/work")

    assert calls == [((["tool"],), {"cwd": "/work", "output": CommandOutput.STREAM})]


def test_exec_command_output_returns_stdout(monkeypatch):
    monkeypatch.setattr(
        sh,
        "run_command",
        lambda *args, **kwargs: CommandResult(["tool"], 0, "version\n", ""),
    )

    assert sh.exec_command_output(["tool"]) == "version\n"
