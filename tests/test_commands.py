"""Tests for the Net Install Manager CLI commands."""

import argparse
from unittest.mock import MagicMock, patch
import pytest
import semver

from net_install_manager.config import Config
from net_install_manager.app_manager import AppManager
import net_install_manager.commands.install as c_inst
import net_install_manager.commands.install_release as c_inst_release
import net_install_manager.commands.app_details as c_ad
import net_install_manager.commands.list_versions as c_lv
import net_install_manager.commands.rollback as c_roll
import net_install_manager.commands.uninstall as c_uninst
from net_install_manager.errors import AppNotRegisteredError, CannotResolveManagerError
from net_install_manager.net_install_manager import get_version, register_commands
from net_install_manager.registry import AppRegistry, TrackedApp
from net_install_manager.utilities.install_tools import InstallSource
from net_install_manager.utilities.github_release_tools import GitHubReleaseInfo

# pylint: disable=unused-argument,redefined-outer-name


def test_get_version_uses_git_when_package_metadata_is_placeholder():
    """Use a Git version when dynamic package metadata has its default value."""
    with (
        patch("net_install_manager.net_install_manager.gv", return_value="0.0.0"),
        patch(
            "net_install_manager.net_install_manager.get_version_from_git",
            return_value=semver.Version.parse("1.2.3"),
        ),
    ):
        assert get_version() == "1.2.3"


def test_get_version_uses_non_placeholder_package_metadata():
    """Prefer an installed package version when it is not the default placeholder."""
    with (
        patch("net_install_manager.net_install_manager.gv", return_value="2.3.4"),
        patch("net_install_manager.net_install_manager.get_version_from_git") as get_git_version,
    ):
        assert get_version() == "2.3.4"
        get_git_version.assert_not_called()


@pytest.fixture
def mock_manager(tmp_path):
    """Provide a mocked AppManager instance with a sample configuration."""
    config = Config(app_directory="test_app", binary_name="testbin", source_binary_name="Test.dll")
    manager = MagicMock(spec=AppManager)
    manager.config = config
    return manager


def test_command_install_success(mock_manager):
    """Test the install command with a successful installation."""
    mock_manager.install.return_value = semver.Version.parse("1.2.0")
    args = argparse.Namespace(
        source="path/to/proj",
        self_contained=False,
        debug=False,
        versions_to_keep=None,
        force=False,
        app_version=None,
        quiet=False,
    )
    res = c_inst.execute(args, mock_manager)
    assert res == 0
    mock_manager.install.assert_called_once()
    call = mock_manager.install.call_args.kwargs
    assert call["source"] == InstallSource(local_path="path/to/proj")
    assert call["options"].self_contained is False
    assert call["options"].release is True
    assert call["options"].force is False
    assert call["options"].explicit_version is None
    assert call["options"].quiet is False


def test_global_quiet_flag_reaches_install_options(mock_manager):
    """Test that the global quiet flag is passed to install subprocess options."""
    mock_manager.install.return_value = semver.Version.parse("1.2.0")
    args = argparse.Namespace(
        source="path/to/proj",
        self_contained=False,
        debug=False,
        versions_to_keep=None,
        force=False,
        app_version=None,
        quiet=True,
    )

    res = c_inst.execute(args, mock_manager)

    assert res == 0
    assert mock_manager.install.call_args.kwargs["options"].quiet is True


def test_parser_accepts_global_output_flags():
    """Test global output controls are parsed before subcommands."""
    parser = register_commands()

    args = parser.parse_args(["--quiet", "--verbose", "--debug-logs", "list-apps"])

    assert args.quiet is True
    assert args.verbose is True
    assert args.debug_logs is True


def test_parser_accepts_install_release_command():
    """Test that release installation accepts repository and asset options."""
    parser = register_commands()

    args = parser.parse_args(
        [
            "install-release",
            "owner",
            "repo",
            "--asset-pattern",
            "linux-{version}",
            "--tag",
            "v1.2.3",
        ]
    )

    assert args.command == "install-release"
    assert args.owner == "owner"
    assert args.repo == "repo"
    assert args.asset_pattern == "linux-{version}"
    assert args.tag == "v1.2.3"


