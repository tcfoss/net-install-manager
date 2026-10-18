import semver

from net_install_manager.commands import uninstall
from net_install_manager.commands.uninstall import UninstallArguments, UninstallCommand
from net_install_manager.config.app_info import AppInfo
from net_install_manager.config.app_sources import BuiltAppSource
from net_install_manager.config.paths import get_paths
from net_install_manager.core.registry import Registry


def test_uninstall_delegates_cleanup_before_removing_registry_entry(runtime, tmp_path, monkeypatch):
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
