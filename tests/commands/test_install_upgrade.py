from dataclasses import replace

import pytest
import semver

from net_install_manager.commands import install, upgrade
from net_install_manager.commands.install import InstallCommand
from net_install_manager.commands.upgrade import UpgradeCommand
from net_install_manager.config.app_sources import BuiltAppSource
from net_install_manager.config.build_options import BuildOptions
from net_install_manager.config.paths import get_paths
from net_install_manager.core import errors
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
from tests.shared_fixtures.os_ops_fixtures import get_test_os_ops


@pytest.fixture
def installation_request(runtime, tmp_path, monkeypatch):
    build_dir = tmp_path / "build"
    build_dir.mkdir()
    (build_dir / "Demo.dll").write_text("binary", encoding="utf-8")
    service = InstallationService(
        runtime,
        artifacts=get_test_artifact_provider(build_dir, None),
        os_ops=get_test_os_ops(),
    )
    monkeypatch.setattr(install, "InstallationService", lambda _runtime: service)
    monkeypatch.setattr(upgrade, "InstallationService", lambda _runtime: service)
    return InstallationRequest(
        app_source=BuiltAppSource(build_dir),
        targets=TargetOptions("demo", "Demo", "Demo App"),
        installation_options=InstallationOptions(version_override=semver.Version(1, 0, 0)),
        build_options=BuildOptions(),
    )


def test_install_reports_installed_version_and_path(runtime, installation_request, capsys):
    InstallCommand().execute(runtime, installation_request)

    assert Registry(runtime).get("demo") is not None
    assert capsys.readouterr().out == (
        "Successfully installed 'demo' version 1.0.0 "
        f"at '{get_paths(runtime, 'Demo App', 'demo').lib_dir}'.\n"
    )


def test_upgrade_reports_old_and_new_versions(runtime, installation_request, capsys):
    InstallCommand().execute(runtime, installation_request)
    capsys.readouterr()

    UpgradeCommand().execute(
        runtime, UpgradeRequest("demo", UpgradeOptions(version_override=semver.Version(2, 0, 0)))
    )

    app = Registry(runtime).get("demo")
    assert app is not None
    assert app.installed_version == semver.Version(2, 0, 0)
    assert capsys.readouterr().out == (
        "Successfully upgraded 'demo' from version 1.0.0 to 2.0.0.\n"
    )


def test_install_failure_does_not_report_success(runtime, installation_request, capsys):
    InstallCommand().execute(runtime, installation_request)
    capsys.readouterr()

    with pytest.raises(errors.AppAlreadyInstalledError):
        InstallCommand().execute(runtime, installation_request)

    assert capsys.readouterr().out == ""


def test_upgrade_failure_does_not_report_success(runtime, installation_request, capsys):
    with pytest.raises(errors.AppNotRegisteredError):
        UpgradeCommand().execute(runtime, UpgradeRequest("demo", UpgradeOptions()))

    assert capsys.readouterr().out == ""


def test_install_unresolved_version_does_not_report_success(
    runtime, installation_request, monkeypatch, capsys
):
    monkeypatch.setattr(
        "net_install_manager.core.installation_service.version_utils.get_version_from_binary",
        lambda _path: None,
    )
    request = replace(installation_request, installation_options=InstallationOptions())

    with pytest.raises(errors.UnresolvedVersionError):
        InstallCommand().execute(runtime, request)

    assert capsys.readouterr().out == ""
