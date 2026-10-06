"""Installation target paths."""

from dataclasses import dataclass
from pathlib import Path

from net_install_manager.config.app_info import AppInfo
from net_install_manager.runtime.runtime import Runtime
from net_install_manager.utilities import paths as util_paths


@dataclass(frozen=True)
class Paths:
    """Dataclass representing installation target paths."""

    lib_dir: Path
    versions_dir: Path
    current_dir: Path
    bin_dir: Path
    bin_path: Path


def get_paths(
    runtime: Runtime,
    app_directory: str,
    binary_name: str,
    prefer_opt: bool = False,
) -> Paths:
    """Return paths for installation targets.

    If system_wide is True, return system-wide paths.
    Otherwise, return user-specific paths.
    """

    if runtime.os.is_posix:
        if runtime.system_wide:
            prefix = Path("/opt") if prefer_opt else Path("/usr/local")
        else:
            prefix = runtime.home_dir / ".local"

        lib_dir = prefix / "lib" / app_directory
        versions_dir = lib_dir
        current_dir = lib_dir / "current"
        bin_dir = prefix / "bin"
    else:
        if runtime.system_wide:
            program_files = util_paths.get_winpath_env(
                "PROGRAMFILES", runtime.env, r"C:\Program Files"
            )
            app_root = program_files / app_directory
        else:
            local_app_data = util_paths.get_winpath_env(
                "LOCALAPPDATA", runtime.env, runtime.home_dir / "AppData" / "Local"
            )
            app_root = local_app_data / app_directory

        lib_dir = app_root / "versions"
        versions_dir = lib_dir
        current_dir = app_root / "current"
        bin_dir = app_root / "bin" if runtime.system_wide else runtime.home_dir / ".local" / "bin"

    bin_path = bin_dir / binary_name

    return Paths(
        lib_dir=lib_dir,
        versions_dir=versions_dir,
        current_dir=current_dir,
        bin_dir=bin_dir,
        bin_path=bin_path,
    )


def get_paths_from_app_info(runtime: Runtime, app_info: AppInfo) -> Paths:
    """Return installation target paths based on the given AppInfo instance."""

    return get_paths(
        runtime=runtime,
        app_directory=app_info.lib_dir.name,
        binary_name=app_info.binary_name,
        prefer_opt=Path("/opt") in app_info.lib_dir.parents,
    )


__all__ = ["Paths", "get_paths", "get_paths_from_app_info"]
