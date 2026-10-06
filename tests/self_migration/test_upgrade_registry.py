from dataclasses import replace
from pathlib import Path

import pytest
import yaml

from net_install_manager.commands import self_migrate
from net_install_manager.commands.self_migrate import SelfMigrateCommand
from net_install_manager.config.app_sources import BuiltAppSource
from net_install_manager.core import errors
from net_install_manager.core.registry import Registry
from net_install_manager.runtime.runtime import Runtime
from net_install_manager.self_migration import mod_0_2_0_upgrade_registry as migration


def _runtime(registry_path: Path) -> Runtime:
    return replace(Runtime.current(), registry_path=registry_path)


def _legacy_entry(version: str, source: dict | None = None) -> dict:
    return {
        "binary_name": "sample",
        "app_directory": "Sample",
        "source_binary_name": "Sample",
        "source": source if source is not None else {"local_path": "/build"},
        "lib_path": "/install/Sample",
        "installed_version": version,
    }


@pytest.mark.parametrize(
    ("version", "source"),
    [("not-semver", {"local_path": "/build"}), ("1.2.3", {})],
)
def test_legacy_migration_failure_preserves_original_registry(tmp_path, version, source):
    runtime = _runtime(tmp_path / "apps.yaml")
    original = {"sample": _legacy_entry(version, source)}
    original_contents = yaml.safe_dump(original)
    runtime.registry_path.write_text(original_contents, encoding="utf-8")

    assert migration.main(runtime) == 1

    assert runtime.registry_path.read_text(encoding="utf-8") == original_contents


def test_legacy_migration_converts_registry_and_adds_version_marker(tmp_path):
    runtime = _runtime(tmp_path / "apps.yaml")
    runtime.registry_path.write_text(
        yaml.safe_dump({"sample": _legacy_entry("1.2.3")}),
        encoding="utf-8",
    )

    assert migration.main(runtime) == 0

    registry = Registry(runtime)
    app = registry.get("sample")
    assert app is not None
    assert str(app.installed_version) == "1.2.3"
    assert app.app_source == BuiltAppSource(Path("/build"))
    assert registry.version is not None


def test_self_migrate_command_raises_when_migration_fails(monkeypatch, tmp_path):
    monkeypatch.setattr(self_migrate, "migrate_main", lambda _runtime: 1)

    with pytest.raises(errors.SelfMigrationError) as exc_info:
        SelfMigrateCommand().execute(_runtime(tmp_path / "apps.yaml"), None)

    assert exc_info.value.status == 1
