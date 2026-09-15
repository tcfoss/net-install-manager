"""Tests for the sys_platform utility functions."""

from net_install_manager.utilities.sys_platform import (
    OperatingSystem,
    Architecture,
    PlatformInfo,
    _is_admin,
)

def test_operating_system_is_posix():
    """Test the is_posix property of the OperatingSystem enum."""
    assert OperatingSystem.LINUX.is_posix is True
    assert OperatingSystem.MACOS.is_posix is True
    assert OperatingSystem.WINDOWS.is_posix is False

def test_operating_system_current():
    """Test retrieving the current operating system."""
    current_os = OperatingSystem.current()
    assert isinstance(current_os, OperatingSystem)

def test_architecture_current():
    """Test retrieving the current system architecture."""
    current_arch = Architecture.current()
    assert isinstance(current_arch, Architecture)

def test_platform_info_detect():
    """Test detecting platform information."""
    info = PlatformInfo.detect()
    assert isinstance(info.os, OperatingSystem)
    assert isinstance(info.architecture, Architecture)
    assert isinstance(info.is_admin, bool)
    assert info.is_posix == (info.os in (OperatingSystem.LINUX, OperatingSystem.MACOS))

def test_is_admin_check():
    """Test checking if the current user has administrative privileges."""
    admin_status = _is_admin()
    assert isinstance(admin_status, bool)
