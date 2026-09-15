"""Tests for the AppManager (Application Driver) class."""

from unittest.mock import patch
import pytest
import semver

from net_install_manager.config import Config
from net_install_manager.app_manager import AppManager, VersionRegressionError, AppManagerError
from net_install_manager.paths import Paths
from net_install_manager.runtime_config import InstallOptions, RuntimeInfo
from net_install_manager.utilities.git_tools import GitSourceInfo
from net_install_manager.utilities.install_tools import InstallSource
from net_install_manager.utilities.sys_platform import PlatformInfo

# pylint: disable=redefined-outer-name


@pytest.fixture
def test_env(tmp_path):
    """Set up a test environment for the AppManager."""

    app_dir = tmp_path / "app_root"
    versions_dir = app_dir / "versions"
    current_dir = app_dir / "current"
    bin_dir = tmp_path / "bin"
    bin_path = bin_dir / "myapp"

    config = Config(
        app_directory="my_app",
        binary_name="myapp",
        source_binary_name="MyApp.dll",
    )

    platform_info = PlatformInfo.detect()
    home_dir = tmp_path / "home"
    config_dir = tmp_path / "config"
    app_data_dir = tmp_path / "AppData" / "Roaming"
    runtime = RuntimeInfo(
        env={
            "APPDATA": str(app_data_dir),
            "XDG_CONFIG_HOME": str(config_dir),
        },
        home_dir=home_dir,
        platform=platform_info,
        system_wide=False,
    )

    manager = AppManager(
        config=config,
        runtime=runtime,
    )

    manager.paths = Paths(
        lib_dir=app_dir,
        versions_dir=versions_dir,
        current_dir=current_dir,
        bin_dir=bin_dir,
        bin_path=bin_path,
    )

    return manager, tmp_path


def test_install_precompiled_and_list_versions(test_env):
    """Test installing precompiled packages and listing installed versions."""

    manager, tmp = test_env

    # Create precompiled package v1.0.0
    release_dir = tmp / "dist_1.0.0"
    release_dir.mkdir()
    (release_dir / "MyApp.dll").write_text("binary v1.0.0", encoding="utf-8")

    v1 = manager.install(
        source=InstallSource(local_path=str(release_dir)),
        options=InstallOptions(explicit_version="1.0.0"),
    )
    assert v1 == semver.Version.parse("1.0.0")

    installed = manager.get_installed_versions()
    assert installed == [semver.Version.parse("1.0.0")]
    assert manager.get_current_version() == semver.Version.parse("1.0.0")
    assert (manager.paths.versions_dir / "1.0.0" / "MyApp.dll").exists()

    # Install v2.0.0
    release_dir_2 = tmp / "dist_2.0.0"
    release_dir_2.mkdir()
    (release_dir_2 / "MyApp.dll").write_text("binary v2.0.0", encoding="utf-8")

    v2 = manager.install(
        source=InstallSource(local_path=str(release_dir_2)),
        options=InstallOptions(explicit_version="2.0.0"),
    )
    assert v2 == semver.Version.parse("2.0.0")
    assert manager.get_current_version() == semver.Version.parse("2.0.0")
    assert manager.get_installed_versions() == [
        semver.Version.parse("2.0.0"),
        semver.Version.parse("1.0.0"),
    ]


def test_version_regression_prevention(test_env):
    """Test that version regression is prevented unless forced."""

    manager, tmp = test_env

    release_dir = tmp / "dist"
    release_dir.mkdir()
    (release_dir / "MyApp.dll").write_text("binary", encoding="utf-8")

    manager.install(
        source=InstallSource(local_path=str(release_dir)),
        options=InstallOptions(explicit_version="2.0.0"),
    )

    # Trying to install 1.0.0 or 2.0.0 without force should fail
    with pytest.raises(VersionRegressionError):
        manager.install(
            source=InstallSource(local_path=str(release_dir)),
            options=InstallOptions(explicit_version="1.0.0", force=False),
        )

    with pytest.raises(VersionRegressionError):
        manager.install(
            source=InstallSource(local_path=str(release_dir)),
            options=InstallOptions(explicit_version="2.0.0", force=False),
        )

    # With force=True, it succeeds
    v_forced = manager.install(
        source=InstallSource(local_path=str(release_dir)),
        options=InstallOptions(explicit_version="1.0.0", force=True),
    )
    assert v_forced == semver.Version.parse("1.0.0")


