import argparse
from unittest.mock import Mock

import pytest
import semver

from net_install_manager.core.registry import Registry
from net_install_manager.commands.self_migrate import SelfMigrateCommand
from net_install_manager.self_migration import migrate
from net_install_manager.self_migration import mod_0_2_0_upgrade_registry as upgrade


def test_get_last_version_reads_registry(runtime):
    assert migrate._get_last_version(runtime) == Registry(runtime).version


@pytest.mark.parametrize(
    ("last_version", "migration_status", "expected"),
    [
        ("0.1.0", 0, 0),
        ("0.1.0", 3, 3),
        ("0.2.0", 3, 0),
        ("1.0.0", 3, 0),
    ],
)
def test_migrate_only_upgrades_older_registries(
    runtime, monkeypatch, last_version, migration_status, expected
):
    monkeypatch.setattr(migrate, "_get_last_version", lambda _runtime: semver.Version.parse(last_version))
    run_upgrade = Mock(return_value=migration_status)
    monkeypatch.setattr(upgrade, "main", run_upgrade)

    assert migrate.main(runtime) == expected
    if last_version == "0.1.0":
        run_upgrade.assert_called_once_with(runtime)
    else:
        run_upgrade.assert_not_called()


def test_migrate_attempts_legacy_upgrade_when_version_cannot_be_read(
    runtime, monkeypatch, caplog
):
    def fail(_runtime):
        raise ValueError("legacy registry")

    monkeypatch.setattr(migrate, "_get_last_version", fail)
    run_upgrade = Mock(return_value=0)
    monkeypatch.setattr(upgrade, "main", run_upgrade)

    assert migrate.main(runtime) == 0
    run_upgrade.assert_called_once_with(runtime)
    assert "Failed to retrieve last registry version: legacy registry" in caplog.text


def test_self_migrate_parses_without_command_arguments(runtime):
    parser = argparse.ArgumentParser()
    SelfMigrateCommand.register_command(parser.add_subparsers())
    args = parser.parse_args(["self-migrate"])

    assert SelfMigrateCommand.parse_arguments(runtime, args) is None
