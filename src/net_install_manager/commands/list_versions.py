"""List versions command for the Net Install Manager application."""

import argparse
from net_install_manager.cli_output import write
from net_install_manager.runtime_config import RuntimeInfo
from net_install_manager.app_manager import AppManager
from net_install_manager.utilities.resolve_manager import resolve_manager
from net_install_manager.registry import AppRegistry


def execute(
    args: argparse.Namespace,
    manager: AppManager | None = None,
    registry: AppRegistry | None = None,
    runtime: RuntimeInfo | None = None,
) -> int:
    """Execute the list versions command."""
    runtime = runtime or RuntimeInfo.current()
    manager = resolve_manager(args, runtime, manager, registry, app_manager_cls=AppManager)

    versions = manager.get_installed_versions()
    current_ver = manager.get_current_version()

    if not versions:
        write(f"No installed versions found for '{manager.config.binary_name}'.")
        return 0

    if not args.reverse:
        # Default: ascending order (oldest to newest) or descending based on args
        versions = list(reversed(versions))

    for version in versions:
        if version == current_ver:
            write(f"{version} (current)")
        else:
            write(f"{version}")

    return 0


def register_list_versions_command(
    subparsers: argparse._SubParsersAction,
) -> argparse.ArgumentParser:
    """Register the list-versions command arguments."""
    # pylint: disable=duplicate-code

    parser = subparsers.add_parser(
        "list-versions", help="List all installed versions of a .NET application"
    )
    parser.add_argument(
        "app_name",
        nargs="?",
        default=None,
        help=(
            "Name of the tracked application to list versions for "
            "(optional if running in project directory)"
        ),
    )
    parser.add_argument(
        "-r",
        "--reverse",
        action="store_true",
        help="List versions in reverse order (newest first)",
    )
    return parser


__all__ = ["execute", "register_list_versions_command"]
