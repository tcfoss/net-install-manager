"""Update the registry format to version 0.2.0."""

from __future__ import annotations

from dataclasses import dataclass
import logging
from pathlib import Path
import tempfile

import yaml

from net_install_manager.__version__ import __version__
from net_install_manager.config.build_options import BuildOptions
from net_install_manager.runtime.runtime import Runtime
from net_install_manager.core.registry import Registry
from net_install_manager.config import app_sources as aps
from net_install_manager.config.app_info import AppInfo
from net_install_manager.utilities.version import parse_semver
from net_install_manager.utilities import git as git_utils

logger = logging.getLogger(__name__)

# pylint: disable=duplicate-code


@dataclass(frozen=True)
class GitSourceInfo:
    """Parsed git source information."""

    clone_url: str
    ref: str | None = None
    subpath: str | None = None


@dataclass(frozen=True)
class GitHubReleaseInfo:
    """Coordinates and asset selection rules for a GitHub release source."""

    owner: str
    repo: str
    asset_pattern: str
    tag: str | None = None


@dataclass
class BuildableInstallSource:
    """Represents a buildable install source."""

    csproj_path: Path
    source_root: Path
    source: InstallSource


@dataclass(frozen=True)
class InstallSource:
    """Normalized local, Git, or GitHub release installation source."""

    local_path: str | None = None
    git_info: GitSourceInfo | None = None
    release_info: GitHubReleaseInfo | None = None
    project_path: str | None = None


@dataclass
class TrackedApp:
    """Represents an application tracked by the registry."""

    # pylint: disable=too-many-instance-attributes

    binary_name: str
    app_directory: str
    source_binary_name: str
    source: InstallSource
    lib_path: str = ""
    self_contained: bool = False
    release: bool = True
    target_permissions: str | None = None
    installed_version: str | None = None


def _load_registry_old(path: Path) -> dict[str, TrackedApp]:
    """Load the old registry format from the given path."""
    if not path.exists():
        return {}

    try:
        with open(path, "r", encoding="utf-8") as f:
            data = yaml.safe_load(f)
        if not isinstance(data, dict):
            raise ValueError("Old registry must contain a mapping of applications.")

        apps = {}
        for name, entry in data.items():
            if not isinstance(entry, dict):
                raise ValueError(f"Old registry entry '{name}' must be a mapping.")
            if isinstance(entry.get("source"), dict):
                source_data = entry["source"]
                if isinstance(source_data.get("git_info"), dict):
                    source_data["git_info"] = GitSourceInfo(**source_data["git_info"])
                if isinstance(source_data.get("release_info"), dict):
                    source_data["release_info"] = GitHubReleaseInfo(**source_data["release_info"])
                entry["source"] = InstallSource(**source_data)
            apps[name] = TrackedApp(**entry)
        return apps
    except Exception as e:  # pylint: disable=broad-except
        logger.error("Failed to load old registry from path %s: %s", path, e)
        raise e


def _extract_install_source(app: TrackedApp, runtime: Runtime) -> aps.AppSource | None:
    """Extract the install source from a tracked application."""
    build_options = BuildOptions(
        debug_mode=not app.release, self_contained=app.self_contained, runtime_identifier=None
    )

    if app.source.release_info:
        return aps.GitHubReleaseAppSource(
            owner=app.source.release_info.owner,
            repo=app.source.release_info.repo,
            asset_pattern=app.source.release_info.asset_pattern,
        )
    if app.source.git_info:
        if app.source.git_info.subpath:
            subpath = Path(app.source.git_info.subpath)
        elif app.source.project_path:
            subpath = Path(app.source.project_path)
        else:
            subpath = Path()

        return aps.GitCodeAppSource(
            clone_url=app.source.git_info.clone_url,
            ref=app.source.git_info.ref,
            subpath=subpath,
            build_options=build_options,
            cache_dir=git_utils._get_cache_dir(  # pylint: disable=protected-access
                app.source.git_info.clone_url, runtime
            ),
        )
    if app.source.project_path:
        return aps.CodeAppSource(
            project_path=Path(app.source.project_path),
            build_options=build_options,
        )
    if app.source.local_path:
        return aps.BuiltAppSource(
            build_path=Path(app.source.local_path),
        )
    return None


def main(runtime: Runtime):
    """Entry point for the migration script."""

    try:
        _ = Registry(runtime)
        return 0
    except Exception:  # pylint: disable=broad-except
        pass

    try:
        old_registry = _load_registry_old(runtime.registry_path)
    except Exception as e:  # pylint: disable=broad-except
        logger.error("Failed to load old registry: %s", e)
        return 1

    new_entries: dict[str, dict | str] = {"__NINMAN_VERSION__": str(__version__)}

    for name, app in old_registry.items():

        if not app.installed_version:
            logger.error("Application %s has no installed version; migration aborted.", name)
            return 1
        app_version = parse_semver(app.installed_version)
        if not app_version:
            logger.error(
                "Application %s has an invalid installed version; migration aborted.", name
            )
            return 1

        source = _extract_install_source(app, runtime)
        if not source:
            logger.error("Failed to extract source for app %s; migration aborted.", name)
            return 1

        app_info = AppInfo(
            binary_name=app.binary_name,
            source_binary_name=app.source_binary_name,
            lib_dir=Path(app.lib_path),
            installed_version=app_version,
            exclude_patterns=None,
            app_source=source,
        )
        new_entries[name] = app_info.to_dict()

    contents = yaml.safe_dump(new_entries)
    temporary_path = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="w",
            encoding="utf-8",
            dir=runtime.registry_path.parent,
            delete=False,
        ) as registry_file:
            temporary_path = registry_file.name
            registry_file.write(contents)
        Path(temporary_path).replace(runtime.registry_path)
    finally:
        if temporary_path is not None:
            Path(temporary_path).unlink(missing_ok=True)

    return 0
