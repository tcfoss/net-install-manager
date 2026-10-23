import argparse

import pytest
import semver

from net_install_manager.commands.list_apps import ListAppsArgs, ListAppsCommand
from net_install_manager.commands.list_versions import ListVersionsArgs, ListVersionsCommand
from net_install_manager.config.app_info import AppInfo
from net_install_manager.config.app_sources import BuiltAppSource
from net_install_manager.config.paths import get_paths
from net_install_manager.core import errors
from net_install_manager.core.registry import Registry


@pytest.fixture
def installed_app(runtime):
    paths = get_paths(runtime, "Demo", "demo")
    for version in ("1.0.0", "2.0.0", "1.1.0-rc.1"):
        (paths.versions_dir / version).mkdir(parents=True)
    app = AppInfo(
        binary_name="demo", source_binary_name="Demo", lib_dir=paths.lib_dir,
        installed_version=semver.Version(2, 0, 0),
        app_source=BuiltAppSource(runtime.home_dir / "build"),
    )
    Registry(runtime).set("demo", app)
    return app


def test_list_apps_prints_registered_versions(runtime, installed_app, capsys):
    ListAppsCommand().execute(runtime, ListAppsArgs())

    assert capsys.readouterr().out == "Installed applications:\ndemo (2.0.0)\n"


@pytest.mark.parametrize("reverse", [False, True])
def test_list_versions_sorts_semantically_and_labels_current(
    runtime, installed_app, capsys, reverse
):
    ListVersionsCommand().execute(runtime, ListVersionsArgs("demo", reverse))

    lines = [" - 1.0.0", " - 1.1.0-rc.1", " - 2.0.0 (current)"]
    if not reverse:
        lines.reverse()
    assert capsys.readouterr().out == "Installed versions for demo:\n" + "\n".join(lines) + "\n"


def test_list_versions_unregistered_app_does_not_print_success(runtime, capsys):
    with pytest.raises(errors.AppNotRegisteredError) as exc_info:
        ListVersionsCommand().execute(runtime, ListVersionsArgs("missing"))

    assert exc_info.value.app_name == "missing"
    assert exc_info.value.registry_path == runtime.registry_path
    assert capsys.readouterr().out == ""


def test_list_commands_parse_arguments(runtime):
    assert ListAppsCommand.parse_arguments(runtime, argparse.Namespace()) == ListAppsArgs()
    assert ListVersionsCommand.parse_arguments(
        runtime, argparse.Namespace(app_name="demo", reverse=True)
    ) == ListVersionsArgs("demo", True)