def test_app_details_reports_local_source(tmp_path, capsys):
    """Display the source type and path for a locally installed application."""
    registry = AppRegistry(registry_file=tmp_path / "apps.yaml")
    source_path = tmp_path / "source"
    registry.register(
        TrackedApp(
            binary_name="myapp",
            app_directory="my-app",
            source_binary_name="MyApp.dll",
            source=InstallSource(local_path=str(source_path)),
            lib_path="/home/test/.local/lib/my-app",
            installed_version="1.0.0",
        )
    )

    result = c_ad.execute(argparse.Namespace(app_name="myapp"), registry=registry)

    captured = capsys.readouterr()
    assert result == 0
    assert "Details for application 'myapp':" in captured.out
    assert "Source type: Local Path" in captured.out
    assert f"Path:          {source_path}" in captured.out


def test_app_details_reports_github_release_source(tmp_path, capsys):
    """Display the persisted GitHub release coordinates without credentials."""
    registry = AppRegistry(registry_file=tmp_path / "apps.yaml")
    registry.register(
        TrackedApp(
            binary_name="myapp",
            app_directory="my-app",
            source_binary_name="MyApp.dll",
            source=InstallSource(
                release_info=GitHubReleaseInfo(
                    owner="owner",
                    repo="repo",
                    asset_pattern="{rid}-{version}",
                    tag="v1.2.3",
                )
            ),
        )
    )

    result = c_ad.execute(argparse.Namespace(app_name="myapp"), registry=registry)

    captured = capsys.readouterr()
    assert result == 0
    assert "Source type: GitHub Release Artifact" in captured.out
    assert "Owner:         owner" in captured.out
    assert "Repo:          repo" in captured.out
    assert "Asset pattern: {rid}-{version}" in captured.out
    assert "Tag:           v1.2.3" in captured.out


def test_app_details_missing_application_writes_error(tmp_path, capsys):
    """Report a useful error when the requested application is not registered."""
    registry = AppRegistry(registry_file=tmp_path / "apps.yaml")

    result = c_ad.execute(argparse.Namespace(app_name="missing"), registry=registry)

    captured = capsys.readouterr()
    assert result == 1
    assert captured.out == ""
    assert "No details found for application 'missing'." in captured.err


def test_install_release_builds_config_from_cli_when_artifact_has_no_config(tmp_path):
    """Build a release config from complete CLI metadata when discovery finds nothing."""
    args = argparse.Namespace(
        config=None,
        app_directory="my-app",
        binary_name="myapp",
        source_binary_name="MyApp.dll",
        csproj_path=None,
    )

    config = c_inst_release.get_config(args, tmp_path)

    assert config == Config(
        app_directory="my-app",
        binary_name="myapp",
        source_binary_name="MyApp.dll",
    )


def test_command_install_parses_git_project_source(mock_manager):
    """Test that install parses a Git source and project path into InstallSource."""
    args = argparse.Namespace(
        source="https://github.com/example/app.git#src/MyApp",
        project=None,
        self_contained=True,
        debug=True,
        versions_to_keep=2,
        force=True,
        app_version="1.2.3",
        quiet=False,
    )
    mock_manager.install.return_value = semver.Version.parse("1.2.3")

    assert c_inst.execute(args, mock_manager) == 0

    call = mock_manager.install.call_args.kwargs
    source = call["source"]
    assert source.is_git is True
    assert source.git_info is not None
    assert source.git_info.clone_url == "https://github.com/example/app.git"
    assert source.project_path == "src/MyApp"
    options = call["options"]
    assert options.self_contained is True
    assert options.release is False
    assert options.keep_latest == 2
    assert options.force is True
    assert str(options.explicit_version) == "1.2.3"


def test_parse_source_preserves_local_project_path(mock_manager):
    """Test that local CLI sources retain their project selector."""
    args = argparse.Namespace(source="repo", project="src/MyApp")

    source = c_inst.parse_source(args, mock_manager)

    assert source == InstallSource(local_path="repo", project_path="src/MyApp")


def test_command_install_invalid_keep(mock_manager):
    """Test the install command with an invalid versions_to_keep argument."""
    args = argparse.Namespace(
        source="path/to/proj",
        self_contained=False,
        debug=False,
        versions_to_keep=0,
        force=False,
        app_version=None,
        quiet=False,
    )
    res = c_inst.execute(args, mock_manager)
    assert res == 1
    mock_manager.install.assert_not_called()


