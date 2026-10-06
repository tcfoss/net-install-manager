"""Main CLI entry point for the NET Install Manager."""

import argparse
import logging
from pathlib import Path
import sys

from net_install_manager.commands.base_command import BaseCommand
from net_install_manager.commands import list_apps as c_list
from net_install_manager.commands import list_versions as c_ver
from net_install_manager.commands import app_details as c_det
from net_install_manager.commands import install as c_inst
from net_install_manager.commands import upgrade as c_upg
from net_install_manager.commands import prune as c_prune
from net_install_manager.commands import rollback as c_rb
from net_install_manager.commands import uninstall as c_uninst
from net_install_manager.commands import self_migrate as c_migrate


from net_install_manager.core.errors import BaseNinmanError
from net_install_manager.runtime.runtime import Runtime
from net_install_manager.__version__ import __version__

_COMMANDS: dict[str, BaseCommand] = {
    "install": c_inst.InstallCommand(),
    "upgrade": c_upg.UpgradeCommand(),
    "list-apps": c_list.ListAppsCommand(),
    "list-versions": c_ver.ListVersionsCommand(),
    "prune": c_prune.PruneCommand(),
    "rollback": c_rb.RollbackCommand(),
    "uninstall": c_uninst.UninstallCommand(),
    "app-details": c_det.AppDetailsCommand(),
    "self-migrate": c_migrate.SelfMigrateCommand(),
}

logger = logging.getLogger(__name__)


def _register_commands(parser: argparse._SubParsersAction) -> dict[str, argparse.ArgumentParser]:
    """Register the CLI commands."""

    command_parsers = {}
    for name, command in _COMMANDS.items():
        command_parsers[name] = command.register_command(parser)

    return command_parsers


def _register_global_arguments(parser: argparse.ArgumentParser):
    """Register global CLI arguments."""
    parser.add_argument("--version", action="version", version=str(__version__))
    parser.add_argument(
        "--log-level",
        choices=["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"],
        help="Set the logging level",
        default="INFO",
    )
    parser.add_argument(
        "--log-file",
        help="Set the log file path",
        default=None,
    )


def _configure_logging(log_level: str, log_file: str | None):
    """Configure the logging settings."""
    if log_file:
        log_path = Path(log_file).expanduser().resolve()
        log_path.parent.mkdir(parents=True, exist_ok=True)
        log_file = str(log_path)

    logging.basicConfig(
        level=getattr(logging, log_level),
        filename=log_file,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    )


def main():
    """Main entry point for the NET Install Manager CLI."""

    initial_parser = argparse.ArgumentParser(add_help=False)
    _register_global_arguments(initial_parser)
    args, rest = initial_parser.parse_known_args()
    _configure_logging(args.log_level, args.log_file)

    parser = argparse.ArgumentParser(
        description="NET Install Manager CLI", parents=[initial_parser]
    )

    parser.add_argument(
        "--system",
        action="store_true",
        help="Manage system-wide installations (requires administrator privileges)",
    )

    subparsers = parser.add_subparsers(dest="command", required=True)
    command_parsers = _register_commands(subparsers)

    args = parser.parse_args(rest)

    command = _COMMANDS.get(args.command)
    if command is None:
        parser.error(f"Unknown command: {args.command}")

    runtime = Runtime.current(args.system)
    logger.debug("Initialized runtime: %s", runtime)

    if runtime.system_wide and not runtime.platform.is_admin:
        print("Error: Administrator privileges are required for system-wide installations.")
        return 6

    try:
        command.validate_arguments(command_parsers[args.command], runtime, args)
        command_args = command.parse_arguments(runtime, args)
        command.execute(runtime, command_args)
        return 0
    except BaseNinmanError as e:
        print(e)
        return 1


if __name__ == "__main__":
    sys.exit(main())