def test_rollback(test_env):
    """Test the rollback functionality of the AppManager."""

    manager, tmp = test_env

    for ver in ["1.0.0", "1.1.0", "2.0.0"]:
        dist = tmp / f"dist_{ver}"
        dist.mkdir()
        (dist / "MyApp.dll").write_text(f"binary {ver}", encoding="utf-8")
        manager.install(
            source=InstallSource(local_path=str(dist)),
            options=InstallOptions(explicit_version=ver),
        )

    assert manager.get_current_version() == semver.Version.parse("2.0.0")

    # Rollback with --previous -> should roll back to 1.1.0
    rolled = manager.rollback(previous=True)
    assert rolled == semver.Version.parse("1.1.0")
    assert manager.get_current_version() == semver.Version.parse("1.1.0")

    # Rollback to explicit version 1.0.0
    rolled2 = manager.rollback(target_version="1.0.0")
    assert rolled2 == semver.Version.parse("1.0.0")
    assert manager.get_current_version() == semver.Version.parse("1.0.0")


def test_pruning_keep_latest(test_env):
    """Test that only the latest specified number of versions are kept."""

    manager, tmp = test_env

    for ver in ["1.0.0", "1.1.0", "1.2.0", "2.0.0"]:
        dist = tmp / f"dist_{ver}"
        dist.mkdir()
        (dist / "MyApp.dll").write_text(f"binary {ver}", encoding="utf-8")
        manager.install(
            source=InstallSource(local_path=str(dist)),
            options=InstallOptions(explicit_version=ver, keep_latest=2),
        )

    installed = manager.get_installed_versions()
    assert installed == [semver.Version.parse("2.0.0"), semver.Version.parse("1.2.0")]
    assert not (manager.paths.versions_dir / "1.0.0").exists()
    assert not (manager.paths.versions_dir / "1.1.0").exists()


def test_uninstall_single_version_and_all(test_env):
    """Test uninstalling a single version and all versions of the application."""

    manager, tmp = test_env

    for ver in ["1.0.0", "2.0.0"]:
        dist = tmp / f"dist_{ver}"
        dist.mkdir()
        (dist / "MyApp.dll").write_text(f"binary {ver}", encoding="utf-8")
        manager.install(
            source=InstallSource(local_path=str(dist)),
            options=InstallOptions(explicit_version=ver),
        )

    # Uninstall active version 2.0.0 -> should fallback to 1.0.0
    manager.uninstall(target_version="2.0.0")
    assert manager.get_installed_versions() == [semver.Version.parse("1.0.0")]
    assert manager.get_current_version() == semver.Version.parse("1.0.0")

    # Uninstall all
    manager.uninstall(all_versions=True)
    assert not manager.paths.lib_dir.exists()


def test_install_from_csproj(test_env):
    """Test installing an application from a .csproj file."""

    manager, tmp = test_env
    csproj_dir = tmp / "src" / "MyApp"
    csproj_dir.mkdir(parents=True)
    csproj = csproj_dir / "MyApp.csproj"
    csproj.write_text(
        """<Project Sdk="Microsoft.NET.Sdk">
        <PropertyGroup>
            <AssemblyName>MyApp</AssemblyName>
            <Version>3.5.0</Version>
        </PropertyGroup>
        </Project>""",
        encoding="utf-8",
    )

    def mock_publish(csproj_path, output_dir, **kwargs):  # pylint: disable=unused-argument
        (output_dir / "MyApp.dll").write_text("compiled dll", encoding="utf-8")

    with patch("net_install_manager.app_manager.dotnet_publish", side_effect=mock_publish):
        ver = manager.install(
            source=InstallSource(local_path=str(csproj)), options=InstallOptions()
        )
        assert ver == semver.Version.parse("3.5.0")
        assert manager.get_current_version() == semver.Version.parse("3.5.0")
        assert (manager.paths.versions_dir / "3.5.0" / "MyApp.dll").exists()


