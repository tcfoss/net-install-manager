import pytest

from net_install_manager.config.paths import Paths
from net_install_manager.core import os_ops
from net_install_manager.runtime.operating_system import OperatingSystem


def test_posix_mirror_directory_copies_and_excludes(tmp_path):
    source = tmp_path / "source"
    source.mkdir()
    (source / "keep.txt").write_text("keep", encoding="utf-8")
    (source / "omit.tmp").write_text("omit", encoding="utf-8")
    destination = tmp_path / "nested" / "destination"

    os_ops.PosixOsOps.mirror_directory(source, destination, ["*.tmp"])

    assert (destination / "keep.txt").read_text(encoding="utf-8") == "keep"
    assert not (destination / "omit.tmp").exists()


@pytest.mark.parametrize(
    ("source_kind", "error"),
    [("missing", FileNotFoundError), ("file", NotADirectoryError)],
)
def test_posix_mirror_directory_validates_source(tmp_path, source_kind, error):
    source = tmp_path / "missing"
    if source_kind == "file":
        source.write_text("not a directory", encoding="utf-8")

    with pytest.raises(error):
        os_ops.PosixOsOps.mirror_directory(source, tmp_path / "destination")


def test_posix_mirror_directory_replaces_existing_destination(tmp_path):
    source = tmp_path / "source"
    source.mkdir()
    (source / "new.txt").write_text("new", encoding="utf-8")
    destination = tmp_path / "destination"
    destination.mkdir()
    (destination / "old.txt").write_text("old", encoding="utf-8")

    os_ops.PosixOsOps.mirror_directory(source, destination)

    assert (destination / "new.txt").exists()
    assert not (destination / "old.txt").exists()


def test_posix_make_executable_sets_execute_bits(tmp_path):
    path = tmp_path / "app"
    path.write_text("app", encoding="utf-8")
    path.chmod(0o600)

    os_ops.PosixOsOps.make_executable(path)

    assert path.stat().st_mode & 0o111 == 0o111


def test_posix_make_executable_rejects_missing_file(tmp_path):
    with pytest.raises(FileNotFoundError):
        os_ops.PosixOsOps.make_executable(tmp_path / "missing")


@pytest.mark.parametrize(("permissions", "expected"), [(0o640, 0o640), ("700", 0o700)])
def test_posix_set_permissions_accepts_integer_and_octal_string(tmp_path, permissions, expected):
    path = tmp_path / "app"
    path.write_text("app", encoding="utf-8")

    os_ops.PosixOsOps.set_permissions(path, permissions)

    assert path.stat().st_mode & 0o777 == expected


def test_posix_set_permissions_ignores_invalid_string_and_missing_path(tmp_path):
    path = tmp_path / "app"
    path.write_text("app", encoding="utf-8")
    original_mode = path.stat().st_mode & 0o777

    os_ops.PosixOsOps.set_permissions(path, "not-octal")
    os_ops.PosixOsOps.set_permissions(tmp_path / "missing", "700")

    assert path.stat().st_mode & 0o777 == original_mode


def test_posix_update_current_link_points_to_installed_version(tmp_path):
    versions = tmp_path / "versions"
    target = versions / "1.2.3"
    target.mkdir(parents=True)
    current = tmp_path / "app" / "current"

    result = os_ops.PosixOsOps.update_current_link(versions, "1.2.3", current)

    assert result == current
    assert current.is_symlink()
    assert current.resolve() == target.resolve()


def test_posix_update_current_link_replaces_previous_link(tmp_path):
    versions = tmp_path / "versions"
    for version in ("1.0.0", "2.0.0"):
        (versions / version).mkdir(parents=True)
    current = tmp_path / "app" / "current"
    current.parent.mkdir()
    current.symlink_to(versions / "1.0.0")

    os_ops.PosixOsOps.update_current_link(versions, "2.0.0", current)

    assert current.resolve() == (versions / "2.0.0").resolve()


def test_update_current_link_rejects_missing_version(tmp_path):
    with pytest.raises(FileNotFoundError):
        os_ops.PosixOsOps.update_current_link(tmp_path / "versions", "1.0.0", tmp_path / "current")


def test_posix_create_launcher_symlinks_native_executable(tmp_path):
    binary = tmp_path / "versions" / "current" / "app"
    binary.parent.mkdir(parents=True)
    binary.touch()
    bin_dir = tmp_path / "bin"

    os_ops.PosixOsOps.create_bin_launcher(bin_dir, "sample", binary)

    assert (bin_dir / "sample").is_symlink()
    assert (bin_dir / "sample").resolve() == binary


def test_posix_create_launcher_writes_dotnet_wrapper_for_dll(tmp_path):
    binary = tmp_path / "versions" / "current" / "app.dll"
    binary.parent.mkdir(parents=True)
    binary.touch()
    launcher = tmp_path / "bin" / "sample"

    os_ops.PosixOsOps.create_bin_launcher(launcher.parent, launcher.name, binary)

    assert launcher.read_text(encoding="utf-8") == f'#!/bin/sh\nexec dotnet "{binary}" "$@"\n'
    assert launcher.stat().st_mode & 0o111


@pytest.mark.parametrize("kind", ["file", "directory", "symlink", "missing"])
def test_posix_remove_link_or_dir_handles_path_kinds(tmp_path, kind):
    path = tmp_path / "target"
    if kind == "file":
        path.write_text("file", encoding="utf-8")
    elif kind == "directory":
        path.mkdir()
        (path / "child").touch()
    elif kind == "symlink":
        target = tmp_path / "real"
        target.mkdir()
        path.symlink_to(target)

    os_ops.PosixOsOps.remove_link_or_dir(path)

    assert not path.exists(follow_symlinks=False)


