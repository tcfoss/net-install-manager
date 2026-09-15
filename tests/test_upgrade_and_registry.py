"""Tests for the upgrade and registry commands in Net Install Manager."""

import argparse
from pathlib import Path
from unittest.mock import patch
import semver

from net_install_manager.registry import AppRegistry, TrackedApp, get_registry_path
from net_install_manager.runtime_config import RuntimeInfo
from net_install_manager.utilities.git_tools import GitSourceInfo
from net_install_manager.utilities.github_release_tools import GitHubReleaseInfo
from net_install_manager.utilities.install_tools import InstallSource
from net_install_manager.utilities.sys_platform import OperatingSystem, PlatformInfo, get_winpath
import net_install_manager.commands.list_apps as c_la
import net_install_manager.commands.upgrade as c_upg


def test_registry_path_posix_user():
    """Test the registry path resolution for a POSIX user installation."""
    runtime = RuntimeInfo(
        env={},
        home_dir=Path("/home/testuser"),
        platform=PlatformInfo(
            os=OperatingSystem.LINUX,
            architecture=PlatformInfo.detect().architecture,
            is_admin=False,
        ),
        system_wide=False,
    )
    path = get_registry_path(
        runtime=runtime,
    )
    assert path == Path("/home/testuser/.config/ninman/apps.yaml")


def test_registry_path_posix_system():
    """Test the registry path resolution for a POSIX system-wide installation."""
    runtime = RuntimeInfo(
        platform=PlatformInfo(
            os=OperatingSystem.LINUX,
            architecture=PlatformInfo.detect().architecture,
            is_admin=False,
        ),
        system_wide=True,
    )
    path = get_registry_path(
        runtime=runtime,
    )
    assert path == Path("/etc/ninman/apps.yaml")


def test_registry_path_windows_user():
    """Test the registry path resolution for a Windows user installation."""
    fake_env = {"APPDATA": r"C:\Users\testuser\AppData\Roaming"}
    runtime = RuntimeInfo(
        env=fake_env,
        platform=PlatformInfo(
            os=OperatingSystem.WINDOWS,
            architecture=PlatformInfo.detect().architecture,
            is_admin=False,
        ),
        system_wide=False,
    )
    path = get_registry_path(
        runtime=runtime,
    )
    assert path == get_winpath(r"C:\Users\testuser\AppData\Roaming\ninman\apps.yaml")


def test_registry_crud(tmp_path):
    """Test the CRUD operations of the AppRegistry."""
    reg_file = tmp_path / "apps.yaml"
    registry = AppRegistry(registry_file=reg_file)

    app = TrackedApp(
        binary_name="myapp",
        app_directory="my-app",
        source_binary_name="MyApp.dll",
        source=InstallSource(local_path=str(tmp_path / "source")),
        installed_version="1.0.0",
    )

    # Save / register
    registry.register(app)
    assert reg_file.exists()

    # Load / get
    loaded_app = registry.get("myapp")
    assert loaded_app is not None
    assert loaded_app.binary_name == "myapp"
    assert loaded_app.installed_version == "1.0.0"

    # Remove
    assert registry.remove("myapp") is True
    assert registry.get("myapp") is None
    assert registry.remove("myapp") is False


def test_registry_round_trips_git_install_source(tmp_path):
    """Test that nested Git source metadata survives registry serialization."""
    reg_file = tmp_path / "apps.yaml"
    registry = AppRegistry(registry_file=reg_file)
    source = InstallSource(
        git_info=GitSourceInfo(clone_url="https://github.com/example/app.git", ref="main"),
        project_path="src/MyApp",
    )
    registry.register(
        TrackedApp(
            binary_name="myapp",
            app_directory="my-app",
            source_binary_name="MyApp.dll",
            source=source,
        )
    )

    loaded = registry.get("myapp")

    assert loaded is not None
    assert loaded.source == source


def test_registry_round_trips_github_release_source(tmp_path):
    """Test that release coordinates survive registry serialization without a token."""
    reg_file = tmp_path / "apps.yaml"
    registry = AppRegistry(registry_file=reg_file)
    source = InstallSource(
        release_info=GitHubReleaseInfo(
            owner="owner",
            repo="app",
            asset_pattern="{rid}-{version}",
            tag="v1.2.3",
        )
    )
    registry.register(
        TrackedApp(
            binary_name="myapp",
            app_directory="my-app",
            source_binary_name="MyApp.dll",
            source=source,
        )
    )

    loaded = registry.get("myapp")

    assert loaded is not None
    assert loaded.source == source
    assert "token" not in reg_file.read_text(encoding="utf-8").lower()


