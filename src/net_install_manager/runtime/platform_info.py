"""Information about the current platform, including the operating system and CPU architecture."""

from __future__ import annotations

import ctypes
from dataclasses import dataclass
import os

from net_install_manager.runtime.operating_system import OperatingSystem
from net_install_manager.runtime.architecture import Architecture


@dataclass(frozen=True)
class PlatformInfo:
    """Information about the current platform, including the OS and CPU architecture."""

    os: OperatingSystem
    architecture: Architecture
    is_admin: bool = False

    @classmethod
    def current(cls) -> PlatformInfo:
        """Return the current platform information as a PlatformInfo instance."""
        return cls(
            os=OperatingSystem.current(),
            architecture=Architecture.current(),
            is_admin=cls._get_is_admin(),  # Replace with actual admin check if needed
        )

    @staticmethod
    def _get_is_admin(operating_system: OperatingSystem | None = None) -> bool:
        """Return whether the current user has administrative privileges."""

        operating_system = operating_system or OperatingSystem.current()

        if operating_system == OperatingSystem.WINDOWS:
            try:
                return ctypes.windll.shell32.IsUserAnAdmin() != 0  # type: ignore # pylint: disable=no-member
            except Exception:  # pylint: disable=broad-except
                return False

        return os.getuid() == 0 if hasattr(os, "getuid") else False


__all__ = ["PlatformInfo"]
