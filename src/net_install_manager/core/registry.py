"""Registry of installed applications."""

from dataclasses import dataclass
import logging
from pathlib import Path
import tempfile

import semver
import yaml
from net_install_manager.config.paths import get_paths_from_app_info
from net_install_manager.core import errors
from net_install_manager.runtime.runtime import Runtime
from net_install_manager.config.app_info import AppInfo
from net_install_manager.__version__ import __version__
from net_install_manager.utilities.version import parse_semver

logger = logging.getLogger(__name__)


class Registry:
    """Manages the registry of installed applications."""

    def __init__(self, runtime: Runtime):
        self._runtime = runtime
        self._version, self._registry = self._load()

    @property
    def version(self) -> semver.Version:
        """Return the version of the app last used to modify the registry."""
        return self._version

    def _load(self) -> tuple[semver.Version, dict[str, AppInfo]]:
        logger.info("Loading registry from '%s'.", self._runtime.registry_path)

        if not self._runtime.registry_path.exists():
            logger.info(
                "Registry file does not exist at '%s'. Returning empty registry.",
                self._runtime.registry_path,
            )
            return __version__, {}

        with open(self._runtime.registry_path, "r", encoding="utf-8") as f:
            contents = yaml.safe_load(f) or {}

        version = parse_semver(contents["__NINMAN_VERSION__"])
        if not version:
            raise ValueError("Failed to parse registry version.")
        del contents["__NINMAN_VERSION__"]

        registry = {}
        for name, entry in contents.items():
            registry[name] = AppInfo.parse(entry)

        return version, registry

    def _save(self):
        if not self._runtime.registry_path.parent.exists():
            logger.info(
                "Registry directory does not exist at '%s'. Creating it.",
                self._runtime.registry_path.parent,
            )
            self._runtime.registry_path.parent.mkdir(parents=True, exist_ok=True)

        logger.info("Saving registry to '%s'.", self._runtime.registry_path)

        contents = yaml.safe_dump(
            {
                "__NINMAN_VERSION__": str(__version__),
                **{name: app_info.to_dict() for name, app_info in self._registry.items()},
            }
        )
        temporary_path = None
        try:
            with tempfile.NamedTemporaryFile(
                mode="w",
                encoding="utf-8",
                dir=self._runtime.registry_path.parent,
                delete=False,
            ) as registry_file:
                temporary_path = registry_file.name
                registry_file.write(contents)
            Path(temporary_path).replace(self._runtime.registry_path)
        finally:
            if temporary_path is not None:
                Path(temporary_path).unlink(missing_ok=True)

    def get_installed_apps(self) -> list[tuple[str, semver.Version]]:
        """Returns a list of summaries of installed applications."""
        return [(name, app_info.installed_version) for name, app_info in self._registry.items()]

    def get_installed_versions(self, name: str) -> InstalledVersions | None:
        """Retrieve the installed versions of an application from the registry."""
        app_info = self._registry.get(name)
        if not app_info:
            return None

        paths = get_paths_from_app_info(self._runtime, app_info)
        logger.info(
            "Retrieving installed versions for application '%s' from '%s'.",
            name,
            paths.versions_dir,
        )
        if not paths.versions_dir.exists() or not paths.versions_dir.is_dir():
            raise errors.InstallationDirectoryNotFoundError(name, paths.versions_dir)

        versions = []

        for version_dir in paths.versions_dir.iterdir():
            if version_dir.is_dir() and version_dir.name != "current":
                try:
                    version = semver.Version.parse(version_dir.name)
                    versions.append(version)
                except ValueError:
                    logger.warning(
                        "Failed to parse version from directory name: %s", version_dir.name
                    )
                    continue

        return InstalledVersions(versions=versions, current=app_info.installed_version)

    def get_app_with_versions(self, name: str) -> tuple[AppInfo, InstalledVersions]:
        """Retrieve an application and its installed versions from the registry.
        Raises:
            errors.AppNotRegisteredError: If the application is not registered in the registry.

        """
        app_info = self._registry.get(name)
        if not app_info:
            raise errors.AppNotRegisteredError(name, self._runtime.registry_path)

        installed_versions = self.get_installed_versions(name)
        if not installed_versions or not installed_versions.versions:
            logger.error("No installed versions found for registered application '%s'.", name)
            raise errors.NoVersionsInstalledError(name)

        return app_info, installed_versions

    def get(self, name: str) -> AppInfo | None:
        """Retrieve an application from the registry by its name."""

        return self._registry.get(name)

    def set(self, name: str, app_info: AppInfo):
        """Add or update an application in the registry."""
        logger.info(
            "Adding or updating application '%s' in the registry. Details: %s", name, app_info
        )
        self._registry[name] = app_info
        self._save()

    def remove(self, name: str):
        """Remove an application from the registry."""

        if name in self._registry:
            logger.info("Removing application '%s' from the registry.", name)
            del self._registry[name]
            self._save()


@dataclass(frozen=True)
class InstalledVersions:
    """Currently-installed versions of an application."""

    versions: list[semver.Version]
    current: semver.Version | None