def test_upgrade_tracked_app(tmp_path):
    """Test upgrading a tracked application."""
    source_dir = tmp_path / "src"
    source_dir.mkdir()
    (source_dir / "MyApp.dll").write_text("bin", encoding="utf-8")

    tracked = TrackedApp(
        binary_name="myapp",
        app_directory="my-app",
        source_binary_name="MyApp.dll",
        source=InstallSource(local_path=str(source_dir)),
        installed_version="1.0.0",
    )

    with patch(
        "net_install_manager.app_manager.AppManager.install",
        return_value=semver.Version.parse("1.1.0"),
    ) as mock_inst:
        success = c_upg.upgrade_tracked_app(tracked)
        assert success is True
        mock_inst.assert_called_once()


def test_upgrade_tracked_git_app(tmp_path, capsys):
    """Test upgrading a tracked Git-based application."""
    source_dir = tmp_path / "src"
    source_dir.mkdir()
    (source_dir / "src" / "MyApp").mkdir(parents=True)
    (source_dir / "src" / "MyApp" / "MyApp.dll").write_text("bin", encoding="utf-8")

    tracked = TrackedApp(
        binary_name="myapp",
        app_directory="my-app",
        source_binary_name="MyApp.dll",
        source=InstallSource(
            git_info=GitSourceInfo(clone_url="https://github.com/owner/repo.git", ref="main"),
            project_path="src/MyApp",
        ),
        installed_version="1.0.0",
    )

    with patch(
        "net_install_manager.utilities.install_tools.clone_or_update_repo",
        return_value=source_dir,
    ):
        with patch("net_install_manager.commands.upgrade.update_git_repo") as mock_update_git:
            with patch(
                "net_install_manager.app_manager.AppManager.install",
                return_value=semver.Version.parse("1.1.0"),
            ) as mock_inst:
                success = c_upg.upgrade_tracked_app(tracked, quiet=True)
                assert success is True
                mock_update_git.assert_called_once_with(source_dir, ref="main", quiet=True)
                mock_inst.assert_called_once()
                assert mock_inst.call_args.kwargs["source"] == tracked.source
                assert mock_inst.call_args.kwargs["options"].quiet is True
                captured = capsys.readouterr()
                assert "Upgrading" not in captured.out
                assert "Fetching latest changes" not in captured.out
                assert "Successfully upgraded 'myapp' to version 1.1.0." in captured.out


def test_upgrade_unknown_app_writes_to_stderr(tmp_path, capsys):
    """Test upgrade lookup failures are written to stderr."""
    reg_file = tmp_path / "apps.yaml"
    registry = AppRegistry(registry_file=reg_file)
    args = argparse.Namespace(
        app_name="missing", all=False, force=False, debug=None, system=False, quiet=False
    )

    code = c_upg.execute(args, registry=registry)

    captured = capsys.readouterr()
    assert code == 1
    assert captured.out == ""
    assert "Error: Application 'missing' is not registered in ninman." in captured.err


def test_upgrade_command_by_name(tmp_path):
    """Test the upgrade command execution by specifying the application name."""
    reg_file = tmp_path / "apps.yaml"
    registry = AppRegistry(registry_file=reg_file)

    source_dir = tmp_path / "src"
    source_dir.mkdir()
    (source_dir / "MyApp.dll").write_text("bin", encoding="utf-8")

    registry.register(
        TrackedApp(
            binary_name="myapp",
            app_directory="my-app",
            source_binary_name="MyApp.dll",
            source=InstallSource(local_path=str(source_dir)),
            installed_version="1.0.0",
        )
    )

    with patch(
        "net_install_manager.app_manager.AppManager.install",
        return_value=semver.Version.parse("1.1.0"),
    ):
        args = argparse.Namespace(
            app_name="myapp", all=False, force=False, debug=None, system=False, quiet=True
        )
        code = c_upg.execute(args, registry=registry)
        assert code == 0


def test_list_apps_command(tmp_path, capsys):
    """Test the list apps command output."""
    reg_file = tmp_path / "apps.yaml"
    registry = AppRegistry(registry_file=reg_file)

    registry.register(
        TrackedApp(
            binary_name="myapp",
            app_directory="my-app",
            source_binary_name="MyApp.dll",
            source=InstallSource(local_path="/path/to/source"),
            installed_version="1.0.0",
        )
    )

    args = argparse.Namespace(system=False)
    code = c_la.execute(args, registry=registry)
    assert code == 0

    captured = capsys.readouterr()
    assert "myapp (v1.0.0)" in captured.out
