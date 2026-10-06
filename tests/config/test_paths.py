from pathlib import Path, PureWindowsPath

import pytest
import semver

from net_install_manager.config.app_info import AppInfo
from net_install_manager.config.app_sources import BuiltAppSource
from net_install_manager.config.paths import get_paths, get_paths_from_app_info
from net_install_manager.runtime.architecture import Architecture
from net_install_manager.runtime.operating_system import OperatingSystem
from net_install_manager.runtime.platform_info import PlatformInfo
from net_install_manager.runtime.runtime import Runtime


def _runtime(os, *, system_wide=False, env=None, home=Path("/home/tester")):
    return Runtime(
        platform=PlatformInfo(os, Architecture.X86_64),
        env=env or {},
        registry_path=Path("/unused/registry.yaml"),
        home_dir=home,
        system_wide=system_wide,
    )


def test_posix_user_paths():
    paths = get_paths(_runtime(OperatingSystem.LINUX), "Sample", "sample")

    assert paths.lib_dir == Path("/home/tester/.local/lib/Sample")
    assert paths.versions_dir == paths.lib_dir
    assert paths.current_dir == paths.lib_dir / "current"
    assert paths.bin_dir == Path("/home/tester/.local/bin")
    assert paths.bin_path == paths.bin_dir / "sample"


@pytest.mark.parametrize(
    ("prefer_opt", "expected_prefix"),
    [(False, Path("/usr/local")), (True, Path("/opt"))],
)
def test_posix_system_paths(prefer_opt, expected_prefix):
    paths = get_paths(
        _runtime(OperatingSystem.LINUX, system_wide=True),
        "Sample",
        "sample",
        prefer_opt=prefer_opt,
    )

    assert paths.lib_dir == expected_prefix / "lib" / "Sample"
    assert paths.bin_dir == expected_prefix / "bin"


def test_windows_user_paths_use_environment_for_install_root():
    paths = get_paths(
        _runtime(
            OperatingSystem.WINDOWS,
            env={"LOCALAPPDATA": r"D:\Local"},
        ),
        "Sample",
        "sample",
    )

    app_root = Path(PureWindowsPath(r"D:\Local")) / "Sample"
    assert paths.lib_dir == app_root / "versions"
    assert paths.current_dir == app_root / "current"
    assert paths.bin_dir == Path("/home/tester/.local/bin")


def test_windows_system_paths_use_program_files():
    paths = get_paths(
        _runtime(
            OperatingSystem.WINDOWS,
            system_wide=True,
            env={"PROGRAMFILES": r"D:\Apps"},
        ),
        "Sample",
        "sample",
    )

    app_root = Path(PureWindowsPath(r"D:\Apps")) / "Sample"
    assert paths.lib_dir == app_root / "versions"
    assert paths.bin_dir == app_root / "bin"


@pytest.mark.parametrize(
    ("lib_dir", "system_wide", "expected"),
    [
        (Path("/opt/lib/Sample"), True, Path("/opt/lib/Sample")),
        (Path("/usr/local/lib/Sample"), True, Path("/usr/local/lib/Sample")),
    ],
)
def test_paths_from_registered_app_preserve_posix_prefix(lib_dir, system_wide, expected):
    runtime = _runtime(OperatingSystem.LINUX, system_wide=system_wide)
    app = AppInfo(
        "sample",
        "Sample.dll",
        lib_dir,
        semver.Version(1, 0, 0),
        BuiltAppSource(lib_dir),
    )

    assert get_paths_from_app_info(runtime, app).lib_dir == expected
