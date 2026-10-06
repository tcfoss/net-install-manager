"""Information about the current CPU architecture."""

from __future__ import annotations

from enum import Enum
import platform


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


__all__ = ["Architecture"]
