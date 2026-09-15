"""Utilities for determining how to install an application

Possible installation types:
- From a binary (BIN)
- From a local csproj (CSP)
- From a .csproj in an active git repo (GIT)
"""

from dataclasses import dataclass
from pathlib import Path
import tempfile

from net_install_manager.errors import AppManagerError
from net_install_manager.utilities.git_tools import (
    GitSourceInfo,
    clone_or_update_repo,
)
from net_install_manager.utilities.github_release_tools import GitHubReleaseInfo


@dataclass(frozen=True)
class InstallSource:
    """Normalized local, Git, or GitHub release installation source."""

    local_path: str | None = None
    git_info: GitSourceInfo | None = None
    release_info: GitHubReleaseInfo | None = None
    project_path: str | None = None

    def __post_init__(self) -> None:
        source_count = sum(
            value is not None for value in (self.local_path, self.git_info, self.release_info)
        )
        if source_count != 1:
            raise ValueError("InstallSource must contain exactly one source kind.")

    @property
    def is_git(self) -> bool:
        """Return whether this source is backed by Git."""
        return self.git_info is not None

    @property
    def is_release(self) -> bool:
        """Return whether this source is a GitHub release."""
        return self.release_info is not None

    def resolve_root(self, cache_root: Path | None = None, quiet: bool = False) -> Path:
        """Resolve and return the local or cached repository root."""
        if self.git_info:
            return clone_or_update_repo(self.git_info, cache_root=cache_root, quiet=quiet)
        if self.release_info:
            raise AppManagerError("GitHub release sources must be prepared before installation.")
        assert self.local_path is not None
        return Path(self.local_path)


@dataclass
class BuildableInstallSource:
    """Represents a buildable install source.

    Attributes:
        csproj_path (Path): The path to the .csproj file.
        source_root (Path): The root directory of the source.
        source (InstallSource): Normalized local or Git source information.
    """

    csproj_path: Path
    source_root: Path
    source: InstallSource


def find_csproj_files(source_path: Path, include_common_subdirs: bool = False) -> list[Path]:
    """Find project files directly below a path or in common source subdirectories."""
    candidates = list(source_path.glob("*.csproj"))
    if not candidates and include_common_subdirs:
        candidates = list(source_path.glob("src/*/*.csproj"))
        if not candidates:
            candidates = list(source_path.glob("*/*.csproj"))
    return candidates


def get_csproj_path(source_path: Path) -> Path | None:
    """Return the path to the .csproj file if found, otherwise None.

    Args:
        source_path (Path): The root directory or file to search.

    Returns:
        Path | None: The path to the .csproj file if found, otherwise None.
    """
    if source_path.is_file() and source_path.suffix.lower() == ".csproj":
        return source_path

    if source_path.is_dir():
        csproj_candidates = find_csproj_files(source_path)
        if len(csproj_candidates) > 1:
            found = ", ".join(f"'{p}'" for p in csproj_candidates)
            raise AppManagerError(
                f"Multiple .csproj files found in '{source_path}' ({found}). "
                "Please specify the exact .csproj file to install via --project or URL."
            )
        if len(csproj_candidates) == 1:
            return csproj_candidates[0]

    return None


def get_buildable_source(
    source: InstallSource,
    cache_root: Path | None = None,
    quiet: bool = False,
):
    """Determine the buildable install source based on the provided inputs.

    Args:
        source (Path | str | None): The source directory, file, or Git URL.
        project_path (str | None): The relative path to the .csproj file within the source.
        config_csproj_path (Path | None): The path to the configuration .csproj file.
        cache_root (Path | None): The root directory for caching Git repositories.

    Returns:
        BuildableInstallSource | None: The buildable install source if found, otherwise None.
    """
    source_root = source.resolve_root(cache_root=cache_root, quiet=quiet)
    project_root = source_root / source.project_path if source.project_path else source_root
    csproj_path = get_csproj_path(project_root)
    if csproj_path:
        return BuildableInstallSource(
            csproj_path=csproj_path,
            source_root=source_root,
            source=source,
        )

    if source.is_git:
        raise AppManagerError(
            f"No .csproj file found in the source at '{project_root}'. "
            "Please specify the exact .csproj file via --project."
        )
    return None


def get_paths_with_buildable_source(binary_name: str) -> tuple[Path, Path, Path]:
    """Get temporary paths for building a source project.

    Args:
        binary_name (str): The name of the binary to be built.

    Returns:
        tuple[Path, Path, Path]: A tuple containing the copy source directory, the binary path,
                and the temporary staging directory.
    """
    temp_staging_dir = Path(tempfile.mkdtemp(prefix="ninman_publish_"))
    copy_source = temp_staging_dir
    binary_path = temp_staging_dir / binary_name
    return copy_source, binary_path, temp_staging_dir


def get_paths_no_buildable_source(
    binary_name: str,
    source: InstallSource,
    quiet: bool = False,
) -> tuple[Path, Path]:
    """Get paths for a precompiled binary or source directory.

    Args:
        binary_name (str): The name of the binary to be used.
        source (Path | str | None): The source directory or binary file path.

    Returns:
        tuple[Path, Path]: A tuple containing the copy source directory and the binary path.

    Raises:
        AppManagerError: If the binary is not found at the expected location.
    """
    source_as_path: Path
    source_as_path = source.resolve_root(quiet=quiet)
    if source.project_path:
        source_as_path = source_as_path / source.project_path

    if source_as_path.is_file():
        copy_source = source_as_path.parent
        binary_path = source_as_path
    else:
        copy_source = source_as_path
        binary_path = source_as_path / binary_name
    if not binary_path.exists():
        raise AppManagerError(f"Binary not found at expected location '{binary_path}'.")

    return copy_source, binary_path
