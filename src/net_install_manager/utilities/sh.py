"""Shell command execution tools."""

from dataclasses import dataclass
from enum import Enum
import logging
import subprocess

logger = logging.getLogger(__name__)


class CommandOutput(str, Enum):
    """Output handling mode for child processes."""

    STREAM = "stream"
    CAPTURE = "capture"
    QUIET = "quiet"


@dataclass(frozen=True)
class CommandResult:
    """Completed command result with normalized output strings."""

    args: list[str]
    returncode: int
    stdout: str
    stderr: str


def run_command(
    command: list[str],
    cwd: str | None = None,
    output: CommandOutput = CommandOutput.STREAM,
) -> CommandResult:
    """Run a shell command with the requested output handling mode."""
    logger.debug("Executing command <%s> in <%s>", " ".join(command), cwd or ".")

    capture_output = output in (CommandOutput.CAPTURE, CommandOutput.QUIET)
    result = subprocess.run(
        command,
        cwd=cwd,
        stdout=subprocess.PIPE if capture_output else None,
        stderr=subprocess.PIPE if capture_output else None,
        text=True,
        check=False,
    )

    command_result = CommandResult(
        args=list(command),
        returncode=result.returncode,
        stdout=result.stdout or "",
        stderr=result.stderr or "",
    )
    if result.returncode != 0:
        raise subprocess.CalledProcessError(
            result.returncode,
            command,
            output=command_result.stdout,
            stderr=command_result.stderr,
        )

    return command_result


def exec_command(
    command: list[str],
    cwd: str | None = None,
    quiet: bool = False,
    output: CommandOutput | None = None,
) -> None:
    """Execute a shell command in the specified working directory."""
    output_mode = output or (CommandOutput.QUIET if quiet else CommandOutput.STREAM)
    if output_mode is CommandOutput.STREAM:
        logger.info("Executing command <%s> in <%s>", " ".join(command), cwd or ".")

    run_command(command, cwd=cwd, output=output_mode)


def exec_command_output(command: list[str], cwd: str | None = None) -> str:
    """Execute a command and return stdout as string."""
    result = run_command(command, cwd=cwd, output=CommandOutput.CAPTURE)
    return result.stdout


__all__ = ["CommandOutput", "CommandResult", "exec_command", "exec_command_output", "run_command"]
