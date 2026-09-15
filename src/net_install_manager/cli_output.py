"""User-facing CLI output helpers."""

import sys
from typing import TextIO


def write(message: str, stream: TextIO | None = None) -> None:
    """Write a user-facing line to the selected stream."""
    print(message, file=stream or sys.stdout)


def error(message: str) -> None:
    """Write a user-facing error line to stderr."""
    write(message, stream=sys.stderr)


def progress(message: str, quiet: bool = False) -> None:
    """Write progress output unless quiet mode is enabled."""
    if not quiet:
        write(message)


__all__ = ["error", "progress", "write"]
