"""Rollback command for the Net Install Manager application."""

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
    """Execute the rollback command."""
    runtime = runtime or RuntimeInfo.current()
    manager = resolve_manager(args, runtime, manager, registry, app_manager_cls=AppManager)

    try:
        rolled_back_version = manager.rollback(
            target_version=args.target_version,
            previous=args.previous,
        )
        write(f"Successfully rolled back to version {rolled_back_version}.")
        return 0
    except AppManagerError as e:
        error(f"Rollback failed: {e}")
        return 1


def register_rollback_command(subparsers: argparse._SubParsersAction) -> argparse.ArgumentParser:
    """Register the rollback command arguments."""
    # pylint: disable=duplicate-code

    parser = subparsers.add_parser(
        "rollback", help="Rollback a .NET application to a previous installed version"
    )
    parser.add_argument(
        "app_name",
        nargs="?",
        default=None,
        help=(
            "Name of the tracked application to roll back "
            "(optional if running in project directory)"
        ),
    )
    parser.add_argument("-t", "--target-version", help="The target version to rollback to")
    parser.add_argument(
        "-p",
        "--previous",
        action="store_true",
        help="Roll back to the second-latest (or previous) version",
    )
    return parser


__all__ = ["execute", "register_rollback_command"]
