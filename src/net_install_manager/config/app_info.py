"""Details of an application."""

from __future__ import annotations
from dataclasses import dataclass
from pathlib import Path

import semver

from net_install_manager.config.app_sources import AppSource, parse_app_source


@dataclass(frozen=True)
class AppInfo:
    """Information about an application."""

    binary_name: str
    source_binary_name: str
    lib_dir: Path
    installed_version: semver.Version
    app_source: AppSource
    exclude_patterns: list[str] | None = None
    target_permissions: str | int | None = None

    def to_dict(self) -> dict:
        """Convert the AppInfo instance into a dictionary."""
        return {
            "binary_name": self.binary_name,
            "source_binary_name": self.source_binary_name,
            "lib_dir": str(self.lib_dir),
            "installed_version": str(self.installed_version),
            "app_source": self.app_source.to_dict(),
            "exclude_patterns": self.exclude_patterns,
            "target_permissions": self.target_permissions,
        }

    @classmethod
    def parse(cls, data: dict) -> AppInfo:
        """Parse a dictionary into an AppInfo instance."""

        return cls(
            binary_name=data["binary_name"],
            source_binary_name=data["source_binary_name"],
            lib_dir=Path(data["lib_dir"]),
            installed_version=semver.Version.parse(data["installed_version"]),
            app_source=parse_app_source(data["app_source"]),
            exclude_patterns=data.get("exclude_patterns"),
            target_permissions=data.get("target_permissions"),
        )


__all__ = ["AppInfo"]
