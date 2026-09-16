"""Tests for the path resolution logic in Net Install Manager."""

from pathlib import Path
import pytest

from net_install_manager.config import Config
from net_install_manager.paths import get_paths
from net_install_manager.runtime_config import RuntimeInfo
from net_install_manager.utilities.sys_platform import OperatingSystem, PlatformInfo, get_winpath

# pylint: disable=redefined-outer-name


@pytest.fixture
def sample_config():
    """Provide a sample configuration for testing."""
    return Config(app_directory="my_app", binary_name="my_bin", source_binary_name="MyApp.dll")


def test_paths_posix_user(sample_config):
    """Test path resolution for a POSIX user installation."""
    fake_home = Path("/home/testuser")
    runtime = RuntimeInfo(
        home_dir=fake_home,
        platform=PlatformInfo(
            os=OperatingSystem.LINUX,
            architecture=PlatformInfo.detect().architecture,
            is_admin=False,
        ),
        system_wide=False,
    )
    paths = get_paths(
        config=sample_config,
        runtime=runtime,
    )
    assert paths.lib_dir == fake_home / ".local" / "lib" / "my_app"
    assert paths.bin_dir == fake_home / ".local" / "bin"
    assert paths.bin_path == fake_home / ".local" / "bin" / "my_bin"


def test_paths_posix_system_default(sample_config):
    """Test path resolution for a POSIX system-wide installation with default paths."""
    runtime = RuntimeInfo(
        platform=PlatformInfo(
            os=OperatingSystem.LINUX,
            architecture=PlatformInfo.detect().architecture,
            is_admin=False,
        ),
        system_wide=True,
    )
    paths = get_paths(
        config=sample_config,
        prefer_opt=False,
        runtime=runtime,
    )
    assert paths.lib_dir == Path("/usr/local/lib/my_app")
    assert paths.bin_dir == Path("/usr/local/bin")
    assert paths.bin_path == Path("/usr/local/bin/my_bin")


def test_paths_posix_system_opt(sample_config):
    """Test path resolution for a POSIX system-wide installation with /opt paths."""
    runtime = RuntimeInfo(
        platform=PlatformInfo(
            os=OperatingSystem.MACOS,
            architecture=PlatformInfo.detect().architecture,
            is_admin=False,
        ),
        system_wide=True,
    )
    paths = get_paths(
        config=sample_config,
        prefer_opt=True,
        runtime=runtime,
    )
    assert paths.lib_dir == Path("/opt/lib/my_app")
    assert paths.bin_dir == Path("/opt/bin")
    assert paths.bin_path == Path("/opt/bin/my_bin")


def test_paths_windows_user(sample_config):
    """Test path resolution for a Windows user installation."""
    fake_env = {"LOCALAPPDATA": r"C:\Users\testuser\AppData\Local"}
    runtime = RuntimeInfo(
        env=fake_env,
        home_dir=get_winpath(r"C:\Users\testuser"),
        platform=PlatformInfo(
            os=OperatingSystem.WINDOWS,
            architecture=PlatformInfo.detect().architecture,
            is_admin=False,
        ),
        system_wide=False,
    )
    paths = get_paths(
        config=sample_config,
        runtime=runtime,
    )
    assert paths.lib_dir == get_winpath(r"C:\Users\testuser\AppData\Local\my_app\versions")
    assert paths.current_dir == get_winpath(r"C:\Users\testuser\AppData\Local\my_app\current")
    assert paths.bin_dir == get_winpath(r"C:\Users\testuser\.local\bin")
    assert paths.bin_path == get_winpath(r"C:\Users\testuser\.local\bin\my_bin")


def test_paths_windows_system(sample_config):
    """Test path resolution for a Windows system-wide installation."""
    fake_env = {"PROGRAMFILES": r"C:\Program Files"}
    runtime = RuntimeInfo(
        env=fake_env,
        platform=PlatformInfo(
            os=OperatingSystem.WINDOWS,
            architecture=PlatformInfo.detect().architecture,
            is_admin=False,
        ),
        system_wide=True,
    )
    paths = get_paths(
        config=sample_config,
        runtime=runtime,
    )
    assert paths.lib_dir == get_winpath(r"C:\Program Files\my_app\versions")
    assert paths.bin_dir == get_winpath(r"C:\Program Files\my_app\bin")
    assert paths.bin_path == get_winpath(r"C:\Program Files\my_app\bin\my_bin")
