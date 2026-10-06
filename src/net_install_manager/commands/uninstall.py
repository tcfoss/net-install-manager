"""Command to uninstall an application."""

import argparse
from dataclasses import dataclass
import logging

from net_install_manager.commands.base_command import BaseCommand
from net_install_manager.commands.helpers import interaction
from net_install_manager.config.paths import get_paths_from_app_info
from net_install_manager.core import errors
from net_install_manager.core.os_ops import get_os_ops
from net_install_manager.core.registry import Registry
from net_install_manager.runtime.runtime import Runtime

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class UninstallArguments:
    """Arguments for the uninstall command."""

    app_name: str
    assume_yes: bool = False


class UninstallCommand(BaseCommand[UninstallArguments]):
    """Command to uninstall an application."""

    def execute(self, runtime: Runtime, args: UninstallArguments) -> None:

        if not args.assume_yes and not interaction.confirm(
            f"Are you sure you want to uninstall the application '{args.app_name}'?"
        ):
            logger.info("Uninstallation of '%s' cancelled by user.", args.app_name)
            return

        registry = Registry(runtime)
        app_info = registry.get(args.app_name)
        if app_info is None:
            raise errors.AppNotRegisteredError(args.app_name, runtime.registry_path)

        paths = get_paths_from_app_info(runtime, app_info)
        logger.info("Removing installed files for application '%s'.", args.app_name)
        get_os_ops(runtime.os).remove_application(paths)

        registry.remove(app_info.binary_name)
        logger.info("Application '%s' uninstalled successfully.", args.app_name)

    @staticmethod
    def register_command(subparsers: argparse._SubParsersAction) -> argparse.ArgumentParser:
        parser = subparsers.add_parser("uninstall", help="Uninstall an application.")
        parser.add_argument("app_name", type=str, help="Name of the application to uninstall.")
        interaction.register_autoconfirm_argument(parser)
        return parser

    @staticmethod
    def parse_arguments(runtime: Runtime, args: argparse.Namespace) -> UninstallArguments:
        return UninstallArguments(
            app_name=args.app_name,
            assume_yes=args.assume_yes,
        )
