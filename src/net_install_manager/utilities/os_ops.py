"""OS platform-specific filesystem and process operations via static protocol implementations."""

from pathlib import Path
import os
import shutil
import typing as typ
import logging

from net_install_manager.utilities.sys_platform import OperatingSystem
from net_install_manager.utilities.sh import exec_command

logger = logging.getLogger(__name__)

# pylint: disable=unnecessary-ellipsis

@typ.runtime_checkable
class OsOpsProtocol(typ.Protocol):
    """Protocol for OS-specific filesystem and launcher operations."""

    @staticmethod
    def mirror_directory(
        src: Path,
        dest: Path,
        exclude_patterns: list[str] | None = None,
    ) -> None:
        """Mirror the contents of the source directory to the destination directory."""
        ...

    @staticmethod
    def make_executable(file_path: Path) -> None:
        """Make a file executable."""
        ...

    @staticmethod
    def set_permissions(
        path: Path,
        permissions: str | int | None = None,
    ) -> None:
        """Set permissions on path."""
        ...

    @staticmethod
    def update_current_link(
        versions_dir: Path,
        target_version: str,
        current_dir: Path,
    ) -> Path:
        """Update the 'current' symlink/junction to point to the specified version."""
        ...

    @staticmethod
    def create_bin_launcher(
        bin_dir: Path,
        bin_name: str,
        target_executable: Path,
    ) -> None:
        """Create launcher(s) in the bin directory pointing to target executable."""
        ...

    @staticmethod
    def remove_link_or_dir(path: Path) -> None:
        """Remove a link, junction, or directory cleanly."""
        ...


class PosixOsOps:
    """POSIX (Linux / macOS) OS operations."""

    @staticmethod
    def mirror_directory(
        src: Path,
        dest: Path,
        exclude_patterns: list[str] | None = None,
    ) -> None:
        """Mirror the contents of the source directory to the destination directory."""

        if not src.exists():
            raise FileNotFoundError(f"Source directory '{src}' does not exist.")
        if not src.is_dir():
            raise NotADirectoryError(f"Source '{src}' is not a directory.")

        if dest.exists():
            shutil.rmtree(dest)

        dest.parent.mkdir(parents=True, exist_ok=True)
        ignore_func = shutil.ignore_patterns(*exclude_patterns) if exclude_patterns else None
        shutil.copytree(src, dest, ignore=ignore_func)

    @staticmethod
    def make_executable(file_path: Path) -> None:
        """Make a file executable."""

        if not file_path.exists():
            raise FileNotFoundError(f"File '{file_path}' does not exist.")

        try:
            current_mode = file_path.stat().st_mode
            file_path.chmod(current_mode | 0o111 | 0o755)
        except OSError as e:
            logger.warning("Could not set executable permissions on '%s': %s", file_path, e)

    @staticmethod
    def set_permissions(
        path: Path,
        permissions: str | int | None = None,
    ) -> None:
        """Set the permissions of the specified path."""

        if permissions is None or not path.exists():
            return

        if isinstance(permissions, int):
            path.chmod(permissions)
        elif isinstance(permissions, str):
            try:
                mode = int(permissions, 8)
                path.chmod(mode)
            except ValueError:
                pass

    @staticmethod
    def update_current_link(
        versions_dir: Path,
        target_version: str,
        current_dir: Path,
    ) -> Path:
        """Update the 'current' symlink to point to the specified target version."""

        target_version_dir = versions_dir / target_version
        if not target_version_dir.exists() or not target_version_dir.is_dir():
            raise FileNotFoundError(
                f"Target version directory '{target_version_dir}' does not exist."
            )

        current_dir.parent.mkdir(parents=True, exist_ok=True)
        temp_link = current_dir.parent / f".current_tmp_{os.getpid()}"
        if temp_link.exists(follow_symlinks=False):
            temp_link.unlink()

        try:
            rel_target = target_version_dir.relative_to(current_dir.parent)
            temp_link.symlink_to(rel_target)
        except ValueError:
            temp_link.symlink_to(target_version_dir)

        temp_link.replace(current_dir)
        return current_dir

    @staticmethod
    def create_bin_launcher(
        bin_dir: Path,
        bin_name: str,
        target_executable: Path,
    ) -> None:
        """Create a symlink in the bin directory pointing to the target executable."""

        bin_dir.mkdir(parents=True, exist_ok=True)
        bin_path = bin_dir / bin_name

        if bin_path.exists(follow_symlinks=False):
            bin_path.unlink()

        is_dll = target_executable.suffix.lower() == ".dll"
        if is_dll:
            wrapper = (
                "#!/bin/sh\n"
                f'exec dotnet "{target_executable}" "$@"\n'
            )
            bin_path.write_text(wrapper, encoding="utf-8")
            PosixOsOps.make_executable(bin_path)
        else:
            bin_path.symlink_to(target_executable)

    @staticmethod
    def remove_link_or_dir(path: Path) -> None:
        """Remove the specified path, whether it is a symlink, directory, or file."""

        if not path.exists(follow_symlinks=False):
            return

        if path.is_symlink():
            path.unlink()
        elif path.is_dir():
            shutil.rmtree(path, ignore_errors=True)
        else:
            path.unlink()


