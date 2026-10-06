from dataclasses import replace
from pathlib import Path

import pytest
import semver

from net_install_manager.config import app_sources
from net_install_manager.config.app_info import AppInfo
from net_install_manager.config.build_options import BuildOptions
from net_install_manager.core import errors
from net_install_manager.core.artifact_provider import PreparedArtifact
from net_install_manager.core.installation_service import (
    InstallationOptions,
    InstallationRequest,
    InstallationService,
    ResolvedTargets,
    TargetOptions,
    UpgradeOptions,
    UpgradeRequest,
    resolve_manifest,
)
from net_install_manager.core.registry import Registry
from net_install_manager.runtime.runtime import Runtime
from tests.shared_fixtures.artifact_provider_fixtures import get_test_artifact_provider
from tests.shared_fixtures.os_ops_fixtures import get_test_os_ops


def _runtime(tmp_path: Path) -> Runtime:
    return replace(
        Runtime.current(),
        home_dir=tmp_path,
        registry_path=tmp_path / "config" / "apps.yaml",
    )


def _app(tmp_path: Path, source: app_sources.AppSource | None = None) -> AppInfo:
    return AppInfo(
        binary_name="demo",
        source_binary_name="Demo",
        lib_dir=tmp_path / ".local" / "lib" / "DemoApp",
        installed_version=semver.Version(1, 0, 0),
        app_source=source or app_sources.BuiltAppSource(tmp_path / "build"),
    )


def test_resolve_manifest_handles_missing_and_duplicate_source_directories(tmp_path):
    dist_dir = tmp_path / "dist"

    assert resolve_manifest(None, dist_dir) is None
    assert resolve_manifest(None, dist_dir, dist_dir) is None


@pytest.mark.parametrize(
    ("requested", "expected_target"),
    [
        (TargetOptions(), "binary_name"),
        (TargetOptions(binary_name="demo"), "source_binary_name"),
        (
            TargetOptions(binary_name="demo", source_binary_name="Demo"),
            "app_dir_name",
        ),
    ],
)
def test_resolve_targets_requires_all_names(tmp_path, requested, expected_target):
    service = InstallationService(_runtime(tmp_path))

    with pytest.raises(errors.UnresolvedTargetError) as exc_info:
        service._resolve_targets(requested, None, None)

    assert exc_info.value.target_name == expected_target


def test_resolve_targets_infers_project_names_and_applies_requested_override(
    monkeypatch, tmp_path
):
    service = InstallationService(_runtime(tmp_path))
    project_path = tmp_path / "Demo.Tools.csproj"
    monkeypatch.setattr(
        "net_install_manager.core.installation_service.cs_utils.get_assembly_name_from_csproj",
        lambda _path: "Demo.Tools",
    )

    targets = service._resolve_targets(
        TargetOptions(binary_name="chosen-name"), None, project_path
    )

    assert targets == ResolvedTargets("chosen-name", "Demo.Tools", "Demo.Tools")


@pytest.mark.parametrize(
    ("override", "binary_version", "project_version", "expected"),
    [
        (
            semver.Version(4, 0, 0),
            semver.Version(2, 0, 0),
            semver.Version(3, 0, 0),
            semver.Version(4, 0, 0),
        ),
        (None, semver.Version(2, 0, 0), semver.Version(3, 0, 0), semver.Version(2, 0, 0)),
        (None, None, semver.Version(3, 0, 0), semver.Version(3, 0, 0)),
    ],
)
def test_resolve_version_uses_override_then_binary_then_project(
    monkeypatch, tmp_path, override, binary_version, project_version, expected
):
    artifact = PreparedArtifact(
        app_sources.BuiltAppSource(tmp_path / "build"),
        tmp_path / "dist",
        tmp_path / "Demo.csproj",
    )
    targets = ResolvedTargets("demo", "Demo", "Demo")
    monkeypatch.setattr(
        "net_install_manager.core.installation_service.version_utils.get_version_from_binary",
        lambda _path: binary_version,
    )
    monkeypatch.setattr(
        "net_install_manager.core.installation_service.cs_utils.get_version_from_csproj",
        lambda _path: project_version,
    )

    version = InstallationService._resolve_version(artifact, targets, override)

    assert version == expected


def test_resolve_version_raises_when_no_version_can_be_determined(monkeypatch, tmp_path):
    artifact = PreparedArtifact(
        app_sources.BuiltAppSource(tmp_path / "build"),
        tmp_path / "dist",
        None,
    )
    monkeypatch.setattr(
        "net_install_manager.core.installation_service.version_utils.get_version_from_binary",
        lambda _path: None,
    )

    with pytest.raises(errors.UnresolvedVersionError) as exc_info:
        InstallationService._resolve_version(
            artifact,
            ResolvedTargets("demo", "Demo", "Demo"),
            None,
        )

    assert exc_info.value.app_name == "demo"


