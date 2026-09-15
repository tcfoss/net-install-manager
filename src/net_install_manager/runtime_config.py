"""Information about application runtime environment and installation configuration."""

from __future__ import annotations

from dataclasses import dataclass, field
import os
from pathlib import Path
import typing as typ

from net_install_manager.utilities.sys_platform import PlatformInfo, OperatingSystem
from net_install_manager.utilities.csproj_tools import BuildOpts


@dataclass(frozen=True)
class InstallOptions:
    """Options for building and installing an application."""

    prefer_opt: bool = False
    self_contained: bool = False
    release: bool = True
    force: bool = False
    keep_latest: int | None = None
    exclude_patterns: list[str] | None = None
    explicit_version: str | None = None
    quiet: bool = False

    def to_build_opts(self, platform: PlatformInfo | None = None) -> BuildOpts:
        """Convert the install options to build options for dotnet build/publish."""
        platform = platform or PlatformInfo.detect()
        return BuildOpts(
            release=self.release,
            self_contained=self.self_contained,
            runtime_identifier=platform.runtime_identifier,
        )


@dataclass(frozen=True)
class RuntimeInfo:
    """Information about the runtime environment of an application."""

    env: typ.Mapping[str, str] = field(default_factory=lambda: dict(os.environ))
    home_dir: Path = field(default_factory=Path.home)
    platform: PlatformInfo = field(default_factory=PlatformInfo.detect)
    system_wide: bool = False

    @property
    def os(self) -> OperatingSystem:
        """Return the target operating system."""
        return self.platform.os

    @classmethod
    def current(cls, system_wide: bool = False) -> RuntimeInfo:
        """Detect and return current runtime information."""
        return cls(
            env=dict(os.environ),
            home_dir=Path.home(),
            platform=PlatformInfo.detect(),
            system_wide=system_wide,
        )
