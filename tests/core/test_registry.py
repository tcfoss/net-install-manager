from pathlib import Path

import pytest
import semver
import yaml

from net_install_manager.__version__ import __version__
from net_install_manager.config.app_info import AppInfo
from net_install_manager.config.app_sources import BuiltAppSource
from net_install_manager.core import errors
from net_install_manager.core.registry import Registry
from net_install_manager.runtime.architecture import Architecture
from net_install_manager.runtime.operating_system import OperatingSystem
from net_install_manager.runtime.platform_info import PlatformInfo
from net_install_manager.runtime.runtime import Runtime


def _runtime(registry_path: Path) -> Runtime:
    return Runtime(
        platform=PlatformInfo(OperatingSystem.LINUX, Architecture.X86_64),
        env={},
        registry_path=registry_path,
        home_dir=registry_path.parent,
    )


def _app(name: str, version: str = "1.2.3", lib_root: str | None = None) -> AppInfo:
    root = Path(lib_root) if lib_root is not None else Path("/install") / name
    return AppInfo(
        binary_name=name,
        source_binary_name=f"{name}.dll",
        lib_dir=root,
        installed_version=semver.Version.parse(version),
        app_source=BuiltAppSource(root / "dist"),
        exclude_patterns=["*.pdb"],
        target_permissions="755",
    )


def test_registry_starts_empty_when_registry_file_is_missing(tmp_path):
    registry = Registry(_runtime(tmp_path / "config" / "apps.yaml"))

    assert registry.get_installed_apps() == []
    assert registry.get("missing") is None
    assert registry.version == __version__


def test_registry_set_persists_and_reloads_app_info(tmp_path):
    runtime = _runtime(tmp_path / "config" / "apps.yaml")
    app = _app("sample")

    Registry(runtime).set(app.binary_name, app)
    loaded_registry = Registry(runtime)

    assert loaded_registry.get(app.binary_name) == app
    assert loaded_registry.get_installed_apps() == [("sample", semver.Version(1, 2, 3))]
    assert loaded_registry.version == __version__
    assert yaml.safe_load(runtime.registry_path.read_text(encoding="utf-8"))[
        "__NINMAN_VERSION__"
    ] == str(__version__)
    assert runtime.registry_path.is_file()


def test_registry_save_preserves_existing_file_if_serialization_fails(tmp_path, monkeypatch):
    runtime = _runtime(tmp_path / "apps.yaml")
    original_contents = '__NINMAN_VERSION__: "0.2.0"\n'
    runtime.registry_path.write_text(original_contents, encoding="utf-8")
    registry = Registry(runtime)

    def fail_dump(_contents):
        raise yaml.representer.RepresenterError("serialization failed")

    monkeypatch.setattr(yaml, "safe_dump", fail_dump)

    with pytest.raises(yaml.representer.RepresenterError):
        registry._save()

    assert runtime.registry_path.read_text(encoding="utf-8") == original_contents


def test_registry_updates_existing_entry(tmp_path):
    runtime = _runtime(tmp_path / "apps.yaml")
    registry = Registry(runtime)
    registry.set("sample", _app("sample", "1.0.0"))
    registry.set("sample", _app("sample", "2.0.0"))

    app = Registry(runtime).get("sample")
    assert app is not None
    assert app.installed_version == semver.Version(2, 0, 0)


def test_registry_remove_persists_and_missing_remove_is_noop(tmp_path):
    runtime = _runtime(tmp_path / "apps.yaml")
    registry = Registry(runtime)
    registry.set("sample", _app("sample"))

    registry.remove("unknown")
    assert Registry(runtime).get("sample") is not None

    registry.remove("sample")
    assert Registry(runtime).get("sample") is None
    assert Registry(runtime).get_installed_apps() == []


def test_registry_get_installed_versions_none_on_missing_app(tmp_path):
    runtime = _runtime(tmp_path / "apps.yaml")
    registry = Registry(runtime)

    assert registry.get_installed_versions("missing") is None


def test_registry_get_installed_versions_versions_dir_not_exists(tmp_path):
    runtime = _runtime(tmp_path / "apps.yaml")
    registry = Registry(runtime)
    registry.set("sample", _app("sample"))

    with pytest.raises(errors.InstallationDirectoryNotFoundError):
        registry.get_installed_versions("sample")


def test_registry_get_installed_versions_warning_on_unparseable_version_directory(
    tmp_path, caplog
):
    runtime = _runtime(tmp_path / "apps.yaml")
    registry = Registry(runtime)
    registry.set("sample", _app("sample", lib_root=str(tmp_path / "install" / "sample")))

    # Create an unparseable version directory
    (tmp_path / ".local" / "lib" / "sample" / "bad_version").mkdir(parents=True)

    versions = registry.get_installed_versions("sample")
    assert versions
    assert not versions.versions
    assert any("Failed to parse version" in record.message for record in caplog.records)
