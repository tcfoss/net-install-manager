import argparse
from dataclasses import replace
from pathlib import Path

import pytest
import semver

from net_install_manager.commands import rollback
from net_install_manager.commands.rollback import RollbackArguments, RollbackCommand
from net_install_manager.config.app_info import AppInfo
from net_install_manager.config.app_sources import BuiltAppSource
from net_install_manager.config.paths import Paths, get_paths_from_app_info
from net_install_manager.core import errors
from net_install_manager.core.registry import Registry
from net_install_manager.runtime.runtime import Runtime


def _runtime(tmp_path: Path) -> Runtime:
    return replace(
        Runtime.current(),
        home_dir=tmp_path,
        registry_path=tmp_path / "config" / "apps.yaml",
    )


def _app(tmp_path: Path) -> AppInfo:
    return AppInfo(
        binary_name="sample",
        source_binary_name="Sample",
        lib_dir=tmp_path / ".local" / "lib" / "Sample",
        installed_version=semver.Version(3, 0, 0),
        app_source=BuiltAppSource(tmp_path / "build"),
    )


def _install_versions(tmp_path: Path, monkeypatch) -> tuple[Runtime, Paths, list[tuple[str, str]]]:
    runtime = _runtime(tmp_path)
    app = _app(tmp_path)
    paths = get_paths_from_app_info(runtime, app)
    for version in ("1.0.0", "2.0.0", "3.0.0"):
        (paths.versions_dir / version).mkdir(parents=True)
    paths.current_dir.symlink_to(paths.versions_dir / "3.0.0", target_is_directory=True)
    Registry(runtime).set(app.binary_name, app)
    calls: list[tuple[str, str]] = []

    class TestOsOps:
        @staticmethod
        def update_current_link(
            versions_dir: Path, target_version: str, current_dir: Path
        ) -> Path:
            calls.append(("switch", target_version))
            current_dir.unlink()
            current_dir.symlink_to(versions_dir / target_version, target_is_directory=True)
            return current_dir

    monkeypatch.setattr(rollback, "get_os_ops", lambda _os: TestOsOps)
    return runtime, paths, calls


def test_rollback_switches_current_and_updates_registry(tmp_path, monkeypatch):
    runtime, paths, calls = _install_versions(tmp_path, monkeypatch)

    RollbackCommand().execute(
        runtime,
        RollbackArguments("sample", semver.Version(2, 0, 0)),
    )

    registered = Registry(runtime).get("sample")
    assert registered is not None
    assert registered.installed_version == semver.Version(2, 0, 0)
    assert paths.current_dir.resolve() == paths.versions_dir / "2.0.0"
    assert calls == [("switch", "2.0.0")]


def test_rollback_raises_and_does_not_change_state_for_uninstalled_target(tmp_path, monkeypatch):
    runtime, paths, calls = _install_versions(tmp_path, monkeypatch)

    with pytest.raises(errors.VersionNotInstalledError) as exc_info:
        RollbackCommand().execute(
            runtime,
            RollbackArguments("sample", semver.Version(4, 0, 0)),
        )

    registered = Registry(runtime).get("sample")
    assert registered is not None
    assert registered.installed_version == semver.Version(3, 0, 0)
    assert paths.current_dir.resolve() == paths.versions_dir / "3.0.0"
    assert not calls
    assert exc_info.value.app_name == "sample"
    assert exc_info.value.version == "4.0.0"


def test_rollback_does_not_change_state_when_target_is_already_current(tmp_path, monkeypatch):
    runtime, paths, calls = _install_versions(tmp_path, monkeypatch)

    RollbackCommand().execute(
        runtime,
        RollbackArguments("sample", semver.Version(3, 0, 0)),
    )

    registered = Registry(runtime).get("sample")
    assert registered is not None
    assert registered.installed_version == semver.Version(3, 0, 0)
    assert paths.current_dir.resolve() == paths.versions_dir / "3.0.0"
    assert not calls


def test_rollback_raises_for_unregistered_application(tmp_path):
    runtime = _runtime(tmp_path)

    with pytest.raises(errors.AppNotRegisteredError):
        RollbackCommand().execute(
            runtime,
            RollbackArguments("sample", semver.Version(2, 0, 0)),
        )


def test_rollback_rejects_invalid_target_version():
    parser = argparse.ArgumentParser()
    RollbackCommand.register_command(parser.add_subparsers())
    args = parser.parse_args(["rollback", "sample", "not-a-version"])

    with pytest.raises(SystemExit) as exc_info:
        RollbackCommand.validate_arguments(parser, Runtime.current(), args)

    assert exc_info.value.code == 2