def test_install_cleans_staging_directory_when_publish_fails(test_env, tmp_path):
    """Test that a failed publish removes its temporary staging directory."""
    manager, _ = test_env
    csproj = tmp_path / "MyApp.csproj"
    csproj.write_text("<Project />", encoding="utf-8")
    staging_dir = tmp_path / "staging"

    with patch(
        "net_install_manager.app_manager.get_paths_with_buildable_source",
        return_value=(staging_dir, staging_dir / "MyApp.dll", staging_dir),
    ):
        with patch(
            "net_install_manager.app_manager.dotnet_publish",
            side_effect=RuntimeError("publish failed"),
        ):
            with pytest.raises(RuntimeError, match="publish failed"):
                manager.install(
                    source=InstallSource(local_path=str(csproj)),
                    options=InstallOptions(),
                )

    assert not staging_dir.exists()


def test_install_directory_with_multiple_csproj_raises(test_env):
    """Test that installing from a directory with multiple .csproj files raises an error."""

    manager, tmp = test_env
    src_dir = tmp / "multi_csproj"
    src_dir.mkdir()
    (src_dir / "App1.csproj").write_text("<Project></Project>", encoding="utf-8")
    (src_dir / "App2.csproj").write_text("<Project></Project>", encoding="utf-8")

    with pytest.raises(AppManagerError, match="Multiple .csproj files found"):
        manager.install(source=InstallSource(local_path=str(src_dir)), options=InstallOptions())


def test_install_from_git_source(test_env):
    """Test installing an application from a git source."""

    manager, tmp = test_env

    cloned_dir = tmp / "cloned_repo"
    cloned_dir.mkdir()
    csproj = cloned_dir / "MyApp.csproj"
    csproj.write_text(
        """<Project Sdk="Microsoft.NET.Sdk">
        <PropertyGroup>
            <AssemblyName>MyApp</AssemblyName>
            <Version>4.0.0</Version>
        </PropertyGroup>
        </Project>""",
        encoding="utf-8",
    )

    def mock_publish(csproj_path, output_dir, **kwargs):  # pylint: disable=unused-argument
        (output_dir / "MyApp.dll").write_text("compiled dll", encoding="utf-8")

    with patch(
        "net_install_manager.utilities.install_tools.clone_or_update_repo", return_value=cloned_dir
    ):
        with patch("net_install_manager.app_manager.dotnet_publish", side_effect=mock_publish):
            ver = manager.install(
                source=InstallSource(
                    git_info=GitSourceInfo(clone_url="https://github.com/myorg/MyApp.git")
                ),
                options=InstallOptions(),
            )
            assert ver == semver.Version.parse("4.0.0")
            assert manager.get_current_version() == semver.Version.parse("4.0.0")

            tracked = manager.registry.get("myapp")
            assert tracked is not None
            assert tracked.is_git is True
            assert tracked.git_info is not None
            assert tracked.git_info.clone_url == "https://github.com/myorg/MyApp.git"


def test_install_from_git_source_resolves_version_from_repository_root(test_env):
    """Use the cloned repository, not the publish directory, for Git version detection."""
    manager, tmp = test_env
    cloned_dir = tmp / "cloned_repo"
    cloned_dir.mkdir()
    csproj = cloned_dir / "MyApp.csproj"
    csproj.write_text("<Project />", encoding="utf-8")

    def mock_publish(csproj_path, output_dir, **kwargs):  # pylint: disable=unused-argument
        (output_dir / "MyApp.dll").write_text("compiled dll", encoding="utf-8")

    source = InstallSource(git_info=GitSourceInfo(clone_url="https://github.com/myorg/MyApp.git"))
    with patch(
        "net_install_manager.utilities.install_tools.clone_or_update_repo", return_value=cloned_dir
    ):
        with patch("net_install_manager.app_manager.dotnet_publish", side_effect=mock_publish):
            with patch(
                "net_install_manager.app_manager.resolve_version",
                return_value=semver.Version.parse("4.0.0"),
            ) as resolve:
                manager.install(source=source, options=InstallOptions())

    assert resolve.call_args.kwargs["source_dir"] == cloned_dir
