from dataclasses import replace
import argparse
from pathlib import Path

import pytest
import semver

from net_install_manager.commands.helpers import installation as installation_helpers
from net_install_manager.config import app_sources
from net_install_manager.config.app_info import AppInfo
from net_install_manager.config.build_options import BuildOptions
from net_install_manager.core.installation_service import (
    DefaultArtifactProvider,
    InstallationOptions,
    InstallationRequest,
    InstallationService,
    KEEP_EXISTING,
    TargetOptions,
    UpgradeOptions,
    UpgradeRequest,
)
from net_install_manager.core.registry import Registry
from net_install_manager.runtime.runtime import Runtime
from net_install_manager.config.ninman_manifest import NinmanManifest
from net_install_manager.core.installation_service import resolve_manifest
from net_install_manager.commands.install import InstallCommand
from net_install_manager.commands.upgrade import UpgradeCommand
from tests.shared_fixtures.os_ops_fixtures import OpsOptions, get_test_os_ops
from tests.shared_fixtures.artifact_provider_fixtures import get_test_artifact_provider


def test_extract_installation_options_parses_version_override():
    args = argparse.Namespace(
        force=False,
        version_override="1.2.3",
        asset_pattern=None,
        exclude_patterns=None,
        target_permissions=None,
        prefer_opt=False,
        token=None,
    )

    options = installation_helpers.extract_installation_options(args)

    assert options.version_override == semver.Version(1, 2, 3)


def _write_manifest(directory: Path, filename: str, binary_name: str) -> Path:
    directory.mkdir(parents=True, exist_ok=True)
    path = directory / filename
    path.write_text(
        f"binary_name: {binary_name}\nsource_binary_name: App\napp_dir_name: App\n",
        encoding="utf-8",
    )
    return path


def test_resolve_manifest_prefers_explicit_path(tmp_path):
    dist_dir = tmp_path / "dist"
    source_dir = tmp_path / "source"
    _write_manifest(dist_dir, "ninman.yaml", "dist-app")
    _write_manifest(source_dir, "ninman.yml", "source-app")
    explicit_path = _write_manifest(tmp_path, "custom.yml", "explicit-app")

    manifest = resolve_manifest(explicit_path, dist_dir, source_dir)

    assert manifest == NinmanManifest("explicit-app", "App", "App")


def test_resolve_manifest_prefers_dist_then_falls_back_to_source(tmp_path):
    dist_dir = tmp_path / "dist"
    source_dir = tmp_path / "source"
    _write_manifest(source_dir, "ninman.yml", "source-app")
    _write_manifest(dist_dir, "ninman.yaml", "dist-app")

    assert resolve_manifest(None, dist_dir, source_dir) == NinmanManifest("dist-app", "App", "App")

    (dist_dir / "ninman.yaml").unlink()
    assert resolve_manifest(None, dist_dir, source_dir) == NinmanManifest(
        "source-app", "App", "App"
    )


def test_resolve_manifest_returns_none_when_not_found(tmp_path):
    assert resolve_manifest(None, tmp_path / "dist", tmp_path / "source") is None


def test_install_command_passes_manifest_path_to_request(tmp_path):
    parser = argparse.ArgumentParser()
    subparsers = parser.add_subparsers()

    InstallCommand.register_command(subparsers)
    namespace = parser.parse_args(["install", "--manifest", str(tmp_path / "ninman.yml")])

    request = InstallCommand.parse_arguments(Runtime.current(), namespace)

    assert request.manifest_path == tmp_path / "ninman.yml"


def test_upgrade_command_parses_service_options():
    parser = argparse.ArgumentParser()
    subparsers = parser.add_subparsers()

    UpgradeCommand.register_command(subparsers)
    namespace = parser.parse_args(
        [
            "upgrade",
            "demo",
            "--version-override",
            "2.0.0",
            "--force",
            "--token",
            "secret",
            "--new-ref",
            "next",
            "--new-release-tag",
            "v2",
        ]
    )

    request = UpgradeCommand.parse_arguments(Runtime.current(), namespace)

    assert request == UpgradeRequest(
        "demo",
        UpgradeOptions(
            force=True,
            version_override=semver.Version(2, 0, 0),
            token="secret",
            new_ref="next",
            new_release_tag="v2",
        ),
    )


