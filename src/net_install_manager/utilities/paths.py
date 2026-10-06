"""Utility functions for manipulating paths."""

from pathlib import Path, PureWindowsPath
import typing


def get_winpath_env(name: str, env: typing.Mapping[str, str], default: str | Path) -> Path:
    """Return the Windows-style path from the environment or the default."""
    value = env.get(name)
    if value:
        return Path(PureWindowsPath(value))
    return Path(PureWindowsPath(default))


__all__ = ["get_winpath_env"]
