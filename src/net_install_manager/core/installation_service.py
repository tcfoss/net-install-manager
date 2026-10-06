"""Application installation workflow and source artifact preparation."""

from __future__ import annotations

from dataclasses import dataclass, replace
from enum import Enum, auto
import logging
from pathlib import Path
import tempfile

import semver

from net_install_manager.config import app_sources as aps
from net_install_manager.config.app_info import AppInfo
from net_install_manager.config.build_options import BuildOptions
from net_install_manager.config.ninman_manifest import NinmanManifest
from net_install_manager.config.paths import Paths, get_paths, get_paths_from_app_info
from net_install_manager.core import errors
from net_install_manager.core.artifact_provider import (
    ArtifactProvider,
    DefaultArtifactProvider,
    PreparedArtifact,
)
from net_install_manager.core.os_ops import OsOpsProtocol, get_os_ops
from net_install_manager.core.registry import Registry
from net_install_manager.runtime.runtime import Runtime
from net_install_manager.utilities import csproj as cs_utils
from net_install_manager.utilities import version as version_utils

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class TargetOptions:
    """Optional application names supplied by the caller."""

    binary_name: str | None = None
    source_binary_name: str | None = None
    app_dir_name: str | None = None


@dataclass(frozen=True)
class ResolvedTargets:
    """Complete application names for installation."""

    binary_name: str
    source_binary_name: str
    app_dir_name: str


@dataclass(frozen=True)
class InstallationOptions:
    """Policy and file options for an installation."""

    force: bool = False
    version_override: semver.Version | None = None
    exclude_patterns: list[str] | None = None
    target_permissions: str | int | None = None
    prefer_opt: bool = False
    token: str | None = None


@dataclass(frozen=True)
class InstallationRequest:
    """Input required to install an application, independent of its CLI source."""

    app_source: aps.AppSource
    targets: TargetOptions
    installation_options: InstallationOptions
    build_options: BuildOptions
    manifest_path: Path | None = None


@dataclass(frozen=True)
class InstallationResult:
    """Details of the successfully installed application."""

    app: AppInfo
    paths: Paths


class _KeepExisting(Enum):
    VALUE = auto()


KEEP_EXISTING = _KeepExisting.VALUE


@dataclass(frozen=True)
class UpgradeOptions:
    """Options for upgrading an installed application."""

    force: bool = False
    version_override: semver.Version | None = None
    token: str | None = None
    new_ref: str | None | _KeepExisting = KEEP_EXISTING
    new_release_tag: str | None | _KeepExisting = KEEP_EXISTING


@dataclass(frozen=True)
class UpgradeRequest:
    """Input required to upgrade an installed application."""

    app_name: str
    upgrade_options: UpgradeOptions


@dataclass(frozen=True)
class UpgradeResult:
    """Details of the successfully upgraded application."""

    app: AppInfo
    paths: Paths


def resolve_manifest(
    manifest_path: Path | None,
    dist_dir: Path,
    source_dir: Path | None = None,
) -> NinmanManifest | None:
    """Load an explicit manifest or discover one beside the artifact or source."""

    if manifest_path is not None:
        return NinmanManifest.load(manifest_path)

    searched: set[Path] = set()
    for directory in (dist_dir, source_dir):
        if directory is None:
            continue
        resolved_dir = directory.resolve()
        if resolved_dir in searched:
            continue
        searched.add(resolved_dir)
        for filename in ("ninman.yaml", "ninman.yml"):
            candidate = directory / filename
            if candidate.is_file():
                return NinmanManifest.load(candidate)
    return None


