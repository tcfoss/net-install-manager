"""Utilities for inspecting the current platform (OS, user, architecture)."""

from __future__ import annotations

import ctypes
from dataclasses import dataclass
from enum import Enum
import os
import platform
from pathlib import Path, PureWindowsPath


class OperatingSystem(Enum):
    """Enumeration of supported operating systems."""

    WINDOWS = "Windows"
    LINUX = "Linux"
    MACOS = "macOS"

    @property
    def is_posix(self) -> bool:
        """Return True if the operating system is POSIX-compliant."""
        return self in (OperatingSystem.LINUX, OperatingSystem.MACOS)

    @property
    def rid_string(self) -> str:
        """Return the .NET Runtime Identifier (RID) string for this operating system."""
        return {
            OperatingSystem.WINDOWS: "win",
            OperatingSystem.LINUX: "linux",
            OperatingSystem.MACOS: "osx",
        }[self]

    @classmethod
    def current(cls) -> OperatingSystem:
        """Return the current operating system as an OperatingSystem enum member."""
        curr_os = platform.system().lower()
        if curr_os == "windows":
            return cls.WINDOWS
        if curr_os == "linux":
            return cls.LINUX
        if curr_os == "darwin":
            return cls.MACOS
        raise ValueError(f"Unsupported operating system: {curr_os}")


class Architecture(Enum):
    """Enumeration of supported CPU architectures."""

    X86_64 = "x86_64"
    ARM64 = "arm64"

    @property
    def rid_string(self) -> str:
        """Return the .NET Runtime Identifier (RID) string for this architecture."""
        return {
            Architecture.X86_64: "x64",
            Architecture.ARM64: "arm64",
        }[self]

    @classmethod
    def current(cls) -> Architecture:
        """Return the current CPU architecture as an Architecture enum member."""
        arch = platform.machine().lower()
        if arch in ("x86_64", "amd64"):
            return cls.X86_64
        if arch in ("arm64", "aarch64"):
            return cls.ARM64
        raise ValueError(f"Unsupported architecture: {arch}")


def _is_admin(target_os: OperatingSystem | None = None) -> bool:
    """Return whether the current user has administrative privileges.

    If target_os is specified, check for admin privileges on that OS.
    Otherwise, use the current operating system.
    """
    target_os = target_os or OperatingSystem.current()

    if target_os == OperatingSystem.WINDOWS:
        try:
            return ctypes.windll.shell32.IsUserAnAdmin() != 0  # type: ignore # pylint: disable=no-member
        except Exception:  # pylint: disable=broad-except
            return False

    return os.getuid() == 0 if hasattr(os, "getuid") else False


@dataclass(frozen=True)
class PlatformInfo:
    """Information about the current platform."""

    os: OperatingSystem
    architecture: Architecture = Architecture.X86_64
    is_admin: bool = False

    @property
    def is_posix(self) -> bool:
        """Return True if the platform's operating system is POSIX-compliant."""
        return self.os.is_posix

    @property
    def runtime_identifier(self) -> str:
        """Return the .NET Runtime Identifier (RID) for this platform."""
        os_part = {
            OperatingSystem.WINDOWS: "win",
            OperatingSystem.LINUX: "linux",
            OperatingSystem.MACOS: "osx",
        }[self.os]

        arch_part = {
            Architecture.X86_64: "x64",
            Architecture.ARM64: "arm64",
        }[self.architecture]

        return f"{os_part}-{arch_part}"

    @classmethod
    def detect(cls) -> PlatformInfo:
        """Detect and return the current platform information."""
        return cls(
            os=OperatingSystem.current(),
            architecture=Architecture.current(),
            is_admin=_is_admin(),
        )


def get_winpath(path: str) -> Path:
    """Convert a Windows path string to a Path object using PureWindowsPath."""
    return Path(PureWindowsPath(path))


__all__ = ["OperatingSystem", "Architecture", "PlatformInfo", "_is_admin", "get_winpath"]
