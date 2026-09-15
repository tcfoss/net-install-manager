"""Main entry-point for the Net Install Manager application."""

import argparse
from importlib.metadata import version as gv, PackageNotFoundError
import logging
from pathlib import Path
import sys

from net_install_manager.config import load_config, auto_discover_config, Config
from net_install_manager.app_manager import AppManager
from net_install_manager.cli_output import error
from net_install_manager.errors import AppNotRegisteredError, CannotResolveManagerError
from net_install_manager.runtime_config import RuntimeInfo
from net_install_manager.utilities.sys_platform import PlatformInfo
from net_install_manager.utilities.git_tools import (
    is_git_url,
    parse_git_source,
    clone_or_update_repo,
)
from net_install_manager.utilities.version_tools import get_version_from_git
import net_install_manager.commands.install as c_inst
import net_install_manager.commands.install_release as c_inst_release
import net_install_manager.commands.list_apps as c_la
import net_install_manager.commands.list_versions as c_lv
import net_install_manager.commands.rollback as c_roll
import net_install_manager.commands.uninstall as c_uninst
import net_install_manager.commands.upgrade as c_upg
import net_install_manager.commands.app_details as c_ad


def get_version() -> str:
    """Attempt to get the version of the application from the package metadata or Git."""
    try:
        package_version = gv("net-install-manager")
        if package_version != "0.0.0":
            return package_version
    except PackageNotFoundError:
        pass

    git_version = get_version_from_git(Path(__file__).parent)
    if git_version:
        return str(git_version)

    return "0.0.0"


__version__ = get_version()


def configure_logging(args: argparse.Namespace) -> None:
    """Configure package logging from global CLI verbosity flags."""
    if getattr(args, "debug_logs", False):
        level = logging.DEBUG
    elif getattr(args, "verbose", False):
        level = logging.INFO
    else:
        level = logging.WARNING

    logging.basicConfig(level=level, format="%(levelname)s: %(message)s", stream=sys.stderr)


def register_commands() -> argparse.ArgumentParser:
    """Build the argument parser for the application."""
    parser = argparse.ArgumentParser(
        prog="ninman",
        description=".NET Application Installation Manager",
    )

    parser.add_argument(
        "--version",
        action="version",
        version=f"ninman {__version__}",  # Replace with dynamic version if available
    )

    parser.add_argument("--config", help="Path to the configuration YAML file")
    parser.add_argument(
        "--system",
        action="store_true",
        help="Manage installations at the system level (requires administrator/root privileges)",
    )
    parser.add_argument(
        "--prefer-opt",
        action="store_true",
        help="Use /opt instead of /usr/local for system installations on POSIX",
    )
    parser.add_argument(
        "-q",
        "--quiet",
        action="store_true",
        help="Suppress subprocess output for install and upgrade operations",
    )
    parser.add_argument(
        "--verbose",
        action="store_true",
        help="Show informational diagnostic logs",
    )
    parser.add_argument(
        "--debug-logs",
        action="store_true",
        help="Show debug diagnostic logs",
    )

    sp = parser.add_subparsers(dest="command", required=True)

    c_lv.register_list_versions_command(sp)
    c_inst.register_install_command(sp)
    c_inst_release.register_install_release_command(sp)
    c_uninst.register_uninstall_command(sp)
    c_roll.register_rollback_command(sp)
    c_upg.register_upgrade_command(sp)
    c_la.register_list_apps_command(sp)
    c_ad.register_app_details_command(sp)

    return parser