@pytest.mark.parametrize(
    ("source", "options", "expected_source", "expected_build_options"),
    [
        (
            app_sources.CodeAppSource(Path("/Demo.csproj"), BuildOptions(debug_mode=True)),
            UpgradeOptions(),
            app_sources.CodeAppSource(Path("/Demo.csproj"), BuildOptions(debug_mode=True)),
            BuildOptions(debug_mode=True),
        ),
        (
            app_sources.GitCodeAppSource(
                "https://example.com/demo.git",
                "main",
                Path("Demo.csproj"),
                BuildOptions(self_contained=True),
                Path("/cache"),
            ),
            UpgradeOptions(new_ref=None),
            app_sources.GitCodeAppSource(
                "https://example.com/demo.git",
                None,
                Path("Demo.csproj"),
                BuildOptions(self_contained=True),
                Path("/cache"),
            ),
            BuildOptions(self_contained=True),
        ),
        (
            app_sources.GitHubReleaseAppSource("owner", "repo", "linux", "v1"),
            UpgradeOptions(new_release_tag=None),
            app_sources.GitHubReleaseAppSource("owner", "repo", "linux", None),
            BuildOptions(),
        ),
        (
            app_sources.BuiltAppSource(Path("/build")),
            UpgradeOptions(),
            app_sources.BuiltAppSource(Path("/build")),
            BuildOptions(),
        ),
    ],
)
def test_apply_upgrade_modifications_preserves_or_updates_source(
    tmp_path, source, options, expected_source, expected_build_options
):
    service = InstallationService(_runtime(tmp_path))
    app = _app(tmp_path, source)

    updated_app, build_options = service._apply_upgrade_modifications_get_build_options(
        app, UpgradeRequest("demo", options)
    )

    assert updated_app.app_source == expected_source
    assert build_options == expected_build_options


def test_guard_existing_install_allows_unregistered_app(tmp_path):
    service = InstallationService(_runtime(tmp_path))

    service._guard_existing_install(semver.Version(2, 0, 0), "demo", False)


def test_guard_existing_install_rejects_without_force(tmp_path):
    runtime = _runtime(tmp_path)
    registry = Registry(runtime)
    app = _app(tmp_path)
    registry.set(app.binary_name, app)
    service = InstallationService(runtime, registry=registry)

    with pytest.raises(errors.AppAlreadyInstalledError):
        service._guard_existing_install(semver.Version(2, 0, 0), "demo", False)


def test_guard_existing_install_allows_force_and_warns(tmp_path, caplog):
    runtime = _runtime(tmp_path)
    registry = Registry(runtime)
    app = _app(tmp_path)
    registry.set(app.binary_name, app)
    service = InstallationService(runtime, registry=registry)

    service._guard_existing_install(semver.Version(2, 0, 0), "demo", True)

    assert "forcing installation" in caplog.text.lower()


def test_guard_existing_upgrade_allows_new_version(tmp_path):
    runtime = _runtime(tmp_path)
    registry = Registry(runtime)
    app = _app(tmp_path)
    (app.lib_dir / "1.0.0").mkdir(parents=True)
    registry.set(app.binary_name, app)
    service = InstallationService(runtime, registry=registry)

    service._guard_existing_upgrade(semver.Version(2, 0, 0), "demo", False)


def test_guard_existing_upgrade_rejects_duplicate_without_force(tmp_path):
    runtime = _runtime(tmp_path)
    registry = Registry(runtime)
    app = _app(tmp_path)
    (app.lib_dir / "1.0.0").mkdir(parents=True)
    registry.set(app.binary_name, app)
    service = InstallationService(runtime, registry=registry)

    with pytest.raises(errors.VersionAlreadyInstalledError):
        service._guard_existing_upgrade(semver.Version(1, 0, 0), "demo", False)


def test_guard_existing_upgrade_allows_force_and_warns(tmp_path, caplog):
    runtime = _runtime(tmp_path)
    registry = Registry(runtime)
    app = _app(tmp_path)
    (app.lib_dir / "1.0.0").mkdir(parents=True)
    registry.set(app.binary_name, app)
    service = InstallationService(runtime, registry=registry)

    service._guard_existing_upgrade(semver.Version(1, 0, 0), "demo", True)

    assert "overwriting existing version" in caplog.text.lower()


def test_upgrade_raises_for_unregistered_application(tmp_path):
    service = InstallationService(_runtime(tmp_path))

    with pytest.raises(errors.AppNotRegisteredError):
        service.upgrade(UpgradeRequest("demo", UpgradeOptions()))


def test_install_applies_requested_target_permissions(tmp_path):
    runtime = _runtime(tmp_path)
    build_dir = tmp_path / "build"
    build_dir.mkdir()
    calls = {}
    request = InstallationRequest(
        app_source=app_sources.BuiltAppSource(build_dir),
        targets=TargetOptions("demo", "Demo", "DemoApp"),
        installation_options=InstallationOptions(
            version_override=semver.Version(2, 0, 0),
            target_permissions=0o755,
        ),
        build_options=BuildOptions(),
    )

    result = InstallationService(
        runtime,
        artifacts=get_test_artifact_provider(build_dir, None),
        os_ops=get_test_os_ops(calls),
    ).install(request)

    assert calls["set_permissions"] == (result.paths.versions_dir / "2.0.0", 0o755)