def test_posix_remove_application_handles_app_named_versions(tmp_path):
    library_parent = tmp_path / ".local" / "lib"
    lib_dir = library_parent / "versions"
    (lib_dir / "1.0.0").mkdir(parents=True)
    bin_dir = tmp_path / ".local" / "bin"
    bin_dir.mkdir(parents=True)
    bin_path = bin_dir / "sample"
    bin_path.symlink_to(tmp_path / "missing-target")
    paths = Paths(
        lib_dir=lib_dir,
        versions_dir=lib_dir,
        current_dir=lib_dir / "current",
        bin_dir=bin_dir,
        bin_path=bin_path,
    )

    os_ops.PosixOsOps.remove_application(paths)

    assert not lib_dir.exists()
    assert library_parent.is_dir()
    assert not bin_path.exists(follow_symlinks=False)


def test_windows_update_current_link_generates_junction_command(tmp_path, monkeypatch):
    versions = tmp_path / "versions"
    (versions / "1.2.3").mkdir(parents=True)
    current = tmp_path / "application" / "current"
    commands = []
    monkeypatch.setattr(
        os_ops,
        "exec_command",
        lambda command, **kwargs: commands.append((command, kwargs)),
    )

    result = os_ops.WindowsOsOps.update_current_link(versions, "1.2.3", current)

    assert result == current
    assert commands == [(["cmd", "/c", "mklink", "/J", str(current), str(versions / "1.2.3")], {})]


def test_windows_update_current_link_cleans_existing_nonempty_directory(tmp_path, monkeypatch):
    versions = tmp_path / "versions"
    (versions / "1.2.3").mkdir(parents=True)
    current = tmp_path / "application" / "current"
    current.mkdir(parents=True)
    (current / "child").touch()
    commands = []
    monkeypatch.setattr(
        os_ops,
        "exec_command",
        lambda command, **kwargs: commands.append((command, kwargs)),
    )

    os_ops.WindowsOsOps.update_current_link(versions, "1.2.3", current)

    assert commands[0] == (
        ["cmd", "/c", "rmdir", str(current)],
        {"output": os_ops.CommandOutput.QUIET},
    )
    assert commands[1][0][:4] == ["cmd", "/c", "mklink", "/J"]


def test_windows_create_bin_launcher_writes_cmd_and_shell_wrappers(tmp_path):
    bin_dir = tmp_path / "bin"
    binary = tmp_path / "versions" / "current" / "app.dll"
    binary.parent.mkdir(parents=True)
    binary.touch()

    os_ops.WindowsOsOps.create_bin_launcher(bin_dir, "sample", binary)

    command_file = (bin_dir / "sample.cmd").read_text(encoding="utf-8")
    shell_file = (bin_dir / "sample").read_text(encoding="utf-8")
    assert command_file.startswith('@dotnet "%~dp0')
    assert "app.dll" in command_file
    assert "exec dotnet" in shell_file
    assert "app.dll" in shell_file


def test_windows_create_bin_launcher_writes_executable_wrappers(tmp_path):
    bin_dir = tmp_path / "bin"
    binary = tmp_path / "versions" / "current" / "app.exe"
    binary.parent.mkdir(parents=True)
    binary.touch()

    os_ops.WindowsOsOps.create_bin_launcher(bin_dir, "sample", binary)

    command_file = (bin_dir / "sample.cmd").read_text(encoding="utf-8")
    shell_file = (bin_dir / "sample").read_text(encoding="utf-8")
    assert command_file.startswith('@"%~dp0')
    assert "app.exe" in command_file
    assert 'exec "$CURR_DIR/' in shell_file


def test_windows_remove_link_or_dir_removes_nonempty_directory(tmp_path):
    path = tmp_path / "target"
    path.mkdir()
    (path / "child").touch()

    os_ops.WindowsOsOps.remove_link_or_dir(path)

    assert not path.exists()


def test_windows_remove_application_cleans_app_root_and_both_launchers(tmp_path):
    app_root = tmp_path / "Program Files" / "DemoApp"
    versions_dir = app_root / "versions"
    version_dir = versions_dir / "1.0.0"
    version_dir.mkdir(parents=True)
    current_dir = app_root / "current"
    current_dir.symlink_to(version_dir, target_is_directory=True)
    bin_dir = tmp_path / "home" / ".local" / "bin"
    bin_dir.mkdir(parents=True)
    bin_path = bin_dir / "sample"
    bin_path.write_text("shell launcher", encoding="utf-8")
    (bin_dir / "sample.cmd").write_text("cmd launcher", encoding="utf-8")
    sibling = bin_dir / "other-app"
    sibling.touch()
    paths = Paths(
        lib_dir=versions_dir,
        versions_dir=versions_dir,
        current_dir=current_dir,
        bin_dir=bin_dir,
        bin_path=bin_path,
    )

    os_ops.WindowsOsOps.remove_application(paths)

    assert not app_root.exists()
    assert not bin_path.exists()
    assert not (bin_dir / "sample.cmd").exists()
    assert sibling.is_file()


@pytest.mark.parametrize(
    ("target_os", "expected"),
    [
        (OperatingSystem.LINUX, os_ops.PosixOsOps),
        (OperatingSystem.MACOS, os_ops.PosixOsOps),
        (OperatingSystem.WINDOWS, os_ops.WindowsOsOps),
    ],
)
def test_get_os_ops_selects_platform_implementation(target_os, expected):
    assert os_ops.get_os_ops(target_os) is expected