class InstallationService:
    """Orchestrate building, activating, and registering an application install."""

    def __init__(
        self,
        runtime: Runtime,
        registry: Registry | None = None,
        artifacts: ArtifactProvider | None = None,
        os_ops: type[OsOpsProtocol] | None = None,
    ) -> None:
        self._runtime = runtime
        self._registry = registry or Registry(runtime)
        self._artifacts = artifacts or DefaultArtifactProvider()
        self._os_ops = os_ops or get_os_ops(runtime.os)

    def install(
        self,
        request: InstallationRequest,
    ) -> InstallationResult:
        """Install an application and register its resolved source and location."""

        with tempfile.TemporaryDirectory() as temporary_directory:
            prepared = self._artifacts.prepare_and_build(
                request.app_source,
                request.build_options,
                self._runtime,
                Path(temporary_directory),
                request.installation_options.token,
            )
            manifest = resolve_manifest(
                request.manifest_path,
                prepared.directory,
                prepared.project_path.parent if prepared.project_path else None,
            )
            targets = self._resolve_targets(request.targets, manifest, prepared.project_path)
            targets = self._find_source_binary(prepared.directory, targets)
            version = self._resolve_version(
                prepared, targets, request.installation_options.version_override
            )
            self._guard_existing_install(
                version, targets.binary_name, request.installation_options.force
            )

            paths = get_paths(
                self._runtime,
                targets.app_dir_name,
                targets.binary_name,
                request.installation_options.prefer_opt,
            )
            version_dir = paths.versions_dir / str(version)
            self._os_ops.mirror_directory(
                prepared.directory,
                version_dir,
                exclude_patterns=request.installation_options.exclude_patterns,
            )
            self._os_ops.make_executable(version_dir / targets.source_binary_name)
            if request.installation_options.target_permissions is not None:
                self._os_ops.set_permissions(
                    version_dir, request.installation_options.target_permissions
                )

            self._os_ops.update_current_link(paths.versions_dir, str(version), paths.current_dir)
            self._os_ops.create_bin_launcher(
                paths.bin_dir,
                targets.binary_name,
                paths.current_dir / targets.source_binary_name,
            )

            app = AppInfo(
                binary_name=targets.binary_name,
                source_binary_name=targets.source_binary_name,
                lib_dir=paths.lib_dir,
                installed_version=version,
                app_source=prepared.app_source,
                exclude_patterns=request.installation_options.exclude_patterns,
                target_permissions=request.installation_options.target_permissions,
            )
            self._registry.set(targets.binary_name, app)
            return InstallationResult(app=app, paths=paths)

    def upgrade(self, request: UpgradeRequest) -> UpgradeResult:
        """Upgrade an application."""

        app = self._registry.get(request.app_name)
        if not app:
            raise errors.AppNotRegisteredError(request.app_name, self._runtime.registry_path)

        app, build_options = self._apply_upgrade_modifications_get_build_options(app, request)

        with tempfile.TemporaryDirectory() as temp_dir:
            prepared = self._artifacts.prepare_and_build(
                app.app_source,
                build_options,
                self._runtime,
                Path(temp_dir),
                request.upgrade_options.token,
            )

            targets = ResolvedTargets(
                binary_name=app.binary_name,
                source_binary_name=app.source_binary_name,
                app_dir_name=app.lib_dir.name,
            )
            targets = self._find_source_binary(prepared.directory, targets)
            version = self._resolve_version(
                prepared, targets, request.upgrade_options.version_override
            )
            self._guard_existing_upgrade(version, app.binary_name, request.upgrade_options.force)

            paths = get_paths_from_app_info(self._runtime, app)
            version_dir = paths.versions_dir / str(version)
            self._os_ops.mirror_directory(prepared.directory, version_dir, app.exclude_patterns)
            self._os_ops.make_executable(version_dir / targets.source_binary_name)
            if app.target_permissions is not None:
                self._os_ops.set_permissions(version_dir, app.target_permissions)

            self._os_ops.update_current_link(paths.versions_dir, str(version), paths.current_dir)

            self._os_ops.create_bin_launcher(
                paths.bin_dir,
                app.binary_name,
                paths.current_dir / targets.source_binary_name,
            )

            app = replace(
                app,
                installed_version=version,
                source_binary_name=targets.source_binary_name,
            )
            self._registry.set(app.binary_name, app)

            return UpgradeResult(app=app, paths=paths)

    def _resolve_targets(
        self,
        requested: TargetOptions,
        manifest: NinmanManifest | None,
        project_path: Path | None,
    ) -> ResolvedTargets:
        inferred: TargetOptions | None = None
        if project_path:
            assembly_name = cs_utils.get_assembly_name_from_csproj(project_path)
            inferred = TargetOptions(
                binary_name=self._normalize_binary_name(assembly_name),
                source_binary_name=assembly_name,
                app_dir_name=assembly_name,
            )

        binary_name = requested.binary_name or (manifest.binary_name if manifest else None)
        source_binary_name = requested.source_binary_name or (
            manifest.source_binary_name if manifest else None
        )
        app_dir_name = requested.app_dir_name or (manifest.app_dir_name if manifest else None)

        binary_name = binary_name or (inferred.binary_name if inferred else None)
        source_binary_name = source_binary_name or (
            inferred.source_binary_name if inferred else None
        )
        app_dir_name = app_dir_name or (inferred.app_dir_name if inferred else None)

        if not source_binary_name:
            raise errors.UnresolvedTargetError("source_binary_name")
        if not binary_name:
            binary_name = self._normalize_binary_name(source_binary_name)
        if not app_dir_name:
            app_dir_name = binary_name

        return ResolvedTargets(binary_name, source_binary_name, app_dir_name)

    @staticmethod
    def _resolve_version(
        artifact: PreparedArtifact,
        targets: ResolvedTargets,
        version_override: semver.Version | None,
    ) -> semver.Version:
        if version_override is not None:
            return version_override
        if version := version_utils.get_version_from_binary(
            artifact.directory / targets.source_binary_name
        ):
            return version
        if artifact.project_path:
            if version := cs_utils.get_version_from_csproj(artifact.project_path):
                return version
        raise errors.UnresolvedVersionError(targets.binary_name)

    def _apply_upgrade_modifications_get_build_options(
        self, app: AppInfo, request: UpgradeRequest
    ) -> tuple[AppInfo, BuildOptions]:
        build_options = BuildOptions()
        match app.app_source:
            case aps.CodeAppSource() as cs_source:
                build_options = cs_source.build_options
            case aps.GitCodeAppSource() as git_source:
                build_options = git_source.build_options
                new_ref = request.upgrade_options.new_ref
                if new_ref is not KEEP_EXISTING:
                    new_git_source = replace(git_source, ref=new_ref)
                    app = replace(app, app_source=new_git_source)
            case aps.GitHubReleaseAppSource() as gh_source:
                new_release_tag = request.upgrade_options.new_release_tag
                if new_release_tag is not KEEP_EXISTING:
                    new_release_source = replace(gh_source, tag=new_release_tag)
                    app = replace(app, app_source=new_release_source)
        return (app, build_options)

    def _guard_existing_install(self, version: semver.Version, app_name: str, force: bool) -> None:
        registered_app = self._registry.get(app_name)
        if registered_app is None:
            return
        if not force:
            raise errors.AppAlreadyInstalledError(app_name, registered_app.lib_dir)

        logger.warning(
            "Forcing installation of '%s' over existing installation at '%s' (new version %s)",
            app_name,
            registered_app.lib_dir,
            version,
        )

    def _guard_existing_upgrade(self, version: semver.Version, app_name: str, force: bool) -> None:
        registered_app, versions = self._registry.get_app_with_versions(app_name)

        if version not in versions.versions:
            return
        if not force:
            raise errors.VersionAlreadyInstalledError(
                app_name, str(version), registered_app.lib_dir
            )

        logger.warning(
            "Overwriting existing version '%s' of '%s' at '%s'",
            version,
            app_name,
            registered_app.lib_dir,
        )

    @staticmethod
    def _normalize_binary_name(binary_name: str) -> str:
        """Normalize the binary name by lowercasing and replacing dots with hyphens."""
        binary_name = binary_name.lower()
        if binary_name.endswith(".exe") or binary_name.endswith(".dll"):
            binary_name = binary_name.rsplit(".", 1)[0]
        return binary_name.lower().replace(".", "-")

    @staticmethod
    def _find_source_binary(working_dir: Path, targets: ResolvedTargets) -> ResolvedTargets:
        """Find the source binary in the working directory, appending .exe or .dll if necessary."""

        bin_path = working_dir / targets.source_binary_name
        if bin_path.exists() and bin_path.is_file():
            return targets

        binary_name = targets.source_binary_name
        if binary_name.lower().endswith(".exe") or binary_name.lower().endswith(".dll"):
            binary_name = binary_name.rsplit(".", 1)[0]

        bin_path = working_dir / binary_name
        if bin_path.exists() and bin_path.is_file():
            targets = replace(targets, source_binary_name=binary_name)
            return targets

        bin_path = working_dir / f"{binary_name}.exe"
        if bin_path.exists() and bin_path.is_file():
            targets = replace(targets, source_binary_name=f"{binary_name}.exe")
            return targets

        bin_path = working_dir / f"{binary_name}.dll"
        if bin_path.exists() and bin_path.is_file():
            targets = replace(targets, source_binary_name=f"{binary_name}.dll")
            return targets

        raise errors.ExecutableNotFoundError(targets.source_binary_name, working_dir)