def test_command_install_invalid_keep_writes_to_stderr(mock_manager, capsys):
    """Test install validation failures are diagnostics, not stdout results."""
    args = argparse.Namespace(
        source="path/to/proj",
        self_contained=False,
        debug=False,
        versions_to_keep=0,
        force=False,
        app_version=None,
        quiet=False,
    )

    res = c_inst.execute(args, mock_manager)

    captured = capsys.readouterr()
    assert res == 1
    assert captured.out == ""
    assert "The number of versions to keep must be at least 1." in captured.err


def test_command_list_versions(mock_manager, capsys):
    """Test the list_versions command output."""
    mock_manager.get_installed_versions.return_value = [
        semver.Version.parse("2.0.0"),
        semver.Version.parse("1.0.0"),
    ]
    mock_manager.get_current_version.return_value = semver.Version.parse("2.0.0")

    args = argparse.Namespace(app_name=None, reverse=False)
    res = c_lv.execute(args, mock_manager)
    assert res == 0
    captured = capsys.readouterr()
    assert "1.0.0" in captured.out
    assert "2.0.0 (current)" in captured.out


def test_command_list_versions_by_app_name(tmp_path, capsys):
    """Test listing versions for an app by app_name via the registry without an initial manager."""

    reg_file = tmp_path / "apps.yaml"
    registry = AppRegistry(registry_file=reg_file)

    tracked = TrackedApp(
        binary_name="registered_app",
        app_directory="registered-app",
        source_binary_name="RegApp.dll",
        source=InstallSource(local_path=str(tmp_path / "source")),
    )
    registry.register(tracked)

    args = argparse.Namespace(
        app_name="registered_app",
        reverse=False,
        system=False,
        prefer_opt=False,
    )

    with patch("net_install_manager.commands.list_versions.AppManager") as mock_app_mgr_cls:
        mock_instance = MagicMock()
        mock_instance.get_installed_versions.return_value = [semver.Version.parse("1.0.0")]
        mock_instance.get_current_version.return_value = semver.Version.parse("1.0.0")
        mock_app_mgr_cls.return_value = mock_instance

        res = c_lv.execute(args, manager=None, registry=registry)
        assert res == 0
        captured = capsys.readouterr()
        assert "1.0.0 (current)" in captured.out


def test_command_list_versions_by_app_name_not_registered(tmp_path):
    """Test listing versions for an unregistered app_name raises AppNotRegisteredError."""

    reg_file = tmp_path / "apps.yaml"
    registry = AppRegistry(registry_file=reg_file)

    args = argparse.Namespace(
        app_name="unknown_app",
        reverse=False,
        system=False,
    )

    with pytest.raises(AppNotRegisteredError):
        c_lv.execute(args, manager=None, registry=registry)


def test_command_list_versions_no_manager_no_app_name():
    """Test listing versions without a manager or app_name raises CannotResolveManagerError."""
    args = argparse.Namespace(app_name=None, reverse=False)
    with pytest.raises(CannotResolveManagerError):
        c_lv.execute(args, manager=None)


def test_command_rollback(mock_manager):
    """Test the rollback command with a specified target version."""
    mock_manager.rollback.return_value = semver.Version.parse("1.0.0")
    args = argparse.Namespace(app_name=None, target_version="1.0.0", previous=False)
    res = c_roll.execute(args, mock_manager)
    assert res == 0
    mock_manager.rollback.assert_called_once_with(target_version="1.0.0", previous=False)


def test_command_rollback_by_app_name(tmp_path):
    """Test rolling back an app by app_name via the registry without an initial manager."""

    reg_file = tmp_path / "apps.yaml"
    registry = AppRegistry(registry_file=reg_file)

    tracked = TrackedApp(
        binary_name="registered_app",
        app_directory="registered-app",
        source_binary_name="RegApp.dll",
        source=InstallSource(local_path=str(tmp_path / "source")),
    )
    registry.register(tracked)

    args = argparse.Namespace(
        app_name="registered_app",
        target_version="1.0.0",
        previous=False,
        system=False,
        prefer_opt=False,
    )

    with patch("net_install_manager.commands.rollback.AppManager") as mock_app_mgr_cls:
        mock_instance = MagicMock()
        mock_instance.rollback.return_value = semver.Version.parse("1.0.0")
        mock_app_mgr_cls.return_value = mock_instance

        res = c_roll.execute(args, manager=None, registry=registry)
        assert res == 0
        mock_instance.rollback.assert_called_once_with(target_version="1.0.0", previous=False)


