import argparse

import pytest
import semver

from net_install_manager.commands import uninstall
from net_install_manager.commands.uninstall import UninstallArguments, UninstallCommand
from net_install_manager.config.app_info import AppInfo
from net_install_manager.config.app_sources import BuiltAppSource
from net_install_manager.config.paths import get_paths
from net_install_manager.core import errors
from net_install_manager.core.registry import Registry


def test_uninstall_delegates_cleanup_before_removing_registry_entry(
    runtime, tmp_path, monkeypatch, capsys
):
    app = AppInfo(
        binary_name="sample",
        source_binary_name="Sample",
        lib_dir=get_paths(runtime, "Sample", "sample").lib_dir,
        installed_version=semver.Version(1, 0, 0),
        app_source=BuiltAppSource(tmp_path / "build"),
    )
    registry = Registry(runtime)
    registry.set(app.binary_name, app)
    expected_paths = get_paths(runtime, "Sample", "sample")
    calls = []

    class TestOsOps:
        @staticmethod
        def remove_application(paths):
            calls.append(paths)
            assert registry.get(app.binary_name) == app

    monkeypatch.setattr(uninstall, "get_os_ops", lambda _os: TestOsOps)

    UninstallCommand().execute(runtime, UninstallArguments("sample", assume_yes=True))

    assert calls == [expected_paths]
    assert Registry(runtime).get(app.binary_name) is None
    assert capsys.readouterr().out == "Successfully uninstalled 'sample' (version 1.0.0).\n"


def test_uninstall_cancellation_does_not_report_success(runtime, monkeypatch, capsys):
    monkeypatch.setattr("builtins.input", lambda _prompt: "n")

    UninstallCommand().execute(runtime, UninstallArguments("sample"))

    assert capsys.readouterr().out == ""


def test_uninstall_failure_does_not_report_success(runtime, capsys):
    with pytest.raises(errors.AppNotRegisteredError):
        UninstallCommand().execute(runtime, UninstallArguments("missing", assume_yes=True))

    assert capsys.readouterr().out == ""


def test_uninstall_cleanup_failure_does_not_report_success(runtime, monkeypatch, capsys):
    app = AppInfo(
        binary_name="sample",
        source_binary_name="Sample",
        lib_dir=get_paths(runtime, "Sample", "sample").lib_dir,
        installed_version=semver.Version(1, 0, 0),
        app_source=BuiltAppSource(runtime.home_dir / "build"),
    )
    Registry(runtime).set(app.binary_name, app)

    class FailingOsOps:
        @staticmethod
        def remove_application(_paths):
            raise PermissionError("cannot remove application")

    monkeypatch.setattr(uninstall, "get_os_ops", lambda _os: FailingOsOps)

    with pytest.raises(PermissionError, match="cannot remove application"):
        UninstallCommand().execute(runtime, UninstallArguments("sample", assume_yes=True))

    assert Registry(runtime).get("sample") == app
    assert capsys.readouterr().out == ""


@pytest.mark.parametrize(("flags", "assume_yes"), [([], False), (["-y"], True), (["--yes"], True)])
def test_uninstall_parses_confirmation_flag(runtime, flags, assume_yes):
    parser = argparse.ArgumentParser()
    UninstallCommand.register_command(parser.add_subparsers())
    args = parser.parse_args(["uninstall", "sample", *flags])

    assert UninstallCommand.parse_arguments(runtime, args) == UninstallArguments("sample", assume_yes)
