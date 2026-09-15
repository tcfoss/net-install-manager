"""Uninstall command for the Net Install Manager application."""

import argparse
from net_install_manager.cli_output import error, write
from net_install_manager.runtime_config import RuntimeInfo
from net_install_manager.app_manager import AppManager, AppManagerError
from net_install_manager.utilities.resolve_manager import resolve_manager
from net_install_manager.registry import AppRegistry


def execute(
    args: argparse.Namespace,
    manager: AppManager | None = None,
    registry: AppRegistry | None = None,
    runtime: RuntimeInfo | None = None,
) -> int:
    """Execute the uninstall command."""
    if not validate_arguments(args):
        error("Please specify either --target-version or --all to uninstall.")
        return 1

    runtime = runtime or RuntimeInfo.current()
    manager = resolve_manager(args, runtime, manager, registry, app_manager_cls=AppManager)

    try:
        manager.uninstall(
            target_version=args.target_version,
            all_versions=args.all,
        )
        if args.all:
            write(f"Successfully uninstalled all versions of '{manager.config.binary_name}'.")
        else:
            write(
                f"Successfully uninstalled version {args.target_version}"
                f" of '{manager.config.binary_name}'."
            )
        return 0
    except AppManagerError as e:
        error(f"Uninstall failed: {e}")
        return 1


def validate_arguments(args: argparse.Namespace) -> bool:
    """Validate the arguments for the uninstall command."""
    if getattr(args, "target_version", None) or getattr(args, "all", False):
        return True
    return False


def register_uninstall_command(subparsers: argparse._SubParsersAction) -> argparse.ArgumentParser:
    """Register the uninstall command arguments."""
    # pylint: disable=duplicate-code

    parser = subparsers.add_parser("uninstall", help="Uninstall a .NET application")
    parser.add_argument(
        "app_name",
        nargs="?",
        default=None,
        help=(
            "Name of the tracked application to uninstall "
            "(optional if running in project directory)"
        ),
    )
    parser.add_argument("-t", "--target-version", help="The target version to uninstall")
    parser.add_argument(
        "-a", "--all", action="store_true", help="Uninstall all versions of the application"
    )
    return parser


__all__ = ["execute", "register_uninstall_command", "validate_arguments"]