def test_upgrade_command_distinguishes_omitted_and_clear_source_values():
    parser = argparse.ArgumentParser()
    subparsers = parser.add_subparsers()
    UpgradeCommand.register_command(subparsers)

    unchanged = UpgradeCommand.parse_arguments(
        Runtime.current(), parser.parse_args(["upgrade", "demo"])
    )
    clear = UpgradeCommand.parse_arguments(
        Runtime.current(),
        parser.parse_args(["upgrade", "demo", "--new-ref", "--new-release-tag"]),
    )

    assert unchanged.upgrade_options.new_ref is KEEP_EXISTING
    assert unchanged.upgrade_options.new_release_tag is KEEP_EXISTING
    assert clear.upgrade_options.new_ref is None
    assert clear.upgrade_options.new_release_tag is None


@pytest.mark.parametrize(
    ("requested_subpath", "project_subpath"),
    [
        (Path("src/App.csproj"), Path("src/App.csproj")),
        (Path("/dev/null"), Path("App.csproj")),
    ],
)
def test_prepare_source_resolves_git_project_path(
    tmp_path, monkeypatch, requested_subpath, project_subpath
):
    cache_dir = tmp_path / "checkout"
    project_path = cache_dir / project_subpath
    project_path.parent.mkdir(parents=True)
    project_path.touch()
    source = app_sources.GitCodeAppSource(
        "https://example.com/source.git",
        "main",
        requested_subpath,
        BuildOptions(),
        cache_dir,
    )
    monkeypatch.setattr(
        "net_install_manager.core.artifact_provider.git_utils.clone_or_update_repo",
        lambda _: None,
    )

    prepared = DefaultArtifactProvider().prepare_source(
        source, Runtime.current(), tmp_path / "work"
    )

    assert isinstance(prepared, app_sources.GitCodeAppSource)
    assert prepared.subpath == project_subpath


def test_install_registers_app_for_future_commands(tmp_path):
    build_dir = tmp_path / "build"
    build_dir.mkdir()
    _write_manifest(build_dir, "ninman.yml", "manifest-app")
    runtime = replace(
        Runtime.current(),
        home_dir=tmp_path,
        registry_path=tmp_path / "config" / "apps.yaml",
    )

    class MyOpts(OpsOptions):
        def mirror_directory_assertions(self, data: dict):
            assert data["exclude_patterns"] is None

        def update_current_link_assertions(self, data: dict):
            assert data["current_dir"].name == "current"
            assert (data["versions_dir"] / data["target_version"]).is_dir()

    TestOsOps = get_test_os_ops(options=MyOpts())

    artifact_provider = get_test_artifact_provider(build_dir, None)

    request = InstallationRequest(
        app_source=app_sources.BuiltAppSource(build_dir),
        targets=TargetOptions(),
        installation_options=InstallationOptions(version_override=semver.Version(1, 2, 3)),
        build_options=BuildOptions(),
    )

    result = InstallationService(runtime, artifacts=artifact_provider, os_ops=TestOsOps).install(
        request
    )

    registered = Registry(runtime).get("manifest-app")
    assert result.app == registered
    assert registered == AppInfo(
        binary_name="manifest-app",
        source_binary_name="App",
        lib_dir=tmp_path / ".local" / "lib" / "App",
        installed_version=semver.Version(1, 2, 3),
        app_source=request.app_source,
    )


