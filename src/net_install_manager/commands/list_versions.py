"""Command to list installed versions of an application."""

import argparse
from dataclasses import dataclass

from net_install_manager.commands.base_command import BaseCommand
from net_install_manager.core import errors
from net_install_manager.runtime.runtime import Runtime
from net_install_manager.core.registry import Registry


@dataclass
class ListVersionsArgs:
    """Arguments for the list versions command."""

    app_name: str
    reverse: bool = False


class ListVersionsCommand(BaseCommand[ListVersionsArgs]):
    """Command to list installed versions of an application."""

    def execute(self, runtime: Runtime, args: ListVersionsArgs) -> None:

        registry = Registry(runtime)
        versions = registry.get_installed_versions(args.app_name)

        if not versions:
            raise errors.AppNotRegisteredError(args.app_name, runtime.registry_path)

        for version in sorted(versions.versions, reverse=not args.reverse):
            current_label = " (current)" if version == versions.current else ""
            print(f" - {version}{current_label}")

    @staticmethod
    def register_command(subparsers: argparse._SubParsersAction) -> argparse.ArgumentParser:
        parser = subparsers.add_parser(
            "list-versions", help="List installed versions of an application."
        )
        parser.add_argument(
            "app_name", type=str, help="Name of the application to list versions for."
        )
        parser.add_argument(
            "--reverse", action="store_true", help="List versions from oldest to newest."
        )
        return parser

    @staticmethod
    def parse_arguments(runtime: Runtime, args: argparse.Namespace) -> ListVersionsArgs:
        return ListVersionsArgs(app_name=args.app_name, reverse=args.reverse)
