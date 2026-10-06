"""Information about the current OS."""

from __future__ import annotations

from enum import Enum
import platform


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


__all__ = ["OperatingSystem"]
