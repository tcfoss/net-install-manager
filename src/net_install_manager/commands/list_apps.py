"""Command to list installed applications."""

import argparse
from dataclasses import dataclass

from net_install_manager.commands.base_command import BaseCommand
from net_install_manager.core.registry import Registry
from net_install_manager.runtime.runtime import Runtime


@dataclass
class ListAppsArgs:
    """Arguments for the ListAppsCommand."""


class ListAppsCommand(BaseCommand[ListAppsArgs]):
    """Command to list installed applications."""

    def execute(self, runtime: Runtime, args: ListAppsArgs):
        """Execute the command to list installed applications."""
        registry = Registry(runtime)

        for app in registry.get_installed_apps():
            print(f"{app[0]} ({app[1]})")

    @staticmethod
    def register_command(subparsers: argparse._SubParsersAction) -> argparse.ArgumentParser:
        """Register the list apps command with the argument parser."""
        parser = subparsers.add_parser("list-apps", help="List installed applications")
        return parser

    @staticmethod
    def parse_arguments(runtime: Runtime, args: argparse.Namespace) -> ListAppsArgs:
        """Parse the command-line arguments into a ListAppsArgs instance."""
        return ListAppsArgs()
