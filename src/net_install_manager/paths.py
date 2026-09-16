"""Path constants for the net install manager."""

from dataclasses import dataclass
from pathlib import Path, PureWindowsPath

from net_install_manager.config import Config
from net_install_manager.runtime_config import RuntimeInfo


@dataclass(frozen=True)
class Paths:
    """Dataclass representing installation target paths."""

    lib_dir: Path
    versions_dir: Path
    current_dir: Path
    bin_dir: Path
    bin_path: Path


def get_paths(
    config: Config,
    prefer_opt: bool = False,
    runtime: RuntimeInfo | None = None,
) -> Paths:
    """Return paths for installation targets.

    If system_wide is True, return system-wide paths.
    Otherwise, return user-specific paths.
    """
    runtime = runtime or RuntimeInfo.current()

    if runtime.os.is_posix:
        if runtime.system_wide:
            prefix = Path("/opt") if prefer_opt else Path("/usr/local")
        else:
            prefix = runtime.home_dir / ".local"

        lib_dir = prefix / "lib" / config.app_directory
        versions_dir = lib_dir
        current_dir = lib_dir / "current"
        bin_dir = prefix / "bin"
    else:
        if runtime.system_wide:
            program_files = Path(
                PureWindowsPath(runtime.env.get("PROGRAMFILES", r"C:\Program Files"))
            )
            app_root = program_files / config.app_directory
        else:
            local_app_data = Path(
                PureWindowsPath(
                    runtime.env.get("LOCALAPPDATA", str(runtime.home_dir / "AppData" / "Local"))
                )
            )
            app_root = local_app_data / config.app_directory

        lib_dir = app_root / "versions"
        versions_dir = lib_dir
        current_dir = app_root / "current"
        bin_dir = (
            app_root / "bin"
            if runtime.system_wide
            else runtime.home_dir / ".local" / "bin"
        )

    bin_path = bin_dir / config.binary_name

    return Paths(
        lib_dir=lib_dir,
        versions_dir=versions_dir,
        current_dir=current_dir,
        bin_dir=bin_dir,
        bin_path=bin_path,
    )


__all__ = ["Paths", "get_paths"]
