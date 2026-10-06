"""Information about the current runtime environment of the application."""

from __future__ import annotations

from dataclasses import dataclass
import os
from pathlib import Path
import typing

from net_install_manager.runtime.operating_system import OperatingSystem
from net_install_manager.runtime.platform_info import PlatformInfo
from net_install_manager.utilities.paths import get_winpath_env


@dataclass(frozen=True)
class Runtime:
    """Information about the current runtime environment of the application."""

    platform: PlatformInfo
    env: typing.Mapping[str, str]
    registry_path: Path
    home_dir: Path
    system_wide: bool = False

    @property
    def os(self) -> OperatingSystem:
        """Return the operating system of the current runtime environment."""
        return self.platform.os

    @property
    def runtime_identifier(self) -> str:
        """Return the .NET Runtime Identifier (RID) for this platform."""
        os_part = self.platform.os.rid_string
        arch_part = self.platform.architecture.rid_string

        return f"{os_part}-{arch_part}"

    @property
    def cache_root(self) -> Path:
        """Return the cache root directory for the current runtime environment."""
        if self.system_wide:
            if self.os.is_posix:
                return Path("/var/cache/ninman/sources")
            return (
                get_winpath_env("PROGRAMDATA", self.env, r"C:\ProgramData")
                / "ninman"
                / "cache"
                / "sources"
            )

        if self.os.is_posix:
            if xdg_cache := self.env.get("XDG_CACHE_HOME"):
                return Path(xdg_cache) / "ninman" / "sources"
            return self.home_dir / ".cache" / "ninman" / "sources"

        default = self.home_dir / "AppData" / "Local"
        return get_winpath_env("LOCALAPPDATA", self.env, default) / "ninman" / "cache" / "sources"

    @classmethod
    def current(cls, system_wide: bool = False) -> Runtime:
        """Return the current runtime environment as a Runtime instance."""
        return cls(
            platform=PlatformInfo.current(),
            system_wide=system_wide,
            home_dir=Path.home(),
            env=os.environ,
            registry_path=cls._get_registry_path(
                OperatingSystem.current(), os.environ, Path.home(), system_wide
            ),
        )

    @staticmethod
    def _get_registry_path(
        operating_system: OperatingSystem,
        env: typing.Mapping[str, str],
        home_dir: Path,
        system_wide: bool,
    ) -> Path:
        """Return the registry path based on whether the installation is system-wide."""
        if operating_system.is_posix:
            if system_wide:
                prefix = Path("/etc")
            elif env.get("XDG_CONFIG_HOME"):
                prefix = Path(env["XDG_CONFIG_HOME"])
            else:
                prefix = home_dir / ".config"
            return prefix / "ninman" / "apps.yaml"

        if system_wide:
            prefix = get_winpath_env("PROGRAMDATA", env, r"C:\ProgramData")
        else:
            prefix = get_winpath_env("LOCALAPPDATA", env, home_dir / "AppData" / "Local")
        return prefix / "ninman" / "apps.yaml"


__all__ = ["Runtime"]