def test_upgrade_updates_registered_release_and_uses_source_binary(tmp_path):
    runtime = replace(
        Runtime.current(),
        home_dir=tmp_path,
        registry_path=tmp_path / "config" / "apps.yaml",
    )
    app_source = app_sources.GitHubReleaseAppSource("owner", "repo", "{rid}-{version}", "v1")
    app = AppInfo(
        binary_name="demo",
        source_binary_name="ActualBinary",
        lib_dir=tmp_path / ".local" / "lib" / "DemoApp",
        installed_version=semver.Version(1, 0, 0),
        app_source=app_source,
        target_permissions=0,
    )
    version_dir = app.lib_dir / "1.0.0"
    version_dir.mkdir(parents=True)
    registry = Registry(runtime)
    registry.set(app.binary_name, app)
    build_dir = tmp_path / "build"
    build_dir.mkdir()
    calls = {}

    request = UpgradeRequest(
        app_name="demo",
        upgrade_options=UpgradeOptions(
            version_override=semver.Version(2, 0, 0),
            new_release_tag="v2",
        ),
    )

    TestOsOps = get_test_os_ops(calls)
    test_artifacts = get_test_artifact_provider(build_dir, None, calls)

    result = InstallationService(
        runtime, registry=registry, artifacts=test_artifacts, os_ops=TestOsOps
    ).upgrade(request)

    registered = Registry(runtime).get("demo")
    assert registered is not None
    assert registered == result.app
    assert registered.installed_version == semver.Version(2, 0, 0)
    assert isinstance(registered.app_source, app_sources.GitHubReleaseAppSource)
    assert registered.app_source.tag == "v2"
    assert calls["prepare_and_build"][0].tag == "v2"
    assert calls["make_executable"] == result.paths.versions_dir / "2.0.0" / "ActualBinary"
    assert calls["create_bin_launcher"][2] == result.paths.current_dir / "ActualBinary"
    assert calls["set_permissions"][1] == 0


@pytest.mark.parametrize("source_kind", ["git", "release"])
@pytest.mark.parametrize("clear_pin", [False, True])
def test_upgrade_preserves_or_clears_source_pin(tmp_path, source_kind, clear_pin):
    runtime = replace(
        Runtime.current(),
        home_dir=tmp_path,
        registry_path=tmp_path / "config" / "apps.yaml",
    )
    if source_kind == "git":
        app_source = app_sources.GitCodeAppSource(
            "https://example.com/source.git",
            "main",
            Path("/dev/null"),
            BuildOptions(),
            tmp_path / "cache",
        )
        new_ref = None if clear_pin else KEEP_EXISTING
        upgrade_options = UpgradeOptions(version_override=semver.Version(2, 0, 0), new_ref=new_ref)
    else:
        app_source = app_sources.GitHubReleaseAppSource("owner", "repo", "{rid}-{version}", "v1")
        new_release_tag = None if clear_pin else KEEP_EXISTING
        upgrade_options = UpgradeOptions(
            version_override=semver.Version(2, 0, 0),
            new_release_tag=new_release_tag,
        )

    app = AppInfo(
        binary_name="demo",
        source_binary_name="ActualBinary",
        lib_dir=tmp_path / ".local" / "lib" / "DemoApp",
        installed_version=semver.Version(1, 0, 0),
        app_source=app_source,
    )
    (app.lib_dir / "1.0.0").mkdir(parents=True)
    registry = Registry(runtime)
    registry.set(app.binary_name, app)
    build_dir = tmp_path / "build"
    build_dir.mkdir()
    calls = {}

    result = InstallationService(
        runtime,
        registry=registry,
        artifacts=get_test_artifact_provider(build_dir, None, calls),
        os_ops=get_test_os_ops(calls),
    ).upgrade(UpgradeRequest("demo", upgrade_options))

    prepared_source = calls["prepare_and_build"][0]
    if source_kind == "git":
        assert isinstance(prepared_source, app_sources.GitCodeAppSource)
        assert prepared_source.ref == (None if clear_pin else "main")
        assert isinstance(result.app.app_source, app_sources.GitCodeAppSource)
        assert result.app.app_source.ref == (None if clear_pin else "main")
    else:
        assert isinstance(prepared_source, app_sources.GitHubReleaseAppSource)
        assert prepared_source.tag == (None if clear_pin else "v1")
        assert isinstance(result.app.app_source, app_sources.GitHubReleaseAppSource)
        assert result.app.app_source.tag == (None if clear_pin else "v1")