def load_app_config(
    config_arg: str | None,
    allow_none: bool = False,
    source_arg: str | None = None,
    project_arg: str | None = None,
) -> Config | None:
    """Load configuration from the specified path, source argument, or auto-discover."""
    if config_arg:
        config_path = Path(config_arg)
        if not config_path.exists():
            error(f"Error: Configuration file '{config_arg}' not found.")
            sys.exit(1)
        return load_config(config_path)

    # Check if source_arg is a Git URL
    if source_arg and is_git_url(source_arg):
        try:
            git_info = parse_git_source(source_arg, project_override=project_arg)
            repo_dir = clone_or_update_repo(git_info)
            if git_info.subpath:
                repo_dir = repo_dir / git_info.subpath
            discovered = auto_discover_config(repo_dir)

            if discovered:
                return discovered
        except Exception as e:  # pylint: disable=broad-except
            error(f"Error resolving Git source '{source_arg}': {e}")
            sys.exit(1)

    # Check if source_arg is a local path
    if source_arg:
        src = Path(source_arg)
        if project_arg:
            src = src / project_arg
        if src.exists():
            discovered = auto_discover_config(src)
            if discovered:
                return discovered

    # Discovery in current directory
    discovered = auto_discover_config()
    if discovered:
        return discovered

    if allow_none:
        return None

    error(
        "Error: No configuration file specified and could not "
        "auto-discover a .NET project or config in the current directory."
    )
    error(
        "Please provide a --config path or run from a directory containing "
        "a .csproj or ninman.yaml."
    )
    sys.exit(1)


def run(
    parser: argparse.ArgumentParser,
    args: argparse.Namespace,
    runtime: RuntimeInfo,
    manager: AppManager | None = None,
) -> None:
    """Run the application"""

    try:
        if args.command == "upgrade":
            exit_code = c_upg.execute(args, runtime=runtime, manager=manager)
        elif args.command == "uninstall":
            exit_code = c_uninst.execute(args, runtime=runtime, manager=manager)
        elif args.command == "list-versions":
            exit_code = c_lv.execute(args, runtime=runtime, manager=manager)
        elif args.command == "rollback":
            exit_code = c_roll.execute(args, runtime=runtime, manager=manager)
        elif args.command == "install":
            assert manager is not None
            exit_code = c_inst.execute(args, manager=manager)
        elif args.command == "install-release":
            exit_code = c_inst_release.execute(args, runtime=runtime)
        elif args.command == "app-details":
            exit_code = c_ad.execute(args, runtime=runtime)
        else:
            error(f"Unknown command '{args.command}'.")
            parser.print_help(file=sys.stderr)
            sys.exit(1)

        if exit_code is not None and exit_code != 0:
            sys.exit(exit_code)
    except CannotResolveManagerError as ex:
        error(str(ex))
        sys.exit(1)
    except AppNotRegisteredError as ex:
        error(str(ex))
        sys.exit(1)


def main() -> None:
    """Main entry point for the Net Install Manager CLI."""

    parser = register_commands()
    args = parser.parse_args()
    configure_logging(args)

    platform_info = PlatformInfo.detect()
    if args.system and not platform_info.is_admin:
        error("Error: System-wide operations require administrator / root privileges. Exiting.")
        sys.exit(1)

    runtime = RuntimeInfo(platform=platform_info, system_wide=args.system)

    if args.command == "list-apps":
        exit_code = c_la.execute(args, runtime=runtime)
        sys.exit(exit_code or 0)

    # Upgrade supports --all (all registered apps) or a specific app_name
    allow_no_config: bool = False
    if args.command == "upgrade" and (
        getattr(args, "all", False) or getattr(args, "app_name", None)
    ):
        allow_no_config = True
    # Uninstall, list-versions, and rollback require a specific app_name to run without local config
    elif args.command in ("uninstall", "list-versions", "rollback", "app-details") and getattr(
        args, "app_name", None
    ):
        allow_no_config = True

    if args.command == "install-release":
        run(parser, args, runtime)
        return

    config = load_app_config(
        config_arg=args.config,
        allow_none=allow_no_config,
        source_arg=getattr(args, "source", None),
        project_arg=getattr(args, "project", None),
    )
    manager = (
        AppManager(
            config=config,
            prefer_opt=args.prefer_opt,
            runtime=runtime,
        )
        if config
        else None
    )

    run(parser, args, runtime, manager=manager)


if __name__ == "__main__":
    main()