def test_command_rollback_by_app_name_not_registered(tmp_path):
    """Test rolling back an unregistered app_name raises AppNotRegisteredError."""

    reg_file = tmp_path / "apps.yaml"
    registry = AppRegistry(registry_file=reg_file)

    args = argparse.Namespace(
        app_name="unknown_app",
        target_version="1.0.0",
        previous=False,
        system=False,
    )

    with pytest.raises(AppNotRegisteredError):
        c_roll.execute(args, manager=None, registry=registry)


def test_command_rollback_no_manager_no_app_name():
    """Test rolling back without a manager or app_name raises CannotResolveManagerError."""
    args = argparse.Namespace(app_name=None, target_version="1.0.0", previous=False)
    with pytest.raises(CannotResolveManagerError):
        c_roll.execute(args, manager=None)


def test_command_uninstall_validation(mock_manager):
    """Test the uninstall command argument validation and execution."""
    args_invalid = argparse.Namespace(app_name=None, target_version=None, all=False)
    assert not c_uninst.validate_arguments(args_invalid)
    res = c_uninst.execute(args_invalid, mock_manager)
    assert res == 1

    args_valid = argparse.Namespace(app_name=None, target_version="1.0.0", all=False)
    assert c_uninst.validate_arguments(args_valid)
    res2 = c_uninst.execute(args_valid, mock_manager)
    assert res2 == 0
    mock_manager.uninstall.assert_called_once_with(target_version="1.0.0", all_versions=False)


def test_command_uninstall_validation_writes_to_stderr(mock_manager, capsys):
    """Test uninstall validation failures are written to stderr."""
    args = argparse.Namespace(app_name=None, target_version=None, all=False)

    res = c_uninst.execute(args, mock_manager)

    captured = capsys.readouterr()
    assert res == 1
    assert captured.out == ""
    assert "Please specify either --target-version or --all to uninstall." in captured.err


def test_command_uninstall_by_app_name(tmp_path):
    """Test uninstalling an app by app_name via the registry without an initial manager."""

    reg_file = tmp_path / "apps.yaml"
    registry = AppRegistry(registry_file=reg_file)

    tracked = TrackedApp(
        binary_name="registered_app",
        app_directory="registered-app",
        source_binary_name="RegApp.dll",
        source=InstallSource(local_path=str(tmp_path / "source")),
    )
    registry.register(tracked)

    args = argparse.Namespace(
        app_name="registered_app",
        target_version=None,
        all=True,
        system=False,
        prefer_opt=False,
    )

    with patch("net_install_manager.commands.uninstall.AppManager") as mock_app_mgr_cls:
        mock_instance = MagicMock()
        mock_instance.config.binary_name = "registered_app"
        mock_app_mgr_cls.return_value = mock_instance

        res = c_uninst.execute(args, manager=None, registry=registry)
        assert res == 0
        mock_instance.uninstall.assert_called_once_with(target_version=None, all_versions=True)


def test_command_uninstall_by_app_name_not_registered(tmp_path):
    """Test uninstalling an unregistered app_name raises AppNotRegisteredError."""

    reg_file = tmp_path / "apps.yaml"
    registry = AppRegistry(registry_file=reg_file)

    args = argparse.Namespace(
        app_name="unknown_app",
        target_version="1.0.0",
        all=False,
        system=False,
    )

    with pytest.raises(AppNotRegisteredError):
        c_uninst.execute(args, manager=None, registry=registry)


def test_command_uninstall_no_manager_no_app_name():
    """Test uninstalling without a manager or app_name raises CannotResolveManagerError."""
    args = argparse.Namespace(
        app_name=None,
        target_version="1.0.0",
        all=False,
    )
    with pytest.raises(CannotResolveManagerError):
        c_uninst.execute(args, manager=None)
