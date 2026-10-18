import pytest
import semver

from net_install_manager.commands.prune import PruneArguments, PruneCommand
from net_install_manager.commands.rollback import RollbackArguments, RollbackCommand
from net_install_manager.commands.uninstall import UninstallArguments, UninstallCommand
from net_install_manager.config.app_sources import BuiltAppSource
from net_install_manager.config.build_options import BuildOptions
from net_install_manager.config.paths import get_paths_from_app_info
from net_install_manager.core.installation_service import (
    InstallationOptions,
    InstallationRequest,
    InstallationService,
    TargetOptions,
    UpgradeOptions,
    UpgradeRequest,
)
from net_install_manager.core.registry import Registry
from tests.shared_fixtures.artifact_provider_fixtures import get_test_artifact_provider


@pytest.mark.parametrize("app_directory", ["Demo App", "versions"])
def test_native_install_upgrade_rollback_prune_uninstall(native_runtime, tmp_path, app_directory):
    runtime = native_runtime
    build_dir = tmp_path / "build"
    build_dir.mkdir()
    binary = build_dir / "Demo.dll"
    binary.write_text("version 1", encoding="utf-8")
    (build_dir / "excluded.pdb").touch()
    artifacts = get_test_artifact_provider(build_dir, None)
    first = semver.Version(1, 0, 0)
    second = semver.Version(2, 0, 0)

    result = InstallationService(runtime, artifacts=artifacts).install(
        InstallationRequest(
            app_source=BuiltAppSource(build_dir),
            targets=TargetOptions("demo", "Demo", app_directory),
            installation_options=InstallationOptions(
                version_override=first, exclude_patterns=["*.pdb"]
            ),
            build_options=BuildOptions(),
        )
    )
    paths = result.paths
    root = paths.lib_dir if runtime.os.is_posix else paths.lib_dir.parent
    sibling = root.parent / "unrelated-app"
    sibling.mkdir()
    (sibling / "keep.txt").write_text("keep", encoding="utf-8")

    def assert_current(version: semver.Version, contents: str) -> None:
        app = Registry(runtime).get("demo")
        assert app is not None
        assert app.installed_version == version
        assert app.lib_dir == paths.lib_dir
        assert get_paths_from_app_info(runtime, app) == paths
        assert paths.current_dir.resolve() == (paths.versions_dir / str(version)).resolve()
        assert (paths.current_dir / "Demo.dll").read_text(encoding="utf-8") == contents
        assert not (paths.current_dir / "excluded.pdb").exists()
        assert paths.bin_path.is_file()
        if runtime.os.is_posix:
            assert paths.current_dir.is_symlink()
            assert paths.bin_path.stat().st_mode & 0o111
            assert "exec dotnet" in paths.bin_path.read_text(encoding="utf-8")
        else:
            assert paths.current_dir.is_junction()
            assert paths.bin_path.with_suffix(".cmd").is_file()

    assert_current(first, "version 1")
    binary.write_text("version 2", encoding="utf-8")
    upgraded = InstallationService(runtime, artifacts=artifacts).upgrade(
        UpgradeRequest("demo", UpgradeOptions(version_override=second))
    )
    assert upgraded.paths == paths
    assert_current(second, "version 2")
    versions = Registry(runtime).get_installed_versions("demo")
    assert versions is not None
    assert set(versions.versions) == {first, second}

    RollbackCommand().execute(runtime, RollbackArguments("demo", first))
    assert_current(first, "version 1")
    RollbackCommand().execute(runtime, RollbackArguments("demo", second))
    assert_current(second, "version 2")
    PruneCommand().execute(
        runtime, PruneArguments("demo", max_version=first, assume_yes=True)
    )
    assert_current(first, "version 1")
    assert not (paths.versions_dir / str(second)).exists()
    assert (paths.versions_dir / str(first)).is_dir()

    UninstallCommand().execute(runtime, UninstallArguments("demo", assume_yes=True))
    assert Registry(runtime).get("demo") is None
    assert not root.exists()
    assert not paths.current_dir.exists(follow_symlinks=False)
    assert not paths.bin_path.exists(follow_symlinks=False)
    assert not paths.bin_path.with_suffix(".cmd").exists()
    assert (sibling / "keep.txt").read_text(encoding="utf-8") == "keep"
