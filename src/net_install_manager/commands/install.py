"""Install command for the Net Install Manager application."""

import argparse
from pathlib import Path

from net_install_manager.app_manager import AppManager, VersionRegressionError
from net_install_manager.cli_output import error, write
from net_install_manager.runtime_config import InstallOptions
from net_install_manager.utilities.git_tools import is_git_url, parse_git_source
from net_install_manager.utilities.install_tools import InstallSource


def parse_options(args: argparse.Namespace) -> InstallOptions:
    """Parse InstallOptions from command-line arguments."""
    return InstallOptions(
        self_contained=getattr(args, "self_contained", False),
        release=not getattr(args, "debug", False),
        keep_latest=getattr(args, "versions_to_keep", None),
        force=getattr(args, "force", False),
        explicit_version=getattr(args, "app_version", None),
        quiet=getattr(args, "quiet", False),
    )


def parse_source(args: argparse.Namespace, manager: AppManager) -> InstallSource:
    """Parse the install source and project selector from CLI arguments."""
    source = args.source
    project_path = getattr(args, "project", None)
    if source and is_git_url(str(source)):
        git_info = parse_git_source(str(source), project_override=project_path)
        return InstallSource(
            git_info=git_info,
            project_path=git_info.subpath,
        )

    source_path = source or manager.config.csproj_path or Path.cwd()
    return InstallSource(local_path=str(source_path), project_path=project_path)


def execute(args: argparse.Namespace, manager: AppManager):
    """Execute the install command."""
    if args.versions_to_keep is not None and args.versions_to_keep < 1:
        error("The number of versions to keep must be at least 1.")
        return 1

    try:
        options = parse_options(args)
        installed_version = manager.install(
            source=parse_source(args, manager),
            options=options,
        )
        write(
            f"Successfully installed version {installed_version} of '{manager.config.binary_name}'."
        )
        return 0
    except VersionRegressionError as e:
        error(f"Error: {e}")
        return 6
    except Exception as e:  # pylint: disable=broad-except
        error(f"Installation failed: {e}")
        return 1


def register_install_command(subparsers: argparse._SubParsersAction) -> argparse.ArgumentParser:
    """Register the install command arguments."""
    parser = subparsers.add_parser("install", help="Install a .NET application")
    parser.add_argument(
        "source",
        nargs="?",
        default=None,
        help="Path to .csproj file, project folder, precompiled directory, or Git/GitHub URL",
    )
    parser.add_argument(
        "-p",
        "--project",
        "--project-path",
        dest="project",
        default=None,
        help="Path to the target .csproj file within the repository or directory",
    )
    parser.add_argument(
        "--self-contained",
        action="store_true",
        help="Install as self-contained application (includes .NET runtime)",
    )
    parser.add_argument(
        "--debug",
        action="store_true",
        help="Build using Debug configuration instead of Release",
    )
    parser.add_argument(
        "-k",
        "--versions-to-keep",
        type=int,
        default=None,
        help="Number of previous versions to keep",
    )
    parser.add_argument(
        "-f",
        "--force",
        action="store_true",
        help="Force reinstallation even if version is already installed or older",
    )
    parser.add_argument(
        "-v",
        "--app-version",
        type=str,
        default=None,
        help="Explicit version string (overrides automatic detection)",
    )
    return parser


__all__ = ["execute", "register_install_command"]
