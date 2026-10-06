"""Application installation sources."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from pathlib import Path

from net_install_manager.config.build_options import BuildOptions


class AppSourceKind(Enum):
    """Types of app sources"""

    CODE = "code"
    BUILT = "built"
    GIT_SOURCE = "git_source"
    GITHUB_RELEASE = "github_release"


@dataclass(frozen=True)
class CodeAppSource:
    """An installation from code."""

    project_path: Path
    build_options: BuildOptions
    kind: AppSourceKind = AppSourceKind.CODE

    def to_dict(self) -> dict:
        """Convert the CodeAppSource instance into a dictionary."""
        return {
            "kind": self.kind.value,
            "project_path": str(self.project_path),
            "build_options": self.build_options.to_dict(),
        }

    @classmethod
    def parse(cls, data: dict) -> CodeAppSource:
        """Parse a dictionary into a CodeAppSource instance."""

        return cls(
            project_path=Path(data["project_path"]),
            build_options=BuildOptions.parse(data["build_options"]),
        )


@dataclass(frozen=True)
class BuiltAppSource:
    """An installation from a built application."""

    build_path: Path
    kind: AppSourceKind = AppSourceKind.BUILT

    def to_dict(self) -> dict:
        """Convert the BuiltAppSource instance into a dictionary."""
        return {
            "kind": self.kind.value,
            "build_path": str(self.build_path),
        }

    @classmethod
    def parse(cls, data: dict) -> BuiltAppSource:
        """Parse a dictionary into a BuiltAppSource instance."""

        return cls(
            build_path=Path(data["build_path"]),
        )


@dataclass(frozen=True)
class GitCodeAppSource:
    """An installation from source code in a Git repository."""

    clone_url: str
    ref: str | None
    subpath: Path
    build_options: BuildOptions
    cache_dir: Path
    kind: AppSourceKind = AppSourceKind.GIT_SOURCE

    @property
    def project_path(self) -> Path:
        """Compute the full project path within the Git repository."""
        return self.cache_dir / self.subpath

    def to_dict(self) -> dict:
        """Convert the GitCodeAppSource instance into a dictionary."""
        return {
            "kind": self.kind.value,
            "clone_url": self.clone_url,
            "ref": self.ref,
            "subpath": str(self.subpath),
            "build_options": self.build_options.to_dict(),
            "cache_dir": str(self.cache_dir),
        }

    @classmethod
    def parse(cls, data: dict) -> GitCodeAppSource:
        """Parse a dictionary into a GitCodeAppSource instance."""

        return cls(
            clone_url=data["clone_url"],
            ref=data.get("ref"),
            subpath=Path(data["subpath"]),
            build_options=BuildOptions.parse(data["build_options"]),
            cache_dir=Path(data["cache_dir"]),
        )


@dataclass(frozen=True)
class GitHubReleaseAppSource:
    """An installation from a GitHub release."""

    owner: str
    repo: str
    asset_pattern: str
    tag: str | None = None
    kind: AppSourceKind = AppSourceKind.GITHUB_RELEASE

    def to_dict(self) -> dict:
        """Convert the GitHubReleaseAppSource instance into a dictionary."""
        return {
            "kind": self.kind.value,
            "owner": self.owner,
            "repo": self.repo,
            "asset_pattern": self.asset_pattern,
            "tag": self.tag,
        }

    @classmethod
    def parse(cls, data: dict) -> GitHubReleaseAppSource:
        """Parse a dictionary into a GitHubReleaseAppSource instance."""

        return cls(
            owner=data["owner"],
            repo=data["repo"],
            asset_pattern=data["asset_pattern"],
            tag=data.get("tag"),
        )


AppSource = CodeAppSource | BuiltAppSource | GitCodeAppSource | GitHubReleaseAppSource


def parse_app_source(data: dict) -> AppSource:
    """Parse a dictionary into an appropriate AppSource instance based on its kind."""

    kind = AppSourceKind(data.get("kind"))

    match kind:
        case AppSourceKind.CODE:
            return CodeAppSource.parse(data)
        case AppSourceKind.BUILT:
            return BuiltAppSource.parse(data)
        case AppSourceKind.GIT_SOURCE:
            return GitCodeAppSource.parse(data)
        case AppSourceKind.GITHUB_RELEASE:
            return GitHubReleaseAppSource.parse(data)
        case _:
            raise ValueError(f"Unknown app source kind: {kind}")


__all__ = [
    "AppSourceKind",
    "CodeAppSource",
    "BuiltAppSource",
    "GitCodeAppSource",
    "GitHubReleaseAppSource",
    "AppSource",
    "parse_app_source",
]
