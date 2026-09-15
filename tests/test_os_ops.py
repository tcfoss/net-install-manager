"""Tests for the os_ops utility functions."""

from unittest.mock import patch
from net_install_manager.utilities.os_ops import (
    PosixOsOps,
    WindowsOsOps,
    get_os_ops,
    OsOpsProtocol,
)
from net_install_manager.utilities.sys_platform import OperatingSystem


def test_os_ops_protocol_conformance():
    """Test that the OS operations classes conform to the OsOpsProtocol."""
    assert isinstance(PosixOsOps, OsOpsProtocol)
    assert isinstance(WindowsOsOps, OsOpsProtocol)
    assert get_os_ops(OperatingSystem.LINUX) is PosixOsOps
    assert get_os_ops(OperatingSystem.MACOS) is PosixOsOps
    assert get_os_ops(OperatingSystem.WINDOWS) is WindowsOsOps


def test_mirror_directory(tmp_path):
    """Test mirroring a directory while excluding certain patterns."""
    src = tmp_path / "src"
    src.mkdir()
    (src / "file1.txt").write_text("hello", encoding="utf-8")
    (src / "sub").mkdir()
    (src / "sub" / "file2.txt").write_text("world", encoding="utf-8")
    (src / "ignore.log").write_text("skip", encoding="utf-8")

    dest = tmp_path / "dest"
    PosixOsOps.mirror_directory(
        src=src,
        dest=dest,
        exclude_patterns=["*.log"],
    )

    assert (dest / "file1.txt").read_text(encoding="utf-8") == "hello"
    assert (dest / "sub" / "file2.txt").read_text(encoding="utf-8") == "world"
    assert not (dest / "ignore.log").exists()


def test_make_executable_posix(tmp_path):
    """Test making a file executable on POSIX systems."""
    f = tmp_path / "test.sh"
    f.write_text("#!/bin/sh\necho test\n", encoding="utf-8")
    with patch("pathlib.Path.chmod") as mock_chmod:
        PosixOsOps.make_executable(f)
        mock_chmod.assert_called_once()


def test_make_executable_windows_noop(tmp_path):
    """Test that making a file executable on Windows is a no-op."""
    f = tmp_path / "test.exe"
    f.write_text("binary", encoding="utf-8")
    with patch("pathlib.Path.chmod") as mock_chmod:
        WindowsOsOps.make_executable(f)
        mock_chmod.assert_not_called()


def test_set_permissions_posix(tmp_path):
    """Test setting file permissions on POSIX systems."""
    f = tmp_path / "perm.txt"
    f.write_text("content", encoding="utf-8")
    with patch("pathlib.Path.chmod") as mock_chmod:
        PosixOsOps.set_permissions(f, permissions="0644")
        mock_chmod.assert_called_once_with(0o644)


def test_set_permissions_windows_noop(tmp_path):
    """Test that setting file permissions on Windows is a no-op."""
    f = tmp_path / "perm.txt"
    f.write_text("content", encoding="utf-8")
    with patch("pathlib.Path.chmod") as mock_chmod:
        WindowsOsOps.set_permissions(f, permissions="0644")
        mock_chmod.assert_not_called()


def test_create_bin_launcher_posix(tmp_path):
    """Test creating a binary launcher on POSIX systems."""
    bin_dir = tmp_path / "bin"
    target_exec = tmp_path / "app" / "current" / "myapp"
    target_exec.parent.mkdir(parents=True)
    target_exec.write_text("executable", encoding="utf-8")

    with patch("pathlib.Path.symlink_to") as mock_symlink:
        PosixOsOps.create_bin_launcher(
            bin_dir=bin_dir,
            bin_name="myapp",
            target_executable=target_exec,
        )
        mock_symlink.assert_called_once_with(target_exec)


def test_create_bin_launcher_posix_dll(tmp_path):
    """Test creating a binary launcher for a .dll file on POSIX systems."""
    bin_dir = tmp_path / "bin"
    target_dll = tmp_path / "app" / "current" / "myapp.dll"
    target_dll.parent.mkdir(parents=True)
    target_dll.write_text("dll", encoding="utf-8")

    PosixOsOps.create_bin_launcher(
        bin_dir=bin_dir,
        bin_name="myapp",
        target_executable=target_dll,
    )

    launcher = bin_dir / "myapp"
    assert launcher.is_file()
    content = launcher.read_text(encoding="utf-8")
    assert "dotnet" in content


def test_create_bin_launcher_windows(tmp_path):
    """Test creating a binary launcher on Windows systems."""
    bin_dir = tmp_path / "bin"
    target_exe = tmp_path / "app" / "current" / "myapp.exe"
    target_exe.parent.mkdir(parents=True)
    target_exe.write_text("exe", encoding="utf-8")

    WindowsOsOps.create_bin_launcher(
        bin_dir=bin_dir,
        bin_name="myapp",
        target_executable=target_exe,
    )

    cmd_file = bin_dir / "myapp.cmd"
    assert cmd_file.is_file()
    content = cmd_file.read_text(encoding="utf-8")
    assert "%~dp0" in content
    assert "myapp.exe" in content

    bash_file = bin_dir / "myapp"
    assert bash_file.is_file()
