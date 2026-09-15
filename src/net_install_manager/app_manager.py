"""Unified application manager for installing and managing .NET applications."""

from __future__ import annotations

from pathlib import Path
import shutil
import logging
import semver

from net_install_manager.config import Config
from net_install_manager.paths import get_paths
from net_install_manager.registry import AppRegistry, TrackedApp
from net_install_manager.runtime_config import InstallOptions, RuntimeInfo
from net_install_manager.utilities.sys_platform import PlatformInfo, OperatingSystem
from net_install_manager.utilities.os_ops import (
    OsOpsProtocol,
    get_os_ops,
)
from net_install_manager.utilities.csproj_tools import (
    publish as dotnet_publish,
)
from net_install_manager.utilities.version_tools import (
    parse_semver,
    resolve_version,
)
from net_install_manager.utilities.install_tools import (
    InstallSource,
    get_buildable_source,
    get_paths_no_buildable_source,
    get_paths_with_buildable_source,
)
from net_install_manager.errors import AppManagerError, VersionRegressionError

logger = logging.getLogger(__name__)


class AppManager:
    """Manages the installation, rollback, uninstallation, and listing of a .NET application."""

    def __init__(
        self,
        config: Config,
        prefer_opt: bool = False,
        runtime: RuntimeInfo | None = None,
        os_ops: type[OsOpsProtocol] | None = None,
        registry: AppRegistry | None = None,
    ):
        self.config = config
        self.runtime = runtime or RuntimeInfo.current()
        self.os_ops = os_ops or get_os_ops(self.runtime.os)
        self.registry = registry or AppRegistry(runtime=self.runtime)
        self.paths = get_paths(
            config=self.config,
            prefer_opt=prefer_opt,
            runtime=self.runtime,
        )

    def with_config(self, config: Config) -> AppManager:
        """Return a new AppManager instance with the given configuration."""
        return AppManager(
            config=config,
            prefer_opt=self.prefer_opt,
            runtime=self.runtime,
            os_ops=self.os_ops,
            registry=self.registry,
        )

    @property
    def prefer_opt(self) -> bool:
        """Return whether target paths use /opt."""
        return self.paths.lib_dir.as_posix().startswith("/opt/")

    @property
    def platform(self) -> PlatformInfo:
        """Return platform info for this application manager."""
        return self.runtime.platform

    @property
    def target_os(self) -> OperatingSystem:
        """Return target operating system for backward compatibility."""
        return self.runtime.os

    def get_installed_versions(self) -> list[semver.Version]:
        """Return a sorted list of installed versions (highest first)."""
        if not self.paths.versions_dir.exists() or not self.paths.versions_dir.is_dir():
            return []

        versions: list[semver.Version] = []
        for item in self.paths.versions_dir.iterdir():
            if item.is_dir() and item.name != "current":
                v = parse_semver(item.name)
                if v is not None:
                    versions.append(v)

        versions.sort(reverse=True)
        return versions

    def get_current_version(self) -> semver.Version | None:
        """Get the version currently targeted by the 'current' link/junction."""
        if not self.paths.current_dir.exists(follow_symlinks=False):
            return None

        try:
            target = self.paths.current_dir.resolve()
            return parse_semver(target.name)
        except Exception:  # pylint: disable=broad-except
            return None

    def install(
        self,
        source: InstallSource,
        options: InstallOptions,
        registry_source: InstallSource | None = None,
    ) -> semver.Version:
        """Install application from source (.csproj, git repo, or precompiled directory)."""
        buildable_source = get_buildable_source(source=source, quiet=options.quiet)

        temp_staging_dir: Path | None = None
        copy_source: Path
        binary_path: Path

        try:
            if buildable_source:
                copy_source, binary_path, temp_staging_dir = get_paths_with_buildable_source(
                    binary_name=self.config.source_binary_name
                )
                logger.info(
                    "Publishing %s to %s...", buildable_source.csproj_path, temp_staging_dir
                )
                dotnet_publish(
                    csproj_path=buildable_source.csproj_path,
                    output_dir=temp_staging_dir,
                    opts=options.to_build_opts(platform=self.platform),
                    quiet=options.quiet,
                )
            else:
                copy_source, binary_path = get_paths_no_buildable_source(
                    binary_name=self.config.source_binary_name,
                    source=source,
                    quiet=options.quiet,
                )

            version = resolve_version(
                explicit_version=options.explicit_version,
                csproj_path=buildable_source.csproj_path if buildable_source else None,
                binary_path=binary_path,
                source_dir=buildable_source.source_root if buildable_source else copy_source,
            )

            # Version regression check
            installed_versions = self.get_installed_versions()
            if not options.force and installed_versions and installed_versions[0] >= version:
                raise VersionRegressionError(
                    f"Version {installed_versions[0]} is already installed, which is newer than "
                    f"or equal to the version being installed ({version}). Use --force to override."
                )

            target_version_dir = self.paths.versions_dir / str(version)

            # Transfer files
            logger.info("Transferring files to %s...", target_version_dir)
            self.os_ops.mirror_directory(
                src=copy_source,
                dest=target_version_dir,
                exclude_patterns=options.exclude_patterns,
            )

            # Executable & Permissions
            executable_path = target_version_dir / self.config.source_binary_name
            self.os_ops.make_executable(executable_path)
            if self.config.target_permissions:
                self.os_ops.set_permissions(
                    target_version_dir,
                    permissions=self.config.target_permissions,
                )

            # Update 'current' link
            logger.info("Updating 'current' link...")
            self.os_ops.update_current_link(
                versions_dir=self.paths.versions_dir,
                target_version=str(version),
                current_dir=self.paths.current_dir,
            )

            # Update launcher in bin
            target_current_exec = self.paths.current_dir / self.config.source_binary_name
            logger.info("Updating binary launcher in %s...", self.paths.bin_dir)
            self.os_ops.create_bin_launcher(
                bin_dir=self.paths.bin_dir,
                bin_name=self.config.binary_name,
                target_executable=target_current_exec,
            )

            # Prune old versions if keep_latest specified
            if options.keep_latest and options.keep_latest > 0:
                self.prune_versions(options.keep_latest)

            # Track in registry
            try:
                tracked = TrackedApp(
                    binary_name=self.config.binary_name,
                    app_directory=self.config.app_directory,
                    source_binary_name=self.config.source_binary_name,
                    source=registry_source
                    or (buildable_source.source if buildable_source else source),
                    lib_path=str(self.paths.lib_dir),
                    self_contained=options.self_contained,
                    release=options.release,
                    target_permissions=self.config.target_permissions,
                    installed_version=str(version),
                )
                self.registry.register(tracked)
            except Exception as e:  # pylint: disable=broad-except
                logger.warning("Could not register app in registry: %s", e)

            return version

        finally:
            if temp_staging_dir and temp_staging_dir.exists():
                shutil.rmtree(temp_staging_dir, ignore_errors=True)

    def prune_versions(self, keep_latest: int) -> list[semver.Version]:
        """Prune older installed versions, keeping only the specified number of latest versions."""
        installed = self.get_installed_versions()
        if len(installed) <= keep_latest:
            return []

        removed = []
        for v in installed[keep_latest:]:
            version_dir = self.paths.versions_dir / str(v)
            if version_dir.exists():
                self.os_ops.remove_link_or_dir(version_dir)
                removed.append(v)
        return removed

    def rollback(
        self, target_version: str | None = None, previous: bool = False
    ) -> semver.Version:
        """Rollback to a previous installed version."""
        installed = self.get_installed_versions()
        if not installed:
            raise AppManagerError("No installed versions found to rollback to.")

        current = self.get_current_version()
        selected_version: semver.Version | None = None

        if previous:
            # Find the version directly before the current version
            if current and len(installed) > 1:
                for idx, v in enumerate(installed):
                    if v == current and idx + 1 < len(installed):
                        selected_version = installed[idx + 1]
                        break
            if not selected_version and len(installed) > 1:
                selected_version = installed[1]
            elif not selected_version:
                raise AppManagerError(
                    "Cannot rollback with --previous: only one version is installed."
                )
        elif target_version:
            target_v = parse_semver(target_version)
            if not target_v:
                raise AppManagerError(f"Invalid semver version: '{target_version}'")
            if target_v not in installed:
                raise AppManagerError(f"Target version '{target_version}' is not installed.")
            selected_version = target_v
        else:
            raise AppManagerError("Must specify either a target version or --previous.")

        # Switch current link
        self.os_ops.update_current_link(
            versions_dir=self.paths.versions_dir,
            target_version=str(selected_version),
            current_dir=self.paths.current_dir,
        )

        # Update binary launcher
        target_current_exec = self.paths.current_dir / self.config.source_binary_name
        self.os_ops.create_bin_launcher(
            bin_dir=self.paths.bin_dir,
            bin_name=self.config.binary_name,
            target_executable=target_current_exec,
        )

        return selected_version

    def uninstall(self, target_version: str | None = None, all_versions: bool = False) -> None:
        """Uninstall a specific version or the entire application."""
        if all_versions:
            # Remove versions dir and current
            if self.target_os == OperatingSystem.WINDOWS:
                app_root = self.paths.lib_dir.parent
                self.os_ops.remove_link_or_dir(app_root)
            else:
                self.os_ops.remove_link_or_dir(self.paths.lib_dir)

            # Remove launchers
            cmd_launcher = self.paths.bin_dir / f"{self.config.binary_name}.cmd"
            posix_launcher = self.paths.bin_dir / self.config.binary_name
            self.os_ops.remove_link_or_dir(cmd_launcher)
            self.os_ops.remove_link_or_dir(posix_launcher)

            # Remove from tracking registry
            try:
                self.registry.remove(self.config.binary_name)
            except Exception as e:  # pylint: disable=broad-except
                logger.warning("Could not remove app from registry: %s", e)
            return

        if target_version:
            target_v = parse_semver(target_version)
            if not target_v:
                raise AppManagerError(f"Invalid semver version: '{target_version}'")

            target_dir = self.paths.versions_dir / str(target_v)
            if not target_dir.exists():
                raise AppManagerError(f"Version '{target_version}' is not installed.")

            current = self.get_current_version()

            self.os_ops.remove_link_or_dir(target_dir)

            # If the current link pointed to the deleted version, fallback to newest remaining
            if current == target_v:
                remaining = self.get_installed_versions()
                if remaining:
                    self.rollback(target_version=str(remaining[0]))
                else:
                    self.os_ops.remove_link_or_dir(self.paths.current_dir)
                    cmd_launcher = self.paths.bin_dir / f"{self.config.binary_name}.cmd"
                    posix_launcher = self.paths.bin_dir / self.config.binary_name
                    self.os_ops.remove_link_or_dir(cmd_launcher)
                    self.os_ops.remove_link_or_dir(posix_launcher)
            return

        raise AppManagerError("Must specify either --target-version or --all for uninstall.")


__all__ = ["AppManager", "AppManagerError", "VersionRegressionError"]