class WindowsOsOps:
    """Windows OS operations."""

    @staticmethod
    def mirror_directory(
        src: Path,
        dest: Path,
        exclude_patterns: list[str] | None = None,
    ) -> None:
        """Mirror the contents of the source directory to the destination directory."""

        if not src.exists():
            raise FileNotFoundError(f"Source directory '{src}' does not exist.")
        if not src.is_dir():
            raise NotADirectoryError(f"Source '{src}' is not a directory.")

        if dest.exists():
            shutil.rmtree(dest)

        dest.parent.mkdir(parents=True, exist_ok=True)
        ignore_func = shutil.ignore_patterns(*exclude_patterns) if exclude_patterns else None
        shutil.copytree(src, dest, ignore=ignore_func)

    @staticmethod
    def make_executable(file_path: Path) -> None:
        """Make the specified file executable. No-op on Windows."""

    @staticmethod
    def set_permissions(
        path: Path,
        permissions: str | int | None = None,
    ) -> None:
        """Set the permissions of the specified path. No-op on Windows."""

    @staticmethod
    def update_current_link(
        versions_dir: Path,
        target_version: str,
        current_dir: Path,
    ) -> Path:
        """Update the 'current' junction to point to the specified target version."""

        target_version_dir = versions_dir / target_version
        if not target_version_dir.exists() or not target_version_dir.is_dir():
            raise FileNotFoundError(
                f"Target version directory '{target_version_dir}' does not exist."
            )

        current_dir.parent.mkdir(parents=True, exist_ok=True)

        if current_dir.exists(follow_symlinks=False):
            try:
                current_dir.unlink()
            except OSError:
                try:
                    os.rmdir(current_dir)
                except OSError:
                    exec_command(["cmd", "/c", "rmdir", str(current_dir)], quiet=True)

        cmd = ["cmd", "/c", "mklink", "/J", str(current_dir), str(target_version_dir)]
        exec_command(cmd)
        return current_dir

    @staticmethod
    def create_bin_launcher(
        bin_dir: Path,
        bin_name: str,
        target_executable: Path,
    ) -> None:
        """Create a launcher script in the bin directory pointing to the target executable."""
        bin_dir.mkdir(parents=True, exist_ok=True)
        cmd_name = bin_name if bin_name.lower().endswith(".cmd") else f"{bin_name}.cmd"
        cmd_path = bin_dir / cmd_name

        try:
            rel_path = target_executable.relative_to(bin_dir, walk_up=True)
            rel_path_win = str(rel_path).replace("/", "\\")
            rel_path_posix = rel_path.as_posix()
        except (ValueError, TypeError):
            rel_path_win = str(target_executable)
            rel_path_posix = str(target_executable).replace("\\", "/")

        is_dll = target_executable.suffix.lower() == ".dll"
        if is_dll:
            cmd_content = f'@dotnet "%~dp0{rel_path_win}" %*\r\n'
            bash_content = (
                "#!/bin/bash\n"
                'CURR_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" &>/dev/null && pwd)"\n'
                f'exec dotnet "$CURR_DIR/{rel_path_posix}" "$@"\n'
            )
        else:
            cmd_content = f'@"%~dp0{rel_path_win}" %*\r\n'
            bash_content = (
                "#!/bin/bash\n"
                'CURR_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" &>/dev/null && pwd)"\n'
                f'exec "$CURR_DIR/{rel_path_posix}" "$@"\n'
            )

        with open(cmd_path, "w", encoding="utf-8", newline="") as f:
            f.write(cmd_content)

        sh_path = bin_dir / bin_name.removesuffix(".cmd")
        with open(sh_path, "w", encoding="utf-8", newline="") as f:
            f.write(bash_content)

    @staticmethod
    def remove_link_or_dir(path: Path) -> None:
        """Remove the specified path, whether it is a symlink, directory, or file."""

        if not path.exists(follow_symlinks=False):
            return

        if path.is_symlink():
            path.unlink()
        elif path.is_dir():
            try:
                path.unlink()
            except OSError:
                shutil.rmtree(path, ignore_errors=True)
        else:
            path.unlink()


def get_os_ops(target_os: OperatingSystem | None = None) -> type[OsOpsProtocol]:
    """Get the appropriate OS operations class for the given operating system."""
    target_os = target_os or OperatingSystem.current()
    if target_os.is_posix:
        return PosixOsOps
    return WindowsOsOps


__all__ = [
    "OsOpsProtocol",
    "PosixOsOps",
    "WindowsOsOps",
    "get_os_ops",
]
