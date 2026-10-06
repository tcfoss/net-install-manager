import shutil
from pathlib import Path
from typing import Any

from net_install_manager.config.paths import Paths
from net_install_manager.core.os_ops import OsOpsProtocol


class OpsOptions:
    """Optional assertions for shared fake OS operations."""

    def mirror_directory_assertions(self, data: dict[str, Any]) -> None:
        pass

    def make_executable_assertions(self, data: dict[str, Any]) -> None:
        pass

    def update_current_link_assertions(self, data: dict[str, Any]) -> None:
        pass

    def create_bin_launcher_assertions(self, data: dict[str, Any]) -> None:
        pass

    def set_permissions_assertions(self, data: dict[str, Any]) -> None:
        pass

    def remove_link_or_dir_assertions(self, data: dict[str, Any]) -> None:
        pass

    def remove_application_assertions(self, data: dict[str, Any]) -> None:
        pass


def get_test_os_ops(
    calls: dict[str, Any] | None = None,
    options: OpsOptions | None = None,
) -> type[OsOpsProtocol]:
    real_calls = calls if calls is not None else {}
    real_options = options or OpsOptions()

    class TestOsOps:
        @staticmethod
        def mirror_directory(
            src: Path,
            dest: Path,
            exclude_patterns: list[str] | None = None,
        ) -> None:
            real_calls["mirror_directory"] = (src, dest, exclude_patterns)
            shutil.copytree(src, dest)
            real_options.mirror_directory_assertions(locals())

        @staticmethod
        def make_executable(file_path: Path) -> None:
            real_calls["make_executable"] = file_path
            real_options.make_executable_assertions(locals())

        @staticmethod
        def update_current_link(
            versions_dir: Path,
            target_version: str,
            current_dir: Path,
        ) -> Path:
            real_calls["update_current_link"] = (versions_dir, target_version, current_dir)
            real_options.update_current_link_assertions(locals())

            return current_dir

        @staticmethod
        def create_bin_launcher(
            bin_dir: Path,
            bin_name: str,
            target_executable: Path,
        ) -> None:
            real_calls["create_bin_launcher"] = (bin_dir, bin_name, target_executable)
            real_options.create_bin_launcher_assertions(locals())

        @staticmethod
        def set_permissions(path: Path, permissions: str | int | None = None) -> None:
            real_calls["set_permissions"] = (path, permissions)
            real_options.set_permissions_assertions(locals())

        @staticmethod
        def remove_link_or_dir(path: Path) -> None:
            real_calls["remove_link_or_dir"] = path
            real_options.remove_link_or_dir_assertions(locals())

        @staticmethod
        def remove_application(paths: Paths) -> None:
            real_calls["remove_application"] = paths
            real_options.remove_application_assertions(locals())

    return TestOsOps
