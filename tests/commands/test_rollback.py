import argparse
from pathlib import Path

import pytest
import semver

from net_install_manager.commands import rollback
from net_install_manager.commands.rollback import RollbackArguments, RollbackCommand
from net_install_manager.config.app_info import AppInfo
from net_install_manager.config.app_sources import BuiltAppSource
from net_install_manager.config.paths import Paths, get_paths
from net_install_manager.core import errors
from net_install_manager.core.registry import Registry
from net_install_manager.runtime.runtime import Runtime


def _app(runtime: Runtime) -> AppInfo:
    return AppInfo(
        binary_name="sample",
        source_binary_name="Sample",
        lib_dir=get_paths(runtime, "Sample", "sample").lib_dir,
        installed_version=semver.Version(3, 0, 0),
        app_source=BuiltAppSource(runtime.home_dir / "build"),
    )


def _install_versions(runtime: Runtime, monkeypatch) -> tuple[Runtime, Paths, list[tuple[str, str]]]:
    app = _app(runtime)
    paths = get_paths(runtime, "Sample", "sample")
    for version in ("1.0.0", "2.0.0", "3.0.0"):
        (paths.versions_dir / version).mkdir(parents=True)
    Registry(runtime).set(app.binary_name, app)
    calls: list[tuple[str, str]] = []

    class TestOsOps:
        @staticmethod
        def update_current_link(
            versions_dir: Path, target_version: str, current_dir: Path
        ) -> Path:
            assert versions_dir == paths.versions_dir
            assert current_dir == paths.current_dir
            calls.append(("switch", target_version))
            return current_dir

    monkeypatch.setattr(rollback, "get_os_ops", lambda _os: TestOsOps)
    return runtime, paths, calls


def test_rollback_switches_current_and_updates_registry(runtime, monkeypatch, capsys):
    runtime, paths, calls = _install_versions(runtime, monkeypatch)

    RollbackCommand().execute(
        runtime,
        RollbackArguments("sample", semver.Version(2, 0, 0)),
    )

    registered = Registry(runtime).get("sample")
    assert registered is not None
    assert registered.installed_version == semver.Version(2, 0, 0)
    assert calls == [("switch", "2.0.0")]
    assert capsys.readouterr().out == (
        "Successfully rolled back 'sample' from version 3.0.0 to 2.0.0.\n"
    )


def test_rollback_raises_and_does_not_change_state_for_uninstalled_target(
    runtime, monkeypatch, capsys
):
    runtime, paths, calls = _install_versions(runtime, monkeypatch)

    with pytest.raises(errors.VersionNotInstalledError) as exc_info:
        RollbackCommand().execute(
            runtime,
            RollbackArguments("sample", semver.Version(4, 0, 0)),
        )

    registered = Registry(runtime).get("sample")
    assert registered is not None
    assert registered.installed_version == semver.Version(3, 0, 0)
    assert not calls
    assert exc_info.value.app_name == "sample"
    assert exc_info.value.version == "4.0.0"
    assert capsys.readouterr().out == ""


def test_rollback_does_not_change_state_when_target_is_already_current(
    runtime, monkeypatch, capsys
):
    runtime, paths, calls = _install_versions(runtime, monkeypatch)

    RollbackCommand().execute(
        runtime,
        RollbackArguments("sample", semver.Version(3, 0, 0)),
    )

    registered = Registry(runtime).get("sample")
    assert registered is not None
    assert registered.installed_version == semver.Version(3, 0, 0)
    assert not calls
    assert capsys.readouterr().out == "Application 'sample' is already at version 3.0.0.\n"


def test_rollback_raises_for_unregistered_application(runtime):
    with pytest.raises(errors.AppNotRegisteredError):
        RollbackCommand().execute(
            runtime,
            RollbackArguments("sample", semver.Version(2, 0, 0)),
        )


def test_rollback_link_failure_does_not_report_success(runtime, monkeypatch, capsys):
    _install_versions(runtime, monkeypatch)

    class FailingOsOps:
        @staticmethod
        def update_current_link(*_args):
            raise PermissionError("cannot update current")

    monkeypatch.setattr(rollback, "get_os_ops", lambda _os: FailingOsOps)

    with pytest.raises(PermissionError, match="cannot update current"):
        RollbackCommand().execute(runtime, RollbackArguments("sample", semver.Version(2, 0, 0)))

    app = Registry(runtime).get("sample")
    assert app is not None
    assert app.installed_version == semver.Version(3, 0, 0)
    assert capsys.readouterr().out == ""


def test_rollback_rejects_invalid_target_version():
    parser = argparse.ArgumentParser()
    RollbackCommand.register_command(parser.add_subparsers())
    args = parser.parse_args(["rollback", "sample", "not-a-version"])

    with pytest.raises(SystemExit) as exc_info:
        RollbackCommand.validate_arguments(parser, Runtime.current(), args)

    assert exc_info.value.code == 2


def test_rollback_parses_valid_semantic_version(runtime):
    parser = argparse.ArgumentParser()
    command_parser = RollbackCommand.register_command(parser.add_subparsers())
    args = parser.parse_args(["rollback", "sample", "v1.2.3"])

    RollbackCommand.validate_arguments(command_parser, runtime, args)

    assert RollbackCommand.parse_arguments(runtime, args) == RollbackArguments(
        "sample", semver.Version(1, 2, 3)
    )
